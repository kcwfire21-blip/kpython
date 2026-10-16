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
    # KPython (Drop r7): cells don't get the app's kp_* bridges, and can't replace them for other tools
    import builtins
    return {"__name__": "__cells__", "__builtins__": {k: v for k, v in vars(builtins).items() if not k.startswith("kp_")}}

CELL_OUT_MAX = 200_000   # KPython: cap captured output per cell
CELL_TIMEOUT = 60.0      # KPython: per-cell time limit (Python-level code); Stop always works too

class _CapBuf(io.StringIO):
    def __init__(self):
        super().__init__(); self.cut = False
    def write(self, s):
        if self.tell() >= CELL_OUT_MAX:
            self.cut = True; return len(s)
        return super().write(s[:CELL_OUT_MAX - self.tell()])

class CellTimeout(Exception):
    pass

def run_cell(code, ns, idx, timeout=None):
    import builtins
    buf = _CapBuf()
    t0 = time.perf_counter()
    ok = True
    real_out = sys.stdout
    def _cell_input(prompt=""):  # KPython: show this cell's output so far, then the prompt
        real_out.write(buf.getvalue()); buf.seek(0); buf.truncate()
        with contextlib.redirect_stdout(real_out):
            return builtins.input(prompt)
    ns["__builtins__"]["input"] = _cell_input if isinstance(ns.get("__builtins__"), dict) else None
    if not isinstance(ns.get("__builtins__"), dict): ns["input"] = _cell_input
    deadline = t0 + (CELL_TIMEOUT if timeout is None else timeout)
    def tr(frame, event, arg):
        if time.perf_counter() > deadline:
            raise CellTimeout(f"cell took longer than {deadline - t0:.0f}s")
        return tr
    old = sys.gettrace()
    try:
        with contextlib.redirect_stdout(buf):
            sys.settrace(tr)
            try:
                exec(compile(code, f"<cell {idx}>", "exec"), ns)
            finally:
                sys.settrace(old)
    except KeyboardInterrupt:
        real_out.write(buf.getvalue()); raise          # Stop / Cancel: show what we have, then stop
    except SystemExit as e:
        ok = False; buf.write(f"exit() was called in this cell (code {e.code}); the cell runner keeps going.\n")
    except CellTimeout as e:
        ok = False; buf.write(f"Stopped: {e}.\n")
    except Exception:
        ok = False
        et, ev, tb = sys.exc_info()
        frames = [f for f in traceback.extract_tb(tb) if f.filename.startswith("<cell")]  # KPython: hide the runner's own frames
        buf.write("Traceback (most recent call last):\n" + "".join(traceback.format_list(frames)) + "".join(traceback.format_exception_only(et, ev)))
    out = buf.getvalue() + ("\n…[output truncated]" if buf.cut else "")
    return ok, out, (time.perf_counter() - t0) * 1000

def run_range(cells, ns, idxs):
    results = []
    for i in idxs:
        title, code = cells[i]
        ok, out, ms = run_cell(code, ns, i + 1)
        results.append((i + 1, title, ok, out, ms))
        if not ok:
            break
    return results

def cells_to_src(cells):
    return "\n".join(f"# %% {t}\n{c.rstrip()}\n" for t, c in cells)

def edit_cells(cells, path):
    """KPython: add, delete, reorder cells; w writes them back to the file. Returns True if unsaved edits remain."""
    dirty = False
    while True:
        for i, (t, c) in enumerate(cells, 1):
            print(f" {i}. {t}  ({len(c.splitlines())} lines)")
        s = input("Edit: + N = add after N (0 = top) | d N = delete | m N M = move N to M | w = write file | blank = back: ").strip().lower()
        if not s or s in ("q", "b"):
            return dirty
        p = s.replace("+", "+ ").split()
        try:
            if p[0] == "w":
                if input(f"Write {len(cells)} cell(s) to {path}? (y/N): ").strip().lower() in ("y", "yes"):
                    text = cells_to_src(cells)
                    if len(text) > MAX_BYTES: raise ValueError("over 500KB")
                    tmp = path + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f: f.write(text)
                    os.replace(tmp, path); print("Written."); dirty = False
            elif p[0] == "+" and len(p) == 2:
                n = int(p[1])
                if not 0 <= n <= len(cells): raise ValueError
                title = input("Cell title: ").strip() or f"cell {len(cells) + 1}"
                print("Type or paste the cell code, END on its own line to finish:")
                lines = []
                while True:
                    try: l = input()
                    except (KeyboardInterrupt, EOFError): break
                    if l.strip() == "END": break
                    lines.append(l)
                cells.insert(n, (title, "\n".join(lines))); dirty = True
            elif p[0] == "d" and len(p) == 2:
                n = int(p[1])
                if not 1 <= n <= len(cells): raise ValueError
                if input(f"Delete cell {n} ({cells[n-1][0]})? (y/N): ").strip().lower() in ("y", "yes"):
                    cells.pop(n - 1); dirty = True
            elif p[0] == "m" and len(p) == 3:
                a, b = int(p[1]), int(p[2])
                if not (1 <= a <= len(cells) and 1 <= b <= len(cells)): raise ValueError
                cells.insert(b - 1, cells.pop(a - 1)); dirty = True
            else:
                raise ValueError
        except (ValueError, OSError) as e:
            print(f"Use + N, d N, m N M, w, or blank. Cells are numbered 1-{len(cells)}." + (f" ({e})" if str(e) else ""))
        if not cells:
            return dirty

def cells_to_src(cells):
    return "\n".join(f"# %% {t}\n{c.rstrip()}\n" for t, c in cells)

def edit_cells(cells, path):
    """KPython: add, delete, reorder cells; w writes them back to the file. Returns True if unsaved edits remain."""
    dirty = False
    while True:
        for i, (t, c) in enumerate(cells, 1):
            print(f" {i}. {t}  ({len(c.splitlines())} lines)")
        s = input("Edit: + N = add after N (0 = top) | d N = delete | m N M = move N to M | w = write file | blank = back: ").strip().lower()
        if not s or s in ("q", "b"):
            return dirty
        p = s.replace("+", "+ ").split()
        try:
            if p[0] == "w":
                if input(f"Write {len(cells)} cell(s) to {path}? (y/N): ").strip().lower() in ("y", "yes"):
                    text = cells_to_src(cells)
                    if len(text) > MAX_BYTES: raise ValueError("over 500KB")
                    tmp = path + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f: f.write(text)
                    os.replace(tmp, path); print("Written."); dirty = False
            elif p[0] == "+" and len(p) == 2:
                n = int(p[1])
                if not 0 <= n <= len(cells): raise ValueError
                title = input("Cell title: ").strip() or f"cell {len(cells) + 1}"
                print("Type or paste the cell code, END on its own line to finish:")
                lines = []
                while True:
                    try: l = input()
                    except (KeyboardInterrupt, EOFError): break
                    if l.strip() == "END": break
                    lines.append(l)
                cells.insert(n, (title, "\n".join(lines))); dirty = True
            elif p[0] == "d" and len(p) == 2:
                n = int(p[1])
                if not 1 <= n <= len(cells): raise ValueError
                if input(f"Delete cell {n} ({cells[n-1][0]})? (y/N): ").strip().lower() in ("y", "yes"):
                    cells.pop(n - 1); dirty = True
            elif p[0] == "m" and len(p) == 3:
                a, b = int(p[1]), int(p[2])
                if not (1 <= a <= len(cells) and 1 <= b <= len(cells)): raise ValueError
                cells.insert(b - 1, cells.pop(a - 1)); dirty = True
            else:
                raise ValueError
        except (ValueError, OSError) as e:
            print(f"Use + N, d N, m N M, w, or blank. Cells are numbered 1-{len(cells)}." + (f" ({e})" if str(e) else ""))
        if not cells:
            return dirty

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
    assert "run_cell" not in out and "<cell 2>" in out, out
    c2 = [("a", "x = 1"), ("b", "y = 2")]
    assert [(t, x.strip()) for t, x in split_cells(cells_to_src(c2))] == c2
    assert "run_cell" not in out and "<cell 2>" in out, out
    c2 = [("a", "x = 1"), ("b", "y = 2")]
    assert [(t, x.strip()) for t, x in split_cells(cells_to_src(c2))] == c2
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
        with open(path, encoding="utf-8", errors="replace") as f:
            cells = split_cells(f.read())
    except ValueError as e:
        print("Error:", e); return
    if not cells:
        print("No cells found."); return
    ns = new_ns(); dirty = False
    while True:
        print()
        for i, (t, c) in enumerate(cells, 1):
            print(f" {i}. {t}  ({len(c.splitlines())} lines)")
        cmd = input("Run: number | a=all | u N=up to N | r=reset | e=edit cells | q=quit (Stop interrupts a cell): ").strip().lower()
        if cmd in ("q", "quit", ""):
            if dirty and input("Cell edits aren't written to the file. Quit anyway? (y/N): ").strip().lower() not in ("y", "yes"):
                continue
            break
        if cmd == "e":
            dirty = edit_cells(cells, path) or dirty
            if not cells: print("No cells left."); break
            continue
        if cmd == "r":
            ns = new_ns(); print("Namespace reset."); continue
        try:
            if cmd == "a":
                idxs = range(len(cells))
            elif cmd.startswith("u"):
                n = int(cmd[1:].strip())
                if n < 1: raise ValueError
                idxs = range(min(n, len(cells)))
            else:
                n = int(cmd)
                if not 1 <= n <= len(cells): raise ValueError
                idxs = [n - 1]
        except ValueError:
            print(f"Pick 1-{len(cells)}, a, u N, r or q."); continue
        if input(f"Run {len(idxs)} cell(s)? (y/N): ").strip().lower() not in ("y", "yes"):
            print("Cancelled."); continue
        show(run_range(cells, ns, idxs))

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
