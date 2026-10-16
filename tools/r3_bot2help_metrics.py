# Code metrics report: lines, functions/classes, per-function cyclomatic complexity (ast), long/complex flags, TODO/FIXME finder. Stdlib only, Pyodide-friendly.
import ast
import io
import os
import sys
import tokenize

BASE_DIR = "/home/pyodide"
TAGS = ("TODO", "FIXME", "XXX", "HACK")


def safe_path(path, base=BASE_DIR):
    """Resolve path; raise ValueError if outside base."""
    base_r = os.path.realpath(base)
    p = path if os.path.isabs(path) else os.path.join(base_r, path)
    p = os.path.realpath(p)
    if p != base_r and not p.startswith(base_r + os.sep):
        raise ValueError("Access denied: path outside " + base)
    return p


def load_file(path, base=BASE_DIR):
    with open(safe_path(path, base), "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _comment_lines(source):
    lines = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        for i, l in enumerate(source.splitlines(), 1):
            if l.strip().startswith("#"):
                lines.add(i)
    return lines


def line_counts(source):
    lines = source.splitlines()
    comments = _comment_lines(source)
    blank = sum(1 for l in lines if not l.strip())
    comment = sum(1 for i, l in enumerate(lines, 1)
                  if l.strip() and i in comments and l.strip().startswith("#"))
    total = len(lines)
    return {"total": total, "code": total - blank - comment,
            "comment": comment, "blank": blank}


def complexity(func_node):
    """Cyclomatic complexity of a function, not descending into nested defs/classes."""
    score = 1
    stack = list(ast.iter_child_nodes(func_node))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp,
                          ast.ExceptHandler)):
            score += 1
        elif isinstance(n, ast.BoolOp):
            score += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            score += 1 + len(n.ifs)
        elif hasattr(ast, "match_case") and isinstance(n, ast.match_case):
            score += 1
        stack.extend(ast.iter_child_nodes(n))
    return score


def functions(tree):
    out = []

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + ch.name
                end = getattr(ch, "end_lineno", ch.lineno) or ch.lineno
                out.append({"name": q, "line": ch.lineno,
                            "length": end - ch.lineno + 1,
                            "complexity": complexity(ch)})
                walk(ch, q + ".<locals>.")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, prefix + ch.name + ".")
            else:
                walk(ch, prefix)
    walk(tree, "")
    return out


def find_tags(source, tags=TAGS):
    found = []
    for i, l in enumerate(source.splitlines(), 1):
        if "#" not in l:
            continue
        c = l[l.index("#"):]
        up = c.upper()
        for t in tags:
            if t in up:
                found.append({"line": i, "tag": t, "text": c.strip()})
                break
    return found


def analyze(source, max_len=50, max_cc=10):
    rep = {"lines": line_counts(source), "todos": find_tags(source),
           "error": None, "functions": [], "classes": 0,
           "max_len": max_len, "max_cc": max_cc}
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        rep["error"] = "SyntaxError line %s: %s" % (e.lineno, e.msg)
        return rep
    rep["classes"] = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
    for f in functions(tree):
        f["long"] = f["length"] > max_len
        f["complex"] = f["complexity"] > max_cc
        rep["functions"].append(f)
    return rep


def format_report(rep):
    L = rep["lines"]
    o = ["== Code Metrics ==",
         "Lines: total %d, code %d, comment %d, blank %d" %
         (L["total"], L["code"], L["comment"], L["blank"])]
    if rep["error"]:
        o.append("Could not parse: " + rep["error"])
    else:
        o.append("Functions: %d  Classes: %d" % (len(rep["functions"]), rep["classes"]))
        if rep["functions"]:
            w = max(len(f["name"]) for f in rep["functions"])
            o.append("%-*s %5s %5s %4s  flags" % (w, "name", "line", "len", "cc"))
            for f in rep["functions"]:
                fl = []
                if f["long"]:
                    fl.append("LONG>%d" % rep["max_len"])
                if f["complex"]:
                    fl.append("COMPLEX>%d" % rep["max_cc"])
                o.append("%-*s %5d %5d %4d  %s" % (w, f["name"], f["line"],
                         f["length"], f["complexity"], " ".join(fl)))
    o.append("Tags: %d" % len(rep["todos"]))
    for t in rep["todos"]:
        o.append("  L%d [%s] %s" % (t["line"], t["tag"], t["text"]))
    return "\n".join(o)


def read_pasted():
    print("Paste code; finish with a line: END")
    buf = []
    while True:
        try:
            l = input()
        except (EOFError, KeyboardInterrupt):
            break
        if l.strip() == "END":
            break
        buf.append(l)
    return "\n".join(buf) + "\n"


def main():
    max_len, max_cc = 50, 10
    while True:
        print("\n1) Paste code  2) Load file (under %s)  3) Thresholds (len=%d, cc=%d)  "
              "4) Self-test  q) Quit" % (BASE_DIR, max_len, max_cc))
        try:
            c = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if c == "1":
            print(format_report(analyze(read_pasted(), max_len, max_cc)))
        elif c == "2":
            try:
                src = load_file(input("Path: ").strip())
                print(format_report(analyze(src, max_len, max_cc)))
            except (ValueError, OSError, EOFError) as e:
                print("Error:", e)
        elif c == "3":
            try:
                max_len = int(input("Max lines [%d]: " % max_len) or max_len)
                max_cc = int(input("Max complexity [%d]: " % max_cc) or max_cc)
            except (ValueError, EOFError):
                print("Invalid number.")
        elif c == "4":
            run_selftests()
        elif c in ("q", "quit", "exit"):
            break
        else:
            print("Unknown choice.")


def run_selftests():
    src = (
        "# header\n\n"
        "class A:\n"
        "    def m(self, x):\n"
        "        if x and x > 1 or x < -5:  # TODO fix\n"
        "            return [i for i in range(x) if i % 2]\n"
        "        elif x:\n"
        "            return 1 if x else 2\n"
        "        return 0\n\n"
        "def outer():\n"
        "    def inner():\n"
        "        for i in range(3):\n"
        "            while i:\n"
        "                i -= 1\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError:\n"
        "        pass  # FIXME later\n"
    )
    r = analyze(src)
    assert r["error"] is None
    assert r["lines"] == {"total": 19, "code": 16, "comment": 1, "blank": 2}, r["lines"]
    names = {f["name"]: f for f in r["functions"]}
    assert set(names) == {"A.m", "outer", "outer.<locals>.inner"}, names
    # m: 1 + if + boolop(and:1, or:1) + comp(1+1 if) + elif + ifexp = 8
    assert names["A.m"]["complexity"] == 8, names["A.m"]
    assert names["outer"]["complexity"] == 2
    assert names["outer.<locals>.inner"]["complexity"] == 3
    assert names["A.m"]["line"] == 4 and names["A.m"]["length"] == 6
    assert r["classes"] == 1
    assert [t["tag"] for t in r["todos"]] == ["TODO", "FIXME"]
    r2 = analyze(src, max_len=3, max_cc=5)
    assert names and [f for f in r2["functions"] if f["name"] == "A.m"][0]["complex"]
    assert [f for f in r2["functions"] if f["name"] == "A.m"][0]["long"]
    if hasattr(ast, "match_case"):
        m = analyze("def f(x):\n    match x:\n        case 1: pass\n        case _: pass\n")
        assert m["functions"][0]["complexity"] == 3
    bad = analyze("def f(:\n  pass  # XXX\n")
    assert bad["error"] and bad["todos"][0]["tag"] == "XXX"
    assert "Could not parse" in format_report(bad)
    for p in ("/etc/passwd", "../etc/passwd", "/home/pyodide/../x"):
        try:
            safe_path(p)
            assert False, p
        except ValueError:
            pass
    assert safe_path("a.py") == os.path.join(os.path.realpath(BASE_DIR), "a.py")
    assert "A.m" in format_report(r)
    print("All self-tests passed.")
    return True


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_selftests()
    else:
        main()
