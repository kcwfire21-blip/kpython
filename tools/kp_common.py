"""KPython shared helpers for the Dev tools (v9).

* Input helpers with one convention for every menu (Forlor's r7 UX review):
  q / quit exits, blank goes back, Cancel never prints a traceback, y/N defaults to No.
* harden(): one shared copy of the size caps and path checks that used to be pasted into
  every tool (Drop's r7 review). Paths are checked BEFORE the tool's own resolver runs,
  and again on the result.
"""
import builtins, functools

MAX_TEXT = 500_000
HOME = "/home/pyodide"

# ---------------- input helpers ----------------
def ask(prompt=""):
    """input() that returns None on Cancel/EOF instead of raising."""
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return None

def yes(prompt, default=False):
    """y/N question. Only 'y' or 'yes' (any case) means yes; Cancel means the default (No)."""
    a = ask(prompt + (" (Y/n): " if default else " (y/N): "))
    if a is None or a == "":
        return default
    return a.lower() in ("y", "yes")

def is_quit(a):
    return a is None or a.lower() in ("q", "quit", "exit")

def pick_index(prompt, n):
    """Ask for a 1-based number up to n. Returns a 0-based index, or None for blank/q/Cancel."""
    while True:
        a = ask(f"{prompt} (1-{n}, blank = back): ")
        if not a or is_quit(a):
            return None
        if a.isdigit() and 1 <= int(a) <= n:
            return int(a) - 1
        print(f"Enter a number 1-{n}, or press Enter to go back.")

def read_paste(end="END", prompt=None):
    """Read pasted lines until END (or a lone '.'), blank-free Cancel/EOF also finishes."""
    if prompt:
        print(prompt)
    lines = []
    while True:
        try:
            l = input("")
        except (KeyboardInterrupt, EOFError):
            break
        if l.strip() in (end, "."):
            break
        lines.append(l)
    return "\n".join(lines)

# ---------------- shared hardening ----------------
CAP_NAMES = ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses",
             "b64dec", "hexdec", "render", "measure", "profile_source", "scan_text", "convert", "parse",
             "explain", "gen_tests", "scan_code", "to_fstrings", "extract", "inline", "split_cells", "merge3",
             "parse_requirements", "scan_setup", "parse_cron", "parse_any", "analyze_lines", "md_to_html", "coverage_report")
PATH_NAMES = ("safe_path", "_safe_path", "_safe")
BASE_VARS = ("BASE", "BASE_DIR", "SAFE_ROOT", "HOME")

def cap(fn, limit=MAX_TEXT):
    @functools.wraps(fn)
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, (str, bytes, bytearray)) and len(x) > limit:
                raise ValueError(f"input too big (max {limit // 1000} KB)")
            if isinstance(x, (list, tuple)) and (len(x) > limit // 10 or sum(len(i) for i in x if isinstance(i, (str, bytes))) > limit):
                raise ValueError(f"input too big (max {limit // 1000} KB)")
        return fn(*a, **k)
    return w

def _check(p):
    sp = getattr(builtins, "kp_safe_path", None)
    if sp is None:
        import sys
        if sys.platform == "emscripten":   # v10 (Get back L2): inside the app a missing guard is an error, not a pass
            raise ValueError("path check unavailable (kp_safe_path missing); refusing")
        return p
    return sp(p)

def guard_path(fn, g):
    @functools.wraps(fn)
    def w(*a, **k):
        home_based = all(g.get(v, HOME) == HOME for v in BASE_VARS)
        first = next((x for x in a if isinstance(x, str)), None)
        if first is None: first = next((k[n] for n in ("path", "p", "name", "rel") if isinstance(k.get(n), str)), None)
        if home_based and first and first.strip():
            _check(first)                  # refuse ../, outside ~ and symlinks before the tool touches the path
        r = fn(*a, **k)
        if home_based and isinstance(r, str) and r.startswith("/"):
            r = _check(r)                 # and the resolved result too
        return r
    return w

def harden(g, extra=()):
    """Apply caps and path checks to the names a tool actually defines (others are skipped)."""
    for n in CAP_NAMES + tuple(extra):
        f = g.get(n)
        if callable(f) and not isinstance(f, type) and not getattr(f, "_kp_capped", False):
            g[n] = cap(f); g[n]._kp_capped = True
    for n in PATH_NAMES:
        f = g.get(n)
        if callable(f) and not getattr(f, "_kp_guarded", False):
            g[n] = guard_path(f, g); g[n]._kp_guarded = True
    D = g.get("Debugger")
    if isinstance(D, type) and not getattr(D, "_kp_capped", False):
        init = D.__init__
        @functools.wraps(init)
        def _init(self, source, *a, **k):
            if len(source) > MAX_TEXT:
                raise ValueError("code too big to debug (max 500 KB)")
            init(self, source, *a, **k)
        D.__init__ = _init; D._kp_capped = True

def self_test():
    import io, contextlib
    assert cap(lambda s: len(s))("abc") == 3
    try:
        cap(lambda s: s)("x" * (MAX_TEXT + 1)); raise AssertionError("cap")
    except ValueError: pass
    g = {"safe_path": lambda p: "/home/pyodide/" + p}
    harden(g); assert g["safe_path"].__name__ == "<lambda>"
    import builtins as b
    old = b.input
    try:
        seq = iter(["0", "-1", "abc", "2"]); b.input = lambda p="": next(seq)
        with contextlib.redirect_stdout(io.StringIO()): assert pick_index("n", 3) == 1
        b.input = lambda p="": ""; assert pick_index("n", 3) is None and yes("ok?") is False
        b.input = lambda p="": "yeah"; assert yes("ok?") is False
        b.input = lambda p="": "YES"; assert yes("ok?") is True
        def ki(p=""): raise KeyboardInterrupt("input cancelled")
        b.input = ki; assert ask("x") is None and yes("x") is False and pick_index("n", 2) is None
    finally:
        b.input = old
    print("kp_common self-tests passed.")
    return True
