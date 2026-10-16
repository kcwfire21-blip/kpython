# PEP8-ish code formatter: tabs to spaces, trailing whitespace, comma spacing, import sorting, blank lines; shows a diff and confirms before saving.
"""Stdlib-only formatter for KPython. format_code(src) returns formatted text; safety-checked by comparing ASTs."""
import ast
import difflib
import io
import os
import tokenize

SAFE_ROOT = "/home/pyodide"


def _fix_commas(src):
    """Ensure one space after commas (outside strings/comments), using token positions."""
    lines = src.splitlines(keepends=True)
    edits = []
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    for i, t in enumerate(toks[:-1]):
        nxt = toks[i + 1]
        if t.type == tokenize.OP and t.string == ",":
            if nxt.start[0] == t.end[0] and nxt.string not in (")", "]", "}") \
                    and nxt.type not in (tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT):
                gap = nxt.start[1] - t.end[1]
                if gap != 1:
                    edits.append((t.end[0], t.end[1], nxt.start[1]))
    for row, a, b in sorted(edits, reverse=True):
        ln = lines[row - 1]
        lines[row - 1] = ln[:a] + " " + ln[b:]
    return "".join(lines)


def _sort_imports(lines):
    """Sort the first contiguous block of plain top-level import lines."""
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")
                              or lines[i].startswith(('"""', "'''"))):
        if lines[i].startswith(('"""', "'''")):
            q = lines[i][:3]
            if lines[i].count(q) < 2:
                i += 1
                while i < len(lines) and q not in lines[i]:
                    i += 1
        i += 1
    j = i
    while j < len(lines) and lines[j].startswith(("import ", "from ")) and "(" not in lines[j] \
            and not lines[j].rstrip().endswith("\\"):
        j += 1
    block = lines[i:j]
    plain = sorted(l for l in block if l.startswith("import "))
    froms = sorted(l for l in block if l.startswith("from "))
    return lines[:i] + plain + froms + lines[j:]


def _blank_lines(lines):
    """Two blank lines before top-level def/class (after code), collapse 3+ blanks."""
    out = []
    for ln in lines:
        top = ln.startswith(("def ", "class ", "async def ", "@"))
        if top and out and not (out[-1].startswith("@")):
            while out and out[-1] == "":
                out.pop()
            if out:
                out += ["", ""]
        if ln == "" and len(out) >= 2 and out[-1] == "" and out[-2] == "":
            continue
        out.append(ln)
    while out and out[-1] == "":
        out.pop()
    return out


def format_code(src):
    """Return formatted source. Raises ValueError if the input has a syntax error or formatting would change meaning."""
    original_ast = ast.dump(ast.parse(src))
    text = src.expandtabs(4)
    try:
        text = _fix_commas(text)
    except (tokenize.TokenError, IndentationError):
        pass
    lines = [l.rstrip() for l in text.splitlines()]
    lines = _blank_lines(_sort_imports(lines))
    result = "\n".join(lines) + "\n"
    try:
        new_ast = ast.dump(ast.parse(result))
    except SyntaxError:
        return src
    if new_ast != original_ast and _sort_imports(src.splitlines()) == src.splitlines():
        return src  # changed meaning beyond import order: refuse
    return result


def show_diff(old, new, name="code"):
    """Print a unified diff; return True if anything changed."""
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                     f"{name} (before)", f"{name} (after)", lineterm=""))
    print("\n".join(diff) if diff else "Already formatted. No changes.")
    return bool(diff)


def _safe_path(path):
    full = os.path.realpath(os.path.join(SAFE_ROOT, path))
    if not (full == SAFE_ROOT or full.startswith(SAFE_ROOT + os.sep)):
        raise ValueError(f"Only files under {SAFE_ROOT} are allowed.")
    return full


def format_file(path):
    """Format a file under /home/pyodide, show a diff, and ask before overwriting."""
    full = _safe_path(path)
    with open(full, encoding="utf-8") as f:
        old = f.read()
    try:
        new = format_code(old)
    except SyntaxError as e:
        print(f"Can't format: syntax error on line {e.lineno}: {e.msg}")
        return False
    if not show_diff(old, new, os.path.basename(full)):
        return False
    if input("Apply these changes? (y/N): ").strip().lower() == "y":
        with open(full, "w", encoding="utf-8") as f:
            f.write(new)
        print("Saved.")
        return True
    print("Not saved.")
    return False


def _self_test():
    messy = "import sys\nimport os\nx=[1,2,  3]\t \ndef f(a,b):\n\treturn a+b\nclass C:\n    pass\n\n\n\n\ny = 'a,b'\n"
    out = format_code(messy)
    assert "import os\nimport sys" in out, out
    assert "[1, 2, 3]" in out, out
    assert "'a,b'" in out, "string contents must not change"
    assert "\t" not in out and not any(l != l.rstrip() for l in out.splitlines())
    assert "\n\n\ndef f(a, b):" in out and "\n\n\nclass C:" in out, out
    assert format_code(out) == out, "formatter should be idempotent"
    try:
        format_code("def f(:\n")
        raise AssertionError("expected SyntaxError")
    except SyntaxError:
        pass
    try:
        _safe_path("../../etc/passwd")
        raise AssertionError("path escape not blocked")
    except ValueError:
        pass
    print("Self-tests passed.")


def main():
    """Run self-tests, then format a file or pasted code."""
    _self_test()
    choice = input(f"\nFile under {SAFE_ROOT} to format (or Enter to paste code): ").strip()
    if choice:
        try:
            format_file(choice)
        except (OSError, ValueError) as e:
            print(f"Error: {e}")
        return
    print("Paste code, then a line with just END:")
    buf = []
    while True:
        try:
            ln = input()
        except EOFError:
            break
        if ln == "END":
            break
        buf.append(ln)
    if buf:
        src = "\n".join(buf) + "\n"
        try:
            new = format_code(src)
        except SyntaxError as e:
            print(f"Syntax error on line {e.lineno}: {e.msg}")
            return
        if show_diff(src, new):
            print("\n--- formatted ---\n" + new)


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
    main()
