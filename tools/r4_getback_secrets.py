# KPython secret scanner (Get back, round 4): finds hard-coded tokens/keys/passwords in your scripts under /home/pyodide, shows file:line with MASKED values and how to fix each.
import os, re, math, tempfile, shutil

HOME = "/home/pyodide"  # KPython: fixed, no env override
EXTS = {".py", ".txt", ".json", ".env", ".cfg", ".ini", ".toml", ".yaml", ".yml"}
MAX_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}

FIX_ROTATE = "Revoke/rotate this key now, then load it at runtime (getpass/input() or os.environ) instead of hard-coding."
RULES = [
    ("GitHub token", "critical", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b"), FIX_ROTATE),
    ("Private key", "critical", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"), "Remove the key from the file, store it outside your scripts, and generate a new key pair."),
    ("AWS access key", "critical", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), FIX_ROTATE),
    ("Stripe live key", "critical", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"), FIX_ROTATE),
    ("Slack token", "high", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), FIX_ROTATE),
    ("OpenAI-style key", "high", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b"), FIX_ROTATE),
    ("Google API key", "high", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), FIX_ROTATE),
    ("JWT", "medium", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "Don't paste session tokens into code; ask for it with getpass at runtime. It may grant access until it expires."),
    ("Password in URL", "high", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:([^\s@/'\"]+)@"), "Remove the user:pass from the URL; build it at runtime from getpass/os.environ and change that password."),
    ("Hard-coded secret", "high", re.compile(r"""(?i)\b[\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|auth)[\w-]*["']?\s*[:=]\s*[rbuf]?(["'])([^"'\n]{4,})\1"""), "Use getpass.getpass() or input() at runtime, or os.environ.get('NAME'), instead of a literal value."),
]
PLACEHOLDER = re.compile(r"(?i)^(x+|\*+|\.+|<.*>|\{.*\}|\$\{?.*|your[_ -]?.*|changeme|change_me|placeholder|example|dummy|test|none|null|password|secret|token|todo|redacted|xxx.*|.*here)$")
ENTROPY_RE = re.compile(r"""["']([A-Za-z0-9+/=_\-]{32,})["']""")

def mask(s):
    s = str(s)
    if len(s) <= 10:
        return s[:2] + "..." if len(s) > 2 else "***"
    return s[:4] + "..." + s[-4:]

def entropy(s):
    if not s: return 0.0
    n = len(s); return -sum(c / n * math.log2(c / n) for c in (s.count(ch) for ch in set(s)))

def is_placeholder(v):
    v = v.strip()
    return (not v) or bool(PLACEHOLDER.match(v)) or len(set(v)) <= 2

def scan_text(text):
    """Return list of (line_no, type, severity, masked, fix)."""
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        hits = []
        for name, sev, rx, fix in RULES:
            for m in rx.finditer(line):
                val = m.group(m.lastindex) if m.lastindex else m.group(0)
                if name == "Hard-coded secret":
                    val = m.group(2)
                    if re.match(r"(?i)^(?:input|getpass|os\.)", val): continue
                if name != "Private key" and is_placeholder(val): continue
                if any(val in h[1] or h[1] in val for h in hits): continue
                hits.append((name, val, sev, fix))
        if not hits:
            for m in ENTROPY_RE.finditer(line):
                v = m.group(1)
                if entropy(v) >= 4.0 and not v.isalpha() and not is_placeholder(v):
                    hits.append(("High-entropy string", v, "low", "If this is a credential, move it to getpass/os.environ and rotate it; if not, ignore."))
        for name, val, sev, fix in hits:
            out.append((ln, name, sev, mask(val) if name != "Private key" else "-----BEGIN ... KEY-----", fix))
    return out

def safe_path(p):
    home = os.path.realpath(HOME)
    if ".." in p.replace("\\", "/").split("/"):
        raise ValueError("'..' is not allowed")
    full = os.path.realpath(p if os.path.isabs(p) else os.path.join(home, p))
    if full != home and not full.startswith(home + os.sep):
        raise ValueError("Path must be inside " + home)
    return full

def scan_file(path):
    if os.path.getsize(path) > MAX_BYTES:
        return None, "skipped (over 2 MB)"
    with open(path, "rb") as f:
        data = f.read()
    if b"\x00" in data[:4096]:
        return None, "skipped (binary)"
    return scan_text(data.decode("utf-8", errors="replace")), None

def iter_files(root):
    if os.path.isfile(root):
        yield root; return
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXTS or fn.startswith(".env"):
                full = os.path.join(d, fn)
                if os.path.islink(full):
                    try: safe_path(full)
                    except ValueError: continue
                yield full

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

def scan(target):
    root = safe_path(target)
    if not os.path.exists(root):
        raise FileNotFoundError(target)
    findings, notes = [], []
    for f in iter_files(root):
        try:
            res, note = scan_file(f)
        except OSError as e:
            notes.append((f, "unreadable: %s" % e.__class__.__name__)); continue
        if note: notes.append((f, note)); continue
        for ln, name, sev, masked, fix in res:
            findings.append((os.path.relpath(f, os.path.realpath(HOME)), ln, name, sev, masked, fix))
    findings.sort(key=lambda x: (SEV_ORDER[x[3]], x[0], x[1]))
    return findings, notes

def report(findings, notes):
    if not findings:
        print("No secrets found. 👍")
    for path, ln, name, sev, masked, fix in findings:
        print("[%s] %s:%d  %s  %s\n    fix: %s" % (sev.upper(), path, ln, name, masked, fix))
    for path, note in notes:
        print("  note: %s %s" % (path, note))
    if findings:
        c = {}
        for f in findings: c[f[3]] = c.get(f[3], 0) + 1
        print("Total: " + ", ".join("%d %s" % (c[k], k) for k in SEV_ORDER if k in c))

def self_test():
    global HOME
    old = HOME
    tmp = tempfile.mkdtemp(prefix="kp_secrets_")
    ok = True
    def check(cond, label):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + label); ok = ok and cond
    try:
        HOME = tmp
        gh = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
        aws = "AKIA" + "ABCDEFGHIJKLMNOP"
        sample = "\n".join([
            "token = '%s'" % gh,
            "AWS = '%s'" % aws,
            "password = 'hunter2secret'",
            "api_key = 'your_key_here'",
            "secret = ''",
            "db = 'postgres://bob:s3cr3tpw@host/db'",
            "-----BEGIN RSA PRIVATE KEY-----",
            "slack = 'xox" + "b-1234567890-abcdefghij'",
            "k = 'sk_" + "live_abcdefghijklmnop1234'",
            "g = 'AIza" + "SyA1234567890abcdefghijklmnopqrstuv'",
            "jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.abcdefghijklmnop'",
            "blob = 'Zx9Qp2Lm7Vb4Nc8Rt1Yw6Ks3Hd5Jf0Ga'",
            "pw = getpass.getpass()",
            "print('hello world')",
        ])
        os.makedirs(os.path.join(tmp, "proj"))
        with open(os.path.join(tmp, "proj", "app.py"), "w") as f: f.write(sample)
        with open(os.path.join(tmp, "proj", "big.txt"), "wb") as f: f.write(b"a" * (MAX_BYTES + 1))
        with open(os.path.join(tmp, "proj", "bad.json"), "wb") as f: f.write(b'{"x": "\xff\xfe"}\n')
        with open(os.path.join(tmp, "proj", "skip.bin"), "w") as f: f.write("token = '%s'" % gh)
        findings, notes = scan("proj")
        types = {(f[1], f[2]) for f in findings}
        check((1, "GitHub token") in types, "GitHub token found on line 1")
        check((2, "AWS access key") in types, "AWS key")
        check((3, "Hard-coded secret") in types, "password assignment")
        check(not any(f[1] in (4, 5) for f in findings), "placeholders/empty skipped")
        check((6, "Password in URL") in types, "user:pass@ URL")
        check((7, "Private key") in types, "PEM header")
        check((8, "Slack token") in types, "Slack token")
        check((9, "Stripe live key") in types, "Stripe key")
        check((10, "Google API key") in types, "Google key")
        check((11, "JWT") in types, "JWT")
        check((12, "High-entropy string") in types, "entropy heuristic")
        check(not any(f[1] in (13, 14) for f in findings), "no false positives on getpass/print")
        out = repr(findings)
        check(gh not in out and aws not in out and "hunter2secret" not in out and "s3cr3tpw" not in out, "full secrets never shown")
        check(mask(gh) == "ghp_...Q7r8", "mask format first4...last4")
        check(any("big.txt" in n[0] and "2 MB" in n[1] for n in notes), "size cap")
        check(not any("skip.bin" in f[0] for f in findings), ".bin ignored")
        for bad in ("../etc", "/etc/passwd", "proj/../../x"):
            try: scan(bad); check(False, "reject " + bad)
            except ValueError: check(True, "reject " + bad)
        ft = [f for f in findings if f[2] == "GitHub token"][0]
        check("rotate" in ft[5].lower(), "fix suggests rotation")
    finally:
        HOME = old
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
    return ok

def main():
    print("🔐 Secret scanner. Files under %s only. Values are always masked." % HOME)
    while True:
        print("\n1) Scan a file or folder   2) Scan everything   t) Self-tests   q) Quit")
        c = (input("Choice: ") or "").strip().lower()
        if c in ("q", "quit", "exit", ""):
            if c == "": continue
            break
        try:
            if c == "1":
                p = input("Path (relative to %s): " % HOME).strip()
                if not p: continue
                report(*scan(p))
            elif c == "2":
                report(*scan(HOME))
            elif c == "t":
                self_test()
            else:
                print("Pick 1, 2, t or q.")
        except (ValueError, FileNotFoundError) as e:
            print("Error:", e)

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
