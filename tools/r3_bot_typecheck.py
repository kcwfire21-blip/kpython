# Type-hint checker: flags missing annotations and obvious literal type mismatches in calls, returns and annotated assignments (ast-based, stdlib only).
import ast, sys

LIT = {int: "int", float: "float", str: "str", bool: "bool", bytes: "bytes", type(None): "None"}
COMPAT = {"float": {"float", "int"}, "complex": {"complex", "float", "int"}, "int": {"int", "bool"},
          "object": None, "Any": None}

def lit_type(node):
    if isinstance(node, ast.Constant): return LIT.get(type(node.value))
    if isinstance(node, (ast.List, ast.ListComp)): return "list"
    if isinstance(node, (ast.Dict, ast.DictComp)): return "dict"
    if isinstance(node, (ast.Set, ast.SetComp)): return "set"
    if isinstance(node, ast.Tuple): return "tuple"
    if isinstance(node, ast.JoinedStr): return "str"
    return None

def ann_names(ann):
    """Set of accepted simple type names, or None if unknown/too complex."""
    if ann is None: return None
    if isinstance(ann, ast.Constant):
        if ann.value is None: return {"None"}
        if isinstance(ann.value, str):
            try: return ann_names(ast.parse(ann.value, mode="eval").body)
            except SyntaxError: return None
    if isinstance(ann, ast.Name):
        n = {"List": "list", "Dict": "dict", "Set": "set", "Tuple": "tuple"}.get(ann.id, ann.id)
        if n in COMPAT and COMPAT[n] is None: return None
        return set(COMPAT.get(n, {n}))
    if isinstance(ann, ast.Attribute): return ann_names(ast.Name(ann.attr))
    if isinstance(ann, ast.Subscript):
        base = ann.value.id if isinstance(ann.value, ast.Name) else getattr(ann.value, "attr", "")
        if base == "Optional": s = ann_names(ann.slice); return None if s is None else s | {"None"}
        if base == "Union":
            out = set()
            for e in (ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]):
                s = ann_names(e)
                if s is None: return None
                out |= s
            return out
        return ann_names(ann.value)
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        a, b = ann_names(ann.left), ann_names(ann.right)
        return None if a is None or b is None else a | b
    return None

class Checker(ast.NodeVisitor):
    def __init__(self): self.issues = []; self.funcs = {}; self.stack = []
    def add(self, node, msg): self.issues.append((getattr(node, "lineno", 0), msg))

    def collect(self, tree):
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): self.funcs.setdefault(n.name, n)

    def visit_FunctionDef(self, f):
        args = f.args.posonlyargs + f.args.args + f.args.kwonlyargs
        for i, a in enumerate(args):
            if i == 0 and a.arg in ("self", "cls"): continue
            if a.annotation is None: self.add(a, f"{f.name}(): parameter '{a.arg}' has no type hint")
        if f.returns is None and f.name != "__init__": self.add(f, f"{f.name}(): missing return type hint")
        # defaults vs annotations
        pos = f.args.posonlyargs + f.args.args
        for a, d in zip(pos[len(pos) - len(f.args.defaults):], f.args.defaults): self._match(d, a.annotation, f"{f.name}(): default for '{a.arg}'")
        for a, d in zip(f.args.kwonlyargs, f.args.kw_defaults):
            if d is not None: self._match(d, a.annotation, f"{f.name}(): default for '{a.arg}'")
        self.stack.append(f); self.generic_visit(f); self.stack.pop()
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Return(self, r):
        if self.stack and r.value is not None: self._match(r.value, self.stack[-1].returns, f"{self.stack[-1].name}(): return value")
        self.generic_visit(r)

    def visit_AnnAssign(self, a):
        if a.value is not None: self._match(a.value, a.annotation, f"variable '{ast.unparse(a.target)}'")
        self.generic_visit(a)

    def visit_Call(self, c):
        name = c.func.id if isinstance(c.func, ast.Name) else (c.func.attr if isinstance(c.func, ast.Attribute) else None)
        f = self.funcs.get(name)
        if f:
            params = f.args.posonlyargs + f.args.args
            if isinstance(c.func, ast.Attribute) and params and params[0].arg in ("self", "cls"): params = params[1:]
            for a, v in zip(params, c.args): self._match(v, a.annotation, f"call {name}(): argument '{a.arg}'")
            byname = {a.arg: a for a in params + f.args.kwonlyargs}
            for kw in c.keywords:
                if kw.arg in byname: self._match(kw.value, byname[kw.arg].annotation, f"call {name}(): argument '{kw.arg}'")
        self.generic_visit(c)

    def _match(self, value, ann, where):
        got, want = lit_type(value), ann_names(ann)
        if got and want is not None and got not in want:
            self.add(value, f"{where} is {got}, but hint says {ast.unparse(ann)}")

def check(src, filename="<code>"):
    try: tree = ast.parse(src, filename)
    except SyntaxError as e: return [(e.lineno or 0, f"SyntaxError: {e.msg}")]
    c = Checker(); c.collect(tree); c.visit(tree)
    return sorted(c.issues)

def report(src):
    issues = check(src)
    if not issues: print("✅ No type-hint problems found."); return
    for ln, m in issues: print(f"line {ln}: {m}")
    print(f"\n{len(issues)} issue(s).")

def _self_test():
    src = '''
def add(a: int, b: int) -> int:
    return a + b
def greet(name, times: int = "3"):
    return "hi"
def ok(x: float, y: "Optional[str]" = None) -> float:
    return 1
def bad() -> int:
    return "nope"
class K:
    def m(self, n: int) -> None: ...
add("1", 2)
add(1, b="2")
ok(2)
ok(1.5, y=3)
K().m("x")
age: int = "ten"
v: int | None = None
'''
    msgs = [m for _, m in check(src)]
    expect = ["parameter 'name' has no type hint", "greet(): missing return type hint", "default for 'times' is str",
              "bad(): return value is str", "call add(): argument 'a' is str", "argument 'b' is str",
              "argument 'y' is int", "call m(): argument 'n' is str", "variable 'age' is str"]
    for e in expect: assert any(e in m for m in msgs), f"missing: {e}\n{msgs}"
    assert not any("ok(): return" in m or "call ok(): argument 'x'" in m or "'v'" in m for m in msgs), msgs
    assert check("def f(:") [0][1].startswith("SyntaxError")
    print(f"self-tests passed ({len(expect)} checks)")

def main():
    print("=== Type-Hint Checker ===")
    while True:
        c = input("\n1 check pasted code  2 check a file  3 self-test  q quit: ").strip()
        if c == "q": break
        if c == "1":
            print("Paste code, end with a single '.' line"); lines = []
            try:
                while (l := input()) != ".":
                    lines.append(l)
                    if sum(map(len, lines)) > 500_000: print("Too big (max 500 KB)."); lines = []; break
            except EOFError: pass
            report("\n".join(lines))
        elif c == "2":
            p = input("File path: ").strip()
            try: (_ for _ in ()).throw(ValueError("file too big (max 500 KB)")) if __import__("os").path.getsize(__import__("builtins").kp_safe_path(p)) > 500_000 else None; report(open(__import__("builtins").kp_safe_path(p) if hasattr(__import__("builtins"), "kp_safe_path") else p).read())  # KPython: /home/pyodide only
            except OSError as e: print("Error:", e)
        elif c == "3": _self_test()

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
    if "--test" in sys.argv: _self_test()
    else: main()
