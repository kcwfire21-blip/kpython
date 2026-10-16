# bot2: Python Katas - 16 coding challenges (easy to hard) with starter code, hidden tests, hints, and saved progress.
import json, os

PROGRESS = "/home/pyodide/.katas.json"

# (id, level, prompt, function name, hint, reference solution, tests[(args, expected)])
KATAS = [
 ("reverse", "easy", "Return the string s reversed.", "solve", "Slicing with a step of -1 works: s[::-1].",
  "def solve(s):\n    return s[::-1]", [(("abc",), "cba"), (("",), ""), (("racecar",), "racecar")]),
 ("evens", "easy", "Return a list of the even numbers in nums, in order.", "solve", "Use n % 2 == 0 in a list comprehension.",
  "def solve(nums):\n    return [n for n in nums if n % 2 == 0]", [(([1,2,3,4],), [2,4]), (([],), []), (([-2,3],), [-2])]),
 ("vowels", "easy", "Count the vowels (aeiou, any case) in s.", "solve", "Lowercase s first, then count letters in 'aeiou'.",
  "def solve(s):\n    return sum(c in 'aeiou' for c in s.lower())", [(("Hello",), 2), (("xyz",), 0), (("AEIOU",), 5)]),
 ("fizzbuzz", "easy", "Return 'Fizz' if n divisible by 3, 'Buzz' by 5, 'FizzBuzz' by both, else str(n).", "solve", "Check divisibility by 15 first.",
  "def solve(n):\n    return 'FizzBuzz' if n%15==0 else 'Fizz' if n%3==0 else 'Buzz' if n%5==0 else str(n)",
  [((3,), "Fizz"), ((10,), "Buzz"), ((30,), "FizzBuzz"), ((7,), "7")]),
 ("maxnum", "easy", "Return the largest number in a non-empty list without using max().", "solve", "Track the best value seen so far in a loop.",
  "def solve(nums):\n    b = nums[0]\n    for n in nums:\n        if n > b: b = n\n    return b", [(([3,9,2],), 9), (([-5,-1],), -1), (([4],), 4)]),
 ("palindrome", "medium", "Return True if s is a palindrome, ignoring case and non-letters/digits.", "solve", "Keep only c.isalnum() characters, lowercase, compare to reverse.",
  "def solve(s):\n    t = [c.lower() for c in s if c.isalnum()]\n    return t == t[::-1]",
  [(("A man, a plan, a canal: Panama",), True), (("hello",), False), (("",), True)]),
 ("wordfreq", "medium", "Return a dict mapping each lowercase word in text to its count (split on whitespace).", "solve", "collections.Counter or dict.get(word, 0) + 1.",
  "def solve(text):\n    d = {}\n    for w in text.lower().split(): d[w] = d.get(w, 0) + 1\n    return d",
  [(("a B a",), {"a": 2, "b": 1}), (("",), {})]),
 ("anagram", "medium", "Return True if a and b are anagrams (ignore spaces and case).", "solve", "Compare sorted letters after removing spaces.",
  "def solve(a, b):\n    f = lambda s: sorted(s.replace(' ', '').lower())\n    return f(a) == f(b)",
  [(("Listen", "Silent"), True), (("abc", "abd"), False), (("dormitory", "dirty room"), True)]),
 ("twosum", "medium", "Return indices [i, j] (i < j) of two numbers in nums adding to target, or [] if none.", "solve", "Store seen values in a dict mapping value to index.",
  "def solve(nums, target):\n    seen = {}\n    for j, n in enumerate(nums):\n        if target - n in seen: return [seen[target-n], j]\n        seen[n] = j\n    return []",
  [(([2,7,11,15], 9), [0,1]), (([3,2,4], 6), [1,2]), (([1,2], 7), [])]),
 ("flatten", "medium", "Flatten an arbitrarily nested list of ints into one flat list.", "solve", "Recurse when an item is a list.",
  "def solve(x):\n    out = []\n    for i in x:\n        out += solve(i) if isinstance(i, list) else [i]\n    return out",
  [(([1,[2,[3,[4]]],5],), [1,2,3,4,5]), (([],), []), (([[[]]],), [])]),
 ("brackets", "medium", "Return True if the brackets ()[]{} in s are balanced and properly nested.", "solve", "Use a list as a stack; pop and match on closers.",
  "def solve(s):\n    st, pairs = [], {')':'(', ']':'[', '}':'{'}\n    for c in s:\n        if c in '([{': st.append(c)\n        elif c in pairs:\n            if not st or st.pop() != pairs[c]: return False\n    return not st",
  [(("([]{})",), True), (("(]",), False), (("((",), False), (("",), True)]),
 ("primes", "hard", "Return all primes below n, in order (n can be up to 100000).", "solve", "Sieve of Eratosthenes: cross out multiples starting at p*p.",
  "def solve(n):\n    if n < 3: return []\n    s = [True]*n; s[0]=s[1]=False\n    for p in range(2, int(n**0.5)+1):\n        if s[p]: s[p*p::p] = [False]*len(range(p*p, n, p))\n    return [i for i, v in enumerate(s) if v]",
  [((10,), [2,3,5,7]), ((2,), []), ((30,), [2,3,5,7,11,13,17,19,23,29])]),
 ("roman", "hard", "Convert an integer 1..3999 to a Roman numeral string.", "solve", "Walk a table of values like (1000,'M'), (900,'CM'), ... subtracting greedily.",
  "def solve(n):\n    t = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]\n    r = ''\n    for v, s in t:\n        while n >= v: r += s; n -= v\n    return r",
  [((3,), "III"), ((1994,), "MCMXCIV"), ((3999,), "MMMCMXCIX")]),
 ("lcs", "hard", "Return the length of the longest common subsequence of strings a and b.", "solve", "Dynamic programming table: dp[i][j] from dp[i-1][j-1]+1 or max of neighbors.",
  "def solve(a, b):\n    dp = [[0]*(len(b)+1) for _ in range(len(a)+1)]\n    for i in range(len(a)):\n        for j in range(len(b)):\n            dp[i+1][j+1] = dp[i][j]+1 if a[i]==b[j] else max(dp[i][j+1], dp[i+1][j])\n    return dp[-1][-1]",
  [(("abcde", "ace"), 3), (("abc", "def"), 0), (("", "x"), 0)]),
 ("intervals", "hard", "Merge overlapping [start, end] intervals; return them sorted.", "solve", "Sort by start, then extend the last merged interval when they overlap.",
  "def solve(iv):\n    out = []\n    for s, e in sorted(iv):\n        if out and s <= out[-1][1]: out[-1][1] = max(out[-1][1], e)\n        else: out.append([s, e])\n    return out",
  [(([[1,3],[2,6],[8,10]],), [[1,6],[8,10]]), (([[1,4],[4,5]],), [[1,5]]), (([],), [])]),
 ("rle", "hard", "Run-length encode s: 'aaabcc' -> 'a3b1c2'.", "solve", "itertools.groupby groups equal neighbors.",
  "def solve(s):\n    from itertools import groupby\n    return ''.join(f'{k}{len(list(g))}' for k, g in groupby(s))",
  [(("aaabcc",), "a3b1c2"), (("",), ""), (("z",), "z1")]),
]

def stub(k):
    args = ", ".join(f"arg{i+1}" for i in range(len(k[6][0][0])))
    import re
    args = re.search(r"def \w+\((.*?)\)", k[5]).group(1)
    return f"def {k[3]}({args}):\n    # {k[2]}\n    pass\n"

def run_tests(kata, code):
    ns = {"__name__": "kata"}
    try:
        exec(compile(code, "<solution>", "exec"), ns)
        fn = ns[kata[3]]
    except Exception as e:
        return 0, len(kata[6]), [f"Code error: {type(e).__name__}: {e}"]
    passed, notes = 0, []
    for i, (args, want) in enumerate(kata[6], 1):
        try:
            got = fn(*[json.loads(json.dumps(a)) for a in args])
            if got == want: passed += 1
            else: notes.append(f"Test {i} failed.")
        except Exception as e:
            notes.append(f"Test {i} crashed: {type(e).__name__}: {e}")
    return passed, len(kata[6]), notes

def load_progress(path=None):
    try:
        with open(path or PROGRESS) as f: return json.load(f)
    except (OSError, ValueError):
        return {}

def save_progress(p, path=None):
    path = path or PROGRESS
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: json.dump(p, f)

def self_test():
    import tempfile
    assert len(KATAS) >= 15 and len({k[0] for k in KATAS}) == len(KATAS)
    for k in KATAS:
        p, t, n = run_tests(k, k[5])
        assert p == t, (k[0], n)
        assert run_tests(k, stub(k))[0] < t, k[0]
    p, t, n = run_tests(KATAS[0], "def solve(:")
    assert p == 0 and "Code error" in n[0]
    tmp = os.path.join(tempfile.mkdtemp(), "k.json")
    save_progress({"reverse": True}, tmp)
    assert load_progress(tmp) == {"reverse": True}
    print(f"Self-tests passed ({len(KATAS)} katas).")

def read_code():
    print("Paste your solution, then a line with only END:")
    lines = []
    while True:
        l = input()
        if l.strip() == "END": break
        lines.append(l)
    return "\n".join(lines)

def main():
    print("Python Katas")
    prog = load_progress()
    while True:
        done = sum(1 for k in KATAS if prog.get(k[0]))
        print(f"\nSolved {done}/{len(KATAS)}")
        for i, k in enumerate(KATAS, 1):
            print(f"{i:2}. [{'x' if prog.get(k[0]) else ' '}] {k[0]:11} {k[1]}")
        c = input("Pick a number, t) self-test, r) reset progress, q) quit: ").strip().lower()
        if c == "q": break
        if c == "t": self_test(); continue
        if c == "r":
            if input("Reset all progress? (y/n): ").lower() == "y":
                prog = {}; save_progress(prog)
            continue
        if not c.isdigit() or not 1 <= int(c) <= len(KATAS): continue
        k = KATAS[int(c) - 1]
        print(f"\n{k[0]} ({k[1]}): {k[2]}\nStarter code:\n{stub(k)}")
        code = read_code()
        if input("Run hidden tests on your code? (y/n): ").lower() != "y": continue
        p, t, notes = run_tests(k, code)
        print(f"Passed {p}/{t}.")
        for n in notes: print(" ", n)
        if p == t:
            print("Solved!"); prog[k[0]] = True; save_progress(prog)
        else:
            print("Hint:", k[4])

# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse"):
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
