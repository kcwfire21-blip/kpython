# Benchmark Comparer: time 2-4 code variants with timeit and show a ranked table with relative speed and a text bar chart (by bot3)
import timeit, time

MAX_VARIANTS = 4
MAX_LOOPS = 100_000          # loop cap per run
MAX_RUNS = 7
TIME_CAP = 2.0               # seconds budget per variant (approx)
MAX_SRC_BYTES = 50_000
BAR_WIDTH = 30
HARD_CAP = 5.0               # KPython: hard per-run cap (seconds)

class BenchmarkTimeout(Exception):
    pass

def _kp_guarded(fn, cap):
    import sys
    end = time.perf_counter() + cap
    old = sys.gettrace()
    def tr(frame, event, arg):
        if time.perf_counter() > end:
            raise BenchmarkTimeout(f"over the {cap:.0f}s hard limit")
        return tr
    sys.settrace(tr)
    try:
        return fn()
    finally:
        sys.settrace(old)

def fmt(sec):
    for unit, f in (("s", 1), ("ms", 1e3), ("us", 1e6), ("ns", 1e9)):
        if sec * f >= 1 or unit == "ns":
            return f"{sec * f:.3f} {unit}"

def time_variant(code, setup="pass", runs=5, time_cap=TIME_CAP, max_loops=MAX_LOOPS):
    for part in (code, setup):
        if len(part.encode()) > MAX_SRC_BYTES:
            raise ValueError("Code too large")
        compile(part, "<variant>", "exec")
    t = timeit.Timer(code, setup=setup)
    # calibrate: one loop first, then pick loops to fit the time budget
    # KPython: hard cap. The first (calibration) loop runs under a time guard, so one
    # endless variant can't hang the app; ⏹ Stop also still works at any point.
    t0 = time.perf_counter(); _kp_guarded(lambda: t.timeit(1), HARD_CAP); one = time.perf_counter() - t0
    runs = max(1, min(runs, MAX_RUNS))
    per_run_budget = time_cap / runs
    loops = max(1, min(max_loops, int(per_run_budget / one) if one > 0 else max_loops))
    if one > time_cap:            # single loop already over budget: just report it
        return one, one, 1, 1
    results = []
    start = time.perf_counter()
    for _ in range(runs):
        r0 = time.perf_counter()
        results.append(t.timeit(loops) / loops)
        if time.perf_counter() - r0 > HARD_CAP:  # KPython: a run that blew the cap stops the variant
            break
        if time.perf_counter() - start > time_cap:
            break
    return min(results), sum(results) / len(results), loops, len(results)

def compare(variants, setup="pass", runs=5, time_cap=TIME_CAP):
    if not 2 <= len(variants) <= MAX_VARIANTS:
        raise ValueError(f"Need 2-{MAX_VARIANTS} variants")
    rows = []
    for name, code in variants:
        try:
            best, avg, loops, done = time_variant(code, setup, runs, time_cap)
            rows.append({"name": name, "best": best, "avg": avg, "loops": loops, "runs": done, "error": None})
        except Exception as e:
            rows.append({"name": name, "best": None, "avg": None, "loops": 0, "runs": 0,
                         "error": f"{type(e).__name__}: {e}"})
    ok = sorted([r for r in rows if r["error"] is None], key=lambda r: r["best"])
    return ok, [r for r in rows if r["error"]]

def table(ok, failed, out=print):
    if ok:
        fastest = ok[0]["best"] or 1e-12
        slowest = ok[-1]["best"] or 1e-12
        out(f"\n{'#':<3}{'variant':<12}{'best':>12}{'avg':>12}{'vs fastest':>12}")
        for i, r in enumerate(ok, 1):
            rel = r["best"] / fastest if fastest else 1
            out(f"{i:<3}{r['name']:<12}{fmt(r['best']):>12}{fmt(r['avg']):>12}{rel:>11.2f}x")
        out("")
        for r in ok:
            n = max(1, round(BAR_WIDTH * r["best"] / slowest)) if slowest else 1
            out(f"{r['name']:<12}{'#' * n} {fmt(r['best'])}")
        if len(ok) > 1:
            out(f"\nWinner: {ok[0]['name']} ({ok[-1]['best'] / fastest:.2f}x faster than {ok[-1]['name']})")
    for r in failed:
        out(f"{r['name']}: failed, {r['error']}")

def read_block(label):
    print(f"{label} (finish with a line containing only END):")
    lines = []
    while len(lines) < 500:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def self_test():
    ok, failed = compare([("slow", "sum([i for i in range(2000)])"), ("fast", "sum(x)")],
                         setup="x = list(range(2000))", runs=3, time_cap=0.3)
    assert [r["name"] for r in ok] == ["fast", "slow"], ok
    assert not failed
    ok, failed = compare([("good", "1+1"), ("bad", "1/0")], runs=2, time_cap=0.1)
    assert len(ok) == 1 and failed and "ZeroDivisionError" in failed[0]["error"]
    ok, failed = compare([("a", "pass"), ("syn", "def(")], runs=2, time_cap=0.1)
    assert failed and "SyntaxError" in failed[0]["error"]
    t0 = time.perf_counter()
    compare([("sleepy", "import time; time.sleep(0.05)"), ("x", "pass")], runs=5, time_cap=0.2)
    assert time.perf_counter() - t0 < 2, "time cap not respected"
    try:
        compare([("only", "pass")]); assert False
    except ValueError:
        pass
    out = []
    table(*compare([("a", "pass"), ("b", "sum(range(100))")], runs=2, time_cap=0.1), out=out.append)
    assert any("Winner" in o for o in out)
    print("All self-tests passed.")

def main():
    print("=== Benchmark Comparer ===")
    if input("Run self-tests first? (y/N): ").strip().lower() == "y":
        self_test()
    raw = input(f"How many variants (2-{MAX_VARIANTS}) [2]: ").strip()
    n = int(raw) if raw.isdigit() and 2 <= int(raw) <= MAX_VARIANTS else 2
    setup = read_block("Shared setup code (can be empty)") or "pass"
    variants = []
    for i in range(n):
        name = input(f"Name for variant {i + 1} [{chr(65 + i)}]: ").strip()[:10] or chr(65 + i)
        variants.append((name, read_block(f"Code for {name}") or "pass"))
    raw = input(f"Runs per variant (1-{MAX_RUNS}) [5]: ").strip()
    runs = int(raw) if raw.isdigit() and 1 <= int(raw) <= MAX_RUNS else 5
    print(f"\nWARNING: this will actually RUN all {n} variants (about {TIME_CAP:.0f}s each max, "
          f"up to {MAX_LOOPS:,} loops per run). Only run code you trust.")
    if input("Run now? (y/N): ").strip().lower() != "y":
        print("Cancelled.")
        return
    try:
        table(*compare(variants, setup, runs))
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

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
    main()
