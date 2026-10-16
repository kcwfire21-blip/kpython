# bot2: Code Outline & Refactor Helper - outline classes/functions with signatures, find name uses, safe token-based rename, and per-function complexity.
import ast, io, tokenize, keyword, os
def _kp_safe(p, base="/home/pyodide"):
    """KPython rule: files only under /home/pyodide (realpath check)."""
    p = (p or "").strip()
    if p.startswith("~/"): p = p[2:]
    full = os.path.realpath(os.path.join(base, p))
    if full != base and not full.startswith(base + os.sep):
        raise ValueError(f"refused: {p} is outside {base}")
    return full


def _sig(fn):
    a = fn.args
    parts = [x.arg for x in a.posonlyargs]
    if a.posonlyargs: parts.append("/")
    parts += [x.arg for x in a.args]
    if a.vararg: parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs: parts.append("*")
    parts += [x.arg for x in a.kwonlyargs]
    if a.kwarg: parts.append("**" + a.kwarg.arg)
    pre = "async def " if isinstance(fn, ast.AsyncFunctionDef) else "def "
    return f"{pre}{fn.name}({', '.join(parts)})"

def outline(src):
    out = []
    def walk(node, depth):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, ast.ClassDef):
                bases = ", ".join(ast.unparse(b) for b in n.bases)
                out.append(f"{'  '*depth}L{n.lineno}: class {n.name}({bases})")
                walk(n, depth + 1)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(f"{'  '*depth}L{n.lineno}: {_sig(n)}")
                walk(n, depth + 1)
    walk(ast.parse(src), 0)
    return out

def find_uses(src, name):
    hits = []
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type == tokenize.NAME and t.string == name:
            hits.append((t.start[0], t.start[1], t.line.rstrip()))
    return hits

def rename(src, old, new):
    if not new.isidentifier() or keyword.iskeyword(new):
        raise ValueError("New name is not a valid identifier.")
    if find_uses(src, new):
        raise ValueError(f"'{new}' is already used; pick another name.")
    lines = src.splitlines(keepends=True)
    hits = find_uses(src, old)
    for row, col, _ in sorted(hits, reverse=True):
        ln = lines[row - 1]
        lines[row - 1] = ln[:col] + new + ln[col + len(old):]
    result = "".join(lines)
    ast.parse(result)
    return result, len(hits)

_BRANCH = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With,
           ast.AsyncWith, ast.IfExp, ast.Assert, ast.comprehension, ast.match_case)

def complexity(src):
    res = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score = 1
            for c in ast.walk(n):
                if isinstance(c, _BRANCH): score += 1
                elif isinstance(c, ast.BoolOp): score += len(c.values) - 1
            rating = "simple" if score <= 5 else "moderate" if score <= 10 else "complex"
            res.append((n.lineno, n.name, score, rating))
    return sorted(res)

def read_code():
    path = input("File path (blank to paste code): ").strip()
    if path:
        path = _kp_safe(path)
        if os.path.getsize(path) > 500_000: raise OSError('file too big')
        with open(path) as f: return f.read(), path
    print("Paste code, then a line with only END:")
    lines = []
    while True:
        l = input()
        if l.strip() == "END": break
        lines.append(l)
    return "\n".join(lines) + "\n", None

def main():
    print("Code Outline & Refactor Helper")
    try:
        src, path = read_code(); ast.parse(src)
    except (OSError, SyntaxError) as e:
        print("Could not load code:", e); return
    while True:
        c = input("\n1) Outline  2) Find uses  3) Rename  4) Complexity  q) Quit: ").strip().lower()
        try:
            if c == "1":
                print("\n".join(outline(src)) or "(no classes or functions)")
            elif c == "2":
                name = input("Name: ").strip()
                hits = find_uses(src, name)
                for r, col, line in hits: print(f"L{r}:{col}  {line}")
                print(f"{len(hits)} use(s)")
            elif c == "3":
                old, new = input("Old name: ").strip(), input("New name: ").strip()
                src, n = rename(src, old, new)
                print(f"Renamed {n} occurrence(s).")
                if path and input(f"Overwrite {path}? type yes: ").strip().lower() == "yes":
                    with open(path, "w") as f: f.write(src)
                    print("Saved.")
            elif c == "4":
                for ln, name, s, r in complexity(src): print(f"L{ln}: {name}  {s} ({r})")
            elif c == "q":
                break
        except (ValueError, SyntaxError) as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
