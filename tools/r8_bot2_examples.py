# bot2: Practical Example Scripts - 10 runnable stdlib examples (JSON fetch, CSV summary, regex tester, SQLite, file walk, dataclass, and more) in an EXAMPLES dict.
import io, os, contextlib

BASE = "/home/pyodide/kp_examples"   # every example writes only inside this folder

EXAMPLES = {
 "json_fetch": ("Fetch JSON from a URL, with an offline sample fallback", '''import json
SAMPLE = '{"name": "kpython", "stars": 42, "topics": ["python", "ios"]}'
def fetch(url):
    try:
        from pyodide.http import open_url
        return open_url(url).read()
    except Exception:
        return None
text = fetch("https://api.github.com/repos/python/cpython") if ONLINE else None
data = json.loads(text or SAMPLE)
print("Source:", "network" if text else "offline sample")
for k in list(data)[:3]:
    print(f"{k}: {str(data[k])[:40]}")
'''),
 "csv_summary": ("Write a CSV, then summarize each numeric column", '''import csv, os, statistics
path = os.path.join(BASE, "sales.csv")
rows = [["item", "qty", "price"], ["soap", 4, 2.5], ["mop", 1, 12], ["bags", 10, 0.4]]
with open(path, "w", newline="") as f:
    csv.writer(f).writerows(rows)
with open(path, newline="") as f:
    data = list(csv.DictReader(f))
for col in ("qty", "price"):
    vals = [float(r[col]) for r in data]
    print(f"{col}: count={len(vals)} sum={sum(vals):g} mean={statistics.mean(vals):.2f} min={min(vals):g} max={max(vals):g}")
'''),
 "regex_tester": ("Test a regex against sample lines and show matches and groups", '''import re
pattern = r"(?P<user>[\\w.]+)@(?P<domain>[\\w.]+\\.\\w+)"
lines = ["contact: kei@example.com", "no email here", "two: a@b.io, c.d@e.org"]
rx = re.compile(pattern)
for line in lines:
    found = [m.groupdict() for m in rx.finditer(line)]
    print(f"{line!r} -> {found or 'no match'}")
'''),
 "sqlite_demo": ("Create a SQLite table, insert rows, and query with GROUP BY", '''import sqlite3
con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE jobs (client TEXT, hours REAL, rate REAL)")
con.executemany("INSERT INTO jobs VALUES (?, ?, ?)", [("Acme", 3, 25), ("Acme", 2, 25), ("Bolt", 4, 30)])
for client, hrs, total in con.execute("SELECT client, SUM(hours), SUM(hours*rate) FROM jobs GROUP BY client ORDER BY client"):
    print(f"{client}: {hrs:g} h, ${total:.2f}")
con.close()
'''),
 "file_walk": ("Make a small folder tree, then walk it and list sizes", '''import os
root = os.path.join(BASE, "tree")
for sub in ("a", "a/b", "c"):
    os.makedirs(os.path.join(root, sub), exist_ok=True)
for name, text in (("a/one.txt", "hi"), ("a/b/two.py", "print(2)"), ("c/three.md", "# hi there")):
    with open(os.path.join(root, name), "w") as f:
        f.write(text)
total = 0
for dirpath, dirs, files in os.walk(root):
    dirs.sort()
    for fn in sorted(files):
        p = os.path.join(dirpath, fn); size = os.path.getsize(p); total += size
        print(f"{os.path.relpath(p, root):14} {size} bytes")
print("Total:", total, "bytes")
'''),
 "dataclass_demo": ("Dataclasses with defaults, sorting, and conversion to dict", '''from dataclasses import dataclass, field, asdict
@dataclass(order=True)
class Task:
    priority: int
    title: str = field(compare=False)
    done: bool = field(default=False, compare=False)
tasks = sorted([Task(2, "Mop floors"), Task(1, "Buy supplies"), Task(3, "Send invoice", True)])
for t in tasks:
    print(f"[{'x' if t.done else ' '}] P{t.priority} {t.title}")
print(asdict(tasks[0]))
'''),
 "word_count": ("Count words and top words in text", '''import re
from collections import Counter
text = """Python is fun. Python on a phone is handy, and handy tools are fun to build."""
words = re.findall(r"[a-z']+", text.lower())
print("Words:", len(words), "Unique:", len(set(words)))
for w, n in Counter(words).most_common(3):
    print(f"{w}: {n}")
'''),
 "date_math": ("Date math: days between dates, add days, next weekday", '''from datetime import date, timedelta
start = date.today()
end = date(start.year, 12, 25)
if end < start: end = date(start.year + 1, 12, 25)
print("Today:", start)
print("Days until Dec 25:", (end - start).days)
print("In 30 days:", start + timedelta(days=30))
monday = start + timedelta(days=(7 - start.weekday()) % 7 or 7)
print("Next Monday:", monday, monday.strftime("%A"))
'''),
 "json_file_store": ("Save and load app settings as a JSON file", '''import json, os
path = os.path.join(BASE, "settings.json")
settings = {"theme": "dark", "font": 14, "recent": ["a.py", "b.py"]}
with open(path, "w") as f:
    json.dump(settings, f, indent=2)
with open(path) as f:
    loaded = json.load(f)
loaded["font"] += 2
print("Loaded:", loaded)
print("Round-trip ok:", {**settings, "font": 16} == loaded)
'''),
 "timer_profile": ("Time two approaches and compare speed", '''import timeit
setup = "data = list(range(1000))"
loop = timeit.timeit("s=0\\nfor x in data: s+=x", setup=setup, number=200)
builtin = timeit.timeit("sum(data)", setup=setup, number=200)
print(f"loop:    {loop*1000:.2f} ms")
print(f"sum():   {builtin*1000:.2f} ms")
print("sum() is faster" if builtin < loop else "loop is faster")
'''),
}

def safe_base(base=None):
    import builtins as _b
    g = getattr(_b, "kp_safe_path", None)
    if g is not None and base and os.path.realpath(base).startswith("/home/pyodide"):
        g(os.path.relpath(os.path.realpath(base), "/home/pyodide"))   # v11 (Drop #9): confine an explicit base to ~
    b = os.path.realpath(base or BASE)
    os.makedirs(b, exist_ok=True)
    return b

def run(name, base=None, online=False):
    """Run one example; returns its printed output."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(EXAMPLES[name][1], {"__name__": "example", "BASE": safe_base(base), "ONLINE": online})
    return buf.getvalue()

def self_test():
    import tempfile
    assert len(EXAMPLES) == 10
    tmp = tempfile.mkdtemp()
    for name in EXAMPLES:
        out = run(name, base=tmp)
        assert out.strip(), name
    for root, _, files in os.walk(tmp):
        for f in files:
            assert os.path.realpath(os.path.join(root, f)).startswith(os.path.realpath(tmp))
    assert "offline sample" in run("json_fetch", base=tmp)
    assert "Acme: 5 h, $125.00" in run("sqlite_demo", base=tmp)
    print("Self-tests passed (10 examples ran, all files stayed in the sandbox folder).")

def main():
    names = list(EXAMPLES)
    print("Practical Example Scripts")
    while True:
        for i, n in enumerate(names, 1): print(f"{i:2}. {n:16} {EXAMPLES[n][0]}")
        c = input("\nNumber to view/run, t) self-test, q) quit: ").strip().lower()
        if c == "q": break
        if c == "t": self_test(); continue
        if not c.isdigit() or not 1 <= int(c) <= len(names):
            if c: print(f"Pick 1-{len(names)}, t or q.")
            continue
        n = names[int(c) - 1]
        print(f"\n--- {n} ---\n{EXAMPLES[n][1]}")
        if input("Run it? (y/N): ").strip().lower() in ("y", "yes"):
            try: print(run(n, online=(n == "json_fetch")))
            except Exception as e: print("Error:", type(e).__name__, e)


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
