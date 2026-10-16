# bot2: Offline Code Explainer - reads a Python script with ast and writes a plain-English walkthrough of its functions, classes, and the Python features it uses.
import ast, os, re

BASE = "/home/pyodide"

NOTES = {
    "comprehension": "A comprehension like [x*2 for x in items] builds a list (or set/dict) in one line by looping and transforming.",
    "decorator": "A decorator (@name above a def) wraps a function to add behavior without changing its code.",
    "with": "A 'with' block opens a resource (like a file) and closes it automatically, even if an error happens.",
    "try": "try/except runs code and catches errors so the program can handle them instead of crashing.",
    "lambda": "A lambda is a tiny unnamed function written on one line, like lambda x: x + 1.",
    "fstring": "An f-string like f\"Hi {name}\" puts variable values directly inside text.",
    "async": "async/await lets code wait for slow things (like network calls) without blocking everything else.",
    "yield": "yield makes a generator: a function that hands back values one at a time instead of all at once.",
    "class": "A class is a blueprint for objects that bundle data (attributes) and actions (methods).",
    "global": "global/nonlocal lets a function change a variable defined outside it.",
}

def _words(name):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").strip()
    return s.lower() or name

def _calls(node):
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            try: nm = ast.unparse(n.func)
            except Exception: continue
            if nm not in out: out.append(nm)
    return out

def _describe_func(fn, owner=None):
    kind = "method" if owner else "function"
    a = [x.arg for x in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
    if owner and a and a[0] in ("self", "cls"): a = a[1:]
    if fn.args.vararg: a.append("*" + fn.args.vararg.arg)
    if fn.args.kwarg: a.append("**" + fn.args.kwarg.arg)
    pre = "async " if isinstance(fn, ast.AsyncFunctionDef) else ""
    lines = [f"- The {pre}{kind} `{fn.name}` (line {fn.lineno}) seems to {_words(fn.name)}."]
    if fn.name == "__init__": lines[0] = f"- `__init__` (line {fn.lineno}) sets up a new {owner} object when it's created."
    elif fn.name.startswith("__") and fn.name.endswith("__"):
        lines[0] = f"- `{fn.name}` (line {fn.lineno}) is a special method Python calls automatically."
    doc = ast.get_docstring(fn)
    if doc: lines.append(f"  Its docstring says: \"{doc.strip().splitlines()[0]}\"")
    lines.append(f"  It takes {', '.join('`'+x+'`' for x in a) if a else 'no inputs'}.")
    if fn.decorator_list:
        lines.append("  It is decorated with " + ", ".join("`@" + ast.unparse(d) + "`" for d in fn.decorator_list) + ".")
    loops = sum(isinstance(n, (ast.For, ast.While, ast.AsyncFor)) for n in ast.walk(fn))
    ifs = sum(isinstance(n, ast.If) for n in ast.walk(fn))
    if loops: lines.append(f"  It uses {loops} loop(s) to repeat work.")
    if ifs: lines.append(f"  It makes {ifs} decision(s) with if statements.")
    calls = [c for c in _calls(fn)][:8]
    if calls: lines.append("  It calls " + ", ".join(f"`{c}`" for c in calls) + ".")
    rets = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None]
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn)):
        lines.append("  It yields values one at a time (it's a generator).")
    elif rets:
        lines.append(f"  It returns a result, for example `{ast.unparse(rets[0].value)[:60]}`.")
    else:
        lines.append("  It doesn't return a value; it does its work by side effects like printing or changing data.")
    return lines

def features(tree):
    found = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)): found.add("comprehension")
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.decorator_list: found.add("decorator")
        elif isinstance(n, (ast.With, ast.AsyncWith)): found.add("with")
        elif isinstance(n, ast.Try): found.add("try")
        elif isinstance(n, ast.Lambda): found.add("lambda")
        elif isinstance(n, ast.JoinedStr): found.add("fstring")
        elif isinstance(n, (ast.AsyncFunctionDef, ast.Await)): found.add("async")
        elif isinstance(n, (ast.Yield, ast.YieldFrom)): found.add("yield")
        elif isinstance(n, ast.ClassDef): found.add("class")
        elif isinstance(n, (ast.Global, ast.Nonlocal)): found.add("global")
        if isinstance(n, ast.AsyncFunctionDef): found.add("async")
    return [k for k in NOTES if k in found]

def explain(src):
    tree = ast.parse(src)
    out = ["# Code walkthrough"]
    doc = ast.get_docstring(tree)
    if doc: out.append(f"The script describes itself as: \"{doc.strip().splitlines()[0]}\"")
    imps = []
    for n in tree.body:
        if isinstance(n, ast.Import): imps += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom): imps.append(n.module or ".")
    if imps: out.append("It imports: " + ", ".join(f"`{i}`" for i in imps) + ".")
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in n.bases)
            out.append(f"\n## Class `{n.name}` (line {n.lineno})")
            out.append(f"A blueprint for {_words(n.name)} objects" + (f", built on `{bases}`." if bases else "."))
            d = ast.get_docstring(n)
            if d: out.append(f"Docstring: \"{d.strip().splitlines()[0]}\"")
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out += _describe_func(m, n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(f"\n## Function `{n.name}`")
            out += _describe_func(n)
    top = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Expr)) or (isinstance(n, ast.Expr) and not isinstance(getattr(n, "value", None), ast.Constant))]
    if top:
        out.append("\n## Top-level code")
        out.append(f"{len(top)} statement(s) run directly when the script starts, for example line {top[0].lineno}: `{ast.unparse(top[0]).splitlines()[0][:70]}`.")
    f = features(tree)
    if f:
        out.append("\n## Python features used")
        out += [f"- {NOTES[k]}" for k in f]
    return "\n".join(out)

def safe_path(p):
    path = os.path.realpath(os.path.join(BASE, p.strip()))
    if not (path == BASE or path.startswith(BASE + os.sep)):
        raise ValueError("Files must be inside /home/pyodide.")
    return path

SAMPLE = '''"""Tiny inventory demo."""
import json

class InventoryItem:
    """One product on the shelf."""
    def __init__(self, name, qty):
        self.name, self.qty = name, qty
    def __repr__(self):
        return f"InventoryItem({self.name!r}, {self.qty})"

@staticmethod
def load_items(path):
    try:
        with open(path) as f:
            return [InventoryItem(**d) for d in json.load(f)]
    except OSError:
        return []

def count_low(items, limit=5):
    n = 0
    for it in items:
        if it.qty < limit:
            n += 1
    return n

def gen():
    yield 1

print(count_low([]))
'''

def self_test():
    r = explain(SAMPLE)
    for must in ("Class `InventoryItem`", "sets up a new InventoryItem", "special method", "count low", "1 loop", "returns a result",
                 "comprehension", "decorator", "'with' block", "try/except", "f-string", "generator", "Top-level code", "`json`", "Tiny inventory demo"):
        assert must in r, must
    assert explain("") == "# Code walkthrough"
    try: safe_path("../../etc/passwd"); raise AssertionError("escape")
    except ValueError: pass
    try: explain("def (:"); raise AssertionError("syntax")
    except SyntaxError: pass
    print("Self-tests passed.")

_KP_EXPL_MAX = 500_000
def _kp_read(path):
    if os.path.getsize(path) > _KP_EXPL_MAX:
        raise ValueError("File over 500KB.")
    return open(path, encoding="utf-8", errors="replace")

def main():
    print("Offline Code Explainer")
    while True:
        c = input("\n1) Explain a file  2) Paste code  3) Demo  t) Self-test  q) Quit: ").strip().lower()
        try:
            if c == "1":
                with _kp_read(safe_path(input("File (inside /home/pyodide): "))) as f: src = f.read()
            elif c == "2":
                print("Paste code, then a line with only END:")
                lines = []
                while True:
                    l = input()
                    if l.strip() == "END": break
                    lines.append(l)
                    if len(lines) > 10000: raise ValueError("Paste too long (max 10,000 lines).")
                src = "\n".join(lines)
            elif c == "3": src = SAMPLE
            elif c == "t": self_test(); continue
            elif c == "q": break
            else: continue
            print(explain(src))
        except SyntaxError as e:
            print(f"Syntax error on line {e.lineno}: {e.msg}")
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
