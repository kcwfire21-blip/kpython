# KPython dependency safety check (Get back, round 6): audits installed packages and requirements text for typosquats, loose pins, URL/VCS/index sources, risky setup.py install hooks, and (optionally, with your OK) PyPI licenses.
import os, re, json, ast, shutil, tempfile

HOME = "/home/pyodide"  # KPython: fixed, no env override
MAX_BYTES = 2 * 1024 * 1024
NAME_RE = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", re.I)  # PEP 508 / 503 valid project name

POPULAR = """requests numpy pandas matplotlib scipy sympy pillow scikit-learn urllib3 certifi idna charset-normalizer
setuptools wheel pip six python-dateutil pytz pyyaml packaging attrs typing-extensions click jinja2 markupsafe
flask django fastapi pydantic sqlalchemy boto3 botocore s3transfer jmespath cryptography cffi pycparser rsa
pyasn1 google-auth protobuf grpcio tensorflow torch keras opencv-python beautifulsoup4 soupsieve lxml
selenium pytest coverage tox black isort flake8 pylint mypy colorama tqdm rich httpx aiohttp yarl multidict
async-timeout frozenlist aiosignal websockets werkzeug itsdangerous gunicorn uvicorn starlette openpyxl
xlrd tabulate networkx regex simplejson ujson orjson pyjwt bcrypt paramiko psutil docutils sphinx pygments
toml tomli filelock platformdirs virtualenv wrapt decorator more-itertools zipp importlib-metadata pyparsing
kiwisolver cycler fonttools contourpy joblib threadpoolctl seaborn plotly bokeh dash statsmodels xgboost
lightgbm nltk spacy transformers tokenizers huggingface-hub openai anthropic redis pymongo psycopg2
psycopg2-binary mysqlclient pymysql markdown python-dotenv tzdata pyodide-http micropip""".split()

def norm(name):
    return re.sub(r"[-_.]+", "-", str(name)).lower()

POP = {norm(p) for p in POPULAR}
KNOWN_OK = {"boto", "boto3-stubs", "jwt", "tomlkit", "tomli-w", "httpcore", "pytest-cov", "pyyaml-include", "flask-cors", "numba", "scrapy", "pandas-ta"}  # real projects that look close to popular names
CONFUSE = str.maketrans({"0": "o", "1": "l", "i": "l", "5": "s", "3": "e"})

def lev(a, b, cap=3):
    """Damerau-Levenshtein (adjacent swaps count as 1)."""
    if abs(len(a) - len(b)) > cap: return cap + 1
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1): d[i][0] = i
    for j in range(len(b) + 1): d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]

def skel(n):
    n = norm(n).replace("rn", "m").replace("vv", "w").translate(CONFUSE)
    return re.sub(r"[-]", "", n)

def typosquat(name):
    """Return the popular package this name imitates, or None."""
    n = norm(name)
    if n in POP or n in KNOWN_OK: return None
    for p in POP:
        if skel(n) == skel(p): return p
        if len(p) >= 5 and lev(n, p) <= (1 if len(p) < 9 else 2): return p
        if n in (p + "s", p + "-python", "python-" + p, p + "-py", "py" + p) and len(p) >= 5: return p
    return None

REQ_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")

def parse_requirements(text):
    """Return list of findings dicts: line, name, spec, issue, severity."""
    out = []
    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"): continue
        low = line.lower()
        if low.startswith(("--index-url", "-i ", "--extra-index-url", "--find-links", "-f ", "--trusted-host")):
            sev = "high" if "extra-index" in low or "trusted-host" in low or "http://" in low else "medium"
            out.append(dict(line=ln, name="-", spec=line, issue="custom package index/source (dependency confusion risk)", severity=sev)); continue
        if low.startswith(("-r ", "-c ", "--requirement", "--constraint")):
            out.append(dict(line=ln, name="-", spec=line, issue="includes another file (audit it too)", severity="info")); continue
        if low.startswith(("-e ", "--editable")) or re.match(r"^(git|hg|svn|bzr)\+", low) or "://" in low or " @ " in line:
            m = re.match(r"^([A-Za-z0-9][\w.-]*)\s*@", line)
            out.append(dict(line=ln, name=m.group(1) if m else "-", spec=line, issue="URL/VCS source (not from PyPI, no version pin or hash)", severity="high" if "http://" in low else "medium")); continue
        m = REQ_RE.match(line)
        if not m or not NAME_RE.match(m.group(1)):
            out.append(dict(line=ln, name="?", spec=line, issue="unparseable line", severity="low")); continue
        name, spec = m.group(1), m.group(3).split(";", 1)[0].strip()
        t = typosquat(name)
        if t: out.append(dict(line=ln, name=name, spec=spec, issue="possible typosquat of '%s'" % t, severity="high"))
        if not spec: out.append(dict(line=ln, name=name, spec="", issue="unpinned (any version)", severity="medium"))
        elif not re.match(r"^===?\s*[\w.!+*-]+$", spec) or "*" in spec:
            out.append(dict(line=ln, name=name, spec=spec, issue="loose version (use == to pin)", severity="low"))
    return out

def installed():
    try:
        from importlib import metadata
        return sorted({(d.metadata["Name"] or "?", d.version) for d in metadata.distributions()}, key=lambda x: x[0].lower())
    except Exception:
        return []

def audit_installed(pkgs=None):
    res = []
    for name, ver in (pkgs if pkgs is not None else installed()):
        t = typosquat(name)
        if t: res.append(dict(name=name, version=ver, issue="possible typosquat of '%s'" % t, severity="high"))
    return res

HOOKS = [("cmdclass", r"\bcmdclass\b", "custom install command"), ("os.system", r"\bos\.system\s*\(", "runs shell commands"),
         ("subprocess", r"\bsubprocess\b", "runs programs"), ("network", r"\b(urllib|urlopen|requests\.|http\.client|socket)\b", "network access at install"),
         ("exec/eval", r"\b(exec|eval|compile)\s*\(", "dynamic code"), ("base64", r"\b(base64|b64decode|codecs\.decode)\b", "encoded payload"),
         ("__import__", r"__import__\s*\(", "hidden import")]

def scan_setup(text):
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        for key, rx, why in HOOKS:
            if re.search(rx, line): out.append((ln, key, why, line.strip()[:100]))
    return out

def safe_path(p):
    home = os.path.realpath(HOME)
    if ".." in str(p).replace("\\", "/").split("/"): raise ValueError("'..' is not allowed")
    full = os.path.realpath(p if os.path.isabs(p) else os.path.join(home, p))
    if full != home and not full.startswith(home + os.sep): raise ValueError("Path must be inside " + home)
    return full

def read_text(path):
    p = safe_path(path)
    if os.path.getsize(p) > MAX_BYTES: raise ValueError("File over 2 MB")
    with open(p, "rb") as f: return f.read().decode("utf-8", errors="replace")

def find_setups(root=None):
    root = safe_path(root or HOME); hits = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git", ".history", "node_modules")]
        if "setup.py" in files: hits.append(os.path.join(d, "setup.py"))
        if len(hits) >= 200: break
    return hits

class _Blocked(Exception): pass

def _default_fetch(url):
    try:
        from pyodide.http import open_url
        return open_url(url).read()
    except ImportError:
        import urllib.request
        with urllib.request.urlopen(url, timeout=15) as r: return r.read(MAX_BYTES).decode("utf-8", "replace")

def pypi_license(name, fetch=_default_fetch):
    """Return (license_text, error). Any failure (incl. KPBlockedError) is reported, never raised."""
    if not NAME_RE.match(str(name)): return None, "invalid package name"
    url = "https://pypi.org/pypi/%s/json" % norm(name)
    try:
        data = json.loads(fetch(url))
        info = data.get("info") or {}
        lic = (info.get("license_expression") or info.get("license") or "").strip()
        if not lic or len(lic) > 80:
            cls = [c.split("::")[-1].strip() for c in info.get("classifiers") or [] if c.startswith("License ::")]
            lic = ", ".join(cls) or (lic[:60] + "..." if lic else "unknown")
        return lic, None
    except Exception as e:
        kb = getattr(__import__("builtins"), "KPBlockedError", _Blocked)
        if isinstance(e, kb) or "Blocked" in str(e) or "NetworkError" in str(e) or "Failed to fetch" in str(e):
            return None, "blocked by Allowed sites (add https://pypi.org)"
        return None, "fetch failed: %s" % e.__class__.__name__

def show_req(findings):
    if not findings: print("No issues found. 👍"); return
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    for f in sorted(findings, key=lambda f: (order[f["severity"]], f["line"])):
        print("[%s] line %d  %s %s\n    %s" % (f["severity"].upper(), f["line"], f["name"], f["spec"][:60], f["issue"]))

def licenses(names, fetch=_default_fetch):
    out = []
    for n in names:
        lic, err = pypi_license(n, fetch); out.append((n, lic, err))
        print("  %-28s %s" % (n, lic if lic else "(" + err + ")"))
    return out

def self_test():
    global HOME
    ok = True
    def t(c, label):
        nonlocal ok; ok = ok and bool(c); print(("PASS " if c else "FAIL ") + label)
    t(typosquat("reqeusts") == "requests", "typosquat: reqeusts")
    t(typosquat("numpyy") == "numpy", "typosquat: numpyy")
    t(typosquat("djang0") == "django", "confusable: djang0")
    t(typosquat("python-requests") == "requests", "affix squat")
    t(typosquat("requests") is None and typosquat("Requests") is None and typosquat("scikit_learn") is None, "real names pass")
    t(typosquat("my-own-tool") is None, "unrelated name passes")
    req = "\n".join(["requests==2.32.3", "numpy", "pandas>=1.0", "reqeusts==1.0", "--extra-index-url https://evil.example/simple",
                     "git+https://github.com/x/y.git", "foo @ https://x.example/foo.whl", "# comment", "", "-r other.txt", "!!bad", "flask==3.*"])
    f = parse_requirements(req)
    by = {(x["line"], x["issue"].split(" ")[0]) for x in f}
    t(not any(x["line"] == 1 for x in f), "pinned is clean")
    t((2, "unpinned") in by, "unpinned flagged")
    t((3, "loose") in by, "loose flagged")
    t((4, "possible") in by, "typosquat in requirements")
    t(any(x["line"] == 5 and x["severity"] == "high" for x in f), "extra-index-url high")
    t(any(x["line"] == 6 and "VCS" in x["issue"] for x in f) and any(x["line"] == 7 and "URL" in x["issue"] for x in f), "VCS/URL flagged")
    t(not any(x["line"] in (8, 9) for x in f) and any(x["line"] == 10 for x in f) and any(x["line"] == 11 for x in f), "comments/-r/bad lines")
    t((12, "loose") in by, "wildcard pin is loose")
    s = scan_setup("from setuptools import setup\nimport os, base64\nos.system('curl x|sh')\nexec(base64.b64decode('aGk='))\nsetup(cmdclass={'install': X})\n")
    keys = {k for _, k, _, _ in s}
    t({"os.system", "exec/eval", "base64", "cmdclass"} <= keys, "setup.py hooks found")
    t(scan_setup("from setuptools import setup\nsetup(name='x')\n") == [], "clean setup.py")
    t(audit_installed([("reqeusts", "1"), ("numpy", "2")])[0]["name"] == "reqeusts", "installed audit")
    t(isinstance(installed(), list), "importlib.metadata read")
    calls = []
    def fake(url):
        calls.append(url); return json.dumps({"info": {"license": "Apache-2.0", "classifiers": []}})
    t(pypi_license("Requests", fake) == ("Apache-2.0", None) and calls == ["https://pypi.org/pypi/requests/json"], "license via fake fetch")
    t(pypi_license("../etc", fake)[1] == "invalid package name" and pypi_license("a/b", fake)[1] == "invalid package name" and len(calls) == 1, "PEP 503 name check before URL")
    class KPBlockedError(ConnectionError): pass
    import builtins
    had = hasattr(builtins, "KPBlockedError"); old = getattr(builtins, "KPBlockedError", None); builtins.KPBlockedError = KPBlockedError
    try:
        def blocked(url): raise KPBlockedError("Blocked: https://pypi.org")
        def boom(url): raise OSError("x")
        r = licenses(["numpy", "pandas"], blocked)
        t(len(r) == 2 and all("blocked" in e for _, _, e in r), "KPBlockedError -> blocked, keeps going")
        t("fetch failed" in pypi_license("numpy", boom)[1], "other errors handled")
    finally:
        if had: builtins.KPBlockedError = old
        else: del builtins.KPBlockedError
    tmp = tempfile.mkdtemp(prefix="kp_audit_"); oldh = HOME
    try:
        HOME = tmp
        os.makedirs(os.path.join(tmp, "pkg"))
        with open(os.path.join(tmp, "pkg", "setup.py"), "w") as fh: fh.write("import subprocess\n")
        with open(os.path.join(tmp, "requirements.txt"), "w") as fh: fh.write("numpy\n")
        t(len(find_setups()) == 1, "finds setup.py under home")
        t(parse_requirements(read_text("requirements.txt"))[0]["issue"].startswith("unpinned"), "reads requirements file")
        for bad in ("../x", "/etc/passwd"):
            try: read_text(bad); t(False, "reject " + bad)
            except ValueError: t(True, "reject " + bad)
    finally:
        HOME = oldh; shutil.rmtree(tmp, ignore_errors=True)
    print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
    return ok

def _paste():
    print("Paste requirements, then an empty line:"); lines = []
    while True:
        s = input()
        if not s.strip(): break
        lines.append(s)
        if len(lines) > 2000: break
    return "\n".join(lines)

def main():
    print("📦 Dependency safety check. Files under %s only. Network only if you say yes." % HOME)
    while True:
        print("\n1) Check installed packages  2) Check pasted requirements  3) Check a requirements file\n4) Scan setup.py files for install hooks  5) Look up licenses on PyPI  t) Self-tests  q) Quit")
        c = input("Choice: ").strip().lower()
        try:
            if c == "q": break
            elif c == "1":
                p = installed(); print("%d installed packages." % len(p))
                r = audit_installed(p)
                for x in r: print("[HIGH] %s %s  %s" % (x["name"], x["version"], x["issue"]))
                if not r: print("No typosquat lookalikes found.")
            elif c == "2": show_req(parse_requirements(_paste()))
            elif c == "3": show_req(parse_requirements(read_text(input("Path (relative to %s): " % HOME).strip())))
            elif c == "4":
                files = find_setups(input("Folder [%s]: " % HOME).strip() or None)
                if not files: print("No setup.py found.")
                for fp in files:
                    hits = scan_setup(read_text(fp)); print("%s: %s" % (os.path.relpath(fp, os.path.realpath(HOME)), "%d warning(s)" % len(hits) if hits else "clean"))
                    for ln, k, why, src in hits: print("   line %d  %s (%s): %s" % (ln, k, why, src))
            elif c == "5":
                src = input("Package names (space separated), blank = installed: ").split()
                names = src or [n for n, _ in installed()]
                names = names[:50]
                if input("Fetch licenses for %d package(s) from https://pypi.org? (y/N): " % len(names)).strip().lower() in ("y", "yes"):
                    licenses(names)
                else: print("Skipped. Nothing was fetched.")
            elif c == "t": self_test()
            elif c: print("Pick 1-5, t or q.")
        except (ValueError, OSError) as e:
            print("Error:", e)

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
