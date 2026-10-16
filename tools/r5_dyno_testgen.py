# Dyno: unittest generator - reads a script's functions via ast and writes a test_<name>.py skeleton (one test per function, sample asserts from type hints, edge-case stubs); previews a diff first. Stdlib only.
import os, ast, difflib

BASE = "/home/pyodide"  # KPython: fixed, no env override
MAX_BYTES = 500_000

try:
    kp_safe_path  # provided by the KPython app when merged
except NameError:
    def kp_safe_path(p):
        full = os.path.realpath(os.path.join(BASE, p))
        if full != BASE and not full.startswith(BASE + os.sep):
            raise ValueError("Only paths under " + BASE + " are allowed.")
        return full

SAMPLES = {"int": ("1", ["0", "-1"]), "float": ("1.5", ["0.0", "-1.5"]),
           "str": ("'abc'", ["''", "' '"]), "bool": ("True", ["False"]),
           "list": ("[1, 2]", ["[]"]), "dict": ("{'a': 1}", ["{}"]),
           "tuple": ("(1, 2)", ["()"]), "set": ("{1}", ["set()"])}
RESULT_ASSERT = {"int": "assertIsInstance(result, int)", "float": "assertIsInstance(result, float)",
                 "str": "assertIsInstance(result, str)", "bool": "assertIsInstance(result, bool)",
                 "list": "assertIsInstance(result, list)", "dict": "assertIsInstance(result, dict)",
                 "tuple": "assertIsInstance(result, tuple)", "set": "assertIsInstance(result, set)",
                 "None": "assertIsNone(result)"}

def hint(node):
    if node is None:
        return None
    s = ast.unparse(node)
    return s.split("[")[0].split(".")[-1]

def public_functions(src):
    tree = ast.parse(src)
    return [n for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]

def gen_tests(src, module):
    funcs = public_functions(src)
    out = ["import unittest", f"from {module} import " + (", ".join(f.name for f in funcs) or "*"), "",
           "", f"class Test{module.title().replace('_', '')}(unittest.TestCase):"]
    if not funcs:
        out.append("    pass")
    for f in funcs:
        args = [a for a in f.args.args if a.arg not in ("self", "cls")]
        # KPython: arguments with defaults are left out; unknown types get a TODO + skipTest instead of None
        args = args[:len(args) - len(f.args.defaults)] if f.args.defaults else args
        hints = [hint(a.annotation) for a in args]
        unknown = [a.arg for a, h in zip(args, hints) if h not in SAMPLES]
        call = ", ".join(SAMPLES[h][0] if h in SAMPLES else f"{a.arg}=...  # TODO" for a, h in zip(args, hints)) if not unknown else ", ".join(a.arg for a in args)
        ret = hint(f.returns)
        out.append(f"    def test_{f.name}(self):")
        if unknown:
            out.append(f"        self.skipTest('TODO: pick values for {', '.join(unknown)}')")
            out.append(f"        result = {f.name}({call})  # TODO: replace with real values")
            hints = []
        else:
            out.append(f"        result = {f.name}({call})")
        out.append(f"        self.{RESULT_ASSERT.get(ret, 'assertIsNotNone(result)')}  # TODO: assert exact expected value")
        out.append("")
        edges = []
        for i, h in enumerate(hints):
            for e in SAMPLES.get(h, ("None", []))[1]:
                vals = [SAMPLES.get(x, ("None",))[0] for x in hints]
                vals[i] = e
                edges.append(", ".join(vals))
        out.append(f"    def test_{f.name}_edge_cases(self):")
        if edges:
            for e in edges:
                out.append(f"        # TODO: expected result for {f.name}({e})")
                out.append(f"        {f.name}({e})")
        else:
            out.append("        self.skipTest('TODO: add edge cases')")
        out.append("")
    out += ["", "if __name__ == '__main__':", "    unittest.main()", ""]
    return "\n".join(out)

def preview(old, new, name):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile=name + " (current)", tofile=name + " (new)"))

def self_test():
    src = "def add(a: int, b: int) -> int:\n    return a + b\n\ndef greet(n: str) -> str:\n    return 'hi ' + n\n\ndef _private():\n    pass\n"
    t = gen_tests(src, "mymod")
    assert "from mymod import add, greet" in t and "_private" not in t, t
    assert "result = add(1, 1)" in t and "assertIsInstance(result, int)" in t, t
    assert "add(0, 1)" in t and "greet('')" in t, t
    compile(t, "<gen>", "exec")
    ns = {}
    exec(src, ns)
    exec(t.replace("from mymod import add, greet", ""), ns)
    assert "+++" in preview("", t, "test_mymod.py")
    try:
        kp_safe_path("../../etc/passwd"); assert False
    except ValueError:
        pass
    print("self-tests passed")

def main():
    print("== Unittest Generator ==")
    p = input("Script path under " + BASE + " (t = self-test): ").strip()
    if p == "t":
        self_test(); return
    try:
        path = kp_safe_path(p)
        if not path.endswith(".py") or not os.path.isfile(path):
            raise ValueError("Not a .py file.")
        if os.path.getsize(path) > MAX_BYTES:
            raise ValueError("File over 500KB.")
        with open(path) as f:
            src = f.read()
        module = os.path.splitext(os.path.basename(path))[0]
        new = gen_tests(src, module)
        target = kp_safe_path(os.path.join(os.path.dirname(os.path.relpath(path, BASE)), "test_" + module + ".py"))
    except (ValueError, SyntaxError) as e:
        print("Error:", e); return
    old = ""
    if os.path.exists(target):
        with open(target) as f:
            old = f.read()
    print(preview(old, new, os.path.basename(target)) or "(no changes)")
    q = "Overwrite existing " if old else "Write "
    if input(q + target + "? (y/N): ").strip().lower() not in ("y", "yes"):
        print("Cancelled."); return
    with open(target, "w") as f:
        f.write(new)
    print("Saved", target)

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
