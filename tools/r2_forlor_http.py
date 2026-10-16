# Forlor: mini HTTP/API tester (like Postman) - GET/POST/PUT/DELETE with headers + JSON body; shows status, headers, timing, pretty JSON. Stores nothing.
import json, time, sys

try:
    from pyodide.http import pyfetch  # in-browser (Pyodide)
    IN_BROWSER = True
except ImportError:
    IN_BROWSER = False
    import urllib.request, urllib.error

METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")

def read_headers():
    print("Headers, one per line as Name: value. Blank line to finish.")
    h = {}
    while True:
        line = input("  > ").strip()
        if not line:
            return h
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip()] = v.strip()
        else:
            print("  (skipped: use Name: value)")

def read_body():
    print("JSON body, multiple lines allowed. Type END on its own line to finish (or just END for none).")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    raw = "\n".join(lines).strip()
    if not raw:
        return None
    try:
        return json.dumps(json.loads(raw))
    except json.JSONDecodeError as e:
        print(f"  Not valid JSON ({e}); sending as raw text.")
        return raw

SENSITIVE = ("authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "api-key", "x-auth-token")
def mask(k, v):
    kl = k.lower()
    return "****(hidden)" if kl in SENSITIVE or "token" in kl or "secret" in kl or "auth" in kl else v

def show(status, headers, text, ms):
    print(f"\n=== {status} | {ms:.0f} ms ===")
    print("--- Headers ---")
    for k, v in headers.items():
        print(f"{k}: {mask(k, v)}")
    print("--- Body ---")
    try:
        print(json.dumps(json.loads(text), indent=2)[:20000])
    except Exception:
        print(text[:20000])

def send_sync(method, url, headers, body):
    data = body.encode() if body is not None else None
    if data is not None and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
            show(f"{r.status} {r.reason}", dict(r.headers), text, (time.perf_counter() - t) * 1000)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        show(f"{e.code} {e.reason}", dict(e.headers), text, (time.perf_counter() - t) * 1000)
    except Exception as e:
        print("Request failed:", e)

async def send_async(method, url, headers, body):
    if body is not None and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json"
    kw = {"method": method, "headers": headers}
    if body is not None:
        kw["body"] = body
    t = time.perf_counter()
    try:
        r = await pyfetch(url, **kw)
        text = await r.string()
        try:
            hdrs = dict(r.js_response.headers.entries())
        except Exception:
            hdrs = {}
        show(f"{r.status} {r.status_text}", hdrs, text, (time.perf_counter() - t) * 1000)
    except Exception as e:
        print("Request failed (CORS may block some sites in the browser):", e)

def send_xhr(method, url, headers, body):
    import js
    if body is not None and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json"
    x = js.XMLHttpRequest.new(); x.open(method, url, False)
    t = time.perf_counter()
    try:
        for k, v in headers.items(): x.setRequestHeader(k, v)
        x.send(body)
    except Exception as e:
        return print("Request failed (the site may block browser requests via CORS):", e)
    hd = {}
    for line in str(x.getAllResponseHeaders()).strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1); hd[k.strip()] = v.strip()
    show(f"{x.status} {x.statusText}", hd, str(x.responseText), (time.perf_counter() - t) * 1000)

def get_request():
    m = input(f"Method {METHODS} [GET]: ").strip().upper() or "GET"
    if m not in METHODS:
        print("Unknown method, using GET.")
        m = "GET"
    url = input("URL: ").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if url.startswith("http://"):
        print("WARNING: plain http is not encrypted; anyone on the network can read it. Do not send tokens over http.")
    headers = read_headers()
    body = read_body() if m in ("POST", "PUT", "PATCH", "DELETE") else None
    return m, url, headers, body

def main():
    print("=== Mini API Tester === (nothing is saved)")
    while True:
        m, url, h, b = get_request()
        if IN_BROWSER:
            send_xhr(m, url, h, b)  # KPython: sync XHR in the worker, nothing stored
        else:
            send_sync(m, url, h, b)
        h.clear()  # drop headers (incl. any auth) right away
        if input("\nAnother request? (y/N): ").strip().lower() != "y":
            break

if __name__ == "__main__":
    main()
