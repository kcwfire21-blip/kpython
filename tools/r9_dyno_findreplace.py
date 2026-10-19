# Dyno: project-wide find & replace across saved scripts/files under /home/pyodide - plain text or regex, per-file preview diff, y/N confirm, atomic writes, kp_safe_path + size caps. Stdlib only.
import os, re, sys, difflib, tempfile

for _d in ("/kptools", os.path.dirname(os.path.abspath(__file__)), "/workspace/pyapp/tools"):   # KPython: never dirs under ~
    if os.path.isdir(_d) and _d not in sys.path:
        sys.path.append(_d)

try:
    import kp_common as _kc
    MAX_TEXT, HOME = _kc.MAX_TEXT, _kc.HOME
except ImportError:
    _kc, MAX_TEXT, HOME = None, 500_000, "/home/pyodide"
try:
    from r8_forlor_nav import ask, need, confirm, run_menu, run_tool, Back
except ImportError:
    class Back(Exception): pass
    def ask(p=""):
        try: return input(p).strip() or None
        except (KeyboardInterrupt, EOFError): return None
    def need(p=""):
        a = ask(p)
        if a is None: raise Back()
        return a
    def confirm(p):
        a = ask(p + " (y/N): "); return bool(a) and a.lower() in ("y", "yes")
    def run_tool(fn, *a, **k):
        try: return fn(*a, **k)
        except (Back, KeyboardInterrupt, EOFError): print("Cancelled.")
    run_menu = None

BASE = HOME
TEXT_EXT = (".py", ".txt", ".md", ".json", ".csv", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".html", ".css", ".js", ".sql")
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".kp_history"}
MAX_FILES = 2000
MAX_TOTAL = 20_000_000

def safe_path(p):
    """Resolve p under BASE; refuses ../, absolute paths outside BASE and symlink escapes."""
    import builtins as _b
    _g = getattr(_b, "kp_safe_path", None)
    if _g is not None and BASE == HOME:
        return _g(p or ".")   # KPython: the app's shared rule (also refuses symlinks on the way)
    base = os.path.realpath(BASE)
    full = os.path.realpath(os.path.join(base, p or "."))
    if full != base and not full.startswith(base + os.sep):
        raise ValueError("Only paths under " + base + " are allowed.")
    return full

def build(find, regex=False, ignore_case=False, whole_word=False):
    if not find: raise ValueError("search text is empty")
    if len(find) > 2000: raise ValueError("search text too long")
    pat = find if regex else re.escape(find)
    if whole_word: pat = r"\b(?:" + pat + r")\b"
    return re.compile(pat, re.I if ignore_case else 0)

def iter_files(root=".", exts=TEXT_EXT):
    top = safe_path(root)
    n = total = 0
    for r, ds, fs in os.walk(top):
        ds[:] = sorted(d for d in ds if d not in SKIP_DIRS and not d.startswith(".") and not os.path.islink(os.path.join(r, d)))
        for f in sorted(fs):
            p = os.path.join(r, f)
            if not f.endswith(exts) or os.path.islink(p): continue
            try: sz = os.path.getsize(p)
            except OSError: continue
            if sz > MAX_TEXT: continue
            total += sz; n += 1
            if n > MAX_FILES or total > MAX_TOTAL:
                print(f"(stopped after {n - 1} files: scan limit reached)"); return
            yield p

def _mirrors():
    """KPython: ~/<name>.py copies of saved scripts are re-written from the app before every run, so editing them here
    would be undone. They are skipped; use 🔎 Search & Replace (it changes saved scripts through the app, with a confirm)."""
    import builtins as _b
    f = getattr(_b, "kp_saved_mirrors", None)
    try: return set(f()) if f and BASE == HOME else set()
    except Exception: return set()

def plan(rx, repl, root=".", regex=False):
    """Return [(path, old, new, count)] for files that would change. Nothing is written."""
    out = []
    mir = _mirrors(); skipped = 0
    for p in iter_files(root):
        if p in mir:
            skipped += 1; continue
        try:
            with open(p, encoding="utf-8") as f: old = f.read()
        except (UnicodeDecodeError, OSError): continue
        try:
            new, c = rx.subn(repl if regex else (lambda m: repl), old)
        except (re.error, IndexError) as e:
            raise ValueError(f"bad replacement: {e}")
        if c and new != old:
            if len(new) > MAX_TEXT: raise ValueError(f"{rel(p)} would grow past {MAX_TEXT // 1000} KB")
            out.append((p, old, new, c))
    if skipped: print(f"(skipped {skipped} saved script(s): change those with 🔎 Search & Replace, which edits them in the app)")
    return out

def rel(p):
    return os.path.relpath(p, os.path.realpath(BASE))

def diff(path, old, new, ctx=2):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile=rel(path) + " (before)", tofile=rel(path) + " (after)", n=ctx))

def atomic_write(path, text):
    path = safe_path(rel(path))
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".kp_fr_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(text)
        try: os.chmod(tmp, os.stat(path).st_mode & 0o777)
        except OSError: pass
        os.replace(tmp, path)
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise

def find_only(rx, root="."):
    hits = []
    for p in iter_files(root):
        try:
            with open(p, encoding="utf-8") as f: lines = f.read().splitlines()
        except (UnicodeDecodeError, OSError): continue
        for i, l in enumerate(lines, 1):
            if rx.search(l): hits.append((rel(p), i, l.strip()[:120]))
    return hits

if _kc is not None:
    _kc.harden(globals(), extra=("plan", "build"))

def _options():
    find = need("Find (blank = back): ")
    regex = confirm("Regex?")
    ic = confirm("Ignore case?")
    ww = confirm("Whole words only?")
    root = ask(f"Folder under {BASE} (Enter = everything): ") or "."
    return build(find, regex, ic, ww), regex, root

def do_find():
    rx, _, root = _options()
    hits = find_only(rx, root)
    for r, i, l in hits[:300]: print(f"{r}:{i}: {l}")
    print(f"\n{len(hits)} matching line(s)" + (" (first 300 shown)" if len(hits) > 300 else ""))

def do_replace():
    rx, regex, root = _options()
    repl = ask("Replace with (" + (r"\1 / \g<name> ok" if regex else "plain text") + ", Enter = delete match): ") or ""
    changes = plan(rx, repl, root, regex)
    if not changes: print("No matches. Nothing to change."); return
    total = sum(c for *_, c in changes)
    print(f"{total} replacement(s) in {len(changes)} file(s).")
    written = 0
    apply_all = False
    for k, (p, old, new, c) in enumerate(changes):
        print("\n" + (diff(p, old, new) or "(no visible diff)"))
        if not apply_all:
            a = (ask(f"Write {rel(p)} ({c} change(s))? y = yes, N = skip, a = all remaining, q = stop: ") or "n").lower()
            if a in ("q", "quit"): break
            if a == "a":
                left = len(changes) - k
                if not confirm(f"Write this file and ALL {left - 1} remaining file(s) without asking again? Diffs are still printed."):
                    print("Skipped (not applying to all)."); continue
                apply_all = True
            elif a not in ("y", "yes"): print("Skipped."); continue
        atomic_write(p, new); written += 1; print("Saved", rel(p))
    print(f"\nDone: {written} of {len(changes)} file(s) written.")

def self_test():
    global BASE
    old_base = BASE
    tmp = os.path.realpath(tempfile.mkdtemp())
    BASE = tmp
    try:
        os.makedirs(os.path.join(tmp, "proj", "__pycache__"))
        os.makedirs(os.path.join(tmp, ".hidden"))
        files = {"a.py": "def greet(name):\n    return 'hi ' + name\nprint(greet('x'))\n",
                 "proj/b.py": "from a import greet\ngreeting = greet('y')\n",
                 "proj/notes.md": "greet people\n", "proj/__pycache__/c.py": "greet\n",
                 ".hidden/d.py": "greet\n", "big.py": "greet\n" + "x" * (MAX_TEXT + 1), "img.bin": "greet"}
        for n, c in files.items():
            with open(os.path.join(tmp, n), "w") as f: f.write(c)
        # plain whole-word: greeting must not change
        ch = plan(build("greet", whole_word=True), "welcome")
        names = sorted(rel(p) for p, *_ in ch)
        assert names == ["a.py", "proj/b.py", "proj/notes.md"], names
        new_b = dict((rel(p), n) for p, _, n, _ in ch)["proj/b.py"]
        assert "greeting = welcome('y')" in new_b and "import welcome" in new_b, new_b
        # plain replacement treats backslashes literally
        ch = plan(build("hi "), r"\1 ")
        assert dict((rel(p), n) for p, _, n, _ in ch)["a.py"].count(r"\1 ") == 1
        # regex with groups + ignore case
        ch = plan(build(r"GREET\('(\w)'\)", regex=True, ignore_case=True), r"hello('\1!')", regex=True)
        assert "hello('x!')" in dict((rel(p), n) for p, _, n, _ in ch)["a.py"]
        # bad regex / bad group refs refused
        for bad in (lambda: build("(", regex=True), lambda: plan(build("greet", regex=True), r"\9", regex=True), lambda: build("")):
            try: bad(); raise AssertionError("accepted bad input")
            except (ValueError, re.error): pass
        # diff + atomic write
        p, old, new, _ = plan(build("greet", whole_word=True), "welcome", "proj")[0]
        assert "+++" in diff(p, old, new)
        atomic_write(p, new)
        with open(p) as f: assert f.read() == new
        assert not [f for f in os.listdir(os.path.dirname(p)) if f.startswith(".kp_fr_")]
        # path safety
        for esc in ("../", "/etc", "proj/../../"):
            try: safe_path(esc); raise AssertionError("escaped: " + esc)
            except ValueError: pass
        os.symlink("/etc", os.path.join(tmp, "link"))
        try: safe_path("link"); raise AssertionError("symlink escape")
        except ValueError: pass
        assert all(not r.startswith("link") for r, *_ in find_only(build("root")))
        # find-only lists line numbers
        assert ("a.py", 3, "print(greet('x'))") in find_only(build("greet"))
    finally:
        BASE = old_base
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
    print("self-tests passed")
    return True

def main():
    print(f"== Find & Replace in {BASE} ==")
    if run_menu:
        run_menu("Find & Replace", [("Find (read-only)", do_find), ("Find and replace", do_replace), ("Self-test", self_test)], top=True)
    else:
        a = ask("1 Find  2 Replace  t Self-test: ")
        {"1": do_find, "2": do_replace, "t": self_test}.get(a or "", lambda: None)()


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    if "--selftest" in sys.argv: self_test()
    else: run_tool(main)
