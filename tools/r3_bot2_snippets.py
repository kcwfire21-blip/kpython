# bot2: Snippet Library - search Python templates (CLI, dataclass, repr class, unittest, fetch, file I/O, async) and save them as a new script under /home/pyodide.
import os

BASE = "/home/pyodide"

SNIPPETS = {
    "argparse-cli": ("Command-line tool with argparse", "cli args command line", '''import argparse

def main(argv=None):
    p = argparse.ArgumentParser(description="My tool")
    p.add_argument("name", help="who to greet")
    p.add_argument("-n", "--times", type=int, default=1)
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)
    for _ in range(a.times):
        print(f"Hello, {a.name}!")

if __name__ == "__main__":
    main(["World", "-n", "2"])  # Pyodide has no real argv; pass a list
'''),
    "dataclass": ("Dataclass with defaults and a method", "data class record model", '''from dataclasses import dataclass, field

@dataclass
class Item:
    name: str
    price: float
    tags: list = field(default_factory=list)

    def total(self, qty: int = 1) -> float:
        return round(self.price * qty, 2)

it = Item("Soap", 2.5, ["clean"])
print(it, it.total(3))
'''),
    "class-repr": ("Class with __init__, __repr__, __eq__", "class object repr oop", '''class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __repr__(self):
        return f"{type(self).__name__}(x={self.x!r}, y={self.y!r})"

    def __eq__(self, other):
        return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)

print(Point(1, 2))
'''),
    "unittest": ("unittest test file that runs in place", "test testing unit assert", '''import unittest

def add(a, b):
    return a + b

class TestAdd(unittest.TestCase):
    def test_ints(self):
        self.assertEqual(add(2, 3), 5)

    def test_str(self):
        self.assertEqual(add("a", "b"), "ab")

if __name__ == "__main__":
    unittest.main(argv=["x"], exit=False)
'''),
    "fetch": ("Fetch a URL (Pyodide open_url, urllib fallback)", "http web request download get json api", '''import json

def fetch_text(url):
    try:
        from pyodide.http import open_url   # works in the browser
        return open_url(url).read()
    except ImportError:
        from urllib.request import urlopen  # works in desktop Python
        with urlopen(url, timeout=10) as r:
            return r.read().decode()

data = json.loads(fetch_text("https://api.github.com/"))
print(list(data)[:5])
'''),
    "file-io": ("Read and write text, CSV, and JSON files", "file read write csv json save load", '''import csv, json, os

folder = "/home/pyodide/data"
os.makedirs(folder, exist_ok=True)

with open(f"{folder}/notes.txt", "w") as f:
    f.write("line one\\nline two\\n")
with open(f"{folder}/notes.txt") as f:
    print(f.read().splitlines())

rows = [{"name": "A", "qty": 2}, {"name": "B", "qty": 5}]
with open(f"{folder}/items.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["name", "qty"]); w.writeheader(); w.writerows(rows)
with open(f"{folder}/items.json", "w") as f:
    json.dump(rows, f, indent=2)
print(json.load(open(f"{folder}/items.json")))
'''),
    "async": ("asyncio example running tasks together", "async await asyncio concurrent tasks", '''import asyncio

async def job(name, delay):
    await asyncio.sleep(delay)
    return f"{name} done after {delay}s"

async def main():
    results = await asyncio.gather(job("a", 0.2), job("b", 0.1))
    print(results)

# In Pyodide top-level await works; elsewhere use asyncio.run(main())
try:
    asyncio.get_running_loop()
    asyncio.ensure_future(main())
except RuntimeError:
    asyncio.run(main())
'''),
}

def search(query):
    q = query.lower().split()
    out = []
    for key, (title, tags, _) in SNIPPETS.items():
        hay = f"{key} {title} {tags}".lower()
        if all(w in hay for w in q):
            out.append(key)
    return out

def safe_path(name):
    name = name.strip()
    if "/" in name or name.startswith("."): raise ValueError("Use a plain file name (no folders).")  # KPython
    if not name.endswith(".py"):
        name += ".py"
    path = os.path.realpath(os.path.join(BASE, name))
    if not (path == BASE or path.startswith(BASE + os.sep)):
        raise ValueError("Path must stay inside /home/pyodide.")
    return path

def build(keys):
    parts = [f"# --- {k}: {SNIPPETS[k][0]} ---\n{SNIPPETS[k][2]}" for k in keys]
    return "\n".join(parts)

def save(keys, name, overwrite=False):
    path = safe_path(name)
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path} exists.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(build(keys))
    return path

def self_test():
    import ast, tempfile
    global BASE
    for k, (_, _, code) in SNIPPETS.items():
        ast.parse(code)
    assert "unittest" in search("test")
    assert search("csv json") == ["file-io"]
    assert search("zzz") == []
    old = BASE
    BASE = os.path.realpath(tempfile.mkdtemp())
    try:
        p = save(["dataclass", "class-repr"], "demo")
        assert p.endswith("demo.py") and "class Point" in open(p).read()
        for bad in ("../evil", "/etc/passwd"):
            try: safe_path(bad); raise AssertionError(bad)
            except ValueError: pass
        try: save(["async"], "demo"); raise AssertionError("overwrite")
        except FileExistsError: pass
    finally:
        BASE = old
    print("Self-tests passed.")

def main():
    print("Snippet Library")
    while True:
        c = input("\n1) List  2) Search  3) View  4) Save new script  t) Self-test  q) Quit: ").strip().lower()
        try:
            if c == "1":
                for k, (t, _, _) in SNIPPETS.items(): print(f"{k:14} {t}")
            elif c == "2":
                hits = search(input("Search: "))
                print("\n".join(f"{k:14} {SNIPPETS[k][0]}" for k in hits) or "No matches.")
            elif c == "3":
                k = input("Snippet name: ").strip()
                print(SNIPPETS[k][2] if k in SNIPPETS else "Unknown snippet.")
            elif c == "4":
                keys = [k.strip() for k in input("Snippet names (comma-separated): ").split(",") if k.strip()]
                bad = [k for k in keys if k not in SNIPPETS]
                if not keys or bad:
                    print("Unknown:", ", ".join(bad) or "(none given)"); continue
                name = input("New file name (saved in /home/pyodide): ")
                try:
                    print("Saved to", save(keys, name))
                except FileExistsError as e:
                    if input(f"{e} Overwrite? (y/n): ").lower() == "y":
                        print("Saved to", save(keys, name, overwrite=True))
            elif c == "t":
                self_test()
            elif c == "q":
                break
        except (ValueError, OSError) as e:
            print("Error:", e)

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
