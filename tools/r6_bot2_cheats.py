# bot2: Python Cheat Sheets - 19 searchable offline topics (strings to algorithms), each with tips and a runnable example.
import io, contextlib

# topic: (tips, example code)
SHEETS = {
 "strings": ("s.upper() lower() strip() split(sep) sep.join(list) replace(a,b) startswith() find() s[::-1] s.isdigit() s.title() s.zfill(n)",
  "s = '  Hello, World  '\nprint(s.strip().lower().split(', '))\nprint('-'.join(['a','b','c']), 'abc'[::-1], '42'.zfill(5))"),
 "lists": ("append extend insert pop remove index count sort(key=, reverse=) sorted() reversed() slicing a[1:3] a[-1] len() in enumerate() zip()",
  "a = [3, 1, 2]\na.append(5); a.sort(reverse=True)\nprint(a, a[-1], sorted(a, key=lambda x: -x))\nfor i, (x, y) in enumerate(zip('ab', [1, 2])): print(i, x, y)"),
 "dicts": ("d[k] d.get(k, default) d.setdefault(k, v) d.items() keys() values() pop(k) update() {**a, **b} a | b del d[k] k in d",
  "d = {'a': 1}\nd['b'] = 2\nprint(d.get('z', 0), list(d.items()))\nprint({**d, 'c': 3}, {k: v*10 for k, v in d.items()})"),
 "sets": ("add remove discard | union & intersection - difference ^ symmetric in issubset frozenset; sets drop duplicates",
  "a, b = {1, 2, 3}, {2, 3, 4}\nprint(a | b, a & b, a - b, a ^ b)\nprint(set([1, 1, 2]), {2} <= a)"),
 "comprehensions": ("[expr for x in it if cond]  {k: v for ...}  {x for ...}  (x for ...) generator  nested: [x for row in m for x in row]",
  "print([x*x for x in range(6) if x % 2 == 0])\nprint({w: len(w) for w in ['hi', 'yes']})\nprint(sum(x for x in range(5)), [x for r in [[1,2],[3]] for x in r])"),
 "itertools": ("count cycle repeat chain islice product permutations combinations groupby accumulate zip_longest pairwise",
  "import itertools as it\nprint(list(it.combinations('abc', 2)))\nprint(list(it.accumulate([1, 2, 3])), list(it.islice(it.count(10), 3)))\nprint([(k, len(list(g))) for k, g in it.groupby('aabbbc')])"),
 "collections": ("Counter(most_common) defaultdict(list) deque(appendleft, popleft, maxlen) namedtuple OrderedDict ChainMap",
  "from collections import Counter, defaultdict, deque, namedtuple\nprint(Counter('banana').most_common(2))\ng = defaultdict(list); g['x'].append(1); print(dict(g))\nq = deque([1, 2]); q.appendleft(0); print(q.popleft(), q)\nP = namedtuple('P', 'x y'); print(P(1, 2).x)"),
 "functools": ("lru_cache / cache memoize, partial(fn, arg), reduce(fn, it), wraps for decorators, cmp_to_key, total_ordering",
  "from functools import lru_cache, partial, reduce\n@lru_cache(None)\ndef fib(n): return n if n < 2 else fib(n-1) + fib(n-2)\nprint(fib(50), partial(int, base=2)('101'), reduce(lambda a, b: a*b, [1, 2, 3, 4]))"),
 "pathlib": ("Path('a')/'b'  .exists() .mkdir(parents=True, exist_ok=True) .read_text() .write_text() .glob('*.py') .name .stem .suffix .parent",
  "from pathlib import Path\nimport tempfile\np = Path(tempfile.mkdtemp()) / 'notes' / 'a.txt'\np.parent.mkdir(parents=True, exist_ok=True)\np.write_text('hi')\nprint(p.read_text(), p.name, p.stem, p.suffix, [f.name for f in p.parent.glob('*.txt')])"),
 "re": ("re.search match fullmatch findall sub split compile; \\d digit \\w word \\s space . any * + ? {n} ^ $ (group) (?P<name>...) flags re.I",
  "import re\nprint(re.findall(r'\\d+', 'a1 b22 c333'))\nm = re.search(r'(?P<user>\\w+)@(\\w+)', 'mail bob@site now')\nprint(m['user'], m.group(2), re.sub(r'\\s+', ' ', 'a   b'))"),
 "datetime": ("datetime.now() date.today() timedelta(days=) strftime('%Y-%m-%d %H:%M') strptime(s, fmt) .isoformat() fromisoformat() weekday()",
  "from datetime import datetime, timedelta\nd = datetime(2026, 10, 16, 9, 30)\nprint(d.strftime('%a %b %d %I:%M %p'), (d + timedelta(days=7)).date())\nprint(datetime.strptime('2026-01-02', '%Y-%m-%d').weekday())"),
 "json": ("json.dumps(obj, indent=2) json.loads(s) json.dump(obj, f) json.load(f); dicts lists str int float bool None only",
  "import json\ns = json.dumps({'a': [1, 2], 'ok': True}, indent=2)\nprint(s)\nprint(json.loads(s)['a'])"),
 "csv": ("csv.reader / writer, DictReader / DictWriter(fieldnames=) writeheader(); open files with newline=''",
  "import csv, io\nbuf = io.StringIO()\nw = csv.DictWriter(buf, fieldnames=['name', 'qty']); w.writeheader(); w.writerow({'name': 'soap', 'qty': 3})\nprint(list(csv.DictReader(io.StringIO(buf.getvalue()))))"),
 "typing": ("list[int] dict[str, int] tuple[int, ...] Optional[X] / X | None, Union, Callable[[int], str], Any, TypedDict, Literal, hints are not enforced at runtime",
  "from typing import Optional, Callable\ndef apply(f: Callable[[int], int], x: Optional[int] = None) -> int:\n    return f(x or 0)\nprint(apply(lambda n: n + 1, 4), apply.__annotations__['return'])"),
 "dataclasses": ("@dataclass auto __init__/__repr__/__eq__; field(default_factory=list); frozen=True; order=True; asdict(); __post_init__",
  "from dataclasses import dataclass, field, asdict\n@dataclass(order=True)\nclass Job:\n    price: float\n    name: str = 'clean'\n    tags: list = field(default_factory=list)\nprint(Job(50), asdict(Job(9, 'mop')), Job(1) < Job(2))"),
 "async": ("async def, await, asyncio.gather(*coros), asyncio.sleep, asyncio.create_task, asyncio.run(main()) (Pyodide: top-level await)",
  "import asyncio\nasync def job(n):\n    await asyncio.sleep(0.01)\n    return n * 2\nasync def main():\n    return await asyncio.gather(*(job(i) for i in range(3)))\ntry:\n    print(asyncio.run(main()))\nexcept RuntimeError:\n    print('Already in a loop (Pyodide): use await main()')"),
 "exceptions": ("try/except Type as e/else/finally, raise ValueError('msg'), raise ... from e, custom: class MyError(Exception), Exception catches most",
  "class TooBig(Exception): pass\ndef check(n):\n    if n > 10: raise TooBig(f'{n} > 10')\n    return n\nfor v in (5, 50, 'x'):\n    try: check(v)\n    except TooBig as e: print('caught', e)\n    except TypeError: print('bad type')\n    else: print('ok', v)\n    finally: pass"),
 "fstrings": ("{x!r} repr  {x:>10} right  {x:<10} left  {x:^10} center  {x:.2f}  {x:,}  {x:.1%}  {x:08.3f}  {x:x} hex  {x:b} binary  {x=} debug  {d:%Y-%m-%d}",
  "x, pi, name = 1234567, 3.14159, 'Kei'\nprint(f'{x:,} {pi:.2f} {0.256:.1%} {name!r} {name:>6}| {255:x} {5:b} {x=}')"),
 "algorithms": ("binary search (bisect), sorting key=, two pointers, sliding window, BFS with deque, DFS recursion, memoized DP, heapq for top-k",
  "import bisect, heapq\nfrom collections import deque\na = [1, 3, 5, 7]\nprint(bisect.bisect_left(a, 5), heapq.nlargest(2, a))\ng = {'a': ['b', 'c'], 'b': ['d'], 'c': [], 'd': []}\nseen, q = ['a'], deque(['a'])\nwhile q:\n    for n in g[q.popleft()]:\n        if n not in seen: seen.append(n); q.append(n)\nprint('BFS order:', seen)"),
}

def search(q):
    words = q.lower().split()
    return [t for t, (tips, code) in SHEETS.items() if all(w in f"{t} {tips} {code}".lower() for w in words)]

def run_example(topic):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(SHEETS[topic][1], {"__name__": "cheat"})
    return buf.getvalue()

def show(topic):
    tips, code = SHEETS[topic]
    return f"== {topic} ==\n{tips}\n\nExample:\n{code}"

def self_test():
    assert len(SHEETS) >= 19
    for t in SHEETS:
        assert run_example(t).strip(), t
    assert "collections" in search("counter")
    assert search("zzqq") == []
    assert "fstrings" in search("hex")
    print(f"Self-tests passed ({len(SHEETS)} topics, all examples run).")

def main():
    print("Python Cheat Sheets")
    while True:
        c = input("\n1) List topics  2) Search  3) Show + run  t) Self-test  q) Quit: ").strip().lower()
        if c == "1":
            print(", ".join(SHEETS))
        elif c == "2":
            hits = search(input("Search: "))
            print(", ".join(hits) if hits else "No matches.")
        elif c == "3":
            t = input("Topic: ").strip().lower()
            if t not in SHEETS:
                hits = search(t); t = hits[0] if len(hits) == 1 else None
            if not t:
                print("Unknown topic. Try Search."); continue
            print(show(t))
            if input("Run the example? (y/N): ").strip().lower() in ("y", "yes"):
                try: print("Output:\n" + run_example(t))
                except Exception as e: print("Example error:", e)
        elif c == "t":
            self_test()
        elif c == "q":
            break

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
