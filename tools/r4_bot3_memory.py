# Memory Profiler: runs a script under tracemalloc and shows top allocations by line, peak usage, and a before/after diff (by bot3)
import os, sys
try:
    import tracemalloc
except ImportError:  # KPython: friendly message if this Pyodide build lacks it
    tracemalloc = None
    print("Memory profiler needs the tracemalloc module, which this Python build does not include.")

SAFE_ROOT = "/home/pyodide"
FNAME = "<memprof>"
MAX_SRC_BYTES = 200_000   # cap on script size
MAX_PASTE_LINES = 2000
TOP_N = 10

def safe_path(path):
    full = os.path.realpath(os.path.join(SAFE_ROOT, path))
    if not (full == SAFE_ROOT or full.startswith(SAFE_ROOT + os.sep)):
        raise PermissionError(f"Only files under {SAFE_ROOT} are allowed")
    return full

def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024

def profile_source(src, top=TOP_N):
    if len(src.encode()) > MAX_SRC_BYTES:
        raise ValueError(f"Script too large (max {MAX_SRC_BYTES // 1000} KB)")
    code = compile(src, FNAME, "exec")
    g = {"__name__": "__main__"}
    was = tracemalloc.is_tracing()
    if not was:
        tracemalloc.start()
    tracemalloc.reset_peak() if hasattr(tracemalloc, "reset_peak") else None
    flt = [tracemalloc.Filter(True, FNAME)]
    before = tracemalloc.take_snapshot().filter_traces(flt)
    base_cur, _ = tracemalloc.get_traced_memory()
    error = None
    try:
        exec(code, g)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    after = tracemalloc.take_snapshot().filter_traces(flt)
    cur, peak = tracemalloc.get_traced_memory()
    if not was:
        tracemalloc.stop()
    lines = src.splitlines()
    def text(ln):
        return lines[ln - 1].strip()[:60] if 0 < ln <= len(lines) else ""
    top_stats = [(s.traceback[0].lineno, s.size, s.count) for s in after.statistics("lineno")[:top]]
    diff = [(s.traceback[0].lineno, s.size_diff, s.count_diff)
            for s in after.compare_to(before, "lineno")[:top] if s.size_diff]
    return {"top": [(l, sz, c, text(l)) for l, sz, c in top_stats],
            "diff": [(l, sz, c, text(l)) for l, sz, c in diff],
            "peak": max(0, peak - base_cur), "net": cur - base_cur, "error": error, "globals": g}

def report(r, out=print):
    out(f"\nPeak extra memory during run: {human(r['peak'])}")
    out(f"Net memory still held after run: {human(r['net'])}")
    if r["error"]:
        out(f"Script raised: {r['error']}")
    out(f"\nTop allocations by line (still alive):")
    for l, sz, c, t in r["top"] or []:
        out(f"  line {l:4}  {human(sz):>10}  {c:6} blocks  {t}")
    if not r["top"]:
        out("  (none)")
    out("\nBefore/after diff:")
    for l, sz, c, t in r["diff"] or []:
        out(f"  line {l:4}  {'+' if sz > 0 else ''}{human(sz):>10}  {c:+6} blocks  {t}")
    if not r["diff"]:
        out("  (no change)")

def read_source():
    print("Load code from: 1) paste it  2) a file under /home/pyodide")
    if input("Choice [1]: ").strip() == "2":
        p = safe_path(input("File name (relative to /home/pyodide): ").strip())
        if os.path.getsize(p) > MAX_SRC_BYTES:
            raise ValueError("File too large")
        with open(p) as f:
            return f.read()
    print("Paste code; finish with a line containing only END:")
    lines = []
    while len(lines) < MAX_PASTE_LINES:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def self_test():
    r = profile_source("big = [0] * 200000\nsmall = 'x' * 10\ntmp = bytearray(500000)\ndel tmp\n")
    lines = [l for l, *_ in r["top"]]
    assert lines and lines[0] == 1, r["top"]          # list is biggest survivor
    assert 3 not in lines, r["top"]                   # deleted bytearray not alive
    assert r["peak"] >= 500000, r["peak"]             # but counted in peak
    assert any(l == 1 and sz > 0 for l, sz, *_ in r["diff"]), r["diff"]
    assert r["error"] is None
    e = profile_source("x = [1]*10\n1/0\n")
    assert "ZeroDivisionError" in e["error"]
    try:
        profile_source("#" * (MAX_SRC_BYTES + 1)); assert False
    except ValueError:
        pass
    try:
        safe_path("../../etc/passwd"); assert False
    except (PermissionError, ValueError):
        pass
    assert not tracemalloc.is_tracing()
    print("All self-tests passed.")

def main():
    print("=== Memory Profiler ===")
    if input("Run self-tests first? (y/N): ").strip().lower() in ("y", "yes"):
        self_test()
    try:
        src = read_source()
        compile(src, FNAME, "exec")
    except Exception as e:
        print(f"Could not load code: {type(e).__name__}: {e}")
        return
    print("\nWARNING: this will actually RUN the code you entered. Only profile code you trust.")
    if input("Run it now? (y/N): ").strip().lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    try:
        report(profile_source(src))
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
