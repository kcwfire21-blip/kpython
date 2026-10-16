# Refactor tool: extract lines into a function, inline a variable, convert %/.format() to f-strings (ast-based, diff + confirm, stdlib only).
import ast, difflib, os, re, string, sys

SAFE_ROOT = "/home/pyodide"
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

class RefactorError(Exception): pass

def diff(old, new, name="file"):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{name}", f"b/{name}"))

def _safe(path):
    p = os.path.realpath(os.path.join(SAFE_ROOT, path))  # KPython: relative to /home/pyodide, no ~ expansion
    if not (p == SAFE_ROOT or p.startswith(SAFE_ROOT + os.sep)): raise PermissionError(f"Only files under {SAFE_ROOT} are allowed.")
    return p

def _check(new):
    try: ast.parse(new)
    except SyntaxError as e: raise RefactorError(f"result would not parse ({e}); nothing changed")
    return new

def _parents(tree):
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n): c._parent = n

def _walk_scope(node):
    """Yield nodes in node's own scope (do not enter nested functions/classes/lambdas/comprehensions)."""
    todo = list(ast.iter_child_nodes(node))
    while todo:
        n = todo.pop()
        yield n
        if not isinstance(n, SCOPES): todo.extend(ast.iter_child_nodes(n))

# ---------- 1. extract function ----------
def _stmt_lists(tree):
    for n in ast.walk(tree):
        for f in ("body", "orelse", "finalbody"):
            v = getattr(n, f, None)
            if isinstance(v, list) and v and isinstance(v[0], ast.stmt): yield n, v
        for h in getattr(n, "handlers", []) or []: yield h, h.body
        for c in getattr(n, "cases", []) or []: yield c, c.body

def extract(src, a, b, name):
    if not name.isidentifier(): raise RefactorError(f"{name!r} is not a valid function name")
    tree = ast.parse(src); _parents(tree)
    lines = src.splitlines()
    if not (1 <= a <= b <= len(lines)): raise RefactorError("line range out of file")
    for n in ast.walk(tree):
        if isinstance(n, ast.stmt):
            start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
            inside = start >= a and n.end_lineno <= b
            outside = n.end_lineno < a or start > b
            encloses = start < a and n.end_lineno >= b
            if not (inside or outside or (encloses and not isinstance(n, ast.expr) and hasattr(n, "body"))):
                raise RefactorError(f"range splits the statement at line {n.lineno}")
    sel = None
    for owner, body in _stmt_lists(tree):
        s = [x for x in body if x.lineno >= a and x.end_lineno <= b]
        if s and not (getattr(owner, "lineno", 0) >= a and getattr(owner, "end_lineno", 0) <= b):
            if sel is not None: raise RefactorError("range spans more than one block")
            sel = s
    if not sel: raise RefactorError("no complete statements in that range")
    for s in sel:
        for n in ast.walk(s):
            if isinstance(n, (ast.Return, ast.Yield, ast.YieldFrom, ast.Break, ast.Continue, ast.Global, ast.Nonlocal, ast.Await)):
                raise RefactorError(f"range contains {type(n).__name__.lower()} (line {n.lineno}); refusing")
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name for n in tree.body):
        raise RefactorError(f"{name} already exists")
    # enclosing scope and top-level statement
    scope, p = tree, sel[0]
    while hasattr(p, "_parent"):
        p = p._parent
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)): scope = p; break
        if isinstance(p, ast.ClassDef): raise RefactorError("extracting from a class body is not supported")
    top = sel[0]
    while getattr(top, "_parent", tree) is not tree: top = top._parent
    sel_ids = {id(n) for s in sel for n in ast.walk(s)}
    defined_before, loads_in, stores_in, loads_after = set(), [], [], set()
    if scope is not tree:
        a_ = scope.args
        for x in a_.posonlyargs + a_.args + a_.kwonlyargs + [a_.vararg, a_.kwarg]:
            if x: defined_before.add(x.arg)
    for n in _walk_scope(scope):
        nm = n.id if isinstance(n, ast.Name) else n.name if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else n.arg if isinstance(n, ast.arg) else None
        if nm is None: continue
        st = isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)) or not isinstance(n, ast.Name)
        if id(n) in sel_ids:
            (stores_in if st else loads_in).append((n.lineno, n.col_offset, nm))
        elif n.lineno < a and st: defined_before.add(nm)
        elif n.lineno > b and not st: loads_after.add(nm)
    for imp in ast.walk(scope):
        if isinstance(imp, (ast.Import, ast.ImportFrom)) and imp.lineno < a and id(imp) not in sel_ids:
            for al in imp.names: defined_before.add((al.asname or al.name).split(".")[0])
    # names imported/read from nested scopes inside range: include free names of nested scopes too
    for s in sel:
        for n in ast.walk(s):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and (n.lineno, n.col_offset, n.id) not in loads_in:
                loads_in.append((n.lineno, n.col_offset, n.id))
    params, outs = [], []
    for _, _, nm in sorted(loads_in):
        if nm in defined_before and nm not in params: params.append(nm)
    for _, _, nm in sorted(stores_in):
        if nm in loads_after and nm not in outs: outs.append(nm)
    first = min([sel[0].lineno] + [d.lineno for d in getattr(sel[0], "decorator_list", [])])
    last = sel[-1].end_lineno
    indent = sel[0].col_offset
    chunk = lines[first - 1:last]
    for l in chunk:
        if l.strip() and not l.startswith(" " * indent) : raise RefactorError("selected lines have uneven indentation (multi-line string?)")
    body = ["    " + l[indent:] if l.strip() else "" for l in chunk]
    if outs: body.append("    return " + ", ".join(outs))
    func = [f"def {name}({', '.join(params)}):"] + body + ["", ""]
    call = " " * indent + (", ".join(outs) + " = " if outs else "") + f"{name}({', '.join(params)})"
    out = lines[:first - 1] + [call] + lines[last:]
    tstart = min([top.lineno] + [d.lineno for d in getattr(top, "decorator_list", [])])
    if top in sel: tstart = first
    out[tstart - 1:tstart - 1] = func
    new = "\n".join(out) + ("\n" if src.endswith("\n") else "")
    return _check(new), f"extracted lines {first}-{last} into {name}({', '.join(params)})" + (f" returning {', '.join(outs)}" if outs else "")

# ---------- 2. inline variable ----------
SIMPLE = (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
          ast.Tuple, ast.List, ast.Load, ast.operator, ast.unaryop, ast.boolop, ast.cmpop, ast.Slice, ast.expr_context)
ATOMIC = (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.Tuple, ast.List)

def _offsets(src):
    starts, pos = [0, 0], 0
    for l in src.encode().splitlines(True): pos += len(l); starts.append(pos)
    return starts

def _replace(src, edits):
    """edits: list of ((line, col), (end_line, end_col), text) with ast byte columns."""
    b, st = src.encode(), _offsets(src)
    for (l1, c1), (l2, c2), t in sorted(edits, key=lambda e: (e[0][0], e[0][1]), reverse=True):
        b = b[:st[l1] + c1] + t.encode() + b[st[l2] + c2:]
    return b.decode()

def inline(src, name, line=None):
    tree = ast.parse(src); _parents(tree)
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, SCOPES)]
    owners = [s for s in scopes if any(isinstance(n, ast.Name) and n.id == name and not isinstance(n.ctx, ast.Load) for n in _walk_scope(s))]
    if line: owners = [s for s in owners if s is tree or s.lineno <= line <= s.end_lineno][-1:]
    if not owners: raise RefactorError(f"{name} is never assigned")
    if len(owners) > 1: raise RefactorError(f"{name} is assigned in {len(owners)} scopes; give the line of the assignment")
    sc = owners[0]
    assigns, uses = [], []
    for n in _walk_scope(sc):
        if isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names: raise RefactorError(f"{name} is declared global/nonlocal")
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == name: raise RefactorError(f"{name} is augmented (line {n.lineno})")
        if isinstance(n, ast.Name) and n.id == name:
            if isinstance(n.ctx, ast.Load): uses.append(n)
            else:
                p = n._parent
                if not (isinstance(p, ast.Assign) and len(p.targets) == 1 and p.targets[0] is n): raise RefactorError(f"{name} is bound in an unsupported way at line {n.lineno}")
                assigns.append(p)
    if isinstance(sc, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a_ = sc.args
        if name in [x.arg for x in a_.posonlyargs + a_.args + a_.kwonlyargs + [a_.vararg, a_.kwarg] if x]: raise RefactorError(f"{name} is a parameter")
    if len(assigns) != 1: raise RefactorError(f"{name} is assigned {len(assigns)} times; refusing")
    asg = assigns[0]
    for n in ast.walk(sc):  # uses in nested scopes
        if isinstance(n, ast.Name) and n.id == name and n not in uses and n is not asg.targets[0]:
            raise RefactorError(f"{name} is used in a different scope (line {n.lineno})")
    if not all(isinstance(n, SIMPLE) for n in ast.walk(asg.value)): raise RefactorError("value is not a simple expression (no calls, lambdas, etc.)")
    deps = {n.id for n in ast.walk(asg.value) if isinstance(n, ast.Name)}
    for n in _walk_scope(sc):
        if isinstance(n, ast.Name) and n.id in deps and not isinstance(n.ctx, ast.Load) and n.lineno > asg.lineno:
            raise RefactorError(f"{n.id} (used by the value) changes at line {n.lineno}")
    for u in uses:
        if (u.lineno, u.col_offset) < (asg.end_lineno, asg.end_col_offset): raise RefactorError(f"{name} is used before its assignment (line {u.lineno})")
        p = u
        while hasattr(p, "_parent"):
            p = p._parent
            if isinstance(p, ast.JoinedStr) and sys.version_info < (3, 12): raise RefactorError("use inside an f-string (needs Python 3.12+)")
            if isinstance(p, (ast.For, ast.While, ast.AsyncFor)) and p.lineno < asg.lineno <= p.end_lineno: pass
    lines = src.splitlines()
    seg = ast.get_source_segment(src, asg.value)
    text = seg if seg and "\n" not in seg else ast.unparse(asg.value)
    if not isinstance(asg.value, ATOMIC): text = f"({text})"
    for s in ast.walk(tree):
        if isinstance(s, ast.stmt) and s is not asg and not (s.lineno <= asg.lineno and s.end_lineno >= asg.end_lineno) and s.lineno <= asg.end_lineno and s.end_lineno >= asg.lineno:
            raise RefactorError("assignment shares a line with another statement")
    parent = asg._parent
    body = next(v for f in ("body", "orelse", "finalbody") if isinstance(v := getattr(parent, f, None), list) and asg in v)
    edits = [((u.lineno, u.col_offset), (u.end_lineno, u.end_col_offset), text) for u in uses]
    new = _replace(src, edits)
    out = new.splitlines()
    ind = " " * asg.col_offset
    out[asg.lineno - 1:asg.end_lineno] = [ind + "pass"] if len(body) == 1 else []
    new = "\n".join(out) + ("\n" if src.endswith("\n") else "")
    return _check(new), f"inlined {name} = {text} into {len(uses)} use(s)"

# ---------- 3. f-strings ----------
PCT = re.compile(r"%(?:(\.\d+)?([sdirf])|%)")
SAFE_DUP = (ast.Name, ast.Constant)

def _fstr(parts):
    vals = []
    for p in parts:
        if isinstance(p, str):
            if p: vals.append(ast.Constant(p))
        else:
            expr, conv, spec = p
            vals.append(ast.FormattedValue(expr, conv, ast.JoinedStr([ast.Constant(spec)]) if spec else None))
    return ast.unparse(ast.JoinedStr(vals))

def _conv_pct(node):
    fmt = node.left.value
    if isinstance(node.right, ast.Tuple): args = node.right.elts
    elif isinstance(node.right, (ast.Dict, ast.Starred)): return None, "dict/starred argument"
    else: args = [node.right]
    if any(isinstance(x, ast.Starred) for x in args): return None, "starred argument"
    parts, pos, i = [], 0, 0
    for m in PCT.finditer(fmt):
        parts.append(fmt[pos:m.start()]); pos = m.end()
        if m.group(0) == "%%": parts.append("%"); continue
        prec, kind = m.group(1), m.group(2)
        if i >= len(args): return None, "too few arguments"
        if prec and kind != "f": return None, f"precision on %{kind}"
        conv, spec = -1, ""
        if kind == "r": conv = 114
        elif kind in "di": args[i] = ast.Call(ast.Name("int", ast.Load()), [args[i]], [])  # KPython: {x:d} raises on floats; %d truncates like int()
        elif kind == "f": spec = (prec or ".6") + "f"
        parts.append((args[i], conv, spec)); i += 1
    parts.append(fmt[pos:])
    rest = "".join(p for p in parts if isinstance(p, str))
    if "%" in PCT.sub("", fmt): return None, "complex % spec"
    if i != len(args): return None, "argument count mismatch"
    return parts, None

def _conv_format(node):
    fmt = node.func.value.value
    if any(isinstance(x, ast.Starred) for x in node.args) or any(k.arg is None for k in node.keywords): return None, "*args/**kwargs"
    kw = {k.arg: k.value for k in node.keywords}
    try: pieces = list(string.Formatter().parse(fmt))
    except ValueError as e: return None, f"bad format string ({e})"
    parts, auto, used = [], 0, {}
    for lit, field, spec, conv in pieces:
        if lit: parts.append(lit)
        if field is None: continue
        if spec and "{" in spec: return None, "nested format spec"
        if field == "": key = auto; auto += 1
        elif field.isdigit(): key = int(field)
        elif field.isidentifier(): key = field
        else: return None, "attribute/index field"
        if isinstance(key, int):
            if key >= len(node.args): return None, "missing positional argument"
            expr = node.args[key]
        else:
            if key not in kw: return None, f"missing keyword {key}"
            expr = kw[key]
        used[key] = used.get(key, 0) + 1
        if used[key] > 1 and not isinstance(expr, SAFE_DUP): return None, "argument used twice"
        parts.append((expr, {"r": 114, "s": 115, "a": 97}.get(conv, -1), spec or ""))
    if set(used) != set(range(len(node.args))) | set(kw): return None, "unused arguments"
    return parts, None

def to_fstrings(src):
    total, skipped = 0, {}
    for _ in range(20):
        tree = ast.parse(src); _parents(tree)
        edits, taken, cands = [], [], []
        for n in ast.walk(tree):
            parts = why = None
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) and isinstance(n.left.value, str):
                parts, why = _conv_pct(n)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format" and isinstance(n.func.value, ast.Constant) and isinstance(n.func.value.value, str):
                parts, why = _conv_format(n)
            else: continue
            p, inf = n, False
            while hasattr(p, "_parent"):
                p = p._parent
                if isinstance(p, ast.JoinedStr): inf = True
            if inf: why, parts = "inside an f-string", None
            if parts is None: skipped[(n.lineno, ast.get_source_segment(src, n) or "")] = why; continue
            cands.append((n, parts))
        st = _offsets(src)
        cands.sort(key=lambda c: (st[c[0].end_lineno] + c[0].end_col_offset) - (st[c[0].lineno] + c[0].col_offset))
        for n, parts in cands:  # innermost first, so nested ones convert cleanly
            span = ((n.lineno, n.col_offset), (n.end_lineno, n.end_col_offset))
            if any(s[0] <= span[0] and span[1] <= s[1] or span[0] <= s[0] and s[1] <= span[1] for s in taken): continue
            try:
                text = _fstr(parts); ast.parse(text, mode="eval")
            except Exception as e:
                skipped[(n.lineno, ast.get_source_segment(src, n) or "")] = f"could not build f-string ({e})"; continue
            taken.append(span); edits.append((span[0], span[1], text))
        if not edits: break
        src = _check(_replace(src, edits)); total += len(edits)
    return src, total, [f"line {l}: {s[:60]}  -- {w}" for (l, s), w in sorted(skipped.items())]

# ---------- UI ----------
def _apply(src, new, msg, path=None, name="pasted.py"):
    d = diff(src, new, name)
    if not d: print("No changes."); return
    print(d); print(msg)
    if path is None: return
    if input("Apply and save? (y/n): ").strip().lower() == "y":
        try:  # KPython: keep the old version in History first
            import r3_drop_history as _h, contextlib, io
            with contextlib.redirect_stdout(io.StringIO()): _h.save_version(os.path.relpath(path, SAFE_ROOT), "auto-save before refactor")
            note = " (old version saved in History)"
        except Exception:
            note = ""
        with open(path, "w", encoding="utf-8") as f: f.write(new)
        print("Saved", path + note)
    else: print("Not changed.")

def _run(kind, src, path=None, name="pasted.py"):
    if kind == "1":
        a, b = input("Lines A-B (e.g. 5-9): ").replace(" ", "").split("-")
        new, msg = extract(src, a, b, input("New function name: ").strip())
    elif kind == "2":
        nm = input("Variable name: ").strip(); ln = input("Line of assignment (Enter to skip): ").strip()
        new, msg = inline(src, nm, int(ln) if ln else None)
    else:
        new, n, sk = to_fstrings(src)
        msg = f"{n} call(s) converted." + ("".join("\nskipped " + s for s in sk) if sk else "")
    _apply(src, new, msg, path, name)

def _self_test():
    s1 = '''import math

def area(r, scale):
    k = 2
    sq = r * r
    big = sq * math.pi * scale
    print("area", big)
    return big * k

def loop():
    for i in range(3):
        if i:
            break
'''
    new, msg = extract(s1, 5, 6, "calc")
    ast.parse(new)
    assert "def calc(r, scale):" in new and "    return big" in new, new
    assert "    big = calc(r, scale)" in new and new.index("def calc") < new.index("def area"), new
    ns = {}; exec(new, ns); assert abs(ns["area"](1, 1) - 2 * 3.141592653589793) < 1e-9
    new, _ = extract(s1, 7, 7, "show")
    assert "    show(big)" in new and "def show(big):" in new and "return" not in new.split("def show")[1].split("def area")[0]
    for a, b in [(3, 5), (12, 13), (8, 8), (11, 11)]:
        try: extract(s1, a, b, "bad"); raise AssertionError(f"should refuse {a}-{b}")
        except RefactorError: pass
    new, _ = extract("x = 1\ny = x + 1\nprint(y)\n", 2, 2, "mk")
    assert new.startswith("x = 1\ndef mk(x):") and "y = mk(x)" in new; ast.parse(new)

    s2 = "def f(a):\n    t = a + 1\n    return t * t\n\ndef g():\n    u = 3\n    u += 1\n    return u\n\ndef h():\n    w = 5\n    return lambda: w\n"
    new, _ = inline(s2, "t")
    assert "return (a + 1) * (a + 1)" in new and "t =" not in new; ast.parse(new)
    for nm in ("u", "w"):
        try: inline(s2, nm); raise AssertionError("should refuse " + nm)
        except RefactorError: pass
    try: inline("x = 1\nx = 2\nprint(x)\n", "x"); raise AssertionError("reassigned")
    except RefactorError: pass
    try: inline("x = f()\nprint(x)\n", "x"); raise AssertionError("call")
    except RefactorError: pass
    new, _ = inline("if 1:\n    z = 4\nprint(z)\n", "z"); assert "pass" in new and "print(4)" in new; ast.parse(new)

    s3 = '''a = "Hi %s, you are %d" % (name, age)
b = "%r!" % name
c = "pi=%.2f %%" % pi
d = "{} and {}".format(x, y)
e = "{0}-{1}-{0}".format(p, q)
f = "{n!r}: {v:>8}".format(n=key, v=val)
g = "{a.b}".format(a=o)
h = "%5s" % w
i = "{{lit}} {}".format(z)
j = "%s" % (t,)
k = "%s %s" % pair
'''
    new, n, sk = to_fstrings(s3)
    ast.parse(new)
    for s in ["a = f'Hi {name}, you are {int(age)}'", "b = f'{name!r}!'", "c = f'pi={pi:.2f} %'", "d = f'{x} and {y}'",
              "e = f'{p}-{q}-{p}'", "f = f'{key!r}: {val:>8}'", "i = f'{{lit}} {z}'", "j = f'{t}'"]:
        assert s in new, (s, new)
    assert 'g = "{a.b}".format(a=o)' in new and 'h = "%5s" % w' in new and 'k = "%s %s" % pair' in new
    assert n == 8 and len(sk) == 3, (n, sk)
    x, y, p, q, key, val, z, t, name, age, pi = 1, 2, "P", "Q", "k", 3, 9, 7, "Bo", 30, 3.14159
    for ln in s3.splitlines():
        if ln[0] in "abcdefij": assert eval(ln.split(" = ", 1)[1]) == eval(next(l for l in new.splitlines() if l.startswith(ln[0] + " =")).split(" = ", 1)[1]), ln
    v = 5; new, n, _ = to_fstrings('r = "<{}>".format("%s" % v)\n'); ns = {"v": v}; exec(new, ns)
    assert n == 2 and ns["r"] == "<5>" and "format" not in new and "%" not in new, new
    try: _safe("/etc/passwd"); raise AssertionError("path guard failed")
    except PermissionError: pass
    try: _safe("/home/pyodide/../../etc/x"); raise AssertionError("path guard failed")
    except PermissionError: pass
    print("self-tests passed")

def main():
    print("=== Refactor Tool ===")
    while True:
        c = input("\n1 extract lines to function  2 inline variable  3 convert to f-strings\n"
                  "4 preview on pasted code  5 self-test  q quit: ").strip()
        try:
            if c == "q": break
            if c in ("1", "2", "3"):
                p = _safe(input(f"File path (under {SAFE_ROOT}): ").strip())
                if os.path.getsize(p) > 500_000: raise ValueError("File over 500KB.")
                _run(c, open(p, encoding="utf-8").read(), p, os.path.basename(p))
            elif c == "4":
                k = input("Which refactor (1/2/3): ").strip()
                print("Paste code, end with a single '.' line"); ls = []
                while (l := input()) != ".": ls.append(l)
                _run(k, "\n".join(ls) + "\n")
            elif c == "5": _self_test()
        except Exception as e: print("Error:", e)

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
    if "--test" in sys.argv: _self_test()
    else: main()
