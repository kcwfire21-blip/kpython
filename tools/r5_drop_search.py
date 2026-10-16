# Drop's Project Search & Replace: search (plain/regex, case, whole word) across text files under /home/pyodide with ReDoS guards, preview matches with ⟦markers⟧, and replace with a typed-y confirm, History auto-save (r3_drop_history format) and atomic writes. Stdlib only, no network.
import os, re, sys, tempfile, time

BASE_DIR = "/home/pyodide"
SKIP_DIRS = {".history", "__pycache__", ".git", "kptools", ".kp_imap"}
TEXT_EXT = {".py", ".txt", ".md", ".json", ".csv", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".html", ".css", ".js", ".sql", ".xml", ".rst", ".log", ""}
MAX_PATTERN = 200
MAX_FILE = 500_000          # bytes per file
MAX_TOTAL = 5_000_000       # bytes scanned per search
MAX_MATCHES = 500
MAX_LINE_REGEX = 2000       # longer lines are skipped in regex mode (ReDoS guard)
FILE_BUDGET = 0.5           # seconds per file, checked between lines
MARK_L, MARK_R = "⟦", "⟧"

# Nested-quantifier heuristics: (x+)+, (x*)*, (x{2,})+, and quantified alternation (a|aa)*.
_G = r"\((?:[^()\\]|\\.)*"
_NESTED = re.compile(_G + r"(?:[+*]|\{\d*,?\d*\})\)\s*(?:[+*]|\{\d*,?\d*\})")
_ALT = re.compile(_G + r"\|(?:[^()\\]|\\.)*\)\s*(?:[+*]|\{\d*,\d*\})")


# ---------------- saved-script bridge ----------------
def saved_script_files():
    """Files the app mirrors from saved scripts on every Run (read-only copies).

    v6.1 has no write-back bridge for saved scripts: the app writes each script to
    /home/pyodide/<module>.py before a run and overwrites it next run, so edits here
    would be lost. We search them but don't replace in them."""
    main = sys.modules.get("__main__")
    mods = getattr(main, "_kp_user_mods", None) or set()
    b = os.path.realpath(BASE_DIR)
    return {os.path.join(b, m + ".py") for m in mods if isinstance(m, str)}


# ---------------- paths ----------------
def base():
    return os.path.realpath(BASE_DIR)


def confine(p):
    """realpath p and require it inside BASE_DIR, outside .history; refuse symlinks."""
    b = base()
    full = os.path.realpath(os.path.join(b, p))
    if not full.startswith(b + os.sep):
        raise ValueError(f"refused: {p} is outside {BASE_DIR}")
    rel = os.path.relpath(full, b)
    if rel.split(os.sep)[0] in SKIP_DIRS:
        raise ValueError(f"refused: {rel} is in a protected folder")
    return full


def iter_files(root="."):
    start = confine(root) if root not in ("", ".", "~") else base()
    if os.path.isfile(start):
        yield start
        return
    for d, dirs, files in os.walk(start, followlinks=False):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith(".") and not os.path.islink(os.path.join(d, x)))
        for f in sorted(files):
            p = os.path.join(d, f)
            if os.path.islink(p) or os.path.splitext(f)[1].lower() not in TEXT_EXT:
                continue
            yield p


# ---------------- patterns ----------------
def build_pattern(text, regex=False, case=False, word=False):
    if not text or len(text) > MAX_PATTERN:
        raise ValueError(f"pattern must be 1-{MAX_PATTERN} characters")
    if regex:
        if _NESTED.search(text) or _ALT.search(text):
            raise ValueError("pattern has nested/alternating repeats like (a+)+ or (a|aa)* that can freeze the phone; simplify it")
        if re.search(r"\\[1-9]", text):
            raise ValueError("backreferences are not allowed in search patterns")
        src = text
    else:
        src = re.escape(text)
    if word:
        src = r"\b(?:" + src + r")\b"
    try:
        return re.compile(src, 0 if case else re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"bad regex: {e}")


def highlight(line, spans):
    out, last = [], 0
    for a, b in spans:
        out += [line[last:a], MARK_L, line[a:b], MARK_R]
        last = b
    out.append(line[last:])
    return "".join(out)


# ---------------- search ----------------
def read_text(full):
    if os.path.getsize(full) > MAX_FILE:
        return None
    with open(full, "rb") as f:
        data = f.read(MAX_FILE + 1)
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def search(rx, root=".", regex=False):
    """Return (hits, notes). hits: list of (rel, line_no, line, spans)."""
    hits, notes, total = [], [], 0
    b = base()
    for full in iter_files(root):
        text = read_text(full)
        rel = os.path.relpath(full, b)
        if text is None:
            continue
        total += len(text)
        if total > MAX_TOTAL:
            notes.append(f"stopped: scanned more than {MAX_TOTAL:,} bytes")
            break
        t0 = time.monotonic()
        for n, line in enumerate(text.splitlines(), 1):
            if time.monotonic() - t0 > FILE_BUDGET:
                notes.append(f"{rel}: time budget hit at line {n}; rest skipped")
                break
            if regex and len(line) > MAX_LINE_REGEX:
                notes.append(f"{rel}:{n}: line longer than {MAX_LINE_REGEX} chars skipped")
                continue
            spans = [m.span() for m in rx.finditer(line) if m.end() > m.start()]
            if spans:
                hits.append((rel, n, line, spans))
                if sum(len(h[3]) for h in hits) >= MAX_MATCHES:
                    notes.append(f"stopped at {MAX_MATCHES} matches")
                    return hits, notes
    return hits, notes


def preview(hits, width=120):
    for rel, n, line, spans in hits:
        s = highlight(line, spans).strip()
        print(f"{rel}:{n}: {s[:width]}{'…' if len(s) > width else ''}")


# ---------------- replace ----------------
def atomic_write(full, text):
    d = os.path.dirname(full)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".kp_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, full)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _history():
    """Reuse r3_drop_history's .history format (app ships it in kptools)."""
    import importlib
    h = importlib.import_module("r3_drop_history")
    h.BASE_DIR = BASE_DIR
    return h


def plan_replace(rx, repl, hits):
    """Group hits per writable file and compute new contents. Returns (plan, skipped)."""
    b, mirrors = base(), saved_script_files()
    plan, skipped = {}, []
    for rel in sorted({h[0] for h in hits}):
        full = confine(rel)
        if full in mirrors:
            skipped.append(f"{rel} (saved-script copy; edit it in the app's editor, the app overwrites this file on each Run)")
            continue
        if os.path.islink(os.path.join(b, rel)):
            skipped.append(f"{rel} (symlink)")
            continue
        old = read_text(full)
        if old is None:
            skipped.append(f"{rel} (too big or not text)")
            continue
        try:
            new, n = rx.subn(repl, old)
        except (re.error, IndexError) as e:
            raise ValueError(f"bad replacement: {e}")
        if n:
            plan[rel] = (full, old, new, n)
    return plan, skipped


def apply_plan(plan, per_file=False, ask=input):
    h = _history()
    import contextlib, io
    done = 0
    for rel, (full, old, new, n) in plan.items():
        if per_file and ask(f"  {rel}: {n} replacement(s). Type y to change this file: ").strip().lower() != "y":
            print(f"  skipped {rel}")
            continue
        if read_text(full) != old:
            print(f"  skipped {rel}: it changed since the preview")
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            h.save_version(rel, "auto-save before search & replace")
        atomic_write(full, new)
        print(f"  ✔ {rel}: {n} replacement(s) (old version saved in History)")
        done += 1
    return done


# ---------------- interactive ----------------
def ask_pattern():
    text = input("Search for: ")
    regex = input("Regex? (y/N): ").strip().lower() == "y"
    case = input("Match case? (y/N): ").strip().lower() == "y"
    word = input("Whole word? (y/N): ").strip().lower() == "y"
    root = input("Folder or file under ~ (Enter = everything): ").strip() or "."
    return build_pattern(text, regex, case, word), regex, root


def main():
    print("=== Project Search & Replace ===  (files under " + BASE_DIR + "; .history is skipped)")
    if not saved_script_files():
        print("Tip: to replace inside your saved scripts, use Dev > Replace in saved scripts (asks you to confirm each change).")
    while True:
        c = input("\n1 Search  2 Replace  t Self-tests  q Quit: ").strip().lower()
        try:
            if c in ("q", "quit", "exit"):
                break
            elif c == "1":
                rx, regex, root = ask_pattern()
                hits, notes = search(rx, root, regex)
                preview(hits)
                print(f"{sum(len(h[3]) for h in hits)} match(es) in {len({h[0] for h in hits})} file(s).")
                for n in notes:
                    print("note:", n)
            elif c == "2":
                rx, regex, root = ask_pattern()
                repl = input("Replace with: ")
                if not regex:
                    repl = repl.replace("\\", "\\\\")
                hits, notes = search(rx, root, regex)
                for n in notes:
                    print("note:", n)
                if any("stopped" in n for n in notes):
                    print("Search was capped, so replace is disabled. Narrow the folder or pattern.")
                    continue
                preview(hits)
                plan, skipped = plan_replace(rx, repl, hits)
                for s in skipped:
                    print("not changing:", s)
                if not plan:
                    print("Nothing to replace.")
                    continue
                total = sum(v[3] for v in plan.values())
                print(f"\n{total} replacement(s) in {len(plan)} file(s):")
                for rel, v in plan.items():
                    print(f"  {rel}: {v[3]}")
                per_file = input("Confirm each file separately? (y/N): ").strip().lower() == "y"
                if input(f"Type y to replace {total} match(es) in {len(plan)} file(s): ").strip().lower() != "y":
                    print("Cancelled. Nothing changed.")
                    continue
                print(f"Changed {apply_plan(plan, per_file)} file(s).")
            elif c == "t":
                run_self_tests()
            else:
                print("Pick 1, 2, t or q.")
        except (ValueError, OSError, ImportError) as e:
            print("Error:", e)


# ---------------- saved scripts (KPython v7 bridge) ----------------
async def saved_replace():
    """Search & replace inside the app's saved scripts. Every change is shown first, needs a typed y here,
    then the app itself asks you to allow each script change. The old text is saved in History first."""
    import js, json, contextlib, io
    if not hasattr(js, "kpScriptsGet"):
        print("This needs the KPython app (saved-scripts bridge)."); return
    scripts = json.loads(await js.kpScriptsGet())
    rx, regex, _root = ask_pattern()
    repl = input("Replace with: ")
    if not regex:
        repl = repl.replace("\\", "\\\\")
    plan = {}
    for name, text in scripts.items():
        if not isinstance(text, str) or len(text) > MAX_FILE:
            continue
        hits = []
        for n, line in enumerate(text.splitlines(), 1):
            if regex and len(line) > MAX_LINE_REGEX:
                continue
            sp = [m.span() for m in rx.finditer(line) if m.end() > m.start()]
            if sp:
                hits.append((n, line, sp))
        if hits:
            try:
                new, k = rx.subn(repl, text)
            except (re.error, IndexError) as e:
                raise ValueError(f"bad replacement: {e}")
            plan[name] = (text, new, k, hits)
    if not plan:
        print("No matches in saved scripts."); return
    for name, (_o, _n, k, hits) in plan.items():
        print(f"\n[{name}] {k} replacement(s)")
        for n, line, sp in hits[:20]:
            print(f"  {n}: {highlight(line, sp).strip()[:120]}")
    total = sum(v[2] for v in plan.values())
    if input(f"\nType y to replace {total} match(es) in {len(plan)} saved script(s): ").strip().lower() != "y":
        print("Cancelled. Nothing changed."); return
    h = _history()
    keep = os.path.join(base(), ".kp_saved")
    os.makedirs(keep, exist_ok=True)
    changed = 0
    for name, (old, new, k, _h) in plan.items():
        safe = re.sub(r"[^\w.-]", "_", name)[:80] + ".py"
        with open(os.path.join(keep, safe), "w", encoding="utf-8") as f:
            f.write(old)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                h.save_version(os.path.join(".kp_saved", safe), f"auto-save of saved script '{name}' before replace")
        except Exception as e:
            print(f"  skipped {name}: could not save History first ({e})"); continue
        ok = await js.kpScriptsSet(name, new, "Search & Replace")
        print(f"  {'✔' if ok else '✖'} {name}: " + (f"{k} replacement(s) (old version in History as .kp_saved/{safe})" if ok else "not changed (declined in the app)"))
        changed += bool(ok)
    print(f"Changed {changed} saved script(s).")


# ---------------- self-tests ----------------
def run_self_tests():
    global BASE_DIR
    import shutil, contextlib, io
    ok = fail = 0

    def check(c, label):
        nonlocal ok, fail
        ok, fail = (ok + 1, fail) if c else (ok, fail + 1)
        if not c:
            print("FAIL:", label)

    for bad in ("(a+)+", "(a*)*b", "(x{2,})+", "(a|aa)*", "(a|b)+$", r"(\w+)\1", "", "x" * 201):
        try:
            build_pattern(bad, regex=True); check(False, f"accepted {bad!r}")
        except ValueError:
            check(True, "")
    try:
        build_pattern("([", regex=True); check(False, "bad regex")
    except ValueError:
        check(True, "")
    check(build_pattern("a.b").search("axb") is None, "plain escapes")
    check(build_pattern("cat", word=True).search("concat") is None, "whole word")
    check(build_pattern("Cat", case=True).search("cat") is None, "case")
    check(highlight("x = foo(foo)", [(4, 7), (8, 11)]) == "x = ⟦foo⟧(⟦foo⟧)", "highlight")

    old = BASE_DIR
    tmp = tempfile.mkdtemp()
    BASE_DIR = tmp
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        os.makedirs(os.path.join(tmp, "sub"))
        files = {"a.py": "total = price * qty\nprint(total)\n", "sub/b.txt": "Total: 3\ntotalled\n", "big.txt": "x" * (MAX_FILE + 1)}
        for k, v in files.items():
            with open(os.path.join(tmp, k), "w") as f:
                f.write(v)
        os.makedirs(os.path.join(tmp, ".history"))
        with open(os.path.join(tmp, ".history", "h.txt"), "w") as f:
            f.write("total\n")
        outside = tempfile.mkdtemp()
        with open(os.path.join(outside, "o.txt"), "w") as f:
            f.write("total\n")
        os.symlink(outside, os.path.join(tmp, "esc"))
        os.symlink(os.path.join(outside, "o.txt"), os.path.join(tmp, "link.txt"))
        rx = build_pattern("total", word=True)
        hits, notes = search(rx)
        rels = {h[0] for h in hits}
        check(rels == {"a.py", "sub/b.txt"}, f"search scope {rels}")
        check(sum(len(h[3]) for h in hits) == 3, "match count (whole word, case-insensitive)")
        for bad in ("../x", "/etc", "esc", "esc/o.txt", ".history"):
            try:
                confine(bad); check(False, f"confine allowed {bad}")
            except ValueError:
                check(True, "")
        plan, skipped = plan_replace(rx, "amount", hits)
        check(set(plan) == {"a.py", "sub/b.txt"} and plan["a.py"][3] == 2, "plan")
        with contextlib.redirect_stdout(io.StringIO()):
            n = apply_plan(plan, per_file=True, ask=lambda p: "y" if "a.py" in p else "n")
        check(n == 1 and open(os.path.join(tmp, "a.py")).read() == "amount = price * qty\nprint(amount)\n", "replace + per-file confirm")
        check(open(os.path.join(tmp, "sub/b.txt")).read() == files["sub/b.txt"], "declined file unchanged")
        h = _history()
        d, rel = h.hist_dir(os.path.realpath(os.path.join(tmp, "a.py")))
        vs = h.load_index(d, rel)["versions"]
        check(len(vs) == 1 and h.get_version(os.path.realpath(os.path.join(tmp, "a.py")), 1) == files["a.py"], "history auto-save")
        check(open(os.path.join(outside, "o.txt")).read() == "total\n", "outside untouched")
        check(not [f for f in os.listdir(tmp) if f.startswith(".kp_tmp_")], "no temp files left")
        # time budget + caps
        with open(os.path.join(tmp, "many.txt"), "w") as f:
            f.write("ab\n" * 2000)
        hits, notes = search(build_pattern("ab"), "many.txt")
        check(any("stopped at" in x for x in notes), "match cap")
        global FILE_BUDGET
        fb, FILE_BUDGET = FILE_BUDGET, -1
        try:
            hits, notes = search(build_pattern("ab"), "many.txt")
            check(not hits and any("time budget" in x for x in notes), "time budget")
        finally:
            FILE_BUDGET = fb
        shutil.rmtree(outside, ignore_errors=True)
    finally:
        BASE_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Self-tests: {ok} passed, {fail} failed")
    return fail == 0


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
