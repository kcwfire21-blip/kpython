# Forlor: saved API request collections ({{var}} variables) run through the KPython HTTP path; secret headers are never saved, prompted per run, and masked in output.
import builtins, json, os, re, time

HOME = "/home/pyodide"
MAX_BYTES = 500_000
MAX_RESPONSE = 2_000_000  # KPython: response body cap
STORE = "kp_api_collections.json"
SECRET_HDR = re.compile(r"^(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key|[\w-]*(token|secret|password|key)[\w-]*)$", re.I)
VAR = re.compile(r"\{\{\s*([A-Za-z_][\w-]*)\s*\}\}")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

def _local_safe(p, base=HOME):
    full = os.path.realpath(os.path.join(base, str(p).strip()))
    if full != base and not full.startswith(base + "/"):
        raise ValueError(f"refused: {p} is outside {base}")
    return full
safe_path = getattr(builtins, "kp_safe_path", _local_safe)

# ---------- storage ----------
def is_secret(name):
    return bool(SECRET_HDR.match(name.strip()))

def strip_secrets(req):
    """Return a copy safe to store: secret header values become a per-run prompt marker."""
    r = dict(req)
    r["headers"] = {k: ("<ask>" if is_secret(k) else v) for k, v in (req.get("headers") or {}).items()}
    return r

def load(path=STORE):
    p = safe_path(path)
    if not os.path.exists(p):
        return {"vars": {}, "requests": {}}
    if os.path.getsize(p) > MAX_BYTES:
        raise ValueError("Collection file is over 500KB")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("vars", {}); data.setdefault("requests", {})
    return data

def save(data, path=STORE, confirm=True):
    clean = {"vars": {k: v for k, v in data["vars"].items() if not is_secret(k)},
             "requests": {n: strip_secrets(r) for n, r in data["requests"].items()}}
    text = json.dumps(clean, indent=2)
    if len(text.encode()) > MAX_BYTES:
        raise ValueError("Collection would exceed 500KB")
    p = safe_path(path)
    if confirm and os.path.exists(p) and input(f"Overwrite {path}? (y/N): ").strip().lower() != "y":
        print("Not saved."); return False
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return True

# ---------- variables / masking ----------
def substitute(text, variables):
    missing = []
    def rep(m):
        k = m.group(1)
        if k in variables: return str(variables[k])
        missing.append(k); return m.group(0)
    out = VAR.sub(rep, text or "")
    if missing:
        raise KeyError("Undefined variable(s): " + ", ".join(sorted(set(missing))))
    return out

def mask_headers(h):
    return {k: ("****(hidden)" if is_secret(k) else v) for k, v in h.items()}

def build(req, variables, ask=input):
    url = substitute(req["url"], variables)
    if not url.startswith("https://"):
        raise ValueError("Only https:// URLs are allowed")
    headers = {}
    for k, v in (req.get("headers") or {}).items():
        if is_secret(k):
            v = ask(f"{k}: ").split(":", 1)[-1].strip() if v in ("", "<ask>") else v
        headers[k] = substitute(v, variables)
    body = substitute(req["body"], variables) if req.get("body") else None
    if body is not None and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json"
    return req.get("method", "GET").upper(), url, headers, body

# ---------- HTTP (KPython path: pyfetch, governed by Allowed sites; urllib fallback) ----------
def _show(status, headers, text, ms):
    print(f"\n=== {status} | {ms:.0f} ms ===")
    for k, v in mask_headers(headers).items():
        print(f"{k}: {v}")
    print("---")
    try: print(json.dumps(json.loads(text), indent=2)[:20000])
    except Exception: print(text[:20000])

async def send_async(method, url, headers, body):
    from pyodide.http import pyfetch
    t = time.perf_counter()
    kw = {"method": method, "headers": headers}
    if body is not None: kw["body"] = body
    try:
        r = await pyfetch(url, **kw)
        # KPython: cap response bodies at 2 MB (checked from Content-Length first, then the real size)
        try: cl = int(r.headers.get("content-length", "0") or 0)
        except Exception: cl = 0
        if cl > MAX_RESPONSE:
            print(f"Response is {cl:,} bytes; over the {MAX_RESPONSE:,}-byte limit, not downloaded."); return
        raw = await r.bytes()
        if len(raw) > MAX_RESPONSE:
            print(f"Response over {MAX_RESPONSE:,} bytes; showing the first part only.")
            raw = raw[:MAX_RESPONSE]
        text = raw.decode("utf-8", "replace")
        try: hdrs = dict(r.js_response.headers.entries())
        except Exception: hdrs = {}
        _show(f"{r.status} {r.status_text}", hdrs, text, (time.perf_counter() - t) * 1000)
    except Exception as e:
        print("Request failed (it may be blocked by Allowed sites or CORS):", e)

def send_sync(method, url, headers, body):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, data=body.encode() if body else None, headers=headers, method=method)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            _show(f"{r.status} {r.reason}", dict(r.headers), r.read(MAX_RESPONSE).decode("utf-8", "replace"), (time.perf_counter() - t) * 1000)
    except urllib.error.HTTPError as e:
        _show(f"{e.code} {e.reason}", dict(e.headers), e.read(MAX_RESPONSE).decode("utf-8", "replace"), (time.perf_counter() - t) * 1000)
    except Exception as e:
        print("Request failed:", e)

def run(req, variables):
    method, url, headers, body = build(req, variables)
    print(f"{method} {url}")
    for k, v in mask_headers(headers).items(): print(f"  {k}: {v}")
    if input("Send it? (y/N): ").strip().lower() != "y":
        print("Cancelled."); return
    try:
        import pyodide.http  # noqa
        import asyncio
        return asyncio.ensure_future(send_async(method, url, headers, body))
    except ImportError:
        send_sync(method, url, headers, body)

# ---------- UI ----------
def _read_headers():
    print("Headers as Name: value, blank line to finish. Secret headers (Authorization, tokens) are asked each run, never saved.")
    h = {}
    while True:
        line = input("  > ").strip()
        if not line: return h
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip()] = "<ask>" if is_secret(k) else v.strip()

def _read_body():
    print("Body (END to finish, or just END for none):")
    lines = []
    while True:
        l = input()
        if l.strip() == "END": break
        lines.append(l)
    return "\n".join(lines).strip() or None

def main():
    data = load()
    while True:
        print("\n=== API Collections ===")
        for i, n in enumerate(data["requests"], 1):
            r = data["requests"][n]; print(f" {i}. {n}  [{r['method']} {r['url']}]")
        print(" vars:", ", ".join(f"{k}={v}" for k, v in data["vars"].items()) or "(none)")
        c = input("[r]un  [a]dd  [d]elete  [v]ar  [s]elf-test  [q]uit: ").strip().lower()
        names = list(data["requests"])
        try:
            if c == "q": return
            if c == "s": self_test(); continue  # KPython: back to the menu
            if c == "v":
                k = input("Variable name: ").strip(); v = input("Value (blank to remove): ")
                if is_secret(k): print("Secret-looking names aren't stored. Put them in a header instead."); continue
                if v: data["vars"][k] = v
                else: data["vars"].pop(k, None)
                save(data, confirm=False)
            elif c == "a":
                n = input("Request name: ").strip()
                if n in data["requests"] and input("Exists. Replace? (y/N): ").strip().lower() != "y": continue
                m = (input(f"Method {METHODS} [GET]: ").strip().upper() or "GET")
                if m not in METHODS: print("Bad method"); continue
                data["requests"][n] = {"method": m, "url": input("URL (can use {{base}}): ").strip(),
                                       "headers": _read_headers(), "body": _read_body() if m != "GET" else None}
                save(data, confirm=False); print("Saved (without secrets).")
            elif c == "d":
                n = names[int(input("Number: ")) - 1]
                if input(f"Delete {n}? (y/N): ").strip().lower() == "y":
                    del data["requests"][n]; save(data, confirm=False)
            elif c == "r":
                n = names[int(input("Number: ")) - 1]
                fut = run(data["requests"][n], data["vars"])
                if fut is not None: return fut  # KPython: Dev tab awaits it  # browser: let the event loop finish the request
        except (ValueError, KeyError, IndexError) as e:
            print("Error:", e)

def self_test():
    v = {"base": "https://httpbin.org", "id": "7"}
    assert substitute("{{base}}/x/{{ id }}", v) == "https://httpbin.org/x/7"
    try: substitute("{{nope}}", v); raise AssertionError
    except KeyError: pass
    req = {"method": "POST", "url": "{{base}}/post", "headers": {"Authorization": "Bearer abc", "X-Trace": "{{id}}"}, "body": '{"id": {{id}}}'}
    s = strip_secrets(req)
    assert s["headers"]["Authorization"] == "<ask>" and s["headers"]["X-Trace"] == "{{id}}"
    m, u, h, b = build(s, v, ask=lambda p: "Bearer zzz")
    assert m == "POST" and u == "https://httpbin.org/post" and h["Authorization"] == "Bearer zzz" and b == '{"id": 7}'
    assert mask_headers(h)["Authorization"] == "****(hidden)" and mask_headers({"x-api-key": "k"})["x-api-key"] == "****(hidden)"
    try: build({"url": "http://x.com"}, {}); raise AssertionError
    except ValueError: pass
    try: _local_safe("../etc/passwd"); raise AssertionError
    except ValueError: pass
    import tempfile
    global safe_path
    old, d = safe_path, tempfile.mkdtemp()
    safe_path = lambda p: _local_safe(p, d)
    try:
        save({"vars": {"base": "https://a.com", "api_token": "SECRET"}, "requests": {"t": req}}, "c.json", confirm=False)
        raw = open(os.path.join(d, "c.json")).read()
        assert "abc" not in raw and "SECRET" not in raw and "<ask>" in raw
        assert load("c.json")["requests"]["t"]["headers"]["Authorization"] == "<ask>"
    finally:
        safe_path = old
    print("All self-tests passed.")

# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse", "explain", "gen_tests", "scan_code", "to_fstrings", "extract", "inline", "check"):
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
