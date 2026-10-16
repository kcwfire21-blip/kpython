# Dyno: test runner - runs unittest TestCases and doctests from pasted code or a .py file under /home/pyodide; shows pass/fail counts, tracebacks, timing. Stdlib only.
import os, sys, io, time, types, unittest, doctest, traceback

BASE = "/home/pyodide"  # KPython: fixed base, no env override
MAX_CODE = 500_000

def safe_path(p):
    full = os.path.realpath(os.path.join(BASE, p))
    if full != BASE and not full.startswith(BASE + os.sep):
        raise ValueError("Only files under " + BASE + " are allowed.")
    if not full.endswith(".py") or not os.path.isfile(full):
        raise ValueError("Not a .py file: " + full)
    return full

def load_module(code, name="code_under_test"):
    mod = types.ModuleType(name)
    mod.__file__ = "<" + name + ">"
    exec(compile(code, mod.__file__, "exec"), mod.__dict__)
    return mod

def run(code, name="code_under_test"):
    print("Note: this runs your code (tests import and execute it).")
    if len(code) > MAX_CODE: return print("Code too big (max 500 KB).")
    t0 = time.perf_counter()
    try:
        mod = load_module(code, name)
    except Exception:
        print("Code failed to load:\n" + traceback.format_exc())
        return
    # unittest
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    out = io.StringIO()
    ut = unittest.TextTestRunner(stream=out, verbosity=2).run(suite)
    ut_fail = len(ut.failures) + len(ut.errors)
    # doctest
    dt_out = io.StringIO()
    old = sys.stdout
    sys.stdout = dt_out
    try:
        dt = doctest.testmod(mod, verbose=False, report=True)
    finally:
        sys.stdout = old
    elapsed = time.perf_counter() - t0
    print("== unittest ==")
    print(out.getvalue().strip() or "(no TestCases found)")
    print("\n== doctest ==")
    print(dt_out.getvalue().strip() or f"{dt.attempted} examples, all passed" if dt.attempted else "(no doctests found)")
    print("\n== Summary ==")
    print(f"unittest: {ut.testsRun - ut_fail} passed, {len(ut.failures)} failed, {len(ut.errors)} errors, {len(ut.skipped)} skipped")
    print(f"doctest:  {dt.attempted - dt.failed} passed, {dt.failed} failed")
    print(f"Time: {elapsed*1000:.1f} ms")
    print("RESULT:", "PASS" if ut_fail == 0 and dt.failed == 0 else "FAIL")

def main():
    print("== Test Runner ==")
    choice = input("1 Run a file under " + BASE + "  2 Paste code: ").strip()
    if choice == "1":
        try:
            path = safe_path(input("File path (relative to " + BASE + "): ").strip())
        except ValueError as e:
            print(e); return
        with open(path) as f:
            run(f.read(), os.path.splitext(os.path.basename(path))[0])
    elif choice == "2":
        print("Paste code; end with a line containing only END")
        lines = []
        while True:
            line = input()
            if line.strip() == "END": break
            lines.append(line)
        run("\n".join(lines))

if __name__ == "__main__":
    main()
