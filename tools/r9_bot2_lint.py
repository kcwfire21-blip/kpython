# bot2: Quick Lint - stdlib checker for unused imports/variables, shadowed builtins, mutable defaults, bare except, == None, and unreachable code (file:line output).
import ast, builtins, os, sys

BASE = "/home/pyodide"
BUILTINS = set(dir(builtins)) - {"__doc__", "__name__", "__spec__", "__loader__", "__package__", "_"}

def _names_loaded(tree):
    used = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Load, ast.Del)):
            used.add(n.id)
        elif isinstance(n, ast.Attribute):
            base = n
            while isinstance(base, ast.Attribute): base = base.value
            if isinstance(base, ast.Name): used.add(base.id)
    for n in ast.walk(tree):  # names listed in __all__ count as used
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets):
            try: used |= set(ast.literal_eval(n.value))
            except Exception: pass
    return used

def lint(src, filename="<code>"):
    tree = ast.parse(src, filename)
    out = []
    add = lambda node, code, msg: out.append((node.lineno, code, msg))
    used = _names_loaded(tree)

    # unused imports (module level and inside functions)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            if isinstance(n, ast.ImportFrom) and n.module == "__future__": continue
            for a in n.names:
                if a.name == "*": continue
                name = a.asname or a.name.split(".")[0]
                if name not in used: add(n, "W001", f"unused import '{name}'")

    for n in ast.walk(tree):
        # function-level checks
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d is not None]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (isinstance(d, ast.Call) and getattr(d.func, "id", "") in ("list", "dict", "set")):
                    add(d, "W003", "mutable default argument; use None and create it inside")
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.name in BUILTINS: add(n, "W002", f"function '{n.name}' shadows a builtin")
            for a in n.args.posonlyargs + n.args.args + n.args.kwonlyargs:
                if a.arg in BUILTINS: add(n, "W002", f"argument '{a.arg}' shadows a builtin")
            assigned, loaded, decl = {}, set(), set()
            for c in ast.walk(n):
                if isinstance(c, (ast.Global, ast.Nonlocal)): decl |= set(c.names)
                if isinstance(c, ast.Name):
                    if isinstance(c.ctx, ast.Store): assigned.setdefault(c.id, c)
                    else: loaded.add(c.id)
            for name, node in assigned.items():
                if name not in loaded and name not in decl and not name.startswith("_"):
                    add(node, "W004", f"local variable '{name}' is assigned but never used")
        if isinstance(n, ast.ClassDef) and n.name in BUILTINS:
            add(n, "W002", f"class '{n.name}' shadows a builtin")
        # module-level assignments shadowing builtins
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.For, ast.With)):
            targets = n.targets if isinstance(n, ast.Assign) else [getattr(n, "target", None)] if not isinstance(n, ast.With) else [i.optional_vars for i in n.items]
            for t in targets:
                for x in ast.walk(t) if t is not None else []:
                    if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store) and x.id in BUILTINS:
                        add(x, "W002", f"variable '{x.id}' shadows a builtin")
        if isinstance(n, ast.ExceptHandler) and n.type is None:
            add(n, "W005", "bare 'except:' also catches KeyboardInterrupt; use 'except Exception:'")
        if isinstance(n, ast.Compare):
            for op, right in zip(n.ops, n.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant) and right.value is None:
                    add(n, "W006", f"use '{'is' if isinstance(op, ast.Eq) else 'is not'} None' instead of '{'==' if isinstance(op, ast.Eq) else '!='} None'")
        # unreachable code after return/raise/break/continue in any block
        for field in ("body", "orelse", "finalbody"):
            block = getattr(n, field, None)
            if isinstance(block, list):
                for i, stmt in enumerate(block[:-1]):
                    if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                        add(block[i + 1], "W007", f"unreachable code after '{type(stmt).__name__.lower()}'")
                        break
    seen, res = set(), []
    for item in sorted(out):
        if item not in seen: seen.add(item); res.append(item)
    return [f"{filename}:{ln}: {code} {msg}" for ln, code, msg in res]

MAX_SRC = 500_000
def safe_path(p):
    """KPython: the app's shared rule when present (refuses .., outside paths and symlinks)."""
    p = str(p or "").strip()
    if not p: raise ValueError("no file name given")
    guard = getattr(builtins, "kp_safe_path", None)
    if guard is not None and BASE == "/home/pyodide":
        path = guard(p)
    else:
        path = os.path.realpath(os.path.join(BASE, p))
        if not (path == BASE or path.startswith(BASE + os.sep)):
            raise ValueError("Files must be inside /home/pyodide.")
    if os.path.isfile(path) and os.path.getsize(path) > MAX_SRC:
        raise ValueError(f"file is over {MAX_SRC // 1000} KB")
    return path

SAMPLE = '''import os, json
import sys as system

def list(items=[], opts={}):
    total = 0
    unused_thing = 5
    try:
        x = items[0]
    except:
        pass
    if x == None:
        return total
        print("never")
    return x

id = 3
'''

def self_test():
    r = "\n".join(lint(SAMPLE, "s.py"))
    for must in ("s.py:1: W001 unused import 'os'", "unused import 'json'", "unused import 'system'",
                 "s.py:4: W002 function 'list' shadows", "W003 mutable default", "W004 local variable 'unused_thing'",
                 "W005 bare", "W006 use 'is None'", "s.py:13: W007 unreachable", "variable 'id' shadows"):
        assert must in r, (must, r)
    assert "'total'" not in r and "'x' is assigned" not in r
    clean = "import os\n\ndef f(a=None):\n    if a is None:\n        a = []\n    return os.sep, a\n"
    assert lint(clean) == [], lint(clean)
    try: safe_path("../../etc/passwd"); raise AssertionError
    except ValueError: pass
    print("Self-tests passed.")

def main():
    print("Quick Lint")
    while True:
        c = input("\n1) Lint a file  2) Paste code  3) Demo  t) Self-test  q) Quit: ").strip().lower()
        try:
            if c == "1":
                name = input("File (inside /home/pyodide): ")
                path = safe_path(name)
                with open(path, encoding="utf-8", errors="replace") as f: src = f.read(MAX_SRC)
                fname = os.path.basename(path)
            elif c == "2":
                print("Paste code, then a line with only END:")
                lines = []
                while True:
                    l = input()
                    if l.strip() == "END": break
                    lines.append(l)
                    if sum(map(len, lines)) > MAX_SRC: print("(stopped: paste is over 500 KB)"); break
                src, fname = "\n".join(lines), "<pasted>"
            elif c == "3": src, fname = SAMPLE, "demo.py"
            elif c == "t": self_test(); continue
            elif c in ("q", "quit", ""): break
            else: print("Pick 1, 2, 3, t or q."); continue
            res = lint(src, fname)
            print("\n".join(res) if res else "No problems found.")
            print(f"{len(res)} issue(s).")
        except SyntaxError as e:
            print(f"{e.filename}:{e.lineno}: E999 syntax error: {e.msg}")
        except (ValueError, OSError) as e:
            print("Error:", e)


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
