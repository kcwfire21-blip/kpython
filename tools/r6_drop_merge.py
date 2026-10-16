# Drop's 3-Way Merge: pick a base from History plus "ours"/"theirs" (current file, History versions, other files, or saved scripts), auto-merge diff3-style, resolve conflicts one by one, preview, then save atomically with a History backup. Stdlib only, no network.
import asyncio, difflib, os, re, sys, tempfile

BASE_DIR = "/home/pyodide"
MAX_BYTES = 500_000
SKIP = {".history"}
IN_PYODIDE = sys.platform == "emscripten" or "pyodide" in sys.modules


# ---------------- merge core (pure) ----------------
class Conflict:
    def __init__(self, ours, base, theirs):
        self.ours, self.base, self.theirs = ours, base, theirs


def _hunks(base, side):
    sm = difflib.SequenceMatcher(None, base, side, autojunk=False)
    return [(i1, i2, side[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def _apply(base, hunks, s, e):
    out, pos = [], s
    for i1, i2, rep in hunks:
        out += base[pos:i1] + rep
        pos = i2
    return out + base[pos:e]


def merge3(base, ours, theirs):
    """diff3-style merge of line lists. Returns a list of str lines and Conflict objects."""
    ho = [(a, b, r, "o") for a, b, r in _hunks(base, ours)]
    ht = [(a, b, r, "t") for a, b, r in _hunks(base, theirs)]
    allh = sorted(ho + ht, key=lambda h: (h[0], h[1]))
    out, pos, i = [], 0, 0
    while i < len(allh):
        s, e = allh[i][0], allh[i][1]
        group = [allh[i]]
        i += 1
        # cluster hunks that overlap or touch (diff3 treats adjacent edits as one region)
        while i < len(allh) and allh[i][0] <= e:
            e = max(e, allh[i][1])
            group.append(allh[i])
            i += 1
        out += base[pos:s]
        go = [h[:3] for h in group if h[3] == "o"]
        gt = [h[:3] for h in group if h[3] == "t"]
        o_txt, t_txt = _apply(base, go, s, e), _apply(base, gt, s, e)
        if not gt:
            out += o_txt
        elif not go or o_txt == t_txt:
            out += t_txt
        else:
            out.append(Conflict(o_txt, base[s:e], t_txt))
        pos = e
    return out + base[pos:]


def _nl(lines):
    lines = list(lines)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def render(parts, choices=None):
    """choices: list per conflict of 'o','t','b'(both),'base','m'(markers). Default markers."""
    out, k = [], 0
    for p in parts:
        if not isinstance(p, Conflict):
            out.append(p)
            continue
        c = choices[k] if choices and k < len(choices) else "m"
        k += 1
        if c == "o":
            out += p.ours
        elif c == "t":
            out += p.theirs
        elif c == "b":
            out += _nl(p.ours) + p.theirs
        elif c == "base":
            out += p.base
        else:
            if out and not out[-1].endswith("\n"):
                out[-1] += "\n"
            out += ["<<<<<<< ours\n"] + _nl(p.ours) + ["||||||| base\n"] + _nl(p.base) + ["=======\n"] + _nl(p.theirs) + [">>>>>>> theirs\n"]
    return "".join(out)


def conflicts(parts):
    return [p for p in parts if isinstance(p, Conflict)]


# ---------------- files & history ----------------
def base():
    return os.path.realpath(BASE_DIR)


def confine(p):
    p = (p or "").strip()
    if not p or "\x00" in p:
        raise ValueError("empty or invalid path")
    if p == "~" or p.startswith("~/"):
        p = p[2:] or "."
    b = base()
    raw = os.path.join(b, p)
    full = os.path.realpath(raw)
    if not full.startswith(b + os.sep):
        raise ValueError(f"refused: {p} is outside {BASE_DIR}")
    if os.path.islink(raw) or os.path.normpath(raw) != full:
        raise ValueError(f"refused: {p} goes through a symlink")
    if os.path.relpath(full, b).split(os.sep)[0] in SKIP:
        raise ValueError("refused: .history is managed by History")
    return full


def read_text(full):
    if not os.path.isfile(full):
        raise ValueError(f"not a file: {os.path.relpath(full, base())}")
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError(f"file too big (max {MAX_BYTES:,} bytes)")
    with open(full, "rb") as f:
        data = f.read(MAX_BYTES + 1)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("only UTF-8 text files are supported")


def atomic_write(full, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(full), prefix=".kp_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, full)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def history():
    import importlib
    h = importlib.import_module("r3_drop_history")
    h.BASE_DIR = BASE_DIR
    return h


def versions(full):
    h = history()
    d, rel = h.hist_dir(full)
    return h.load_index(d, rel)["versions"]


def version_text(full, vid):
    return history().get_version(full, vid)


def backup(rel, why):
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        history().save_version(rel, why)


# ---------------- saved-scripts bridge (v7) ----------------
def _bridge():
    try:
        import js
        if hasattr(js, "kpScriptsGet") and hasattr(js, "kpScriptsSet"):
            return js
    except ImportError:
        pass
    return None


async def saved_scripts():
    import json
    js = _bridge()
    if not js:
        return None
    data = json.loads(str(await js.kpScriptsGet()))
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}


def mirror_rel(name):
    m = re.sub(r"\W+", "_", name.strip().lower().removesuffix(".py")).strip("_") or "script"
    return ("_" + m if m[0].isdigit() else m) + ".py"


# ---------------- interactive ----------------
def choose_source(label, full, scripts):
    print(f"\n{label}: c = current file, vN = History version N, f = another file, s = saved script")
    c = input(f"{label} from: ").strip().lower()
    if c == "c":
        return read_text(full)
    if re.fullmatch(r"v?\d{1,6}", c):
        return version_text(full, int(c.lstrip("v")))
    if c == "f":
        return read_text(confine(input("File path (inside ~): ")))
    if c == "s":
        if scripts is None:
            raise ValueError("no saved-scripts bridge here (only inside the KPython v7 app)")
        n = input("Saved script name: ").strip()
        if n not in scripts:
            raise ValueError("no saved script with that name")
        if len(scripts[n]) > MAX_BYTES:
            raise ValueError("saved script too big")
        return scripts[n]
    raise ValueError("pick c, vN, f or s")


def resolve(parts):
    choices, cs = [], conflicts(parts)
    for k, cf in enumerate(cs, 1):
        print(f"\n--- conflict {k}/{len(cs)} ---")
        print(render([cf]), end="")
        while True:
            c = input("Keep o=ours t=theirs b=both base=base m=markers: ").strip().lower()
            if c in ("o", "t", "b", "base", "m"):
                choices.append(c)
                break
            print("Pick o, t, b, base or m.")
    return choices


async def amain():
    print("=== 3-Way Merge ===  (files under " + BASE_DIR + ")")
    try:
        scripts = await saved_scripts()
    except Exception as e:
        scripts = None
        print("Saved-scripts bridge error:", e)
    print("Saved scripts: " + ("v7 bridge found. Merging into a saved script asks you to approve the change in the app." if scripts is not None
          else "no bridge here, so only files under ~ can be merged."))
    while True:
        c = input("\n1 Merge into a file  2 Merge into a saved script  t Self-tests  q Quit: ").strip().lower()
        try:
            if c in ("q", "quit", "exit"):
                break
            if c == "t":
                run_self_tests()
                continue
            if c not in ("1", "2"):
                print("Pick 1, 2, t or q.")
                continue
            script = None
            if c == "2":
                if scripts is None:
                    print("No saved-scripts bridge (needs the KPython v7 app).")
                    continue
                script = input("Saved script name: ").strip()
                if script not in scripts:
                    print("No saved script with that name.")
                    continue
                rel = mirror_rel(script)
                full = os.path.join(base(), rel)
                atomic_write(full, scripts[script])  # current text, so History and 'c' use it
            else:
                full = confine(input("File to merge into (inside ~): "))
                rel = os.path.relpath(full, base())
                read_text(full)
            vs = versions(full)
            if not vs:
                print("No History versions for this file yet; save one in History first.")
                continue
            for v in vs[-15:]:
                print(f"  v{v['id']}  {v['ts']}  {v.get('msg', '')}")
            b = version_text(full, int(input("Base version number: ").strip().lstrip("v") or "x"))
            o = choose_source("OURS", full, scripts)
            t = choose_source("THEIRS", full, scripts)
            parts = merge3(b.splitlines(True), o.splitlines(True), t.splitlines(True))
            n = len(conflicts(parts))
            print(f"\nAuto-merged. {n} conflict(s).")
            result = render(parts, resolve(parts) if n else None)
            cur = read_text(full)
            d = "".join(difflib.unified_diff(cur.splitlines(True), result.splitlines(True), f"{rel} (current)", f"{rel} (merged)"))
            print(d or "(merged result is identical to the current file)")
            if not d or input("Type y to write the merged result: ").strip().lower() != "y":
                print("Nothing written.")
                continue
            if len(result.encode()) > MAX_BYTES:
                raise ValueError("merged result too big")
            backup(rel, "auto-save before 3-way merge")
            if script is not None:
                r = await _bridge().kpScriptsSet(script, result, "3-way merge (Drop)")
                if r:  # KPython: only update the mirror copy if you allowed the change in the app
                    atomic_write(full, result)
                    print("Saved script updated. The previous version is in History and in Files > Undo last Python change.")
                else:
                    print("Not changed (declined in the app).")
            else:
                atomic_write(full, result)
                print(f"Wrote {rel}. The previous version is in History.")
        except (ValueError, OSError, ImportError, LookupError) as e:
            print("Error:", e)


def main():
    if IN_PYODIDE:
        return asyncio.ensure_future(amain())
    asyncio.run(amain())


# ---------------- self-tests ----------------
def run_self_tests():
    global BASE_DIR
    import random, shutil, contextlib, io
    ok = fail = 0

    def check(c, label):
        nonlocal ok, fail
        ok, fail = (ok + 1, fail) if c else (ok, fail + 1)
        if not c:
            print("FAIL:", label)

    L = lambda s: [x + "\n" for x in s.split()]
    b = L("a b c d e f g")
    # basics
    check(render(merge3(b, L("a B c d e f g"), L("a b c d e F g"))) == "".join(L("a B c d e F g")), "non-overlapping auto-merge")
    check(not conflicts(merge3(b, L("a X c d e f g"), L("a X c d e f g"))), "identical changes clean")
    p = merge3(b, L("a b C1 d e f g"), L("a b C2 d e f g"))
    check(len(conflicts(p)) == 1, "overlap conflict")
    r = render(p)
    check("<<<<<<< ours\nC1\n||||||| base\nc\n=======\nC2\n>>>>>>> theirs\n" in r, "markers")
    check(render(p, ["o"]).split() == "a b C1 d e f g".split() and render(p, ["t"]).split() == "a b C2 d e f g".split(), "choose o/t")
    check(render(p, ["b"]).split() == "a b C1 C2 d e f g".split() and render(p, ["base"]) == "".join(b), "choose both/base")
    check(render(merge3(["x"], ["x"], ["y"])) == "y", "no trailing newline")

    # property tests: random edits
    rnd = random.Random(7)
    words = list("abcdefghij")

    def mutate(lines):
        out = list(lines)
        for _ in range(rnd.randint(1, 4)):
            op, i = rnd.choice("dir"), rnd.randint(0, len(out))
            if op == "d" and out:
                del out[min(i, len(out) - 1)]
            elif op == "i":
                out.insert(i, rnd.choice(words).upper() + "\n")
            elif out:
                out[min(i, len(out) - 1)] = rnd.choice(words).upper() + "\n"
        return out

    prop_ok = True
    for _ in range(300):
        base_l = [rnd.choice(words) + "\n" for _ in range(rnd.randint(0, 15))]
        side = mutate(base_l)
        a = merge3(base_l, side, base_l)
        c = merge3(base_l, base_l, side)
        d = merge3(base_l, side, side)
        if render(a) != "".join(side) or render(c) != "".join(side) or conflicts(d) or render(d) != "".join(side):
            prop_ok = False
            break
    check(prop_ok, "property: one-side-only == that side; identical == clean")
    conf_ok = True
    for _ in range(200):
        base_l = [rnd.choice(words) + "\n" for _ in range(rnd.randint(1, 15))]
        i = rnd.randrange(len(base_l))
        o, t = list(base_l), list(base_l)
        o[i], t[i] = "OURS\n", "THEIRS\n"
        if len(conflicts(merge3(base_l, o, t))) != 1:
            conf_ok = False
            break
    check(conf_ok, "property: overlapping edits conflict")

    # files + history + confinement
    old = BASE_DIR
    tmp = tempfile.mkdtemp()
    BASE_DIR = tmp
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        f = os.path.join(tmp, "m.py")
        atomic_write(f, "a\nb\nc\n")
        backup("m.py", "base")
        atomic_write(f, "a\nB\nc\n")
        check(version_text(f, 1) == "a\nb\nc\n", "history read")
        outside = tempfile.mkdtemp()
        os.symlink(outside, os.path.join(tmp, "esc"))
        os.symlink(f, os.path.join(tmp, "ln.py"))
        for bad in ("../x", "/etc/passwd", "esc/x", "ln.py", ".history", ".history/x", ""):
            try:
                confine(bad); check(False, f"allowed {bad!r}")
            except ValueError:
                check(True, "")
        atomic_write(os.path.join(tmp, "big.txt"), "x" * (MAX_BYTES + 1))
        try:
            read_text(confine("big.txt")); check(False, "size cap")
        except ValueError:
            check(True, "")
        # scripted end-to-end through the menu
        import builtins
        ans = iter(["1", "m.py", "1", "c", "f", "theirs.py", "y", "q"])
        atomic_write(os.path.join(tmp, "theirs.py"), "a\nb\nc\nd\n")
        try:
            asyncio.get_running_loop(); e2e = False   # called from the menu: skip the nested run
        except RuntimeError:
            e2e = not IN_PYODIDE
        real = builtins.input
        builtins.input = lambda p="": next(ans)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                if e2e:
                    asyncio.run(amain())
        finally:
            builtins.input = real
        if e2e:
            check(read_text(f) == "a\nB\nc\nd\n", "end-to-end merge")
            check(len(versions(f)) == 2, "history backup before write")
        check(not [x for x in os.listdir(tmp) if x.startswith(".kp_tmp_")], "no temp files")
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
