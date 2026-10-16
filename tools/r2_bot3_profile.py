# Profiler & Benchmark: time snippets with timeit, profile code with cProfile (top 15 cumulative), compare two snippets (by bot3)
import timeit, cProfile, pstats, io
MAX_LOOPS, MAX_RUNS, MAX_CODE = 100_000, 20, 200_000
print("Note: this runs the code you give it. Tap Stop if it hangs.")

def read_code(label):
    print(f"{label} (multi-line ok; finish with an empty line):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines) or "pass"

def bench(code, setup="pass", number=1000, repeat=5):
    number, repeat = min(number, MAX_LOOPS), min(repeat, MAX_RUNS)
    if len(code) + len(setup) > MAX_CODE: raise ValueError("code too big")
    t = timeit.Timer(code, setup=setup)
    runs = [r / number for r in t.repeat(repeat=repeat, number=number)]
    return min(runs), sum(runs) / len(runs)

def fmt(sec):
    for unit, f in (("s", 1), ("ms", 1e3), ("us", 1e6), ("ns", 1e9)):
        if sec * f >= 1 or unit == "ns":
            return f"{sec * f:.3f} {unit}"

def profile_code(code, setup="pass", top=15):
    if len(code) + len(setup) > MAX_CODE: raise ValueError("code too big")
    ns = {}
    exec(setup, ns)
    pr = cProfile.Profile()
    pr.enable()
    try:
        exec(code, ns)
    finally:
        pr.disable()
    out = io.StringIO()
    pstats.Stats(pr, stream=out).sort_stats("cumulative").print_stats(top)
    return out.getvalue()

def ask_int(prompt, default):
    raw = input(f"{prompt} [{default}]: ").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else default

def main():
    while True:
        print("\n=== Profiler & Benchmark ===\n1) Time a snippet\n2) Profile code (cProfile)\n3) Compare two snippets\nq) Quit")
        c = input("Choice: ").strip().lower()
        if c == "q":
            break
        try:
            if c == "1":
                setup = read_code("Setup code")
                code = read_code("Snippet to time")
                n = ask_int("Loops per run", 1000); r = ask_int("Runs", 5)
                best, avg = bench(code, setup, n, r)
                print(f"Best: {fmt(best)}  Avg: {fmt(avg)}  per loop ({r} runs x {n})")
            elif c == "2":
                setup = read_code("Setup code (define functions here)")
                code = read_code("Code to profile, e.g. my_func(1000)")
                print(profile_code(code, setup))
            elif c == "3":
                setup = read_code("Shared setup code")
                a = read_code("Snippet A"); b = read_code("Snippet B")
                n = ask_int("Loops per run", 1000); r = ask_int("Runs", 5)
                ba, aa = bench(a, setup, n, r); bb, ab = bench(b, setup, n, r)
                print(f"{'':6}{'best':>14}{'avg':>14}")
                print(f"{'A':6}{fmt(ba):>14}{fmt(aa):>14}")
                print(f"{'B':6}{fmt(bb):>14}{fmt(ab):>14}")
                if min(ba, bb) > 0:
                    fast, slow = ("A", "B") if ba <= bb else ("B", "A")
                    print(f"{fast} is {max(ba, bb) / min(ba, bb):.2f}x faster than {slow}")
            else:
                print("Pick 1, 2, 3, or q.")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
