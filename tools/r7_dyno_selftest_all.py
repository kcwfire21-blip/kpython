# Dyno: run every KPython tool's self-test with a per-tool timeout; catches failures, skips tools needing input, prints a PASS/FAIL/SKIP table and summary. Stdlib only.
import os, sys, io, time, builtins, importlib.util, contextlib, traceback

CANDIDATES = ["/home/pyodide/kptools", "/workspace/pyapp/tools"]  # KPython: the app loads tools into ~/kptools
TIMEOUT = 10.0
NAMES = ("self_test", "selftest", "_self_test", "run_self_tests", "self_tests", "run_selftests")  # KPython: + bot2help naming
SLOW = {"r6_bot3_bigo": 30.0, "r5_bot3_timeit": 20.0}  # KPython: extra headroom for timing tools

class NeedsInput(Exception): pass
class TimedOut(Exception): pass

def tools_dir():
    for d in CANDIDATES:  # KPython: no env override
        if d and os.path.isdir(d):
            return d
    raise SystemExit("No tools folder found.")

def _no_input(*a, **k):
    raise NeedsInput("tool asked for input()")

def _deadline_tracer(deadline):
    # Works without threads (Pyodide): checks the clock on every traced call/line.
    def tracer(frame, event, arg):
        if time.perf_counter() > deadline:
            raise TimedOut()
        return tracer
    return tracer

def run_tool(path, timeout=TIMEOUT):
    name = os.path.splitext(os.path.basename(path))[0]
    t0 = time.perf_counter()
    out = io.StringIO()
    old_input, old_argv, old_trace = builtins.input, sys.argv, sys.gettrace()
    builtins.input = _no_input
    sys.argv = [path, "--selftest"]
    status, note = "FAIL", ""
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            sys.settrace(_deadline_tracer(t0 + timeout))
            spec = importlib.util.spec_from_file_location("kp_selftest_" + name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn = next((getattr(mod, n) for n in NAMES if callable(getattr(mod, n, None))), None)
            if fn is None:
                status, note = "SKIP", "no self_test()"
            else:
                r = fn()
                status = "FAIL" if r is False else "PASS"
                if r is False: note = "self_test returned False"
    except NeedsInput:
        status, note = "SKIP", "needs input"
    except TimedOut:
        status, note = "FAIL", f"timeout >{timeout:.0f}s"
    except SystemExit as e:
        status = "PASS" if e.code in (0, None) else "FAIL"
        if status == "FAIL": note = f"exit {e.code}"
    except BaseException as e:
        status, note = "FAIL", f"{type(e).__name__}: {str(e)[:60]}"
    finally:
        sys.settrace(old_trace)
        builtins.input, sys.argv = old_input, old_argv
    return name, status, (time.perf_counter() - t0) * 1000, note

def run_all(d, timeout=TIMEOUT):
    files = sorted(f for f in os.listdir(d) if f.endswith(".py") and not f.startswith("_")
                   and "selftest_all" not in f)
    return [run_tool(os.path.join(d, f), max(timeout, SLOW.get(f[:-3], 0)) if timeout >= TIMEOUT else timeout) for f in files]

def table(rows):
    w = max([4] + [len(r[0]) for r in rows])
    lines = [f"{'TOOL':<{w}}  RESULT  TIME(ms)  NOTE", "-" * (w + 30)]
    for n, s, ms, note in rows:
        lines.append(f"{n:<{w}}  {s:<6}  {ms:8.1f}  {note}")
    c = {k: sum(1 for r in rows if r[1] == k) for k in ("PASS", "FAIL", "SKIP")}
    lines.append(f"\n{len(rows)} tools: {c['PASS']} passed, {c['FAIL']} failed, {c['SKIP']} skipped, "
                 f"{sum(r[2] for r in rows)/1000:.2f}s total")
    return "\n".join(lines)

def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    files = {
        "ok.py": "def self_test():\n    print('hi')\n",
        "bad.py": "def self_test():\n    assert 1 == 2\n",
        "asks.py": "def self_test():\n    input('x')\n",
        "none.py": "x = 1\n",
        "loop.py": "def self_test():\n    while True:\n        pass\n",
        "broken.py": "def (:\n",
    }
    for n, c in files.items():
        with open(os.path.join(d, n), "w") as f:
            f.write(c)
    res = {r[0]: r for r in run_all(d, timeout=0.5)}
    assert res["ok"][1] == "PASS", res
    assert res["bad"][1] == "FAIL", res
    assert res["asks"][1] == "SKIP" and res["none"][1] == "SKIP", res
    assert res["loop"][1] == "FAIL" and "timeout" in res["loop"][3], res
    assert res["broken"][1] == "FAIL", res
    assert builtins.input is not _no_input
    print("self-tests passed")

def main():
    if "--selftest" in sys.argv[1:] or input("Enter = run all tools, t = self-test: ").strip() == "t":
        self_test(); return
    d = tools_dir()
    print("Running self-tests in", d, "...")
    print(table(run_all(d)))

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
