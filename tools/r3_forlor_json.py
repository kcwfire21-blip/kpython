# Forlor: JSON toolkit - pretty/minify, validate (with error line), JSONPath-like query, dataclass generator. Stdlib only; files only under /home/pyodide.
import json, os, re, keyword

SAFE_ROOT = "/home/pyodide"

def pretty(text, indent=2):
    return json.dumps(json.loads(text), indent=indent, ensure_ascii=False)

def minify(text):
    return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)

def validate(text):
    try:
        json.loads(text)
        return True, "Valid JSON"
    except json.JSONDecodeError as e:
        lines = text.splitlines()
        line = lines[e.lineno - 1] if lines else ""
        return False, f"Line {e.lineno}, col {e.colno}: {e.msg}\n  {line}\n  {' ' * (e.colno - 1)}^"

_TOK = re.compile(r"\.([A-Za-z_][\w-]*)|\[(\d+|\*)\]|\.\*|\[['\"]([^'\"]+)['\"]\]")

def query(data, path):
    """Supports $.a.b, $.items[0], $.items[*].name, $.*, $['key']."""
    path = path.strip()
    if path.startswith("$"):
        path = path[1:]
    nodes, pos = [data], 0
    while pos < len(path):
        m = _TOK.match(path, pos)
        if not m:
            raise ValueError(f"Bad path near: {path[pos:]}")
        pos = m.end()
        key, idx, qkey = m.group(1), m.group(2), m.group(3)
        out = []
        for n in nodes:
            if key or qkey:
                k = key or qkey
                if isinstance(n, dict) and k in n:
                    out.append(n[k])
            elif idx == "*" or m.group(0) == ".*":
                if isinstance(n, dict):
                    out.extend(n.values())
                elif isinstance(n, list):
                    out.extend(n)
            else:
                i = int(idx)
                if isinstance(n, list) and -len(n) <= i < len(n):
                    out.append(n[i])
        nodes = out
    return nodes

def _cls(name):
    s = "".join(p.capitalize() for p in re.split(r"[^A-Za-z0-9]+", name) if p) or "Item"
    return s if s[0].isalpha() else "C" + s

def _field(name):
    f = re.sub(r"\W", "_", name)
    if not f or f[0].isdigit():
        f = "f_" + f
    return f + "_" if keyword.iskeyword(f) else f

def gen_dataclasses(sample, root="Root"):
    classes = {}
    def typ(v, hint):
        if isinstance(v, bool): return "bool"
        if isinstance(v, int): return "int"
        if isinstance(v, float): return "float"
        if isinstance(v, str): return "str"
        if v is None: return "Optional[Any]"
        if isinstance(v, list):
            return f"List[{typ(v[0], hint) if v else 'Any'}]"
        if isinstance(v, dict):
            return build(v, _cls(hint))
        return "Any"
    def build(obj, name):
        if name in classes:
            return name
        classes[name] = None
        lines = [f"@dataclass\nclass {name}:"]
        for k, v in obj.items():
            lines.append(f"    {_field(k)}: {typ(v, k)}")
        if len(lines) == 1:
            lines.append("    pass")
        classes[name] = "\n".join(lines)
        return name
    if isinstance(sample, list):
        sample = sample[0] if sample and isinstance(sample[0], dict) else {}
    build(sample, root)
    header = "from dataclasses import dataclass\nfrom typing import Any, List, Optional\n"
    return header + "\n\n" + "\n\n\n".join(reversed([c for c in classes.values() if c]))

def _safe(path):
    p = os.path.realpath(os.path.join(SAFE_ROOT, path))
    if not (p == SAFE_ROOT or p.startswith(SAFE_ROOT + os.sep)):
        raise PermissionError(f"Only files under {SAFE_ROOT} are allowed")
    return p

def read_input():
    first = input("Paste JSON (end with END) or type @filename: ").strip()
    if first.startswith("@"):
        with open(_safe(first[1:]), encoding="utf-8") as f:
            return f.read()
    lines = [] if first == "END" else [first]
    while lines:
        l = input()
        if l.strip() == "END":
            break
        lines.append(l)
    return "\n".join(lines)

def maybe_save(text):
    name = input("Save to file under /home/pyodide? (filename or blank): ").strip()
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
    print("=== JSON Toolkit ===\n1 Pretty  2 Minify  3 Validate  4 Query  5 Dataclasses  6 Self-test")
    c = input("Choose: ").strip()
    if c == "6":
        return self_test()
    text = read_input()
    try:
        if c == "1": out = pretty(text)
        elif c == "2": out = minify(text)
        elif c == "3": print(validate(text)[1]); return
        elif c == "4": out = json.dumps(query(json.loads(text), input("Path (e.g. $.items[*].name): ")), indent=2)
        elif c == "5": out = gen_dataclasses(json.loads(text), input("Root class name [Root]: ").strip() or "Root")
        else: print("Unknown choice"); return
    except (json.JSONDecodeError, ValueError) as e:
        print("Error:", e); return
    print(out)
    maybe_save(out)

def self_test():
    s = '{"a": 1, "items": [{"name": "x", "tags": ["t"]}, {"name": "y", "tags": []}], "class": true}'
    assert minify(s).startswith('{"a":1')
    assert "\n" in pretty(s)
    ok, msg = validate('{"a": 1,\n "b": }')
    assert not ok and "Line 2" in msg
    assert validate(s)[0]
    assert query(json.loads(s), "$.items[*].name") == ["x", "y"]
    assert query(json.loads(s), "$.items[0].tags[0]") == ["t"]
    assert query(json.loads(s), "$['a']") == [1]
    code = gen_dataclasses(json.loads(s))
    assert "class Root:" in code and "class Items:" in code and "class_: bool" in code
    compile(code, "<generated>", "exec")
    try:
        _safe("../etc/passwd")
        raise AssertionError("path escape allowed")
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
