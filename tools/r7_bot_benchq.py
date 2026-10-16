# Benchmark with reliable 'q' cancel (by bot, KPython round 7). Fixes the v5 "bench q" regression:
# 'q' now cancels at EVERY prompt (menu, code blocks, numbers) and always prints a message.
# Pure Python, no network, no files written. Run with --test for the self-test.
import sys, io, timeit, cProfile, pstats, builtins
MAX_LOOPS, MAX_RUNS, MAX_CODE, MAX_LINES = 100_000, 20, 200_000, 500
QUIT = ("q", "quit", "exit")

class Cancelled(Exception):
    pass

def ask(prompt, inp=None):
    inp = inp or builtins.input
    try:
        raw = inp(prompt)
    except (EOFError, KeyboardInterrupt):
        raise Cancelled()
    raw = "" if raw is None else str(raw)   # Pyodide can hand back None when a prompt is dismissed
    if raw.strip().lower() in QUIT:
        raise Cancelled()
    return raw

def read_code(label, inp=None):
    print(f"{label} (multi-line ok; empty line to finish, q to cancel):")
    lines = []
    while len(lines) < MAX_LINES:
        line = ask("", inp)
        if line == "":
            break
        lines.append(line)
    code = "\n".join(lines) or "pass"
    if len(code) > MAX_CODE:
        raise ValueError("code too big")
    compile(code, "<snippet>", "exec")
    return code

def ask_int(prompt, default, hi, inp=None):
    while True:
        raw = ask(f"{prompt} [{default}]: ", inp).strip()
        if not raw:
            return default
        if raw.isdigit() and 0 < int(raw) <= hi:
            return int(raw)
        print(f"Enter a whole number 1-{hi}, or q to cancel.")

def bench(code, setup="pass", number=1000, repeat=5):
    number, repeat = max(1, min(number, MAX_LOOPS)), max(1, min(repeat, MAX_RUNS))
    runs = [r / number for r in timeit.Timer(code, setup=setup).repeat(repeat=repeat, number=number)]
    return min(runs), sum(runs) / len(runs)

def fmt(sec):
    for unit, f in (("s", 1), ("ms", 1e3), ("us", 1e6), ("ns", 1e9)):
        if sec * f >= 1 or unit == "ns":
            return f"{sec * f:.3f} {unit}"

def profile_code(code, setup="pass", top=15):
    ns = {}
    exec(setup, ns)
    pr = cProfile.Profile(); pr.enable()
    try:
        exec(code, ns)
    finally:
        pr.disable()
    out = io.StringIO()
    pstats.Stats(pr, stream=out).sort_stats("cumulative").print_stats(top)
    return out.getvalue()

def main(inp=None):
    print("Note: this runs the code you give it. Type q at any prompt to cancel.")
    while True:
        print("\n=== Profiler & Benchmark ===\n1) Time a snippet\n2) Profile code (cProfile)\n3) Compare two snippets\nq) Quit")
        try:
            c = ask("Choice: ", inp).strip().lower()
        except Cancelled:
            print("Bye.")
            return
        try:
            if c == "1":
                setup = read_code("Setup code", inp); code = read_code("Snippet to time", inp)
                n = ask_int("Loops per run", 1000, MAX_LOOPS, inp); r = ask_int("Runs", 5, MAX_RUNS, inp)
                best, avg = bench(code, setup, n, r)
                print(f"Best: {fmt(best)}  Avg: {fmt(avg)}  per loop ({r} runs x {n})")
            elif c == "2":
                setup = read_code("Setup code (define functions here)", inp)
                code = read_code("Code to profile, e.g. my_func(1000)", inp)
                print(profile_code(code, setup))
            elif c == "3":
                setup = read_code("Shared setup code", inp)
                a = read_code("Snippet A", inp); b = read_code("Snippet B", inp)
                n = ask_int("Loops per run", 1000, MAX_LOOPS, inp); r = ask_int("Runs", 5, MAX_RUNS, inp)
                ba, aa = bench(a, setup, n, r); bb, ab = bench(b, setup, n, r)
                print(f"{'':6}{'best':>14}{'avg':>14}")
                print(f"{'A':6}{fmt(ba):>14}{fmt(aa):>14}")
                print(f"{'B':6}{fmt(bb):>14}{fmt(ab):>14}")
                if min(ba, bb) > 0:
                    fast, slow = ("A", "B") if ba <= bb else ("B", "A")
                    print(f"{fast} is {max(ba, bb) / min(ba, bb):.2f}x faster than {slow}")
            else:
                print("Pick 1, 2, 3, or q.")
        except Cancelled:
            print("Cancelled.")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

def _run(lines):
    it = iter(lines)
    def inp(prompt=""):
        print(prompt, end="")
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        main(inp)
    finally:
        sys.stdout = old
    return buf.getvalue()

def self_test():
    cases = [
        (["q"], "Bye."),                                  # q at menu (old: printed nothing)
        (["Q "], "Bye."),
        (["1", "q"], "Cancelled."),                       # q in setup block (old: ran 'q' as code)
        (["1", "", "x=1", "q"], "Cancelled."),            # q in snippet block
        (["1", "", "", "q"], "Cancelled."),               # q at loops prompt
        (["3", "", "", "", "100", "q"], "Cancelled."),    # q at runs prompt
        (["1", "", "", "abc", "q"], "Enter a whole number"),
        ([], "Bye."),                                     # EOF / closed input never prints nothing
        ([None], "Bye."),
        (["1", "", "1+1", "", "10", "2", "q"], "Best:"),
        (["3", "", "sum(range(50))", "", "pass", "", "10", "2", "q"], "faster than"),
        (["2", "def f(): return 1", "", "f()", "", "q"], "function calls"),
        (["1", "", "def(", "", "q"], "SyntaxError"),
        (["9", "q"], "Pick 1, 2, 3, or q."),
    ]
    for lines, want in cases:
        out = _run(lines)
        assert out.strip(), f"printed nothing for {lines!r}"
        assert want in out, f"{lines!r}: expected {want!r} in output:\n{out}"
        print(f"ok  {lines!r} -> {want!r}")
    assert bench("pass", number=10, repeat=2)[0] >= 0
    assert fmt(0.5).endswith(" ms") and fmt(2).endswith(" s")
    print(f"All {len(cases)} bench_q self-tests passed.")


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    self_test() if "--test" in sys.argv else main()
