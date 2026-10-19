# KPython r9 snippet library: save/edit/delete/list/search/show/insert code snippets with {{var}} fill-in, JSON export/import; no secrets, paths confined to ~.
"""Snippet library for KPython (stdlib only, Pyodide-friendly input()).

Storage: /home/pyodide/kp_snippets.json  ({"version": 1, "snippets": {name: {...}}})
Every path goes through kp_safe_path (the app's guard) or a local equivalent; reads and writes are
capped at 500 KB and writes are atomic (temp file + os.replace).
Uses kp_common + r8_forlor_nav helpers when importable, with a tiny fallback otherwise.
"""
import builtins, datetime, json, os, re, sys, tempfile

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
if _HERE and _HERE not in sys.path:
    sys.path.append(_HERE)

try:
    from kp_common import MAX_TEXT as _KP_MAX
except Exception:
    _KP_MAX = 500_000
MAX_BYTES = min(_KP_MAX, 500_000)

try:
    from r8_forlor_nav import ask, need, confirm, choose, paste, run_menu, run_tool, Back, Quit, QUIT_WORDS
except Exception:  # ---- tiny fallback with the same behavior ----
    QUIT_WORDS = ("q", "quit", "exit")

    class Back(Exception): pass

    class Quit(Exception): pass

    def ask(prompt=""):
        try:
            return input(prompt).strip() or None
        except (KeyboardInterrupt, EOFError):
            return None

    def need(prompt=""):
        a = ask(prompt)
        if a is None:
            raise Back()
        return a

    def confirm(prompt):
        return (ask(prompt + " (y/N): ") or "").lower() in ("y", "yes")

    def choose(prompt, items, label=str):
        items = list(items)
        if not items:
            print("(nothing to choose from)"); return None
        for i, it in enumerate(items, 1):
            print(f"  {i}) {label(it)}")
        while True:
            a = ask(f"{prompt} (1-{len(items)}, blank = back): ")
            if a is None or a.lower() in QUIT_WORDS:
                return None
            if a.isdigit() and 1 <= int(a) <= len(items):
                return items[int(a) - 1]
            print(f"Enter a number 1-{len(items)}, or press Enter to go back.")

    def paste(prompt="Paste text, then a line with only END:", end="END"):
        if prompt: print(prompt)
        lines = []
        while True:
            try: l = input("")
            except (KeyboardInterrupt, EOFError): break
            if l.strip() in (end, "."): break
            lines.append(l)
        return "\n".join(lines)

    def run_menu(title, options, top=False, prompt="> "):
        entries = [((str(n), *o) if len(o) == 2 else o) for n, o in enumerate(options, 1)]
        while True:
            print(f"\n{title}")
            for k, label, _ in entries: print(f"  {k}) {label}")
            try: a = input(prompt).strip().lower()
            except (KeyboardInterrupt, EOFError): return
            if a == "":
                if top: continue
                return
            if a in QUIT_WORDS:
                if top: return
                raise Quit()
            fn = next((f for k, _, f in entries if str(k).lower() == a), None)
            if fn is None:
                print("Pick " + ", ".join(str(k) for k, _, _ in entries) + " or q."); continue
            try: fn()
            except Back: pass
            except KeyboardInterrupt: print("(cancelled)")
            except Quit:
                if top: return
                raise

    def run_tool(main_fn, *a, **k):
        try: return main_fn(*a, **k)
        except (Quit, Back): pass
        except (KeyboardInterrupt, EOFError): print("\nCancelled.")

APP_HOME = "/home/pyodide"
CFG = {"home": APP_HOME, "store": "kp_snippets.json"}
NAME_RE = re.compile(r"^[\w .\-]{1,60}$")
VAR_RE = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*\}\}")
SECRET_RE = re.compile(
    r"(gh[pousr]_[A-Za-z0-9]{10,}|github_pat_\w{10,}|sk-[A-Za-z0-9_\-]{10,}|AKIA[0-9A-Z]{12,}"
    r"|eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]*|xox[abprs]-[\w-]{6,})")


# ---------------- paths & storage ----------------
def safe_path(p):
    """Resolve p under the home dir; refuse '..' escapes, outside absolute paths and symlinks."""
    home = CFG["home"]
    p = str(p or "").strip()
    if not p:
        raise ValueError("empty path")
    guard = getattr(builtins, "kp_safe_path", None)
    if guard is not None and home == APP_HOME:
        return guard(p)                       # the app's shared rule (also refuses symlinks)
    raw = os.path.normpath(os.path.join(home, p))
    full = os.path.realpath(raw)
    root = os.path.realpath(home)
    if full != root and not full.startswith(root + os.sep):
        raise ValueError(f"refused: {p} is outside {home}")
    cur = home
    for part in os.path.relpath(raw, home).split(os.sep):
        if part in ("", "."):
            continue
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise ValueError(f"refused: {p} goes through a symlink")
    return full


def read_text(p):
    full = safe_path(p)
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError(f"{p} is over {MAX_BYTES // 1000} KB")
    with open(full, encoding="utf-8") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"{p} is over {MAX_BYTES // 1000} KB")
    return data


def write_text(p, text):
    """Atomic, capped write inside home."""
    data = text.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError(f"not saved: over {MAX_BYTES // 1000} KB")
    full = safe_path(p)
    d = os.path.dirname(full)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".kp_snip_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush()
            try: os.fsync(f.fileno())
            except OSError: pass
        os.replace(tmp, full)
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise
    return full


def empty_lib():
    return {"version": 1, "snippets": {}}


def load():
    try:
        full = safe_path(CFG["store"])
    except ValueError:
        raise
    if not os.path.exists(full):
        return empty_lib()
    data = json.loads(read_text(CFG["store"]))
    if not isinstance(data, dict) or not isinstance(data.get("snippets"), dict):
        raise ValueError("snippet file is not in the expected format")
    return data


def save(lib):
    return write_text(CFG["store"], json.dumps(lib, indent=1, ensure_ascii=False, sort_keys=True))


# ---------------- core logic (no input) ----------------
def norm_tags(s):
    if isinstance(s, (list, tuple)):
        s = ",".join(map(str, s))
    return sorted({t.strip().lower() for t in re.split(r"[,\s]+", s or "") if t.strip()})


def find_secrets(code):
    return sorted({m.group(0)[:6] + "…" for m in SECRET_RE.finditer(code or "")})


def make(lang, tags, code):
    return {"lang": (lang or "text").strip().lower(), "tags": norm_tags(tags), "code": code,
            "updated": datetime.datetime.now().replace(microsecond=0).isoformat()}


def put(lib, name, snip):
    if not NAME_RE.match(name or ""):
        raise ValueError("name: 1-60 letters, digits, space, . _ -")
    if len(snip.get("code", "")) > MAX_BYTES:
        raise ValueError("code too big")
    lib["snippets"][name] = snip


def matches_filter(name, s, flt):
    if not flt:
        return True
    f = flt.strip().lower()
    if f.startswith("tag:"):
        return f[4:].strip() in s.get("tags", [])
    if f.startswith("lang:"):
        return s.get("lang", "") == f[5:].strip()
    return f in s.get("tags", []) or s.get("lang", "") == f


def list_names(lib, flt=None):
    return sorted(n for n, s in lib["snippets"].items() if matches_filter(n, s, flt))


def search(lib, q):
    q = (q or "").lower()
    if not q:
        return []
    return sorted(n for n, s in lib["snippets"].items()
                  if q in n.lower() or any(q in t for t in s.get("tags", [])) or q in s.get("code", "").lower())


def placeholders(code):
    seen = []
    for v in VAR_RE.findall(code):
        if v not in seen:
            seen.append(v)
    return seen


def fill(code, values):
    return VAR_RE.sub(lambda m: values.get(m.group(1), m.group(0)), code)


def export_data(lib, tags=None):
    tags = norm_tags(tags) if tags else None
    snips = {n: s for n, s in lib["snippets"].items() if not tags or set(tags) & set(s.get("tags", []))}
    return {"version": 1, "kind": "kp_snippets", "snippets": snips}


def parse_import(text):
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("snippets"), dict):
        items = data["snippets"].items()
    elif isinstance(data, list):
        items = [(d.get("name"), d) for d in data if isinstance(d, dict)]
    else:
        raise ValueError("not a snippet export (need {'snippets': {...}} or a list)")
    out = {}
    for n, s in items:
        if not isinstance(s, dict) or not isinstance(s.get("code"), str) or not NAME_RE.match(str(n or "")):
            continue
        out[str(n)] = {"lang": str(s.get("lang") or "text").lower(), "tags": norm_tags(s.get("tags") or []),
                       "code": s["code"], "updated": str(s.get("updated") or "")}
    return out


def editor_hook():
    """Return the app's insert-into-editor function if it exposes one, else None.
    (KPython v9 has none in kp_worker.py / kp_common.py; we look up likely names so a future hook just works.)"""
    for name in ("kp_editor_insert", "kp_insert"):
        f = getattr(builtins, name, None)
        if callable(f):
            return f
    return None   # KPython: only the app's confirmed builtins.kp_editor_insert bridge (no raw JS hook)


# ---------------- interactive pieces ----------------
def _secret_ok(code, what="This code"):
    hits = find_secrets(code)
    if not hits:
        return True
    print(f"WARNING: {what} looks like it contains a secret/token ({', '.join(hits)}).")
    print("Snippets must not store real keys. Replace it with a placeholder like {{token}}.")
    if confirm("Is this only a fake placeholder, not a real secret?"):
        return True
    print("Refused: not saved.")
    return False


def _pick(lib, prompt="Snippet", flt=None):
    names = list_names(lib, flt)
    if not names:
        print("No snippets" + (" match." if flt else " yet."))
        raise Back()
    n = choose(prompt, names, label=lambda n: f"{n}  [{lib['snippets'][n]['lang']}] {' '.join('#' + t for t in lib['snippets'][n]['tags'])}")
    if n is None:
        raise Back()
    return n


def show(lib, name):
    s = lib["snippets"][name]
    print(f"\n== {name} ==  lang: {s['lang']}  tags: {', '.join(s['tags']) or '-'}  updated: {s.get('updated') or '-'}")
    print(s["code"])


def ui_save(lib):
    name = need("Snippet name (blank = back): ")
    if not NAME_RE.match(name):
        print("Use 1-60 letters, digits, space, . _ -"); raise Back()
    if name in lib["snippets"] and not confirm(f"'{name}' exists. Overwrite?"):
        print("Kept the old one."); raise Back()
    lang = ask("Language [python]: ") or "python"
    tags = ask("Tags (comma-separated, blank = none): ") or ""
    code = paste("Paste the code, then a line with only END (Cancel also finishes):")
    if not code.strip():
        print("Empty code, nothing saved."); raise Back()
    if not _secret_ok(code):
        raise Back()
    put(lib, name, make(lang, tags, code)); save(lib); print(f"Saved '{name}'.")


def ui_edit(lib):
    name = _pick(lib, "Edit which")
    s = dict(lib["snippets"][name])
    new_name = ask(f"Name [{name}]: ") or name
    if new_name != name:
        if not NAME_RE.match(new_name):
            print("Bad name."); raise Back()
        if new_name in lib["snippets"] and not confirm(f"'{new_name}' exists. Overwrite?"):
            raise Back()
    lang = ask(f"Language [{s['lang']}]: ") or s["lang"]
    tags = ask(f"Tags [{', '.join(s['tags']) or 'none'}] ('-' = clear): ")
    tags = s["tags"] if tags is None else ([] if tags == "-" else tags)
    code = s["code"]
    if confirm("Replace the code?"):
        c = paste("Paste the new code, then END:")
        if c.strip():
            code = c
    if not _secret_ok(code):
        raise Back()
    if new_name != name:
        del lib["snippets"][name]
    put(lib, new_name, make(lang, tags, code)); save(lib); print(f"Updated '{new_name}'.")


def ui_delete(lib):
    name = _pick(lib, "Delete which")
    if confirm(f"Delete '{name}'?"):
        del lib["snippets"][name]; save(lib); print("Deleted.")
    else:
        print("Kept.")


def ui_list(lib):
    flt = ask("Filter: tag or language, or tag:x / lang:y (blank = all): ")
    names = list_names(lib, flt)
    for n in names:
        s = lib["snippets"][n]
        print(f"  {n:24} [{s['lang']}] {' '.join('#' + t for t in s['tags'])}")
    print(f"{len(names)} snippet(s).")


def ui_search(lib):
    q = need("Search name, tags and code (blank = back): ")
    hits = search(lib, q)
    for n in hits:
        print(f"  {n}  [{lib['snippets'][n]['lang']}]")
    print(f"{len(hits)} match(es).")


def ui_show(lib):
    show(lib, _pick(lib, "Show which"))


def ui_insert(lib):
    name = _pick(lib, "Insert which")
    code = lib["snippets"][name]["code"]
    vars_ = placeholders(code)
    if vars_ and confirm(f"Fill in {len(vars_)} placeholder(s) ({', '.join(vars_)})?"):
        vals = {}
        for v in vars_:
            a = ask(f"  {v} (blank = keep {{{{{v}}}}}): ")
            if a is not None:
                vals[v] = a
        code = fill(code, vals)
    hook = editor_hook()
    if hook is not None:
        try:
            ok = hook(code)
            if ok is False: print("Not inserted (declined in the app)."); print("\n----- copy below -----\n" + code + "\n----- end -----"); return
            print("Inserted into the editor."); return
        except Exception as e:
            print("Editor insert failed:", e)
    print("\n----- copy below -----\n" + code + "\n----- end -----")


def ui_export(lib):
    tags = ask("Only these tags (comma-separated, blank = whole library): ")
    data = export_data(lib, tags)
    if not data["snippets"]:
        print("Nothing to export."); raise Back()
    dest = ask("Export to (file under ~) [kp_snippets_export.json]: ") or "kp_snippets_export.json"
    full = safe_path(dest)
    if os.path.exists(full) and not confirm(f"{dest} exists. Overwrite?"):
        raise Back()
    write_text(dest, json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True))
    print(f"Exported {len(data['snippets'])} snippet(s) to {full}.")


def ui_import(lib):
    src = need("Import from (JSON file under ~, blank = back): ")
    incoming = parse_import(read_text(src))
    if not incoming:
        print("No valid snippets in that file."); raise Back()
    mode = (ask("Duplicates: m = merge (ask for each), s = skip all [s]: ") or "s").lower()
    if mode in QUIT_WORDS:
        raise Back()
    added = replaced = skipped = refused = 0
    for n, s in sorted(incoming.items()):
        if find_secrets(s["code"]) and not _secret_ok(s["code"], f"'{n}'"):
            refused += 1; continue
        if n in lib["snippets"]:
            if lib["snippets"][n]["code"] == s["code"] or mode != "m" or not confirm(f"'{n}' already exists. Overwrite it?"):
                skipped += 1; continue
            replaced += 1
        else:
            added += 1
        put(lib, n, s)
    if added or replaced:
        save(lib)
    print(f"Imported: {added} new, {replaced} replaced, {skipped} skipped, {refused} refused (secrets).")


def main():
    try:
        lib = load()
    except ValueError as e:
        print("Can't open the snippet library:", e); return
    def w(fn):
        def go():
            try:
                fn(lib)
            except (ValueError, OSError) as e:
                print("Error:", e)
        return go
    print(f"=== Snippet Library === {len(lib['snippets'])} snippet(s) in ~/{CFG['store']}")
    run_menu("Snippets", [("List (filter by tag/language)", w(ui_list)), ("Search", w(ui_search)),
                          ("Show", w(ui_show)), ("Insert (copy / fill {{vars}})", w(ui_insert)),
                          ("Save new", w(ui_save)), ("Edit", w(ui_edit)), ("Delete", w(ui_delete)),
                          ("Export to JSON", w(ui_export)), ("Import from JSON", w(ui_import)),
                          ("t", "Self-test", self_test)], top=True)


# ---------------- self-test ----------------
def self_test():
    import io, contextlib, shutil
    CANCEL = object()
    old_input, old_cfg = builtins.input, dict(CFG)
    tmp = tempfile.mkdtemp(prefix="kp_snip_test_")
    out = io.StringIO()

    def feed(answers):
        it = iter(answers)
        def fake(p=""):
            v = next(it, CANCEL)
            if v is CANCEL:
                raise KeyboardInterrupt("input cancelled")
            return v
        builtins.input = fake

    try:
        CFG.update(home=tmp, store="kp_snippets.json")
        with contextlib.redirect_stdout(out):
            lib = load(); assert lib["snippets"] == {}
            # --- save via UI: name, lang, tags, paste (Cancel ends paste) ---
            feed(["hello", "Python", "Demo, Basics", "print('hi {{who}}')", "x = 1", "END"]); ui_save(lib)
            feed(["req", "", "http", "import urllib.request", "url = '{{base}}/x'", CANCEL]); ui_save(lib)
            lib = load()
            assert lib["snippets"]["hello"]["tags"] == ["basics", "demo"] and lib["snippets"]["hello"]["lang"] == "python"
            assert lib["snippets"]["req"]["code"].endswith("/x'") and lib["snippets"]["req"]["lang"] == "python"
            # overwrite existing name: blank = No -> Back, nothing changes
            feed(["hello", ""])
            try: ui_save(lib); raise AssertionError("overwrite without confirm")
            except Back: pass
            assert "x = 1" in load()["snippets"]["hello"]["code"]
            # blank name / Cancel = back
            for a in ([""], [CANCEL]):
                feed(a)
                try: ui_save(lib); raise AssertionError("blank name")
                except Back: pass
            # --- secret refusal and placeholder confirm ---
            tok = "ghp_" + "A1b2C3d4E5f6G7h8I9j0"
            feed(["leak", "py", "", f"T = '{tok}'", "END", ""])
            try: ui_save(lib); raise AssertionError("secret saved")
            except Back: pass
            assert "leak" not in load()["snippets"]
            for t in ("sk-abcdefghijklmnop1234", "AKIAABCDEFGHIJKLMNOP", "eyJhbGciOi.eyJzdWIiOi.sig", "xoxb-123456-abcdef"):
                assert find_secrets(t), t
            assert not find_secrets("token = '{{token}}'  # sk- and ghp_ prefixes only")
            feed(["fake", "py", "", "T = 'sk-THISISAFAKEPLACEHOLDER'", "END", "yes"]); ui_save(lib)
            assert "fake" in load()["snippets"]
            # --- list / filter / search ---
            lib = load()
            assert list_names(lib, "demo") == ["hello"] and list_names(lib, "tag:http") == ["req"]
            assert list_names(lib, "lang:python") == ["hello", "req"] and list_names(lib, "py") == ["fake"] and list_names(lib, None) == ["fake", "hello", "req"]
            assert search(lib, "URLLIB") == ["req"] and search(lib, "BASICS") == ["hello"] and search(lib, "hel") == ["hello"]
            assert search(lib, "") == []
            feed([CANCEL]); ui_list(lib)            # Cancel on filter = show all
            feed([""])
            try: ui_search(lib); raise AssertionError("blank search")
            except Back: pass
            # --- edit: pick 2 (hello), rename blank, lang blank, tags '-', replace code ---
            feed(["9", "abc", "2", "", "", "-", "y", "print('edited')", "END"]); ui_edit(lib)
            lib = load(); assert lib["snippets"]["hello"]["code"] == "print('edited')" and lib["snippets"]["hello"]["tags"] == []
            # edit then Cancel at picker = back, no change
            feed([CANCEL])
            try: ui_edit(lib); raise AssertionError("cancel edit")
            except Back: pass
            # --- insert with placeholder fill ---
            assert placeholders("{{a}} {{ b }} {{a}}") == ["a", "b"] and fill("{{a}}-{{b}}", {"a": "1"}) == "1-{{b}}"
            got = []
            builtins.kp_editor_insert = got.append
            try:
                feed(["3", "y", "https://api.example.com"]); ui_insert(lib)
            finally:
                del builtins.kp_editor_insert
            assert got == ["import urllib.request\nurl = 'https://api.example.com/x'"], got
            feed(["3", ""]); ui_insert(lib)         # no hook -> printed, placeholders kept
            assert "{{base}}/x" in out.getvalue()
            # --- delete: blank confirm = keep; y = delete ---
            feed(["1", ""]); ui_delete(lib); assert "fake" in load()["snippets"]
            feed(["1", "Y"]); ui_delete(lib); lib = load(); assert "fake" not in lib["snippets"]
            # --- export / import round trip ---
            feed(["http", "out.json"]); ui_export(lib)
            exp = json.loads(read_text("out.json")); assert list(exp["snippets"]) == ["req"]
            feed(["", "all.json"]); ui_export(lib)
            feed(["", "all.json", ""])              # exists, blank = don't overwrite
            try: ui_export(lib); raise AssertionError("export overwrite")
            except Back: pass
            CFG["store"] = "second.json"; lib2 = load()
            feed(["all.json", ""]); ui_import(lib2)
            assert load()["snippets"] == lib["snippets"]
            # merge: changed duplicate asks; n = keep, y = replace; skip mode never asks
            ch = export_data(lib); ch["snippets"]["req"] = dict(ch["snippets"]["req"], code="print('v2')")
            write_text("chg.json", json.dumps(ch))
            lib2 = load()
            feed(["chg.json", "m", "n"]); ui_import(lib2); assert "v2" not in load()["snippets"]["req"]["code"]
            feed(["chg.json", "s"]); ui_import(lib2); assert "v2" not in load()["snippets"]["req"]["code"]
            feed(["chg.json", "m", "yes"]); ui_import(lib2); assert load()["snippets"]["req"]["code"] == "print('v2')"
            # import refuses secret snippets
            write_text("bad.json", json.dumps({"snippets": {"k": {"code": "K='AKIAABCDEFGHIJKLMNOP'"}}}))
            feed(["bad.json", "s", ""]); ui_import(lib2); assert "k" not in load()["snippets"]
            CFG["store"] = "kp_snippets.json"
            # --- path escape refusal ---
            for bad in ("../evil.json", "/etc/passwd", "a/../../x"):
                try: safe_path(bad); raise AssertionError("escaped: " + bad)
                except ValueError: pass
            os.symlink("/tmp", os.path.join(tmp, "ln"))
            try: safe_path("ln/x.json"); raise AssertionError("symlink")
            except ValueError: pass
            feed(["../x.json"])
            try: ui_import(lib); raise AssertionError("import escape")
            except ValueError: pass
            # --- size cap on write and read ---
            try: write_text("big.json", "x" * (MAX_BYTES + 1)); raise AssertionError("write cap")
            except ValueError: pass
            assert not os.path.exists(os.path.join(tmp, "big.json"))
            with open(os.path.join(tmp, "big2.json"), "w") as f: f.write(" " * (MAX_BYTES + 10))
            try: read_text("big2.json"); raise AssertionError("read cap")
            except ValueError: pass
            assert not [f for f in os.listdir(tmp) if f.startswith(".kp_snip_")], "temp file left behind"
            # --- full menu: Cancel at top exits; bad key, blank, Cancel in inner prompt, q quits ---
            feed([CANCEL]); main()
            feed(["zz", "", "3", CANCEL, "2", "", "1", "demo", "q"]); main()
            feed(["5", "n2", "", "", "a", CANCEL, "quit"]); main()
            assert "n2" in load()["snippets"]
            run_tool(lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    finally:
        builtins.input = old_input
        CFG.clear(); CFG.update(old_cfg)
        shutil.rmtree(tmp, ignore_errors=True)
    print("r9_forlor_snippets self-tests passed.")
    return True



# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        self_test()
    else:
        run_tool(main)
