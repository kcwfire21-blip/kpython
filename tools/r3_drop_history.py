# Drop's Function Maker + Local History: turn a pasted snippet into a def (params/returns via ast), and keep git-style saved versions of files under /home/pyodide/.history (save, list, diff, restore). Stdlib only, no network.
import ast, builtins, difflib, hashlib, json, keyword, os, time

BASE_DIR = "/home/pyodide"
HIST_NAME = ".history"
MAX_BYTES = 500_000
MAX_LINES = 5000
MAX_VERSIONS = 200
MAX_MSG = 200


# ---------------- shared input helpers ----------------
def paste(label="code"):
    print(f"Paste {label}. End with a line containing only END:")
    lines, size = [], 0
    while True:
        l = input()
        if l.strip() == "END":
            break
        size += len(l) + 1
        if size > MAX_BYTES or len(lines) >= MAX_LINES:
            raise ValueError(f"too much input (max {MAX_LINES} lines / {MAX_BYTES:,} chars)")
        lines.append(l)
    return "\n".join(lines) + ("\n" if lines else "")


def yes(prompt):
    return input(prompt + " (y/n): ").strip().lower() in ("y", "yes")


# ---------------- (1) snippet -> function ----------------
def valid_name(name):
    return name.isidentifier() and not keyword.iskeyword(name)


def analyze(code):
    """Return (params, returns) for a snippet. Raises SyntaxError on bad code."""
    tree = ast.parse(code)
    stored, loaded_first, imported = set(), [], set()
    comp_only = set()

    # names bound inside comprehensions are local to them
    for n in ast.walk(tree):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for g in n.generators:
                for t in ast.walk(g.target):
                    if isinstance(t, ast.Name):
                        comp_only.add(t.id)

    class V(ast.NodeVisitor):
        def __init__(self):
            self.seen_store = set()

        def _bind(self, name):
            stored.add(name)
            self.seen_store.add(name)

        def visit_Name(self, n):
            if isinstance(n.ctx, ast.Load):
                if n.id not in self.seen_store and n.id not in loaded_first:
                    loaded_first.append(n.id)
            else:
                self._bind(n.id)

        def visit_Assign(self, n):  # value is evaluated before targets
            self.visit(n.value)
            for t in n.targets:
                self.visit(t)

        def visit_AugAssign(self, n):  # x += 1 reads x first
            if isinstance(n.target, ast.Name) and n.target.id not in self.seen_store and n.target.id not in loaded_first:
                loaded_first.append(n.target.id)
            self.visit(n.value)
            self.visit(n.target)

        def visit_AnnAssign(self, n):
            if n.value:
                self.visit(n.value)
            self.visit(n.target)

        def visit_For(self, n):
            self.visit(n.iter)
            self.visit(n.target)
            for s in n.body + n.orelse:
                self.visit(s)

        def visit_comprehension(self, n):
            self.visit(n.iter)
            for i in n.ifs:
                self.visit(i)

        def _comp(self, n):
            for g in n.generators:
                self.visit(g)
            for f in ("elt", "key", "value"):
                if getattr(n, f, None) is not None:
                    v = getattr(n, f)
                    # comprehension vars aren't free names
                    for t in ast.walk(v):
                        if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Load) and t.id not in comp_only:
                            if t.id not in self.seen_store and t.id not in loaded_first:
                                loaded_first.append(t.id)

        visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comp

        def visit_Import(self, n):
            for a in n.names:
                nm = (a.asname or a.name).split(".")[0]
                imported.add(nm)
                self._bind(nm)

        visit_ImportFrom = visit_Import

        def visit_FunctionDef(self, n):
            for d in n.decorator_list:
                self.visit(d)
            self._bind(n.name)  # body is a separate scope; don't treat its names as free here

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, n):
            for b in n.bases + n.decorator_list:
                self.visit(b)
            self._bind(n.name)

        def visit_Lambda(self, n):
            pass

        def visit_ExceptHandler(self, n):
            if n.type:
                self.visit(n.type)
            if n.name:
                self._bind(n.name)
            for s in n.body:
                self.visit(s)

        def visit_With(self, n):
            for it in n.items:
                self.visit(it.context_expr)
                if it.optional_vars:
                    self.visit(it.optional_vars)
            for s in n.body:
                self.visit(s)

        visit_AsyncWith = visit_With

    V().visit(tree)
    bi = set(dir(builtins))
    params = [n for n in loaded_first if n not in bi and n not in comp_only and n not in ("__name__", "__file__")]
    returns = [n for n in sorted(stored - comp_only - imported) if not n.startswith("_")]
    # keep return order as first assignment order in the source
    order = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in returns and n.id not in order:
            order.append(n.id)
    returns = order + [r for r in returns if r not in order]
    return params, returns


def scaffold(code, name):
    if not valid_name(name):
        raise ValueError(f"{name!r} is not a valid Python function name")
    params, returns = analyze(code)
    body = [("    " + l) if l.strip() else "" for l in code.rstrip("\n").splitlines()] or ["    pass"]
    doc = ['    """TODO: describe what this does.', ""]
    if params:
        doc.append("    Args:")
        doc += [f"        {p}: TODO" for p in params]
    if returns:
        doc.append("    Returns:")
        doc.append("        " + ", ".join(returns))
    doc.append('    """')
    out = [f"def {name}({', '.join(params)}):"] + doc + body
    if len(returns) == 1:
        out.append(f"    return {returns[0]}")
    elif returns:
        out.append(f"    return {', '.join(returns)}")
    call = f"{name}({', '.join(p + '=...' for p in params)})"
    lhs = (", ".join(returns) + " = ") if returns else ""
    out += ["", "", "# Example call (fill in the values):", f"# {lhs}{call}"]
    result = "\n".join(out) + "\n"
    ast.parse(result)  # sanity check: never executed
    return result


def menu_scaffold():
    code = paste("the snippet")
    if not code.strip():
        print("Nothing pasted.")
        return
    name = input("Function name: ").strip()
    try:
        print("\n" + scaffold(code, name))
    except SyntaxError as e:
        print(f"Syntax error in snippet, line {e.lineno}: {e.msg}")


# ---------------- (2) local history ----------------
def base():
    return os.path.realpath(BASE_DIR)


def hist_root():
    return os.path.join(base(), HIST_NAME)


def safe_path(p):
    """Resolve p inside BASE_DIR (symlinks followed); refuse escapes and the history folder itself."""
    p = (p or "").strip()
    if not p or "\x00" in p:
        raise ValueError("empty or invalid path")
    if p == "~" or p.startswith("~/"):
        p = p[2:] or "."
    b = base()
    full = os.path.realpath(os.path.join(b, p))
    if not full.startswith(b + os.sep):
        raise ValueError(f"refused: {p} is outside {BASE_DIR}")
    h = hist_root()
    if full == h or full.startswith(h + os.sep):
        raise ValueError("refused: files inside .history are managed by this tool")
    return full


def read_text(full):
    if not os.path.isfile(full):
        raise ValueError(f"not a file: {full}")
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError(f"file too big (max {MAX_BYTES:,} bytes)")
    with open(full, "rb") as f:
        data = f.read(MAX_BYTES + 1)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("only UTF-8 text files are supported")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hist_dir(full):
    """History folder for a file: a sha256 of its path relative to BASE_DIR, so no path text reaches the filesystem."""
    rel = os.path.relpath(full, base())
    d = os.path.join(hist_root(), hashlib.sha256(rel.encode("utf-8")).hexdigest()[:32])
    hr = os.path.realpath(hist_root())
    if not hr.startswith(base() + os.sep):
        raise ValueError(".history is a symlink pointing outside; refusing")
    if os.path.lexists(d) and not os.path.realpath(d).startswith(hr + os.sep):
        raise ValueError("history folder is a symlink; refusing")
    return d, rel


def load_index(d, rel):
    p = os.path.join(d, "index.json")
    if not os.path.exists(p):
        return {"path": rel, "versions": []}
    try:
        with open(p, encoding="utf-8") as f:
            idx = json.load(f)
        if not isinstance(idx, dict) or not isinstance(idx.get("versions"), list):
            raise ValueError
        good = []
        for v in idx["versions"]:
            if isinstance(v, dict) and isinstance(v.get("id"), int) and isinstance(v.get("sha256"), str) and isinstance(v.get("ts"), str):
                good.append(v)
        idx["versions"] = good
        return idx
    except (OSError, ValueError):
        raise ValueError("history index is damaged (index.json); not touching it")


def save_index(d, idx):
    tmp = os.path.join(d, "index.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=1)
    os.replace(tmp, os.path.join(d, "index.json"))


def version_file(d, vid):
    return os.path.join(d, f"v{int(vid):05d}.txt")


def save_version(path, msg=""):
    full = safe_path(path)
    text = read_text(full)
    d, rel = hist_dir(full)
    os.makedirs(d, exist_ok=True)
    idx = load_index(d, rel)
    vs = idx["versions"]
    digest = sha(text)
    if vs and vs[-1]["sha256"] == digest:
        print(f"Unchanged since v{vs[-1]['id']}; not saving a duplicate.")
        return vs[-1]["id"]
    if len(vs) >= MAX_VERSIONS:
        raise ValueError(f"{MAX_VERSIONS} versions already saved for this file")
    vid = (vs[-1]["id"] + 1) if vs else 1
    with open(version_file(d, vid), "w", encoding="utf-8") as f:
        f.write(text)
    msg = "".join(c for c in str(msg) if c.isprintable())[:MAX_MSG]
    vs.append({"id": vid, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "msg": msg, "sha256": digest, "bytes": len(text.encode())})
    save_index(d, idx)
    print(f"Saved {rel} as v{vid}.")
    return vid


def list_versions(path):
    full = safe_path(path)
    d, rel = hist_dir(full)
    vs = load_index(d, rel)["versions"]
    if not vs:
        print(f"No saved versions of {rel}.")
    for v in vs:
        print(f"v{v['id']:<4} {v['ts']}  {v.get('bytes', '?'):>7} B  {v['sha256'][:10]}  {v.get('msg', '')}")
    return vs


def get_version(full, vid):
    d, rel = hist_dir(full)
    vs = {v["id"]: v for v in load_index(d, rel)["versions"]}
    if vid not in vs:
        raise ValueError(f"no version v{vid}")
    vf = version_file(d, vid)
    if not os.path.isfile(vf) or os.path.islink(vf):
        raise ValueError(f"v{vid} file is missing")
    with open(vf, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    if sha(text) != vs[vid]["sha256"]:
        raise ValueError(f"v{vid} failed its sha256 check (file changed or damaged)")
    return text


def parse_vid(s):
    s = (s or "").strip().lower().lstrip("v")
    if not s.isdigit() or not 0 < int(s) < 10**6:
        raise ValueError("version must be a number like 3 or v3")
    return int(s)


def diff(path, va, vb=None):
    """Diff version va against version vb, or the current file if vb is None."""
    full = safe_path(path)
    rel = os.path.relpath(full, base())
    a = get_version(full, va)
    if vb is None:
        b, nb = read_text(full), f"{rel} (current)"
    else:
        b, nb = get_version(full, vb), f"{rel} v{vb}"
    out = "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(), f"{rel} v{va}", nb, lineterm=""))
    print(out or "(no differences)")
    return out


def restore(path, vid, confirm=True):
    full = safe_path(path)
    old = get_version(full, vid)
    rel = os.path.relpath(full, base())
    if confirm and not yes(f"Overwrite {rel} with v{vid}? The current file is saved as a new version first."):
        print("Cancelled.")
        return False
    if os.path.exists(full):
        save_version(path, f"auto-save before restoring v{vid}")
    with open(full, "w", encoding="utf-8") as f:
        f.write(old)
    print(f"Restored {rel} to v{vid}.")
    return True


def menu_history():
    path = input("File (inside ~): ").strip()
    safe_path(path)  # validate early
    while True:
        c = input(f"\n[{path}] s Save  l List  d Diff  r Restore  b Back: ").strip().lower()
        try:
            if c == "s":
                save_version(path, input("Message (optional): "))
            elif c == "l":
                list_versions(path)
            elif c == "d":
                va = parse_vid(input("Version: "))
                other = input("Compare with version (Enter = current file): ").strip()
                diff(path, va, parse_vid(other) if other else None)
            elif c == "r":
                restore(path, parse_vid(input("Restore which version: ")))
            elif c == "b":
                return
            else:
                print("Pick s, l, d, r or b.")
        except (ValueError, OSError) as e:
            print("Error:", e)


# ---------------- self-tests ----------------
def run_self_tests():
    """Tests that run inside a throwaway folder under BASE_DIR. Returns True if all pass."""
    global BASE_DIR
    import tempfile, shutil
    ok = fail = 0

    def check(cond, label):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
            print("FAIL:", label)

    p, r = analyze("total = price * qty\ntax = total * rate\n")
    check(p == ["price", "qty", "rate"] and r == ["total", "tax"], "analyze basic")
    p, r = analyze("import math\nx = math.sqrt(n)\nys = [i * 2 for i in range(k)]\nx += 1\n")
    check(p == ["n", "k"] and r == ["x", "ys"], f"analyze imports/comprehension {p} {r}")
    p, _ = analyze("count += 1\n")
    check(p == ["count"], "augassign reads first")
    src = scaffold("area = w * h\nprint(area)\n", "calc_area")
    check(src.startswith("def calc_area(w, h):") and "return area" in src, "scaffold output")
    for bad in ("1abc", "class", "", "a-b"):
        try:
            scaffold("x = 1\n", bad)
            check(False, f"bad name accepted {bad!r}")
        except ValueError:
            check(True, "")
    try:
        scaffold("def (:\n", "f")
        check(False, "syntax error not raised")
    except SyntaxError:
        check(True, "")

    old = BASE_DIR
    tmp = tempfile.mkdtemp(dir=old if os.path.isdir(old) else None)
    BASE_DIR = tmp
    import io, contextlib
    try:
        f = os.path.join(tmp, "app.py")
        with open(f, "w") as fh:
            fh.write("a = 1\n")
        with contextlib.redirect_stdout(io.StringIO()):
            v1 = save_version("app.py", "first")
            with open(f, "w") as fh:
                fh.write("a = 2\nb = 3\n")
            v2 = save_version("~/app.py", "second")
            dup = save_version("app.py")
            d = diff("app.py", 1)
            restore("app.py", 1, confirm=False)
        check((v1, v2, dup) == (1, 2, 2), "version numbering + dedupe")
        check("-a = 1" in d and "+b = 3" in d, "diff")
        check(open(f).read() == "a = 1\n", "restore content")
        d_, rel = hist_dir(os.path.realpath(f))
        vs = load_index(d_, rel)["versions"]
        check(len(vs) == 2 and vs[-1]["sha256"] == sha("a = 2\nb = 3\n"), "auto-save before restore (dedupe kept v2)")
        os.symlink("/", os.path.join(tmp, "esc"))
        for bad in ("../x", "/etc/passwd", "esc/etc/passwd", "~/../x", ".history/x", ""):
            try:
                safe_path(bad)
                check(False, f"path allowed: {bad!r}")
            except ValueError:
                check(True, "")
        with open(version_file(d_, 1), "w") as fh:
            fh.write("tampered\n")
        try:
            get_version(os.path.realpath(f), 1)
            check(False, "tamper not detected")
        except ValueError:
            check(True, "")
        for bad in ("x", "-1", "v", "0"):
            try:
                parse_vid(bad)
                check(False, f"bad version accepted {bad!r}")
            except ValueError:
                check(True, "")
    finally:
        BASE_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Self-tests: {ok} passed, {fail} failed")
    return fail == 0


def main():
    print("=== Function Maker + Local History ===  (files must be inside " + BASE_DIR + ")")
    while True:
        c = input("\n1 Snippet -> function  2 File history  3 Self-tests  q Quit: ").strip().lower()
        try:
            if c in ("q", "quit", "exit"):
                break
            elif c == "1":
                menu_scaffold()
            elif c == "2":
                menu_history()
            elif c == "3":
                run_self_tests()
            else:
                print("Pick 1, 2, 3 or q.")
        except (ValueError, OSError, UnicodeError, RecursionError) as e:
            print("Error:", e)


# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec"):
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
