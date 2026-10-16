# Docstring generator: adds Google-style docstring stubs (Args/Returns/Raises) from signatures and type hints, shows a diff, and asks before saving (ast-based, stdlib only).
import ast, difflib, os, sys

SAFE_ROOT = "/home/pyodide"

def _ann(a): return ast.unparse(a) if a is not None else None

def _raises(fn):
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Raise) and n.exc is not None:
            e = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            name = ast.unparse(e)
            if name not in out: out.append(name)
    return out

def _returns_value(fn):
    return any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(fn)) or \
           any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn))

def build_doc(fn, indent):
    a = fn.args
    params = []
    for p in a.posonlyargs + a.args:
        params.append(p)
    if params and params[0].arg in ("self", "cls"): params = params[1:]
    if a.vararg: params.append(ast.arg(arg="*" + a.vararg.arg, annotation=a.vararg.annotation))
    params += a.kwonlyargs
    if a.kwarg: params.append(ast.arg(arg="**" + a.kwarg.arg, annotation=a.kwarg.annotation))
    pad = " " * indent
    lines = [f'{pad}"""TODO: describe {fn.name}.', ""]
    if params:
        lines.append(f"{pad}Args:")
        for p in params:
            t = _ann(p.annotation)
            lines.append(f"{pad}    {p.arg}{f' ({t})' if t else ''}: TODO.")
        lines.append("")
    ret = _ann(fn.returns)
    is_gen = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn))
    if (ret and ret != "None") or (ret is None and _returns_value(fn)):
        lines += [f"{pad}{'Yields' if is_gen else 'Returns'}:", f"{pad}    {ret + ': ' if ret else ''}TODO.", ""]
    rs = _raises(fn)
    if rs:
        lines.append(f"{pad}Raises:")
        lines += [f"{pad}    {r}: TODO." for r in rs]
        lines.append("")
    if lines[-1] == "": lines.pop()
    if len(lines) == 1: lines[0] += '"""'
    else: lines.append(f'{pad}"""')
    return lines

def generate(src):
    tree = ast.parse(src)
    src_lines = src.splitlines()
    inserts = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ast.get_docstring(n) is None:
            first = n.body[0]
            if first.lineno == n.body[0].end_lineno and first.lineno == n.lineno:  # one-liner: def f(): pass
                continue
            indent = first.col_offset
            if isinstance(n, ast.ClassDef):
                doc = [" " * indent + f'"""TODO: describe {n.name}."""']
            else:
                doc = build_doc(n, indent)
            start = min([first.lineno] + [d.lineno for d in getattr(first, "decorator_list", [])])
            inserts.append((start - 1, doc))
    out = list(src_lines)
    for at, doc in sorted(inserts, reverse=True): out[at:at] = doc
    return "\n".join(out) + ("\n" if src.endswith("\n") else ""), len(inserts)

def diff(old, new, name="file"):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{name}", f"b/{name}"))

def _safe(path):
    p = os.path.realpath(os.path.expanduser(path))
    if not (p == SAFE_ROOT or p.startswith(SAFE_ROOT + os.sep)): raise PermissionError(f"Only files under {SAFE_ROOT} are allowed.")
    return p

def run_file(path):
    p = _safe(path)
    src = open(p).read()
    new, n = generate(src)
    if not n: print("Every function and class already has a docstring."); return
    print(diff(src, new, os.path.basename(p)))
    print(f"{n} docstring stub(s) to add.")
    if input("Apply and save? (y/n): ").strip().lower() == "y":
        open(p, "w").write(new); print("Saved", p)
    else: print("Not changed.")

def _self_test():
    src = '''import os

class Box:
    def put(self, item: str, *, qty: int = 1) -> bool:
        if qty < 0:
            raise ValueError("neg")
        return True

    def done(self):
        """Already documented."""
        return None

def gen(n):
    yield n

async def fetch(url: str, *args, **kw) -> None:
    pass

@staticmethod
def one(): pass
'''
    new, n = generate(src)
    ast.parse(new)  # must stay valid
    assert n == 4, n
    for s in ["TODO: describe Box.", "item (str): TODO.", "qty (int): TODO.", "Returns:\n            bool: TODO.",
              "Raises:\n            ValueError: TODO.", "Yields:", "*args: TODO.", "**kw: TODO.", "url (str): TODO."]:
        assert s in new, s
    assert "self" not in new.split("def put")[1].split('"""')[1], "self listed"
    assert new.count("Already documented.") == 1
    assert "Returns" not in new.split("async def fetch")[1]
    try: _safe("/etc/passwd"); raise AssertionError("path guard failed")
    except PermissionError: pass
    print("self-tests passed")

def main():
    print("=== Docstring Generator ===")
    while True:
        c = input("\n1 add docstrings to a file  2 preview pasted code  3 self-test  q quit: ").strip()
        try:
            if c == "q": break
            if c == "1": run_file(input(f"File path (under {SAFE_ROOT}): ").strip())
            elif c == "2":
                print("Paste code, end with a single '.' line"); ls = []
                while (l := input()) != ".": ls.append(l)
                src = "\n".join(ls) + "\n"; new, n = generate(src)
                print(diff(src, new, "pasted.py") or "Nothing to add.")
            elif c == "3": _self_test()
        except Exception as e: print("Error:", e)

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
    if "--test" in sys.argv: _self_test()
    else: main()
