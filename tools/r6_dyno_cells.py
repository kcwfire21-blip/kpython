# Dyno: notebook-style cell runner - splits a script on '# %%' markers; run one cell, all cells, or cells up to N in a shared namespace (confirms first), shows output and timing, can reset. Stdlib only.
import os, io, sys, time, traceback, contextlib

BASE = "/home/pyodide"  # KPython: fixed, no env override
MAX_BYTES = 500_000

try:
    kp_safe_path
except NameError:
    def kp_safe_path(p):
        full = os.path.realpath(os.path.join(BASE, p))
        if full != BASE and not full.startswith(BASE + os.sep):
            raise ValueError("Only paths under " + BASE + " are allowed.")
        return full

def split_cells(src):
    cells, cur, title = [], [], "cell 1"
    for line in src.splitlines():
        if line.strip().startswith("# %%"):
            if cur and any(l.strip() for l in cur):
                cells.append((title, "\n".join(cur)))
            title = line.strip()[4:].strip() or f"cell {len(cells) + 1}"
            cur = []
        else:
            cur.append(line)
    if cur and any(l.strip() for l in cur):
        cells.append((title, "\n".join(cur)))
    return cells

def new_ns():
    return {"__name__": "__cells__"}

def run_cell(code, ns, idx):
    buf = io.StringIO()
    t0 = time.perf_counter()
    ok = True
    try:
        real_out = sys.stdout
        def _cell_input(prompt=""):  # KPython: input() inside a cell shows the output so far and the prompt
            real_out.write(buf.getvalue()); buf.seek(0); buf.truncate()
            with contextlib.redirect_stdout(real_out):
                import builtins as _b
                return _b.input(prompt)
        ns.setdefault("input", _cell_input)
        with contextlib.redirect_stdout(buf):
            exec(compile(code, f"<cell {idx}>", "exec"), ns)
    except Exception:
        ok = False
        buf.write(traceback.format_exc(limit=-3))
    return ok, buf.getvalue(), (time.perf_counter() - t0) * 1000

def run_range(cells, ns, idxs):
    results = []
    for i in idxs:
        title, code = cells[i]
        ok, out, ms = run_cell(code, ns, i + 1)
        results.append((i + 1, title, ok, out, ms))
        if not ok:
            break
    return results

def show(results):
    for n, title, ok, out, ms in results:
        print(f"\n[{n}] {title}  {'OK' if ok else 'ERROR'}  {ms:.1f} ms")
        print(out.rstrip() or "(no output)")

def self_test():
    src = "x = 1\n# %% setup\ny = x + 1\nprint(y)\n# %% boom\n1/0\n# %%\nprint('never')\n"
    cells = split_cells(src)
    assert [t for t, _ in cells] == ["cell 1", "setup", "boom", "cell 4"], cells
    ns = new_ns()
    r = run_range(cells, ns, range(len(cells)))
    assert len(r) == 3 and r[1][3].strip() == "2" and not r[2][2], r
    assert ns["y"] == 2
    ns = new_ns()
    ok, out, _ = run_cell(cells[1][1], ns, 2)
    assert not ok and "NameError" in out
    try:
        kp_safe_path("../../etc/passwd"); assert False
    except ValueError:
        pass
    print("self-tests passed")

def main():
    print("== Cell Runner ==")
    p = input("Script path under " + BASE + " (t = self-test): ").strip()
    if p == "t":
        self_test(); return
    try:
        path = kp_safe_path(p)
        if not path.endswith(".py") or not os.path.isfile(path):
            raise ValueError("Not a .py file.")
        if os.path.getsize(path) > MAX_BYTES:
            raise ValueError("File over 500KB.")
        with open(path) as f:
            cells = split_cells(f.read())
    except ValueError as e:
        print("Error:", e); return
    if not cells:
        print("No cells found."); return
    ns = new_ns()
    while True:
        print()
        for i, (t, c) in enumerate(cells, 1):
            print(f" {i}. {t}  ({len(c.splitlines())} lines)")
        cmd = input("Run: number | a=all | u N=up to N | r=reset | q=quit: ").strip().lower()
        if cmd == "q":
            break
        if cmd == "r":
            ns = new_ns(); print("Namespace reset."); continue
        try:
            if cmd == "a":
                idxs = range(len(cells))
            elif cmd.startswith("u"):
                n = int(cmd[1:].strip()); idxs = range(min(n, len(cells)))
            else:
                n = int(cmd); assert 1 <= n <= len(cells); idxs = [n - 1]
        except (ValueError, AssertionError):
            print("Invalid choice."); continue
        if input(f"Run {len(idxs)} cell(s)? (y/n): ").strip().lower() != "y":
            print("Cancelled."); continue
        show(run_range(cells, ns, idxs))

# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse", "split_cells", "merge3", "parse_requirements", "scan_setup", "parse_cron", "parse_any", "analyze_lines"):
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
        return _kp_b.kp_safe_path(r) if hasattr(_kp_b, "kp_safe_path") and isinstance(r, str) and r.startswith("/") and all(globals().get(v, "/home/pyodide") == "/home/pyodide" for v in ("BASE", "BASE_DIR", "SAFE_ROOT", "HOME")) else r
    return w
for _n in ("safe_path", "_safe_path", "_safe"):
    if callable(globals().get(_n)): globals()[_n] = _kp_wrap(globals()[_n])

if __name__ == "__main__":
    main()
