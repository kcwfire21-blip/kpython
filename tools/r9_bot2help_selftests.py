# bot2help r9: real assert-based self_test() functions for the 4 merged bot2help tools (metrics, imports, chart, logs); temp dirs only under /home/pyodide, cleaned up after. Stdlib only.
"""
PATCH NOTES (Kai) - KPython round 9, bot2help
==============================================

Why: the merged tools in /workspace/pyapp/tools/ only define `run_selftests()`
(r3_bot2help_metrics, r4_bot2help_imports, r5_bot2help_chart, r6_bot2help_logs).
The v10 Dev-tab runner (tools/r8_dyno_selftest_dev.py) looks up
NAMES = ("self_test", "selftest", "_self_test", "run_self_tests", "self_tests")
- no "run_selftests" - so "Self-test all" reports all four as SKIP "no self_test()".
(The older r7_dyno_selftest_all.py does list run_selftests; the v10 one dropped it.)
Apart from that, the merged copies differ from my contrib originals only in Kai's
v9/v10 hardening: (EOFError, KeyboardInterrupt) on input, the kp_common.harden()
footer, 2 MB / 20 MB file caps in chart/logs, (y/N) prompts and the reworked
_pick(allowed=) in chart, and temp dirs inside ~ in the chart/logs run_selftests.
Every function these tests call has the same signature in the merged copies.

Convention matched (most tools, and Kai's own v10 wiring of r2_bot_projects):
  * module-level `def self_test():` taking no required arguments,
  * assert-based: a failure raises AssertionError (the runner records FAIL),
  * prints "... self-tests passed" and returns True (only `return False` = FAIL),
  * no input() (the runner stubs input() and marks a tool that asks as SKIP;
    tests that drive main() swap builtins.input in try/finally and restore it).

WIRING - option A (same as r2_bot_projects -> r8_dyno_projects_selftest, recommended)
  1. Ship this file as tools/r9_bot2help_selftests.py: add 'r9_bot2help_selftests.py'
     to TOOLS in app.js, 'r9_bot2help_selftests' to the tool list in sw.js, and its
     hash to the manifest, like r8_dyno_projects_selftest. Its name contains
     "selftest", so run_all() skips it as a tool of its own (by design).
  2. In each tool, paste this block directly ABOVE the
     "# --- KPython v9: shared hardening ..." footer (so it sits after run_selftests):

       tools/r3_bot2help_metrics.py  (above line 247)  -> _st.self_test_metrics
       tools/r4_bot2help_imports.py  (above line 392)  -> _st.self_test_imports
       tools/r5_bot2help_chart.py    (above line 476)  -> _st.self_test_chart
       tools/r6_bot2help_logs.py     (above line 359)  -> _st.self_test_logs

     # --- KPython v10: bot2help's full self-test (temp dir under ~; see r9_bot2help_selftests) ---
     def self_test():
         import r9_bot2help_selftests as _st
         return _st.self_test_metrics(sys.modules.get(__name__) or _kp_ns())   # <- per-tool name

     def _kp_ns():
         import types
         return types.SimpleNamespace(**globals())

     (`sys` is already imported by all four tools. `_kp_ns()` covers runners that
     exec the module without registering it in sys.modules, like the older r7 runner.
     Plain `sys.modules[__name__]` as in r2_bot_projects also works under the v10 runner.)
  3. Optional: point the menus and `--selftest` at the new test as well:
       metrics main(): `elif c == "4": run_selftests()`  -> `self_test()`; `__main__`: `self_test()`
       imports main(): `elif ch == "8": run_selftests()` -> `self_test()`
       chart/imports `__main__`: `sys.exit(0 if self_test() else 1)`
       logs  main(): `elif ch == "8": run_selftests()`  -> `self_test()`
     run_selftests() can stay as it is; self_test is first in NAMES, so it wins.

WIRING - option B (no new tool file): paste the matching self_test_<tool>() function
  from this file (plus _test_home/_make_root/_raises/_with_input/_quiet just above
  them) into the tool, rename it `self_test`, and swap its first line
  `if m is None: m = _load(...)` for
  `if m is None: m = sys.modules.get(__name__) or types.SimpleNamespace(**globals())`.

KNOWN ISSUE found while testing (merged r4_bot2help_imports, not changed by me):
  main() wraps menu actions in `except (PermissionError, OSError)`, but inside the app
  harden() routes safe_path() through kp_safe_path(), which raises ValueError. So
  "1) Choose directory" with a path outside ~ (e.g. ../..) ends the tool with a
  traceback instead of printing "Error: ...". One-line fix, line 388:
      except (PermissionError, OSError) as e:   ->   except (PermissionError, OSError, ValueError) as e:
  (metrics, chart and logs already catch ValueError in their menus.)

Temp dirs: always tempfile.mkdtemp(dir=<home>), where home is /home/pyodide. Only off
the device (sys.platform != "emscripten") the env var KP_TEST_HOME may point it at a
scratch folder for local testing; inside the app the override is ignored. Each test
makes one root (base/ + outside/ siblings, so symlink-escape tests never leave ~),
removes it in `finally`, and asserts it is gone.
Under the app's harden(), safe_path() also goes through kp_safe_path(), which can
refuse a path with ValueError before the tool's own check, so the refusal tests
accept ValueError or PermissionError.
"""
import os, sys, io, shutil, tempfile, builtins, contextlib, importlib

HOME = "/home/pyodide"
TOOL_DIRS = ("/kptools", "/workspace/pyapp/tools")


# ---------------- shared helpers ----------------
def _load(name):
    here = os.path.dirname(os.path.abspath(__file__))
    for d in TOOL_DIRS + (here,):
        if os.path.isfile(os.path.join(d, name + ".py")):
            if d not in sys.path:
                sys.path.insert(0, d)
            break
    return importlib.import_module(name)


def _test_home():
    """/home/pyodide; KP_TEST_HOME is honoured only off-device (local testing)."""
    home = HOME
    if sys.platform != "emscripten" and os.environ.get("KP_TEST_HOME"):
        home = os.environ["KP_TEST_HOME"]
    if not os.path.isdir(home):
        raise AssertionError("test home %s missing (off-device: set KP_TEST_HOME)" % home)
    return home


def _make_root(tag):
    """Make <home>/kp_st_<tag>_XXXX with base/ and outside/ inside. Returns (root, base, outside)."""
    root = os.path.realpath(tempfile.mkdtemp(prefix="kp_st_%s_" % tag, dir=_test_home()))
    base, outside = os.path.join(root, "base"), os.path.join(root, "outside")
    os.makedirs(base); os.makedirs(outside)
    return root, base, outside


def _cleanup(root):
    shutil.rmtree(root, ignore_errors=True)
    assert not os.path.exists(root), "temp dir left behind: " + root


def _raises(fn, exc=(ValueError, PermissionError)):
    try:
        fn()
    except exc:
        return True
    return False


def _with_input(answers, fn, *a, **k):
    """Run fn with builtins.input fed from answers (then 'q'); returns (result, stdout)."""
    it = iter(answers)
    old = builtins.input
    builtins.input = lambda p="": next(it, "q")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = fn(*a, **k)
    finally:
        builtins.input = old
    return r, buf.getvalue()


def _quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()


def _symlink(target, link):
    try:
        os.symlink(target, link)
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


# ---------------- r3_bot2help_metrics ----------------
def self_test_metrics(m=None):
    if m is None: m = _load("r3_bot2help_metrics")
    src = ("# header\n"
           "\n"
           "import os\n"
           "class K:\n"
           "    def a(self, x):\n"
           "        if x > 1 and x < 9 or x == 0:  # todo tidy\n"
           "            return [i for i in range(x) if i if i > 2]\n"
           "        elif x:\n"
           "            return 1 if x else 2\n"
           "        return 0\n"
           "\n"
           "    async def b(self):\n"
           "        async for _ in self:\n"
           "            pass\n"
           "\n"
           "def outer(n):\n"
           "    f = lambda v: v if v else 0\n"
           "    def inner():\n"
           "        while n:\n"
           "            break\n"
           "    try:\n"
           "        s = 'TODO not a tag'\n"
           "    except (ValueError, KeyError):\n"
           "        pass  # FIXME later  TODO too\n"
           "    except OSError:\n"
           "        pass\n"
           "    return f, inner\n")
    # line counts
    lc = m.line_counts(src)
    assert lc["total"] == 27 and lc["blank"] == 3 and lc["comment"] == 1, lc
    assert lc["code"] == lc["total"] - lc["blank"] - lc["comment"]
    assert m.line_counts("") == {"total": 0, "code": 0, "comment": 0, "blank": 0}
    # analyze: names, lines, lengths, complexity
    r = m.analyze(src)
    assert r["error"] is None and r["classes"] == 1, r
    f = {x["name"]: x for x in r["functions"]}
    assert set(f) == {"K.a", "K.b", "outer", "outer.<locals>.inner"}, sorted(f)
    # K.a: 1 + if + and/or (1+1) + comprehension (1 + 2 ifs) + elif + ifexp = 9
    assert f["K.a"]["complexity"] == 9, f["K.a"]
    assert f["K.b"]["complexity"] == 2, f["K.b"]            # async for
    # outer: 1 + 2 except handlers; lambda and nested def are not counted
    assert f["outer"]["complexity"] == 3, f["outer"]
    assert f["outer.<locals>.inner"]["complexity"] == 2
    assert f["K.a"]["line"] == 5 and f["K.a"]["length"] == 6, f["K.a"]
    assert f["outer"]["line"] == 16 and f["outer"]["length"] == 12, f["outer"]
    assert not any(x["long"] or x["complex"] for x in r["functions"])
    # thresholds
    r2 = m.analyze(src, max_len=5, max_cc=8)
    f2 = {x["name"]: x for x in r2["functions"]}
    assert f2["K.a"]["long"] and f2["K.a"]["complex"] and f2["outer"]["long"] and not f2["outer"]["complex"]
    assert not f2["K.b"]["long"] and r2["max_len"] == 5 and r2["max_cc"] == 8
    # tags: case-insensitive, comments only, one per line
    t = m.find_tags(src)
    assert [(x["line"], x["tag"]) for x in t] == [(6, "TODO"), (24, "TODO")], t
    assert t[1]["text"] == "# FIXME later  TODO too"
    assert m.find_tags("x = 1  # hack: y\n# XXX\n# nothing")[1]["tag"] == "XXX"
    assert m.find_tags("# NOTE x", tags=("NOTE",))[0]["tag"] == "NOTE"
    # report text
    rep = m.format_report(r2)
    assert rep.startswith("== Code Metrics ==") and "Functions: 4  Classes: 1" in rep
    assert "LONG>5" in rep and "COMPLEX>8" in rep and "Tags: 2" in rep and "L6 [TODO]" in rep
    assert "Functions: 0  Classes: 0" in m.format_report(m.analyze("x = 1\n"))
    # syntax errors still report lines and tags
    bad = m.analyze("def f(:\n    pass  # FIXME\n")
    assert bad["error"].startswith("SyntaxError line 1") and bad["functions"] == []
    assert bad["todos"][0]["tag"] == "FIXME" and "Could not parse" in m.format_report(bad)
    # match/case adds one per case
    if sys.version_info >= (3, 10):
        mm = m.analyze("def g(x):\n    match x:\n        case 1:\n            pass\n        case _:\n            pass\n")
        assert mm["functions"][0]["complexity"] == 3, mm
    # size cap only exists once the app's harden() has wrapped analyze()
    if getattr(m.analyze, "_kp_capped", False):
        assert _raises(lambda: m.analyze("x" * 600_000), ValueError)
    # files: load inside base, refuse escapes
    root, base, outside = _make_root("metrics")
    try:
        with open(os.path.join(base, "a.py"), "w") as fh:
            fh.write(src)
        os.makedirs(os.path.join(base, "sub"))
        with open(os.path.join(base, "sub", "b.py"), "w") as fh:
            fh.write("def z():\n    return 1\n")
        with open(os.path.join(outside, "s.py"), "w") as fh:
            fh.write("x = 1\n")
        assert m.load_file("a.py", base) == src
        assert m.load_file(os.path.join(base, "sub", "b.py"), base).startswith("def z")
        assert m.safe_path("sub/b.py", base) == os.path.join(base, "sub", "b.py")
        assert m.safe_path(base, base) == base
        for p in ("../outside/s.py", os.path.join(outside, "s.py"), "/etc/passwd", "sub/../../outside/s.py"):
            assert _raises(lambda: m.load_file(p, base)), "allowed " + p
        if _symlink(outside, os.path.join(base, "link")):
            assert _raises(lambda: m.load_file("link/s.py", base)), "symlink escape"
        assert _raises(lambda: m.load_file("nope.py", base), (OSError, ValueError))
        # menu: paste code, change thresholds, bad path, unknown choice, quit
        _, out = _with_input(["1", "def f(x):", "    if x:", "        return 1  # TODO", "END",
                              "3", "2", "1", "1", "def f(x):", "    if x: return 1", "    return 2", "END",
                              "2", "../../etc/passwd", "3", "abc", "zz", "q"], m.main)
        assert "f " in out and "Tags: 1" in out, out
        assert "LONG>2" in out and "COMPLEX>1" in out, out
        assert "Error:" in out and "Invalid number." in out and "Unknown choice." in out, out
    finally:
        _cleanup(root)
    print("r3_bot2help_metrics self-tests passed.")
    return True


# ---------------- r4_bot2help_imports ----------------
def self_test_imports(m=None):
    if m is None: m = _load("r4_bot2help_imports")
    # pure helpers
    assert m.module_name_for("/r/pkg/sub/x.py", "/r") == ("pkg.sub.x", False)
    assert m.module_name_for("/r/pkg/__init__.py", "/r") == ("pkg", True)
    assert m.resolve_relative("pkg.mod", False, 1, "x") == "pkg.x"
    assert m.resolve_relative("pkg", True, 1, "x") == "pkg.x"
    assert m.resolve_relative("pkg.sub.mod", False, 2, None) == "pkg"
    assert m.resolve_relative("top", False, 2, "x") is None
    assert m.find_cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a"}}) == [["a", "b", "c"]]
    assert m.find_cycles({"a": {"b"}, "b": set()}) == []
    assert m.find_cycles({"s": {"s"}, "t": set()}) == [["s"]]
    assert m.node_id("pkg.sub-x") == "m_pkg_sub_x"
    assert m.is_available("os") and m.is_available("json.decoder") and not m.is_available("kp_zz_no_such_mod_r9")
    root, base, outside = _make_root("imports")
    try:
        proj = os.path.join(base, "proj")
        files = {
            "app.py": "import util\nimport os, sys as system\nfrom pkg import api\nimport kp_zz_missing_r9 as zz\n"
                      "from collections import OrderedDict as OD, Counter\nprint(util.x, os.sep, api, zz)\n",
            "util.py": "from app import *\nx = 1\n",
            "lone.py": "import json\nvalue: 'json.JSONDecoder' = None\n",
            "exp.py": "from os import path\n__all__ = ['path']\n",
            "broken.py": "def (:\n",
            "pkg/__init__.py": "from .api import run\nimport sys\n",
            "pkg/api.py": "from .core import engine\nfrom . import core\ndef run(): return engine, core\n",
            "pkg/core.py": "from ..pkg import api as a\nfrom .... import far\nengine = a\n",
            ".hidden/h.py": "import app\n",
            "__pycache__/c.py": "import app\n",
        }
        for rel, s in files.items():
            p = os.path.join(proj, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write(s)
        with open(os.path.join(outside, "evil.py"), "w") as fh:
            fh.write("import app\n")
        linked = _symlink(outside, os.path.join(proj, "escape"))
        found = m.find_py_files(proj, base)
        assert all(not ("/.hidden/" in p or "__pycache__" in p or "/escape/" in p) for p in found), found
        r = m.build_map(proj, base=base)
        g = r["graph"]
        assert sorted(r["modules"]) == ["app", "broken", "exp", "lone", "pkg", "pkg.api", "pkg.core", "util"], sorted(r["modules"])
        assert r["modules"]["pkg"]["pkg"] is True and r["modules"]["app"]["pkg"] is False
        assert g["app"] == ["pkg.api", "util"] and g["util"] == ["app"], g
        assert g["pkg"] == ["pkg.api"] and g["pkg.api"] == ["pkg.core"] and g["pkg.core"] == ["pkg.api"], g
        assert r["cycles"] == [["app", "util"], ["pkg.api", "pkg.core"]], r["cycles"]
        un = {k: [u[0] for u in v] for k, v in r["unused"].items()}
        assert un == {"app": ["system", "OD", "Counter"]}, un      # string annotation counts as use in lone
        assert "pkg" not in r["unused"] and "exp" not in r["unused"]
        miss = {k: [t for t, _ in v] for k, v in r["missing"].items()}
        assert miss == {"app": ["kp_zz_missing_r9"], "pkg.core": ["...."]}, miss
        assert r["missing"]["app"][0][1] == 4
        assert list(r["errors"]) == ["broken"] and r["errors"]["broken"].startswith("SyntaxError line 1")
        tree = m.text_tree(r)
        assert "broken  [ERROR]" in tree and "└── app (cycle)" in tree and "├── pkg.api" in tree, tree
        mer = m.mermaid(r).splitlines()
        assert mer[0] == "graph TD" and '    m_pkg_api["pkg.api"]' in mer
        assert "    m_app --> m_util" in mer and "    m_pkg_core --> m_pkg_api" in mer
        assert len([l for l in mer if "-->" in l]) == sum(len(v) for v in g.values())
        rep = m.report(r)
        assert "(8 modules)" in rep and "  app <-> util" in rep and "app:5  Counter" in rep
        assert "pkg.core:2  ...." in rep and "Parse errors:" in rep
        # a clean project says "none" everywhere
        clean = os.path.join(base, "clean")
        os.makedirs(clean)
        with open(os.path.join(clean, "one.py"), "w") as fh:
            fh.write("import two\ntwo.go()\n")
        with open(os.path.join(clean, "two.py"), "w") as fh:
            fh.write("def go(): pass\n")
        rc = m.build_map("clean", base=base)
        assert rc["graph"] == {"one": ["two"], "two": []} and not rc["cycles"]
        rep = m.report(rc)
        for s in ("Circular imports: none", "Unused imports: none", "Missing modules: none"):
            assert s in rep, rep
        assert m.text_tree({"graph": {}, "errors": {}}) == "(no Python files)"
        # path guard
        for p in ("../", "/etc", os.path.join(outside), "proj/../../outside"):
            assert _raises(lambda: m.safe_path(p, base)), "allowed " + p
        assert m.safe_path("", base) == base and m.safe_path("proj", base) == proj
        if linked:
            assert _raises(lambda: m.build_map("proj/escape", base=base))
        # menu: choose dir, cycles, unused, missing, mermaid, bad dir, quit
        # <root>/outside (absolute) is inside ~ but outside base, so the tool's own check refuses it (PermissionError,
        # caught by main). A path outside ~ would hit kp_safe_path's ValueError first, which main() does
        # not catch in the merged copy - see KNOWN ISSUE in the patch notes.
        _, out = _with_input(["1", "proj", "5", "6", "7", "4", "1", outside, "x", "0"], m.main, base)
        assert "app <-> util" in out and "app:2 system" in out and "app:4 kp_zz_missing_r9" in out, out
        assert "graph TD" in out and "Error:" in out and "Unknown choice." in out, out
    finally:
        _cleanup(root)
    print("r4_bot2help_imports self-tests passed.")
    return True


# ---------------- r5_bot2help_chart ----------------
def self_test_chart(m=None):
    if m is None: m = _load("r5_bot2help_chart")
    csv_t = " month , sales ,note\nJan,10,a\nFeb, 20 ,b\nMar,x,c\nApr,-5,d\nMay,,e\n"
    cols, rows = m.parse_data(csv_t)
    assert cols == ["month", "sales", "note"] and len(rows) == 5 and rows[1]["sales"] == "20", (cols, rows)
    jc, jr = m.parse_data('{"a": 1, "b": "x"}')
    assert jc == ["a", "b"] and jr == [{"a": 1, "b": "x"}]
    jc, jr = m.parse_data('[{"a": 1}, {"c": 2, "a": 3}]')
    assert jc == ["a", "c"] and jr[0]["c"] is None and jr[1]["a"] == 3
    for bad in ("", "   ", "[1, 2", "[1, 2]", "[]", "only_header\n"):
        assert _raises(lambda: m.parse_data(bad), ValueError), "accepted %r" % bad
    # numbers and columns
    assert m.to_float("1,234.5") == 1234.5 and m.to_float(" 3 ") == 3.0 and m.to_float(7) == 7.0
    for v in (None, True, "", "abc", "inf", "nan"):
        assert m.to_float(v) is None, v
    assert m.numeric_columns(cols, rows) == ["sales"]
    xs, ys, sk = m.extract(rows, "month", "sales")
    assert xs == ["Jan", "Feb", "Apr"] and ys == [10.0, 20.0, -5.0] and sk == 2
    vals, none_ys, sk = m.extract(rows, "sales")
    assert vals == [10.0, 20.0, -5.0] and none_ys == [] and sk == 2
    h = m.histogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 10], 5)
    assert [c for _, _, c in h] == [2, 2, 2, 2, 2] and h[0][0] == 0 and h[-1][1] == 10, h
    assert m.histogram([], 3) == [] and m.histogram([4, 4, 4], 3) == [(4, 4, 3)]
    assert len(m.histogram([1, 2, 3], 0)) == 1
    # text charts
    bar = m.text_bar(["a", "b"], [10.0, -5.0], width=10).splitlines()
    assert bar[0] == "a | ########## 10" and bar[1] == "b | ----- -5", bar
    line = m.text_line([float(i) for i in range(200)], width=20).splitlines()
    assert len(line[0]) == 20 and line[0][0] == "▁" and line[1] == "min 0  max 190  n=20", line
    sc = m.text_scatter([0, 1, 2], [0.0, 1.0, 2.0], width=10, height=5).splitlines()
    assert len(sc) == 7 and sc[0].endswith("*") and sc[4].strip().startswith("0 |*"), sc
    assert m.text_scatter(["a", "b"], [1.0, 2.0]) == "(no numeric x/y points)"
    assert m.text_hist([]) == "(no data)" and "1-2 |" in m.text_hist([1.0, 2.0, 3.0], 2)
    for kind in m.CHART_TYPES:
        y = None if kind == "hist" else "sales"
        x = "sales" if kind == "hist" else "month"
        t = m.text_chart(kind, rows, x, y, 3)
        assert t.splitlines()[0] == (kind + ": sales" if kind == "hist" else kind + ": sales vs month"), t
        assert t.endswith("(skipped 2 non-numeric/empty rows)"), t
    assert _raises(lambda: m.text_chart("pie", rows, "month", "sales"), ValueError)
    assert _raises(lambda: m.text_chart("bar", rows, "month"), ValueError)
    root, base, outside = _make_root("chart")
    try:
        with open(os.path.join(base, "d.csv"), "w") as fh:
            fh.write(csv_t)
        with open(os.path.join(base, "d.json"), "w") as fh:
            fh.write('[{"x": 1, "y": 2}, {"x": 2, "y": 4}]')
        with open(os.path.join(outside, "s.csv"), "w") as fh:
            fh.write(csv_t)
        assert m.load_file("d.csv", base) == (cols, rows)
        assert m.load_file(os.path.join(base, "d.json"), base)[0] == ["x", "y"]
        for p in ("../outside/s.csv", os.path.join(outside, "s.csv"), "/etc/passwd", "", "nope.csv"):
            assert _raises(lambda: m.load_file(p, base), ValueError), "allowed %r" % p
        if _symlink(outside, os.path.join(base, "link")):
            assert _raises(lambda: m.load_file("link/s.csv", base), ValueError), "symlink escape"
        with open(os.path.join(base, "big.csv"), "w") as fh:
            fh.write("a\n" + "1\n" * 1_000_001)
        assert _raises(lambda: m.load_file("big.csv", base), ValueError), "size cap"
        # saving: suffix, confirm before overwrite, refusals
        asked = []
        p = m.save_txt("hello", "out", base)
        assert p == os.path.join(base, "out.txt") and open(p).read() == "hello\n"
        assert m.save_txt("no", "out.txt", base, lambda msg: asked.append(msg) or False) is None
        assert open(p).read() == "hello\n" and asked and "Overwrite? (y/N)" in asked[0]
        assert m.save_txt("no", "out.txt", base) is None and open(p).read() == "hello\n"
        assert m.save_txt("yes", "out.txt", base, lambda msg: True) == p
        assert open(p).read() == "yes\n"
        os.makedirs(os.path.join(base, "dir.txt"))
        for bad in ("dir.txt", "missing/x.txt", "../outside/x.txt", os.path.join(outside, "x.txt")):
            assert _raises(lambda: m.save_txt("x", bad, base), ValueError), "saved to " + bad
        assert not os.path.exists(os.path.join(outside, "x.txt"))
        # matplotlib if present, otherwise a clear error
        if m.HAVE_MPL:
            for kind in m.CHART_TYPES:
                fig = m.mpl_figure(kind, rows, "sales" if kind == "hist" else "month",
                                   None if kind == "hist" else "sales", 4)
                out = m.save_png(fig, "c_" + kind, base)
                m.plt.close(fig)
                assert out == os.path.join(base, "c_%s.png" % kind) and open(out, "rb").read(8) == b"\x89PNG\r\n\x1a\n"
            fig = m.mpl_figure("line", rows, "month", "sales")
            before = os.path.getmtime(os.path.join(base, "c_line.png"))
            assert m.save_png(fig, "c_line.png", base, lambda msg: False) is None
            assert os.path.getmtime(os.path.join(base, "c_line.png")) == before
            assert _raises(lambda: m.save_png(fig, "../outside/x", base), ValueError)
            m.plt.close(fig)
            assert _raises(lambda: m.mpl_figure("hist", rows, "note"), ValueError)
            assert _raises(lambda: m.mpl_figure("bar", rows, "month", "note"), ValueError)
        else:
            assert _raises(lambda: m.mpl_figure("bar", rows, "month", "sales"), RuntimeError)
        # menu in text mode: load, columns, bad chart type, hist, bar + save, re-save declined, quit
        r, out = _with_input(["4", "2", "d.csv", "3",
                              "4", "pie", "q",
                              "4", "hist", "3", "sales", "2", "n",
                              "4", "bar", "Month", "note", "2", "y", "menu",
                              "4", "bar", "1", "2", "y", "menu", "n",
                              "q"], m.main, base, True)
        assert r == 0 and "Chart maker (text mode)" in out and "Load data first." in out, out
        assert "Loaded 5 rows, columns: month, sales, note" in out and "  sales (numeric)" in out, out
        assert "hist: sales" in out and "bar: sales vs month" in out and "Invalid choice." in out, out
        assert "Saved %s" % os.path.join(base, "menu.txt") in out and "Not saved." in out, out
        assert open(os.path.join(base, "menu.txt")).read().startswith("bar: sales vs month")
    finally:
        _cleanup(root)
    print("r5_bot2help_chart self-tests passed (matplotlib %s)." % ("available" if m.HAVE_MPL else "not available"))
    return True


# ---------------- r6_bot2help_logs ----------------
def self_test_logs(m=None):
    if m is None: m = _load("r6_bot2help_logs")
    from datetime import datetime
    # levels and times
    assert [m.norm_level(x) for x in ("warn", "Fatal", " err ", "trace", "notice", "info", "loud", None)] == \
        ["WARNING", "CRITICAL", "ERROR", "DEBUG", "INFO", "INFO", "UNKNOWN", "UNKNOWN"]
    assert m.parse_time("16/Oct/2026:10:00:01 +0000") == datetime(2026, 10, 16, 10, 0, 1)
    assert m.parse_time("2026-10-16T10:00:00.5Z") == datetime(2026, 10, 16, 10, 0, 0)
    assert m.parse_time("2026-10-16") == datetime(2026, 10, 16)
    assert m.parse_time("1760608800000") == m.parse_time("1760608800") == datetime(2025, 10, 16, 10, 0)
    assert m.parse_time("soon") is None and m.parse_time("") is None and m.parse_time(None) is None
    assert [m.status_level(c) for c in ("200", "302", "404", "500")] == ["INFO", "INFO", "WARNING", "ERROR"]
    # line parsers
    e = m.parse_python("2026-10-16 10:01:02,123 - app.db - ERROR - lost conn")
    assert e["level"] == "ERROR" and e["msg"] == "lost conn" and e["time"] == datetime(2026, 10, 16, 10, 1, 2), e
    assert m.parse_python("[2026-10-16 10:00:00] [WARN] hot")["level"] == "WARNING"
    assert m.parse_python("INFO:root:hi") == {"time": None, "level": "INFO", "msg": "hi"}
    assert m.parse_python("just text") is None
    a = m.parse_access('9.9.9.9 - - [16/Oct/2026:10:00:01 +0000] "GET /a HTTP/1.1" 503 0')
    assert a["level"] == "ERROR" and a["msg"] == "503 GET /a HTTP/1.1", a
    assert m.parse_access("nope") is None
    j = m.parse_json('{"timestamp": "2026-10-16 09:00:00", "severity": "fatal", "event": "x"}')
    assert j == {"time": datetime(2026, 10, 16, 9), "level": "CRITICAL", "msg": "x"}, j
    assert m.parse_json("[1]") is None and m.parse_json("{bad") is None and m.parse_json("x") is None
    assert m.parse_json('{"msg": "m"}')["level"] == "UNKNOWN"
    # detection, tracebacks, caps
    py = ["2026-10-16 10:01:02,123 - app - INFO - started",
          "2026-10-16 10:01:30,000 - app - ERROR - failed id 42 at 0xdeadbeef",
          "Traceback (most recent call last):",
          '  File "x.py", line 1',
          "2026-10-16 10:02:00,000 - app - ERROR - failed id 7 at 0xabc",
          "",
          "2026-10-16 11:15:00 CRITICAL db 'main' down",
          "2026-10-16 11:16:00 DEBUG tick"]
    fmt, ents = m.parse_lines(py)
    assert fmt == "python" and len(ents) == 5 and ents[1]["extra"] == 2, ents
    assert m.detect_format([]) == "python" and m.detect_format(["???"]) == "python"
    acc = ['1.1.1.1 - - [16/Oct/2026:10:00:01 +0000] "GET / HTTP/1.1" 200 5 "-" "ua"', "garbage"]
    fmt2, ents2 = m.parse_lines(acc)
    assert fmt2 == "access" and ents2[1] == {"time": None, "level": "UNKNOWN", "msg": "garbage", "raw": "garbage"}
    assert m.parse_lines(['{"level":"info","msg":"a"}'])[0] == "json"
    assert _raises(lambda: m.parse_lines(py, "xml"), ValueError)
    assert len(m.parse_lines(["2026-10-16 10:00:00 ERROR " + "y" * 5000])[1][0]["raw"]) == m.MAX_LINE
    # reports
    assert list(m.count_levels(ents).items()) == [("DEBUG", 1), ("INFO", 1), ("ERROR", 2), ("CRITICAL", 1)]
    assert m.top_errors(ents) == [("failed id <n> at <hex>", 2), ("db <str> down", 1)]
    assert m.top_errors(ents, min_level="CRITICAL") == [("db <str> down", 1)] and m.top_errors(ents, n=1)[0][1] == 2
    assert m.normalize_msg('k "v" 550e8400-e29b-41d4-a716-446655440000 1.5 deadbeefcafe12') == "k <str> <uuid> <n> <hex>"
    assert m.timeline(ents) == [("2026-10-16 10:01", 2), ("2026-10-16 10:02", 1), ("2026-10-16 11:15", 1), ("2026-10-16 11:16", 1)]
    assert m.timeline(ents, "hour") == [("2026-10-16 10:00", 3), ("2026-10-16 11:00", 2)]
    assert m.bar_chart([("a", 4), ("bb", 2), ("c", 0)], width=4).splitlines() == ["a  | #### 4", "bb | ## 2", "c  |  0"]
    assert m.bar_chart([]) == "(no timestamped entries)"
    rep = m.full_report(ents, fmt, "hour")
    assert rep.startswith("Format: python   Entries: 5") and "  ERROR     2" in rep
    assert "     2  failed id <n> at <hex>" in rep and "Timeline per hour:" in rep
    assert "  (none)" in m.full_report([], "-")
    # regex guard + filters
    assert m.check_pattern(r"id \d+").search("ID 5")                       # case-insensitive
    for bad in ("(a+)+", "(a*)*", "(.+){2,}", "(a|aa)+", r"(x)\1", "a" * 201, "[", "", None):
        assert _raises(lambda: m.check_pattern(bad), ValueError), "accepted %r" % (bad,)
    assert len(m.filter_entries(ents, levels=["error"])) == 2
    assert len(m.filter_entries(ents, levels=["critical", "fatal"])) == 1
    assert [x["level"] for x in m.filter_entries(ents, levels=["ERROR", "debug"], pattern="id 7|tick")] == ["ERROR", "DEBUG"]
    assert m.filter_entries(ents) == ents
    assert _raises(lambda: m.filter_entries(ents, pattern="(a+)+"), ValueError)
    # files
    root, base, outside = _make_root("logs")
    try:
        with open(os.path.join(base, "app.log"), "w") as fh:
            fh.write("\n".join(py) + "\n")
        with open(os.path.join(outside, "s.log"), "w") as fh:
            fh.write("x\n")
        assert m.read_file("app.log", base) == py
        assert m.read_file(os.path.join(base, "app.log"), base) == py
        with open(os.path.join(base, "many.log"), "w") as fh:
            fh.write("x\n" * (m.MAX_LINES + 5))
        assert len(m.read_file("many.log", base)) == m.MAX_LINES
        os.makedirs(os.path.join(base, "d"))
        for p in ("../outside/s.log", os.path.join(outside, "s.log"), "/etc/passwd", "", "missing.log", "d"):
            assert _raises(lambda: m.read_file(p, base), ValueError), "allowed %r" % p
        if _symlink(os.path.join(outside, "s.log"), os.path.join(base, "link.log")):
            assert _raises(lambda: m.read_file("link.log", base), ValueError), "symlink escape"
        # pasted input (inp= hook, no builtins.input needed)
        feed = iter(["a", "b", "END", "never"])
        assert _quiet(m.read_pasted, lambda p="": next(feed))[0] == ["a", "b"]
        def eof(p=""): raise EOFError
        assert _quiet(m.read_pasted, eof)[0] == []
        # menu through inp=
        answers = iter(["1"] + py + ["END", "4", "5", "6", "error,critical", "7", "(a+)+", "7", "tick",
                        "3", "json", "3", "bogus", "2", "../../etc/passwd", "zz", "0"])
        _, out = _quiet(m.main, lambda p="": next(answers, "0"))
        assert "Loaded 5 entries (python)" in out and "Counts by level:" in out, out
        assert "2026-10-16 11:00 | " in out and "3 matches" in out and "1 matches" in out, out
        assert "Error: nested quantifier rejected" in out and "Parsed as json" in out, out
        assert "Error: unknown format: bogus" in out, out
        assert "Error: path outside" in out or "Error: refused" in out, out   # tool check, or kp_safe_path in the app
        assert "Unknown choice" in out
    finally:
        _cleanup(root)
    print("r6_bot2help_logs self-tests passed.")
    return True


# ---------------- all four ----------------
def self_test():
    for fn in (self_test_metrics, self_test_imports, self_test_chart, self_test_logs):
        assert fn() is True, fn.__name__
    print("bot2help r9 self-tests passed (4 tools).")
    return True


def main():
    return self_test()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
