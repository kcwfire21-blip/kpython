# Dyno: line coverage - runs a script plus its tests under sys.settrace; per-line hit/miss report and coverage % per function. Stdlib only.
import os, sys, ast, types, unittest, io

BASE = "/home/pyodide"  # KPython: fixed, no env override
MAX_BYTES = 500_000
FNAME = "<covered>"

def safe_read(p):
    full = os.path.realpath(os.path.join(BASE, p))
    if full != BASE and not full.startswith(BASE + os.sep):
        raise ValueError("Only files under " + BASE + " are allowed.")
    if not full.endswith(".py") or not os.path.isfile(full):
        raise ValueError("Not a .py file: " + full)
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError("File over 500KB.")
    with open(full) as f:
        return f.read()

def executable_lines(code):
    lines = set()
    stack = [code]
    while stack:
        c = stack.pop()
        for _, _, ln in c.co_lines():
            if ln:   # KPython: skip line 0 (the module's RESUME), which made 3/3 lines show as 75%
                lines.add(ln)
        stack.extend(k for k in c.co_consts if isinstance(k, types.CodeType))
    return lines

def functions(src):
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, node.lineno, node.end_lineno))
    return sorted(out, key=lambda x: x[1])

def cover(src, tests=""):
    if len(src) + len(tests) > MAX_BYTES:
        raise ValueError("Input over 500KB.")
    code = compile(src, FNAME, "exec")
    exe = executable_lines(code)
    hits = set()

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != FNAME:
            return None
        if event == "line":
            hits.add(frame.f_lineno)
        return tracer

    mod = types.ModuleType("covered")
    mod.__dict__["__name__"] = "covered"
    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        exec(code, mod.__dict__)
        if tests:
            exec(compile(tests, "<tests>", "exec"), mod.__dict__)
            suite = unittest.defaultTestLoader.loadTestsFromModule(
                types.SimpleNamespace(**{k: v for k, v in mod.__dict__.items()}))
            unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    finally:
        sys.settrace(old)
    return exe, hits

def report(src, exe, hits):
    lines = src.splitlines()
    out = []
    for i, text in enumerate(lines, 1):
        mark = ("HIT " if i in hits else "MISS") if i in exe else "    "
        out.append(f"{i:4} {mark} {text}")
    out.append("")
    out.append("Per function:")
    for name, a, b in functions(src):
        fl = {l for l in exe if a < l <= b} or {l for l in exe if a <= l <= b}
        pct = 100 * len(fl & hits) / len(fl) if fl else 100.0
        out.append(f"  {name:20} {pct:5.1f}%  ({len(fl & hits)}/{len(fl)})")
    tot = 100 * len(exe & hits) / len(exe) if exe else 100.0
    out.append(f"TOTAL {tot:.1f}% ({len(exe & hits)}/{len(exe)} lines)")
    return out

def self_test():
    src = "def f(x):\n    if x:\n        return 1\n    return 2\n\ndef g():\n    return 3\n"
    tests = "import unittest\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(f(1), 1)\n"
    exe, hits = cover(src, tests)
    rep = "\n".join(report(src, exe, hits))
    assert "   3 HIT " in rep and "   4 MISS" in rep and "   7 MISS" in rep, rep
    assert "g                      0.0%" in rep, rep
    try:
        safe_read("../../etc/passwd"); assert False
    except ValueError:
        pass
    print("self-tests passed")

def read_paste(label):
    print(label + " (end with a line containing only END):")
    lines = []
    while True:
        l = input()
        if l.strip() == "END": break
        lines.append(l)
    return "\n".join(lines)

def main():
    print("== Line Coverage ==")
    c = input("1 Files under " + BASE + "  2 Paste code  t Self-test: ").strip()
    if c == "t":
        self_test(); return
    try:
        if c == "1":
            src = safe_read(input("Script path: ").strip())
            tp = input("Tests path (blank for none): ").strip()
            tests = safe_read(tp) if tp else ""
        elif c == "2":
            src = read_paste("Paste script")
            tests = read_paste("Paste tests (or just END)")
        else:
            return
    except ValueError as e:
        print(e); return
    if input("This will run the code. Continue? (y/N): ").strip().lower() not in ("y", "yes"):
        print("Cancelled."); return
    try:
        exe, hits = cover(src, tests)
    except Exception as e:
        print("Error while running:", type(e).__name__, e); return
    print("\n".join(report(src, exe, hits)))

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
