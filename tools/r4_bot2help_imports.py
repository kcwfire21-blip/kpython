# Import/dependency mapper: ast-based local import graph, cycles, unused imports, missing modules, text tree + Mermaid (stdlib only, paths under /home/pyodide).
import ast, os, re, sys, tempfile, importlib.util

BASE_DIR = "/home/pyodide"


def safe_path(path, base=None):
    """Resolve path (following symlinks) and refuse anything outside base."""
    base = os.path.realpath(base or BASE_DIR)
    if not path:
        path = base
    if not os.path.isabs(path):
        path = os.path.join(base, path)
    real = os.path.realpath(path)
    if real != base and not real.startswith(base + os.sep):
        raise PermissionError("Path outside allowed base: %s" % path)
    return real


def find_py_files(root, base=None):
    root = safe_path(root, base)
    out = []
    for dp, dns, fns in os.walk(root, followlinks=False):
        dns[:] = sorted(d for d in dns if not d.startswith(".") and d != "__pycache__")
        for fn in sorted(fns):
            if fn.endswith(".py"):
                full = os.path.join(dp, fn)
                try:
                    safe_path(full, base)
                except PermissionError:
                    continue  # symlink escape
                out.append(full)
    return out


def module_name_for(path, root):
    rel = os.path.relpath(path, root)[:-3]
    parts = rel.split(os.sep)
    is_pkg = parts[-1] == "__init__"
    if is_pkg:
        parts = parts[:-1]
    return ".".join(parts) if parts else "__init__", is_pkg


def resolve_relative(cur_mod, is_pkg, level, module):
    parts = cur_mod.split(".") if cur_mod else []
    if not is_pkg:
        parts = parts[:-1]
    if level > 1:
        if level - 1 > len(parts):
            return None
        parts = parts[:len(parts) - (level - 1)]
    if module:
        parts = parts + module.split(".")
    return ".".join(parts) if parts else None


class _Usage(ast.NodeVisitor):
    def __init__(self):
        self.names = set()
        self.all_names = set()

    def visit_Name(self, n):
        self.names.add(n.id)

    def visit_Attribute(self, n):
        self.generic_visit(n)

    def visit_Assign(self, n):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == "__all__" and isinstance(n.value, (ast.List, ast.Tuple)):
                for e in n.value.elts:
                    if isinstance(e, ast.Constant) and isinstance(e.value, str):
                        self.all_names.add(e.value)
        self.generic_visit(n)

    def visit_Constant(self, n):
        # string annotations, e.g. "os.PathLike"
        if isinstance(n.value, str) and re.fullmatch(r"[A-Za-z_][\w.\[\], ]*", n.value or "x!"):
            for tok in re.findall(r"[A-Za-z_]\w*", n.value):
                self.names.add(tok)


def parse_file(path, mod, is_pkg):
    """Return dict: imports [(target, lineno, kind)], bindings {name: (lineno, desc)}, used, all, error."""
    info = {"imports": [], "bindings": {}, "used": set(), "all": set(), "error": None}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            src = f.read()
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        info["error"] = "SyntaxError line %s: %s" % (e.lineno, e.msg)
        return info
    except (OSError, ValueError) as e:
        info["error"] = "%s: %s" % (type(e).__name__, e)
        return info
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                info["imports"].append((a.name, node.lineno, None))
                bound = a.asname or a.name.split(".")[0]
                info["bindings"][bound] = (node.lineno, "import " + a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            if node.level:
                target = resolve_relative(mod, is_pkg, node.level, node.module)
                if target is None:
                    info["imports"].append(("." * node.level + (node.module or ""), node.lineno, "badrel"))
                    continue
            else:
                target = node.module
            for a in node.names:
                if a.name == "*":
                    info["imports"].append((target, node.lineno, None))
                    continue
                # submodule candidate kept alongside the base module
                info["imports"].append((target, node.lineno, "sub:" + a.name))
                bound = a.asname or a.name
                info["bindings"][bound] = (node.lineno, "from %s import %s" % (target, a.name))
    u = _Usage()
    u.visit(tree)
    info["used"], info["all"] = u.names, u.all_names
    return info


_find_cache = {}


def is_available(name):
    top = name.split(".")[0]
    stdlib = getattr(sys, "stdlib_module_names", None)
    if top in sys.builtin_module_names or (stdlib and top in stdlib):
        return True
    if top in _find_cache:
        return _find_cache[top]
    try:
        ok = importlib.util.find_spec(top) is not None
    except Exception:
        ok = False
    _find_cache[top] = ok
    return ok


def build_map(root=None, base=None):
    root = safe_path(root, base)
    files = find_py_files(root, base)
    modules = {}
    for p in files:
        m, pkg = module_name_for(p, root)
        modules[m] = {"path": p, "pkg": pkg}
    graph, unused, missing, errors = {}, {}, {}, {}
    for m, meta in sorted(modules.items()):
        info = parse_file(meta["path"], m, meta["pkg"])
        graph[m] = set()
        if info["error"]:
            errors[m] = info["error"]
            continue
        for target, line, kind in info["imports"]:
            if kind == "badrel":
                missing.setdefault(m, []).append((target, line))
                continue
            cands = []
            if kind and kind.startswith("sub:"):
                cands.append(target + "." + kind[4:])
            cands.append(target)
            hit = None
            for c in cands:
                parts = c.split(".")
                for i in range(len(parts), 0, -1):  # longest local prefix
                    pre = ".".join(parts[:i])
                    if pre in modules:
                        hit = pre
                        break
                if hit:
                    break
            if hit:
                if hit != m:
                    graph[m].add(hit)
            elif not is_available(target):
                lst = missing.setdefault(m, [])
                if (target, line) not in lst:
                    lst.append((target, line))
        if not meta["pkg"]:
            un = [(n, ln, d) for n, (ln, d) in info["bindings"].items()
                  if n not in info["used"] and n not in info["all"]]
            if un:
                unused[m] = sorted(un, key=lambda x: x[1])
    return {"root": root, "modules": modules, "graph": {k: sorted(v) for k, v in graph.items()},
            "cycles": find_cycles(graph), "unused": unused, "missing": missing, "errors": errors}


def find_cycles(graph):
    """Tarjan SCC (iterative); returns SCCs of size>1 or self-loops."""
    index, low, onstack, stack, out, counter = {}, {}, set(), [], [], [0]
    for start in sorted(graph):
        if start in index:
            continue
        work = [(start, iter(sorted(graph.get(start, ()))))]
        index[start] = low[start] = counter[0]; counter[0] += 1
        stack.append(start); onstack.add(start)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1
                    stack.append(w); onstack.add(w)
                    work.append((w, iter(sorted(graph.get(w, ())))))
                    advanced = True
                    break
                elif w in onstack:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop(); onstack.discard(w); comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in graph.get(v, ()):
                    out.append(sorted(comp))
    return sorted(out)


def text_tree(result, max_depth=6):
    g = result["graph"]
    lines = []

    def walk(m, prefix, seen, depth):
        kids = g.get(m, [])
        for i, k in enumerate(kids):
            last = i == len(kids) - 1
            tag = " (cycle)" if k in seen else ""
            lines.append(prefix + ("└── " if last else "├── ") + k + tag)
            if not tag and depth < max_depth:
                walk(k, prefix + ("    " if last else "│   "), seen | {k}, depth + 1)

    for m in sorted(g):
        lines.append(m + ("  [ERROR]" if m in result["errors"] else ""))
        walk(m, "", {m}, 1)
    return "\n".join(lines) if lines else "(no Python files)"


def node_id(name):
    s = re.sub(r"\W", "_", name)
    return "m_" + s


def mermaid(result):
    out = ["graph TD"]
    g = result["graph"]
    for m in sorted(g):
        label = m.replace('"', "'")
        out.append('    %s["%s"]' % (node_id(m), label))
    for m in sorted(g):
        for k in g[m]:
            out.append("    %s --> %s" % (node_id(m), node_id(k)))
    return "\n".join(out)


def report(result):
    L = ["Import map for %s (%d modules)" % (result["root"], len(result["modules"])), "", text_tree(result), ""]
    L.append("Circular imports: " + ("none" if not result["cycles"] else ""))
    for c in result["cycles"]:
        L.append("  " + " <-> ".join(c))
    L.append("Unused imports: " + ("none" if not result["unused"] else ""))
    for m, items in sorted(result["unused"].items()):
        for n, ln, d in items:
            L.append("  %s:%d  %s  (%s)" % (m, ln, n, d))
    L.append("Missing modules: " + ("none" if not result["missing"] else ""))
    for m, items in sorted(result["missing"].items()):
        for t, ln in items:
            L.append("  %s:%d  %s" % (m, ln, t))
    if result["errors"]:
        L.append("Parse errors:")
        for m, e in sorted(result["errors"].items()):
            L.append("  %s: %s" % (m, e))
    return "\n".join(L)


def run_selftests():
    ok = fail = 0

    def check(cond, msg):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
            print("FAIL:", msg)

    with tempfile.TemporaryDirectory() as td:
        base = os.path.realpath(td)
        proj = os.path.join(base, "proj")
        os.makedirs(os.path.join(proj, "pkg", "sub"))
        files = {
            "a.py": "import b\nimport os\nimport json\nprint(b.x, os.sep)\n",
            "b.py": "from a import *\nx = 1\n",
            "c.py": "from __future__ import annotations\nimport notarealmod_zz9\nfrom pkg import helper\nhelper.go()\n",
            "bad.py": "def f(:\n",
            "exp.py": "from os import path\n__all__ = ['path']\n",
            "pkg/__init__.py": "from .helper import go\nimport sys\n",
            "pkg/helper.py": "from . import sub\nfrom .sub.deep import thing\ndef go(): return thing, sub\n",
            "pkg/sub/__init__.py": "",
            "pkg/sub/deep.py": "from ...pkg import helper as h\nthing = h\n",
        }
        for rel, src in files.items():
            with open(os.path.join(proj, rel), "w") as f:
                f.write(src)
        outside = tempfile.mkdtemp()
        try:
            os.symlink(outside, os.path.join(proj, "escape"))
            with open(os.path.join(outside, "z.py"), "w") as f:
                f.write("import a\n")
        except OSError:
            pass
        r = build_map(proj, base=base)
        g = r["graph"]
        check("pkg.helper" in r["modules"] and "pkg" in r["modules"], "package mapping")
        check(g["a"] == ["b"] and g["b"] == ["a"], "a<->b edges %r" % g)
        check(["a", "b"] in r["cycles"], "cycle a/b")
        check("pkg.sub.deep" in g["pkg.helper"] and "pkg.sub" in g["pkg.helper"], "relative imports")
        check(["pkg.helper", "pkg.sub.deep"] in r["cycles"], "pkg cycle %r" % r["cycles"])
        check(g["pkg"] == ["pkg.helper"], "pkg init edge")
        check([u[0] for u in r["unused"].get("a", [])] == ["json"], "unused json %r" % r["unused"])
        check("exp" not in r["unused"] and "pkg" not in r["unused"], "__all__/__init__ ignored")
        check("annotations" not in str(r["unused"]), "__future__ ignored")
        check(any(t == "notarealmod_zz9" for t, _ in r["missing"].get("c", [])), "missing module")
        check("os" not in str(r["missing"]), "stdlib not missing")
        check("bad" in r["errors"], "syntax error captured")
        check(not any("escape" in m for m in r["modules"]), "symlink escape skipped")
        for bad in ("../", "/etc", os.path.join(proj, "escape")):
            try:
                safe_path(bad, base); check(False, "refuse " + bad)
            except PermissionError:
                check(True, "")
        mm = mermaid(r)
        check(mm.startswith("graph TD") and "m_pkg_helper --> m_pkg_sub_deep" in mm, "mermaid")
        check(node_id('x-y."z') == "m_x_y__z", "node id sanitize")
        check("└──" in text_tree(r), "tree")
        check("Circular imports" in report(r), "report")
        check(find_cycles({"x": {"x"}}) == [["x"]], "self loop")
        import shutil
        shutil.rmtree(outside, ignore_errors=True)
    print("Self-tests: %d passed, %d failed" % (ok, fail))
    return fail == 0


def main(base=None):
    base = base or BASE_DIR
    if not os.path.isdir(base):
        print("Base dir %s not found." % base)
    root, result = base, None
    while True:
        print("\n== Import Map ==  dir: %s" % root)
        print("1) Choose directory  2) Full report  3) Text tree  4) Mermaid graph\n5) Cycles  6) Unused imports  7) Missing modules  8) Self-tests  0) Quit")
        try:
            ch = input("> ").strip()
        except EOFError:
            break
        try:
            if ch == "0" or ch.lower() == "q":
                break
            elif ch == "1":
                p = input("Directory (relative to %s): " % base).strip()
                root, result = safe_path(p, base), None
                continue
            elif ch == "8":
                run_selftests(); continue
            if ch in "234567" and ch:
                if result is None:
                    result = build_map(root, base)
                if ch == "2": print(report(result))
                elif ch == "3": print(text_tree(result))
                elif ch == "4": print(mermaid(result))
                elif ch == "5": print("\n".join(" <-> ".join(c) for c in result["cycles"]) or "No cycles.")
                elif ch == "6":
                    print("\n".join("%s:%d %s" % (m, ln, n) for m, it in sorted(result["unused"].items()) for n, ln, _ in it) or "None.")
                elif ch == "7":
                    print("\n".join("%s:%d %s" % (m, ln, t) for m, it in sorted(result["missing"].items()) for t, ln in it) or "None.")
            else:
                print("Unknown choice.")
        except (PermissionError, OSError) as e:
            print("Error:", e)


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
    if "--selftest" in sys.argv:
        sys.exit(0 if run_selftests() else 1)
    main()
