# Encode/decode & hash kit: base64, URL, hex, JWT decode (no verify), md5/sha1/sha256, UUID, timestamp<->date; masks secret-looking input. No files, no network.
import base64, binascii, hashlib, json, re, uuid, urllib.parse
from datetime import datetime, timezone

SECRET_RE = re.compile(r"(eyJ[\w-]+\.[\w-]+\.[\w-]*|gh[pousr]_\w{20,}|github_pat_\w{20,}|sk-[\w-]{16,}|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,})")

def mask(s):
    return SECRET_RE.sub(lambda m: m.group(0)[:4] + "..." + m.group(0)[-4:] + "[%d chars]" % len(m.group(0)), s)

def b64enc(s): return base64.b64encode(s.encode()).decode()
def b64dec(s):
    s = s.strip(); s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.replace("+", "-").replace("/", "_")).decode("utf-8", "replace")
def urlenc(s): return urllib.parse.quote(s, safe="")
def urldec(s): return urllib.parse.unquote_plus(s)
def hexenc(s): return s.encode().hex()
def hexdec(s): return bytes.fromhex(re.sub(r"[\s:]|0x", "", s)).decode("utf-8", "replace")
def hashes(s):
    b = s.encode()
    return {n: hashlib.new(n, b).hexdigest() for n in ("md5", "sha1", "sha256")}
def jwt_decode(tok):
    parts = tok.strip().split(".")
    if len(parts) < 2: raise ValueError("not a JWT")
    return tuple(json.loads(b64dec(x)) for x in parts[:2])
def ts_to_date(s):
    t = float(s)
    if t > 1e11: t /= 1000
    return datetime.fromtimestamp(t, timezone.utc).isoformat()
def date_to_ts(s):
    d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())

def _jwt_out(tok):
    h, p = jwt_decode(tok)
    out = "Header:  " + json.dumps(h, indent=2) + "\nPayload: " + json.dumps(p, indent=2)
    for k in ("iat", "nbf", "exp"):
        if isinstance(p.get(k), (int, float)): out += "\n%s: %s" % (k, ts_to_date(p[k]))
    return out + "\n(Signature NOT verified.)"

MENU = [
    ("Base64 encode", b64enc), ("Base64 decode", b64dec),
    ("URL encode", urlenc), ("URL decode", urldec),
    ("Hex encode", hexenc), ("Hex decode", hexdec),
    ("Hash md5/sha1/sha256", lambda s: "\n".join("%s: %s" % kv for kv in hashes(s).items())),
    ("JWT decode (no verify)", _jwt_out),
    ("New UUID4", None),
    ("Timestamp -> date (UTC)", ts_to_date), ("Date (ISO) -> timestamp", lambda s: str(date_to_ts(s))),
]

def selftest():
    assert b64dec(b64enc("h\u00e9llo")) == "h\u00e9llo"
    assert urldec(urlenc("a b&c=d/")) == "a b&c=d/"
    assert hexdec(hexenc("xyz")) == "xyz"
    assert hashes("abc")["md5"] == "900150983cd24fb0d6963f7d28e17f72"
    tok = b64enc('{"alg":"none"}').rstrip("=") + "." + b64enc('{"sub":"1"}').rstrip("=") + ".x"
    assert jwt_decode(tok)[1]["sub"] == "1"
    assert ts_to_date("0").startswith("1970-01-01") and ts_to_date("1000000000000").startswith("2001")
    assert date_to_ts("1970-01-02T00:00:00Z") == 86400
    assert "a" * 30 not in mask("ghp_" + "a" * 36)
    print("Self-tests passed.")

def main():
    print("Encode/Decode & Hash Kit (t = self-tests, q = quit)")
    while True:
        for i, (n, _) in enumerate(MENU, 1): print("%2d. %s" % (i, n))
        c = input("Pick: ").strip().lower()
        if c in ("q", "quit", ""): break
        if c == "t": selftest(); continue
        if not c.isdigit() or not 1 <= int(c) <= len(MENU): print("Invalid choice.\n"); continue
        name, fn = MENU[int(c) - 1]
        if fn is None: print(uuid.uuid4(), "\n"); continue
        s = input("Input: ")
        if len(s) > 100000: print("Input too long.\n"); continue
        try:
            out = fn(s)
            print("Result:\n" + mask(out))  # KPython: mask secrets in every result, JWT included
            if SECRET_RE.search(s): print("(Input looked like a secret; nothing was saved.)")
        except (ValueError, binascii.Error, OverflowError, OSError) as e:
            print("Error:", e)
        print()

# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec"):
    if callable(globals().get(_n)) and not isinstance(globals()[_n], type): globals()[_n] = _kp_cap(globals()[_n])
if "Debugger" in globals():
    _kp_dinit = Debugger.__init__
    def _kp_dinit2(self, source, *a, **k):
        if len(source) > _KP_MAX: raise ValueError("code too big to debug (max 500 KB)")
        _kp_dinit(self, source, *a, **k)
    Debugger.__init__ = _kp_dinit2

# --- KPython v5 security wrapper: every path also goes through the app's shared kp_safe_path (/home/pyodide only) ---
import builtins as _kp_b
def _kp_wrap(fn):
    def w(*a, **k):
        r = fn(*a, **k)
        return _kp_b.kp_safe_path(r) if hasattr(_kp_b, "kp_safe_path") and isinstance(r, str) and r.startswith("/") and all(globals().get(v, "/home/pyodide") == "/home/pyodide" for v in ("BASE", "BASE_DIR", "SAFE_ROOT")) else r
    return w
for _n in ("safe_path", "_safe_path", "_safe"):
    if callable(globals().get(_n)): globals()[_n] = _kp_wrap(globals()[_n])

if __name__ == "__main__":
    main()
