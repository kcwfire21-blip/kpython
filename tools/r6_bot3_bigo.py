# Big-O Estimator: times a function at growing input sizes and fits O(1), O(log n), O(n), O(n log n), O(n^2), O(2^n) with a text chart (by bot3)
import time, math

TIME_CAP = 5.0          # total seconds budget
PER_SIZE_CAP = 1.0      # stop growing once one size takes this long
MAX_SIZE = 2_000_000
MAX_POINTS = 16
MAX_SRC_BYTES = 50_000
HARD_CAP = 3.0         # KPython: hard cap for building data + one call at a size
class SizeTimeout(Exception):
    pass

def _kp_guarded(fn, cap):
    """KPython: run fn() but raise SizeTimeout once it runs longer than cap seconds (Stop still works too)."""
    import sys
    end = time.perf_counter() + cap
    old = sys.gettrace()
    def tr(frame, event, arg):
        if time.perf_counter() > end:
            raise SizeTimeout(f"one size took over {cap:.0f}s")
        return tr
    sys.settrace(tr)
    try:
        return fn()
    finally:
        sys.settrace(old)


MODELS = {
    "O(1)":       lambda n: 1.0,
    "O(log n)":   lambda n: math.log2(n) if n > 1 else 1.0,
    "O(n)":       lambda n: float(n),
    "O(n log n)": lambda n: n * math.log2(n) if n > 1 else 1.0,
    "O(n^2)":     lambda n: float(n) ** 2,
    "O(2^n)":     lambda n: 2.0 ** n if n < 1000 else float("inf"),
}

def measure(func, gen, n, reps=3):
    data = _kp_guarded(lambda: gen(n), HARD_CAP)
    t0 = time.perf_counter(); _kp_guarded(lambda: func(data), HARD_CAP); first = time.perf_counter() - t0
    if first > PER_SIZE_CAP:   # one call is already slow: report it, don't repeat
        return first
    best = float("inf")
    loops = 1
    while True:  # repeat fast calls so timing is meaningful
        t0 = time.perf_counter()
        for _ in range(loops):
            func(data)
        dt = time.perf_counter() - t0
        if dt > 0.005 or loops >= 10000:
            break
        loops *= 4
    best = dt / loops
    for _ in range(reps - 1):
        t0 = time.perf_counter()
        for _ in range(loops):
            func(data)
        best = min(best, (time.perf_counter() - t0) / loops)
    return best

def sizes_for(mode, start, step):
    n = start
    while n <= MAX_SIZE:
        yield n
        n = n * 2 if mode == "double" else n + step

def collect(func, gen, mode="double", start=16, step=2, time_cap=TIME_CAP):
    pts = []
    t_start = time.perf_counter()
    for n in sizes_for(mode, start, step):
        if len(pts) >= MAX_POINTS or time.perf_counter() - t_start > time_cap:
            break
        try:
            t = measure(func, gen, n)
        except SizeTimeout:
            break
        pts.append((n, t))
        if t > PER_SIZE_CAP:
            break
    return pts

def fit(pts):
    """Weighted least squares t = a + c*g(n), weights 1/t^2 (relative error). Returns sorted (err, name, c, a)."""
    res = []
    for name, g in MODELS.items():
        xs = [g(n) for n, _ in pts]
        if any(math.isinf(x) or x > 1e300 for x in xs):
            continue
        ys = [t for _, t in pts]
        ws = [1.0 / max(y, 1e-12) ** 2 for y in ys]
        if name == "O(1)":
            a = sum(w * y for w, y in zip(ws, ys)) / sum(ws); c = 0.0
        else:
            sw = sum(ws); sx = sum(w * x for w, x in zip(ws, xs)); sy = sum(w * y for w, y in zip(ws, ys))
            sxx = sum(w * x * x for w, x in zip(ws, xs)); sxy = sum(w * x * y for w, x, y in zip(ws, xs, ys))
            den = sw * sxx - sx * sx
            if den == 0:
                continue
            c = (sw * sxy - sx * sy) / den
            a = (sy - c * sx) / sw
            if c <= 0:          # negative growth isn't a valid fit
                continue
            if a < 0:           # refit through origin to avoid negative baseline
                a = 0.0; c = sxy / sxx
        err = math.sqrt(sum(((a + c * x) - y) ** 2 / max(y, 1e-12) ** 2 for x, y in zip(xs, ys)) / len(ys))
        res.append((err, name, c, a))
    res.sort()
    ts = [t for _, t in pts]
    if max(ts) / max(min(ts), 1e-12) < 1.6 and pts[-1][0] >= 8 * pts[0][0]:
        flat = [r for r in res if r[1] in ("O(1)", "O(log n)")]   # time barely grew: noise, not growth
        res = flat + [r for r in res if r not in flat]
    # prefer simpler model when errors are nearly tied
    order = list(MODELS)
    best = res[0]
    for r in res[1:]:
        if best[1] in ("O(1)", "O(log n)") and r[1] not in ("O(1)", "O(log n)"):
            break
        if r[0] <= best[0] * 1.15 + 0.02 and order.index(r[1]) < order.index(best[1]):
            best = r
    return best, res

def fmt(sec):
    for unit, f in (("s", 1), ("ms", 1e3), ("us", 1e6), ("ns", 1e9)):
        if sec * f >= 1 or unit == "ns":
            return f"{sec * f:.2f} {unit}"

def report(pts, out=print):
    best, res = fit(pts)
    mx = max(t for _, t in pts)
    out(f"\n{'n':>10}  time")
    for n, t in pts:
        bar = "#" * max(1, round(30 * t / mx))
        out(f"{n:>10}  {bar} {fmt(t)}")
    out("\nFit error by model (lower is better):")
    for err, name, c, a in res:
        out(f"  {name:<11} {err * 100:7.1f}%{'   <- best' if name == best[1] else ''}")
    out(f"\nEstimated complexity: {best[1]}")
    out("Note: this is an estimate from timings; noise, caching, and small sizes can mislead it.")
    return best[1]

def load_code(src):
    if len(src.encode()) > MAX_SRC_BYTES:
        raise ValueError("Code too large")
    ns = {"__name__": "__bigo__"}
    exec(compile(src, "<bigo>", "exec"), ns)
    if not callable(ns.get("func")) or not callable(ns.get("gen")):
        raise ValueError("Code must define func(data) and gen(n)")
    return ns["func"], ns["gen"]

def read_block():
    print("Define func(data) and gen(n). Finish with a line containing only END:")
    lines = []
    while len(lines) < 500:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

EXAMPLE = """# Example: is 'x in list' linear?
def gen(n):
    return list(range(n))
def func(data):
    return -1 in data"""

def self_test():
    quiet = lambda *a: None
    def check(func, gen, expect, **kw):
        got = report(collect(func, gen, time_cap=1.5, **kw), out=quiet)
        assert got in expect, (expect, got)
    check(lambda d: -1 in d, lambda n: list(range(n)), {"O(n)", "O(n log n)"}, start=1000)
    check(lambda d: d[0], lambda n: list(range(n)), {"O(1)", "O(log n)"}, start=1000)
    check(lambda d: [a + b for a in d for b in d], lambda n: list(range(n)), {"O(n^2)"}, start=16)
    def fib(k):
        return k if k < 2 else fib(k - 1) + fib(k - 2)
    check(fib, lambda n: n, {"O(2^n)"}, mode="step", start=10, step=2)
    pts = collect(lambda d: time.sleep(0.3), lambda n: n, time_cap=0.5)
    assert len(pts) <= 3, "time cap not respected"
    try:
        load_code("x = 1"); assert False
    except ValueError:
        pass
    print("All self-tests passed.")

def main():
    print("=== Big-O Estimator ===")
    if input("Run self-tests first? (y/N): ").strip().lower() in ("y", "yes"):
        self_test()
    print("\n" + EXAMPLE + "\n")
    src = read_block() or EXAMPLE
    try:
        func, gen = load_code(src)
    except Exception as e:
        print(f"Could not load code: {type(e).__name__}: {e}")
        return
    mode = "step" if input("Sizes: 1) doubling (default)  2) small steps, for exponential code: ").strip() == "2" else "double"
    raw = input("Starting size [16]: ").strip()
    start = min(int(raw), MAX_SIZE) if raw.isdigit() and int(raw) > 0 else 16
    print(f"\nWARNING: this will actually RUN your code many times "
          f"(up to {TIME_CAP:.0f}s total, sizes up to {MAX_SIZE:,}). Only run code you trust.")
    if input("Run now? (y/N): ").strip().lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    try:
        pts = collect(func, gen, mode, start, step=2)
        if len(pts) < 3:
            print("Not enough data points (code too slow for the caps). Try a smaller start size.")
            return
        report(pts)
    except Exception as e:
        print(f"Error while timing: {type(e).__name__}: {e}")

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
