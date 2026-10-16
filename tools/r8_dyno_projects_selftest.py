# Dyno: real self_test() for r2_bot_projects that runs in a temp dir (no /home/pyodide needed): names, new, tree, run, zip, unzip, zip-slip and downloaded-project guards. Stdlib only.
import os, io, sys, zipfile, tempfile, shutil, builtins, contextlib, importlib

def _load_projects():
    for d in ("/kptools", "/workspace/pyapp/tools", os.path.dirname(os.path.abspath(__file__))):
        if os.path.isfile(os.path.join(d, "r2_bot_projects.py")) and d not in sys.path:
            sys.path.insert(0, d)
    return importlib.import_module("r2_bot_projects")

def self_test(m=None):
    m = m or _load_projects()
    tmp = os.path.realpath(tempfile.mkdtemp())
    old_root, old_input, cwd = m.ROOT, builtins.input, os.getcwd()
    m.ROOT = os.path.join(tmp, "projects")
    try:
        os.makedirs(m.ROOT)
        def q(f, *a):
            b = io.StringIO()
            with contextlib.redirect_stdout(b):
                f(*a)
            return b.getvalue()
        # names stay a single folder under ROOT
        for n in ("../x", "/etc", "a/b"): assert os.path.dirname(m.path(n)) == m.ROOT
        for bad in ("", ".", ".."):
            try: m.path(bad); raise AssertionError(bad)
            except ValueError: pass
        # new + list + tree
        q(m.new, "demo"); d = m.path("demo")
        assert sorted(os.listdir(d)) == ["README.md", "helpers.py", "main.py"]
        assert "Already exists" in q(m.new, "demo")
        assert q(m.list_projects) and "demo" in [p for p in os.listdir(m.ROOT)]
        assert "helpers.py" in q(m.tree, "demo")
        # run uses input(); stub it
        builtins.input = lambda p="": "Keivon"
        assert "Hello, Keivon!" in q(m.run, "demo")
        assert "inside the project" in q(m.run, "demo", "../../etc/passwd")
        assert "No nope.py" in q(m.run, "demo", "nope.py")
        # zip round trip
        q(m.zip_project, "demo"); zp = os.path.join(m.ROOT, "demo.zip")
        with zipfile.ZipFile(zp) as z: assert "main.py" in z.namelist()
        # zip-slip blocked
        evil = os.path.join(tmp, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../escaped.txt", "x"); z.writestr("ok.txt", "y")
        with zipfile.ZipFile(evil) as z: n = m._safe_extract(z, os.path.join(m.ROOT, "evil"))
        assert n == 1 and not os.path.exists(os.path.join(tmp, "escaped.txt"))
        # downloaded project needs typed yes before running
        shutil.copytree(d, m.path("dl")); open(os.path.join(m.path("dl"), m.MARK), "w").write("x")
        builtins.input = lambda p="": "n"
        assert "Not run" in q(m.run, "dl")
        # unzip only allowed under /home/pyodide
        try: m.unzip(zp, "copy"); assert zp.startswith("/home/pyodide/")
        except ValueError: pass
        assert os.getcwd() == cwd
    finally:
        m.ROOT, builtins.input = old_root, old_input
        os.chdir(cwd); shutil.rmtree(tmp, ignore_errors=True)
    print("self-tests passed")
    return True


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    self_test()
