# Dyno: Dev-tab "Self-test all" - runs every tool's self_test (per-tool timeout, input stubbed), prints a table, saves the last results with a timestamp, and can show them again. Stdlib only.
import os, sys, io, json, time, builtins, datetime, tempfile, importlib.util, contextlib, inspect, asyncio
PENDING = {}

HOME = "/home/pyodide"
DIRS = ["/kptools", "/workspace/pyapp/tools"]   # KPython: the app's read-only tool folder
RESULTS = HOME + "/.kp_selftest_last.json"
TIMEOUT = 10.0
NAMES = ("self_test", "selftest", "_self_test", "run_self_tests", "self_tests", "run_selftests")

class NeedsInput(Exception): pass
class TimedOut(Exception): pass

def _no_input(*a, **k): raise NeedsInput()

def tools_dir():
    for d in DIRS:  # KPython: no env override
        if d and os.path.isdir(d): return d
    raise FileNotFoundError("No tools folder found.")

def results_path():
    return RESULTS if os.path.isdir(HOME) else os.path.join(tempfile.gettempdir(), ".kp_selftest_last.json")

def run_tool(path, timeout=TIMEOUT):
    name = os.path.splitext(os.path.basename(path))[0]
    t0 = time.perf_counter(); dl = t0 + timeout
    def tracer(f, e, a):
        if time.perf_counter() > dl: raise TimedOut()
        return tracer
    old = (builtins.input, sys.argv, sys.gettrace(), list(sys.path))
    builtins.input = _no_input; sys.argv = [path, "--selftest"]
    sys.path.insert(0, os.path.dirname(path))
    status, note = "FAIL", ""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sys.settrace(tracer)
            spec = importlib.util.spec_from_file_location("kp_st_" + name, path)
            mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod
            try: spec.loader.exec_module(mod)
            except BaseException: sys.modules.pop(spec.name, None); raise
            fn = next((getattr(mod, n) for n in NAMES if callable(getattr(mod, n, None))), None)
            if fn is None: status, note = "SKIP", "no self_test()"
            else:
                r = fn()
                if inspect.iscoroutine(r):   # KPython: async self-tests are awaited later by arun_all()
                    PENDING[name] = r; status, note = "PEND", "async"
                else:
                    status = "FAIL" if r is False else "PASS"
                    if r is False: note = "returned False"
    except NeedsInput: status, note = "SKIP", "needs input"
    except TimedOut: note = f"timeout >{timeout:g}s"
    except SystemExit as e:
        status = "PASS" if e.code in (0, None) else "FAIL"
        if status == "FAIL": note = f"exit {e.code}"
    except BaseException as e: note = f"{type(e).__name__}: {str(e)[:60]}"
    finally:
        sys.settrace(old[2]); builtins.input, sys.argv = old[0], old[1]; sys.path[:] = old[3]
    return {"tool": name, "status": status, "ms": round((time.perf_counter() - t0) * 1000, 1), "note": note}

def run_all(d=None, timeout=TIMEOUT):
    d = d or tools_dir()
    files = sorted(f for f in os.listdir(d) if f.endswith(".py") and not f.startswith("_") and "selftest" not in f)
    rows = [run_tool(os.path.join(d, f), timeout) for f in files]
    return {"timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "dir": d, "rows": rows}

async def arun_all(d=None, timeout=TIMEOUT):
    """KPython: like run_all, but also awaits async self-tests (inside the app's running event loop)."""
    PENDING.clear(); res = run_all(d, timeout)
    for row in res["rows"]:
        co = PENDING.pop(row["tool"], None)
        if co is None: continue
        t0 = time.perf_counter(); old = builtins.input; builtins.input = _no_input
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                r = await asyncio.wait_for(co, timeout)
            row["status"], row["note"] = ("FAIL", "returned False") if r is False else ("PASS", "async")
        except NeedsInput: row["status"], row["note"] = "SKIP", "needs input"
        except asyncio.TimeoutError: row["status"], row["note"] = "FAIL", f"timeout >{timeout:g}s"
        except BaseException as e: row["status"], row["note"] = "FAIL", f"{type(e).__name__}: {str(e)[:60]}"
        finally: builtins.input = old
        row["ms"] = round(row["ms"] + (time.perf_counter() - t0) * 1000, 1)
    for co in PENDING.values(): co.close()
    PENDING.clear(); return res

async def amain():
    c = input("Enter = run all, l = last results, t = self-test: ").strip().lower()
    if c == "t": self_test()
    elif c == "l": dev_last()
    else:
        print("Running every tool's self-test...")
        res = await arun_all(); p = save(res)
        print(table(res)); print(f"\nSaved to {p}")

def save(res, path=None):
    path = path or results_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(res, f, indent=1)
    os.replace(tmp, path)
    return path

def load(path=None):
    path = path or results_path()
    if not os.path.exists(path): return None
    try:
        with open(path) as f: return json.load(f)
    except (OSError, ValueError): return None

def table(res):
    rows = res["rows"]; w = max([4] + [len(r["tool"]) for r in rows])
    out = [f"Self-test all  {res['timestamp']}", f"{'TOOL':<{w}}  RESULT  TIME(ms)  NOTE", "-" * (w + 30)]
    out += [f"{r['tool']:<{w}}  {r['status']:<6}  {r['ms']:8.1f}  {r['note']}" for r in rows]
    c = {k: sum(r["status"] == k for r in rows) for k in ("PASS", "FAIL", "SKIP", "PEND")}
    c["SKIP"] += c.pop("PEND")
    out.append(f"\n{len(rows)} tools: {c['PASS']} passed, {c['FAIL']} failed, {c['SKIP']} skipped, {sum(r['ms'] for r in rows)/1000:.2f}s")
    return "\n".join(out)

# ---- Dev tab entry points (call from kp_worker / app4.js) ----
def dev_run():
    print("Running every tool's self-test...")
    res = run_all(); p = save(res)
    print(table(res)); print(f"\nSaved to {p}")
    return res

def dev_last():
    res = load()
    print(table(res) if res else "No saved results yet. Run Self-test all first.")
    return res

def self_test():
    d = tempfile.mkdtemp()
    for n, c in {"ok.py": "def self_test():\n    print('x')\n", "bad.py": "def self_test():\n    assert 0\n",
                 "asks.py": "def self_test():\n    input()\n", "none.py": "x=1\n",
                 "loop.py": "def self_test():\n    while True: pass\n", "broken.py": "def (:\n"}.items():
        with open(os.path.join(d, n), "w") as f: f.write(c)
    res = run_all(d, timeout=0.5); s = {r["tool"]: r for r in res["rows"]}
    assert s["ok"]["status"] == "PASS" and s["bad"]["status"] == "FAIL", s
    assert s["asks"]["status"] == "SKIP" and s["none"]["status"] == "SKIP", s
    assert "timeout" in s["loop"]["note"] and s["broken"]["status"] == "FAIL", s
    p = save(res, os.path.join(d, "last.json")); back = load(p)
    assert back["rows"] == res["rows"] and back["timestamp"] == res["timestamp"]
    datetime.datetime.fromisoformat(back["timestamp"])
    assert "6 tools" in table(back) and builtins.input is not _no_input
    print("self-tests passed")

def main():
    c = input("Enter = run all, l = last results, t = self-test: ").strip().lower()
    if c == "t": self_test()
    elif c == "l": dev_last()
    else: dev_run()


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
