# Projects & zip: create multi-file projects in /home/pyodide/projects, run main.py, zip/unzip, and import a public GitHub repo as a zip (no login, stdlib only).
import os, sys, io, zipfile, shutil, runpy

ROOT = "/home/pyodide/projects"
TEMPLATE = {"main.py": 'from helpers import greet\n\nif __name__ == "__main__":\n    print(greet(input("Name: ")))\n',
            "helpers.py": 'def greet(name):\n    return f"Hello, {name}!"\n', "README.md": "# __NAME__\n"}

def _bytes(url):
    try:
        import js
        x = js.XMLHttpRequest.new(); x.open("GET", url, False)
        x.overrideMimeType("text/plain; charset=x-user-defined"); x.send(None)
        if x.status != 200: raise RuntimeError(f"HTTP {x.status}")
        return bytes(ord(c) & 0xFF for c in x.responseText)
    except ImportError:
        import urllib.request
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "kp-pyapp"}), timeout=60).read()

def path(name):
    name = os.path.basename((name or "").strip().strip("/"))
    if not name or name in (".", ".."): raise ValueError("bad project name")
    return os.path.join(ROOT, name)
MARK = ".kp_downloaded"  # KPython: downloaded projects need a typed yes before running

def list_projects():
    os.makedirs(ROOT, exist_ok=True)
    ps = sorted(d for d in os.listdir(ROOT) if os.path.isdir(path(d)))
    for n, p in enumerate(ps, 1): print(f"{n:>2}. {p}  ({sum(len(f) for _, _, f in os.walk(path(p)))} files)")
    return ps

def new(name):
    d = path(name)
    if os.path.exists(d): print("Already exists."); return
    os.makedirs(d)
    for f, t in TEMPLATE.items(): open(os.path.join(d, f), "w").write(t.replace("__NAME__", name))
    print("Created", d, "with", ", ".join(TEMPLATE))

def tree(name):
    base = path(name)
    for r, ds, fs in os.walk(base):
        ds.sort(); depth = r[len(base):].count(os.sep)
        print("  " * depth + (os.path.basename(r) or name) + "/")
        for f in sorted(fs): print("  " * (depth + 1) + f)

def run(name, entry="main.py"):
    d = path(name); f = os.path.join(d, entry)
    f = os.path.realpath(f)
    if not f.startswith(os.path.realpath(d) + os.sep): print("Entry must be inside the project"); return
    if not os.path.exists(f): print("No", entry, "in", name); return
    if os.path.exists(os.path.join(d, MARK)) and input(f"{name} was downloaded from the internet. Run {entry}? Only run code you trust. type yes: ").strip().lower() != "yes":
        print("Not run."); return
    old_cwd, old_path = os.getcwd(), list(sys.path)
    before = set(sys.modules)
    os.chdir(d); sys.path.insert(0, d)
    try: runpy.run_path(f, run_name="__main__")
    except SystemExit: pass
    finally:
        os.chdir(old_cwd); sys.path[:] = old_path
        for m in set(sys.modules) - before:  # so edits reload next run
            if getattr(sys.modules[m], "__file__", "") and str(sys.modules[m].__file__).startswith(d): del sys.modules[m]

def zip_project(name):
    out = os.path.join(ROOT, name + ".zip"); base = path(name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for r, _, fs in os.walk(base):
            if "__pycache__" in r: continue
            for f in fs: z.write(os.path.join(r, f), os.path.relpath(os.path.join(r, f), base))
    print("Zipped to", out, f"({os.path.getsize(out):,} bytes)")

def _safe_extract(z, dest, strip_top=False):
    dest = os.path.realpath(dest); n = 0
    for m in z.infolist():
        rel = m.filename.split("/", 1)[1] if strip_top and "/" in m.filename else m.filename
        if not rel or rel.endswith("/"): continue
        target = os.path.realpath(os.path.join(dest, rel))
        if not target.startswith(dest + os.sep): continue  # block ../ tricks
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(m) as s, open(target, "wb") as o: shutil.copyfileobj(s, o); n += 1
    return n

def unzip(zip_path, name=None):
    name = name or os.path.splitext(os.path.basename(zip_path))[0]
    zip_path = os.path.realpath(os.path.join(ROOT, zip_path))
    if not zip_path.startswith("/home/pyodide/"): raise ValueError("zip must be under /home/pyodide")
    with zipfile.ZipFile(zip_path) as z: n = _safe_extract(z, path(name))
    open(os.path.join(path(name), MARK), "w").write("unzipped")
    print(f"Unzipped {n} files into {path(name)}")

def import_github(repo, ref=""):
    repo = repo.strip().replace("https://", "").replace("github.com/", "").strip("/").removesuffix(".git")
    owner, name = repo.split("/")[:2]
    url = f"https://api.github.com/repos/{owner}/{name}/zipball" + (f"/{ref}" if ref else "")
    print("Downloading", url, "...")
    try:
        data = _bytes(url)
    except Exception as e:
        print("Download failed:", e)
        print("GitHub's zip download redirects to codeload.github.com, which browsers block (CORS). Use the GitHub panel in Tools to open files instead.")
        return
    dest = path(name)
    if os.path.exists(dest) and input(f"{name} exists. Overwrite? (y/n): ").lower() != "y": return
    shutil.rmtree(dest, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z: n = _safe_extract(z, dest, strip_top=True)
    open(os.path.join(dest, MARK), "w").write(url)
    print(f"Imported {n} files ({len(data):,} bytes) into {dest}")

def main():
    os.makedirs(ROOT, exist_ok=True)
    menu = """\n=== Projects ===
 1 list   2 new   3 tree   4 run main.py   5 zip   6 unzip   7 import GitHub repo   8 delete   q quit"""
    while True:
        print(menu); c = input("> ").strip()
        try:
            if c == "q": break
            elif c == "1": list_projects()
            elif c == "2": new(input("Project name: ").strip())
            elif c and c in "3458":
                ps = list_projects(); s = input("Project # or name: ").strip()
                p = ps[int(s) - 1] if s.isdigit() else s
                if c == "3": tree(p)
                elif c == "4": run(p, input("Entry file [main.py]: ").strip() or "main.py")
                elif c == "5": zip_project(p)
                elif c == "8" and input(f"Delete {p}? type yes: ") == "yes": shutil.rmtree(path(p)); print("Deleted.")
            elif c == "6": unzip(input("Zip file path: ").strip(), input("Project name (enter = zip name): ").strip() or None)
            elif c == "7": import_github(input("owner/repo or URL: "), input("Branch/tag (enter = default): ").strip())
        except Exception as e: print("Error:", e)

if __name__ == "__main__":
    main()
