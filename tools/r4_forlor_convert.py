# Forlor: config/data converter between JSON, TOML, INI, CSV and Python dict literals. Stdlib only; paths under /home/pyodide; input < 500KB; ast.literal_eval only.
import ast, configparser, csv, io, json, os, re
try:
    import tomllib
except ImportError:
    tomllib = None

SAFE_ROOT = "/home/pyodide"
MAX_BYTES = 500_000
FORMATS = ("json", "toml", "ini", "csv", "py")

def _check_size(text):
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Input is over 500KB")

# ---------- parse ----------
def parse(text, fmt):
    _check_size(text)
    if fmt == "json":
        return json.loads(text)
    if fmt == "toml":
        if tomllib is None:
            raise RuntimeError("tomllib needs Python 3.11+")
        return tomllib.loads(text)
    if fmt == "ini":
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        cp.read_string(text)
        out = {s: dict(cp[s]) for s in cp.sections()}
        if cp.defaults():
            out["DEFAULT"] = dict(cp.defaults())
        return out
    if fmt == "csv":
        return list(csv.DictReader(io.StringIO(text)))
    if fmt == "py":
        return ast.literal_eval(text.strip())
    raise ValueError(f"Unknown format {fmt}")

# ---------- write ----------
_BARE = re.compile(r"^[A-Za-z0-9_-]+$")

def _tkey(k):
    k = str(k)
    return k if _BARE.match(k) else json.dumps(k)

def _tval(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return repr(v)
    if isinstance(v, str): return json.dumps(v)
    if v is None: return '""'
    if isinstance(v, list): return "[" + ", ".join(_tval(x) for x in v) + "]"
    if isinstance(v, dict): return "{ " + ", ".join(f"{_tkey(k)} = {_tval(x)}" for k, x in v.items()) + " }"
    return json.dumps(str(v))

def to_toml(data, prefix=""):
    if not isinstance(data, dict):
        data = {"items": data}
    lines, tables = [], []
    for k, v in data.items():
        if isinstance(v, dict):
            tables.append((k, v))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            tables.append((k, v))
        else:
            lines.append(f"{_tkey(k)} = {_tval(v)}")
    for k, v in tables:
        name = f"{prefix}.{_tkey(k)}" if prefix else _tkey(k)
        if isinstance(v, dict):
            lines.append(f"\n[{name}]")
            lines.append(to_toml(v, name).strip("\n"))
        else:
            for item in v:
                lines.append(f"\n[[{name}]]")
                lines.append("\n".join(f"{_tkey(a)} = {_tval(b)}" for a, b in item.items()))
    return "\n".join(l for l in lines if l != "") + "\n"

def to_ini(data):
    if not isinstance(data, dict):
        raise ValueError("INI needs an object of sections")
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    for sec, vals in data.items():
        if not isinstance(vals, dict):
            vals = {"value": vals}
            sec = str(sec)
        if sec != "DEFAULT":
            cp.add_section(str(sec))
        for k, v in vals.items():
            cp[str(sec)][str(k)] = v if isinstance(v, str) else json.dumps(v)
    buf = io.StringIO()
    cp.write(buf)
    return buf.getvalue()

def to_csv(data):
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ValueError("CSV needs a list of objects")
    cols = []
    for r in data:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in data:
        w.writerow({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
    return buf.getvalue()

def dump(data, fmt):
    if fmt == "json": return json.dumps(data, indent=2, ensure_ascii=False)
    if fmt == "toml": return to_toml(data)
    if fmt == "ini": return to_ini(data)
    if fmt == "csv": return to_csv(data)
    if fmt == "py":
        import pprint
        return pprint.pformat(data, sort_dicts=False)
    raise ValueError(f"Unknown format {fmt}")

def convert(text, src, dst):
    return dump(parse(text, src), dst)

# ---------- files / UI ----------
def _safe(path):
    p = os.path.realpath(os.path.join(SAFE_ROOT, path))
    if not (p == SAFE_ROOT or p.startswith(SAFE_ROOT + os.sep)):
        raise PermissionError(f"Only files under {SAFE_ROOT} are allowed")
    return p

def _guess(name):
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    return {"cfg": "ini", "conf": "ini", "txt": "py"}.get(ext, ext) if ext else None

def read_input():
    first = input("Paste data (end with END) or @filename: ").strip()
    if first.startswith("@"):
        p = _safe(first[1:])
        if os.path.getsize(p) > MAX_BYTES:
            raise ValueError("File is over 500KB")
        with open(p, encoding="utf-8") as f:
            return f.read(), _guess(first[1:])
    lines = [] if first == "END" else [first]
    while lines:
        l = input()
        if l.strip() == "END":
            break
        lines.append(l)
    return "\n".join(lines), None

def ask_fmt(prompt, default=None):
    while True:
        f = (input(f"{prompt} {FORMATS}" + (f" [{default}]" if default else "") + ": ").strip().lower() or default or "")
        if f in FORMATS:
            return f
        print("  Pick one of", FORMATS)

def maybe_save(text):
    name = input("Save under /home/pyodide? (filename or blank): ").strip()
    if not name:
        return
    p = _safe(name)
    if os.path.exists(p) and input(f"{name} exists. Overwrite? (y/N): ").strip().lower() != "y":
        print("Not saved.")
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    print("Saved", p)

def main():
    print("=== Config/Data Converter === JSON, TOML, INI, CSV, Python dict")
    if input("Run self-tests? (y/N): ").strip().lower() == "y":
        return self_test()
    try:
        text, guess = read_input()
        src = ask_fmt("From", guess)
        dst = ask_fmt("To")
        out = convert(text, src, dst)
    except Exception as e:
        print("Error:", e)
        return
    print("\n" + out)
    maybe_save(out)

def self_test():
    data = {"name": "app", "debug": True, "port": 8080, "db": {"host": "localhost", "user": "x"}}
    j = json.dumps(data)
    assert parse(convert(j, "json", "py"), "py") == data
    if tomllib:
        assert parse(convert(j, "json", "toml"), "toml") == data
        arr = {"server": [{"a": 1}, {"a": 2}]}
        assert parse(to_toml(arr), "toml") == arr
    ini = convert('{"main": {"k": "v", "n": 3}}', "json", "ini")
    assert parse(ini, "ini") == {"main": {"k": "v", "n": "3"}}
    rows = [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
    assert parse(convert(json.dumps(rows), "json", "csv"), "csv") == rows
    try:
        parse("__import__('os')", "py"); raise AssertionError("unsafe eval")
    except ValueError:
        pass
    try:
        parse("x" * (MAX_BYTES + 1), "json"); raise AssertionError("size not enforced")
    except ValueError:
        pass
    try:
        _safe("../../etc/passwd"); raise AssertionError("path escape")
    except PermissionError:
        pass
    print("All self-tests passed.")

# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse"):
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
