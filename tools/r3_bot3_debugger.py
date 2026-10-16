# Step Debugger: run Python code line by line with sys.settrace (step, next, continue, line breakpoints, locals) (by bot3)
import sys, os

SAFE_ROOT = "/home/pyodide"
FNAME = "<debug>"
HELP = """Commands:
  s  step (go into function calls)    n  next (step over calls)
  c  continue to next breakpoint      b N  set breakpoint at line N
  d N  delete breakpoint              l  list code around current line
  p  print locals                     p EXPR  evaluate expression
  q  quit debugging                   h  this help"""

class Quit(Exception):
    pass

class Debugger:
    def __init__(self, source, ask=input, out=print):
        self.src = source
        self.lines = source.splitlines()
        self.ask, self.out = ask, out
        self.breaks = set()
        self.mode = "step"      # step | next | continue
        self.next_frame = None
        self.stops = []         # (line, locals snapshot) for tests

    def show(self, lineno, around=2):
        lo, hi = max(1, lineno - around), min(len(self.lines), lineno + around)
        for i in range(lo, hi + 1):
            mark = "->" if i == lineno else ("B " if i in self.breaks else "  ")
            self.out(f"{mark}{i:4} {self.lines[i - 1]}")

    def fmt_locals(self, frame):
        names = {k: v for k, v in frame.f_locals.items() if not k.startswith("__") and k != "Quit"}
        if not names:
            return "  (no locals)"
        return "\n".join(f"  {k} = {v!r}"[:200] for k, v in names.items())

    def should_stop(self, frame):
        line = frame.f_lineno
        if line in self.breaks:
            return True
        if self.mode == "step":
            return True
        if self.mode == "next":
            f = frame
            while f is not None:  # stop in same frame or any caller of it
                if f is self.next_frame:
                    return frame is self.next_frame or self.next_frame not in self._chain(frame)[1:]
                f = f.f_back
            return True  # returned out of the frame
        return False

    @staticmethod
    def _chain(frame):
        out = []
        while frame is not None:
            out.append(frame)
            frame = frame.f_back
        return out

    def trace(self, frame, event, arg):
        if frame.f_code.co_filename != FNAME:
            return None
        if event == "line" and self.should_stop(frame):
            self.interact(frame)
        return self.trace

    def interact(self, frame):
        line = frame.f_lineno
        self.stops.append((line, dict((k, v) for k, v in frame.f_locals.items() if not k.startswith("__"))))
        self.out(f"\n[{frame.f_code.co_name}] line {line}")
        self.show(line, 0)
        self.out(self.fmt_locals(frame))
        while True:
            try:
                cmd = self.ask("(dbg) ").strip()
            except (KeyboardInterrupt, EOFError):
                raise Quit()   # KPython: Cancel quits the debugger and the tracer is switched off
            if cmd in ("", "s"):
                self.mode = "step"; return
            if cmd == "n":
                self.mode, self.next_frame = "next", frame; return
            if cmd == "c":
                self.mode = "continue"; return
            if cmd == "q":
                raise Quit()
            if cmd == "h":
                self.out(HELP)
            elif cmd == "l":
                self.show(line, 4)
            elif cmd == "p":
                self.out(self.fmt_locals(frame))
            elif cmd.startswith("p "):
                try:
                    self.out(repr(eval(cmd[2:], frame.f_globals, frame.f_locals)))
                except Exception as e:
                    self.out(f"  {type(e).__name__}: {e}")
            elif cmd.startswith(("b ", "d ")):
                try:
                    n = int(cmd[2:])
                    (self.breaks.add if cmd[0] == "b" else self.breaks.discard)(n)
                    self.out(f"  breakpoints: {sorted(self.breaks) or 'none'}")
                except ValueError:
                    self.out("  usage: b LINE / d LINE")
            else:
                self.out("  unknown command, type h")

    def run(self, start_mode="step"):
        self.mode = start_mode
        code = compile(self.src, FNAME, "exec")
        g = {"__name__": "__main__"}
        sys.settrace(self.trace)
        try:
            exec(code, g)
            self.out("\n[program finished]")
        except Quit:
            self.out("\n[debugging stopped]")
        except Exception as e:
            tb = e.__traceback__
            ln = None
            while tb:
                if tb.tb_frame.f_code.co_filename == FNAME:
                    ln = tb.tb_lineno
                tb = tb.tb_next
            self.out(f"\n[error] {type(e).__name__}: {e}" + (f" (line {ln})" if ln else ""))
        finally:
            sys.settrace(None)
        return g

def safe_path(path):
    full = os.path.realpath(os.path.join(SAFE_ROOT, path))
    if not (full == SAFE_ROOT or full.startswith(SAFE_ROOT + os.sep)):
        raise PermissionError(f"Only files under {SAFE_ROOT} are allowed")
    return full

def read_source():
    print("Load code from: 1) type/paste it  2) a file under /home/pyodide")
    while True:
        ch = input("Choice [1]: ").strip()
        if ch in ("", "1", "2"): break
        print("Pick 1 or 2.")
    if ch == "2":
        name = input("File name (relative to /home/pyodide): ").strip()
        with open(safe_path(name)) as f:
            return f.read()
    print("Paste code; finish with a line containing only END:")
    lines = []
    while True:
        try: line = input()
        except (KeyboardInterrupt, EOFError): break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def self_test():
    src = "def sq(x):\n    y = x * x\n    return y\na = 3\nb = sq(a)\nc = b + 1\n"
    # step: should enter sq
    cmds = iter(["s"] * 20)
    d = Debugger(src, ask=lambda _: next(cmds), out=lambda *a: None)
    g = d.run()
    assert g["c"] == 10, g
    assert 2 in [l for l, _ in d.stops], d.stops
    # next: should step over sq (never stop on line 2)
    cmds = iter(["n"] * 20)
    d = Debugger(src, ask=lambda _: next(cmds), out=lambda *a: None)
    d.run()
    assert 2 not in [l for l, _ in d.stops], d.stops
    # breakpoint + continue: run free, stop only at line 6, locals visible
    cmds = iter(["c"] * 5)
    d = Debugger(src, ask=lambda _: next(cmds), out=lambda *a: None)
    d.breaks.add(6)
    d.run(start_mode="continue")
    assert [l for l, _ in d.stops] == [6] and d.stops[0][1]["b"] == 9, d.stops
    # quit and error handling
    cmds = iter(["q"])
    out = []
    Debugger(src, ask=lambda _: next(cmds), out=out.append).run()
    assert any("stopped" in o for o in out)
    out = []
    Debugger("x = 1\ny = x / 0\n", ask=lambda _: "c", out=out.append).run(start_mode="continue")
    assert any("ZeroDivisionError" in o and "line 2" in o for o in out), out
    # path safety
    try:
        safe_path("../../etc/passwd"); assert False
    except (PermissionError, ValueError):
        pass
    assert sys.gettrace() is None
    print("All self-tests passed.")

def main():
    print("=== Step Debugger ===")
    if input("Run self-tests first? (y/N): ").strip().lower() in ("y", "yes"):
        self_test()
    try:
        src = read_source()
        compile(src, FNAME, "exec")
    except Exception as e:
        print(f"Could not load code: {type(e).__name__}: {e}")
        return
    print("\nWARNING: this will actually RUN the code you entered. Only debug code you trust.")
    if input("Run it under the debugger? (y/N): ").strip().lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    print(HELP)
    Debugger(src).run()

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
