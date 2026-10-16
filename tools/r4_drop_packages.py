# Drop's Package Manager: list installed packages, look up exact PyPI names (version, summary, pure-Python wheel?), typo-squat warnings, confirmed + pinned micropip installs, and the app's reinstall list. Stdlib + micropip (lazy).
import asyncio, difflib, json, os, re, sys, urllib.parse

PYPI = "https://pypi.org/pypi/"
TIMEOUT = 15            # seconds per request
MAX_BYTES = 8_000_000   # response size cap
BASE_DIR = "/home/pyodide"
MIRROR = ".kp_pkgs.json"  # fallback copy of the reinstall list (see reinstall_get/set)

# Common packages people mean to type; near-misses of these get a typo-squat warning.
POPULAR = """requests numpy pandas matplotlib scipy sympy scikit-learn pillow beautifulsoup4 lxml
pyyaml toml tomli attrs click rich colorama tqdm python-dateutil pytz six urllib3 certifi idna
charset-normalizer jinja2 markupsafe flask django fastapi pydantic httpx aiohttp openpyxl xlrd
networkx regex simplejson ujson orjson cryptography pyjwt boto3 loguru tabulate termcolor
pygments packaging setuptools wheel pytest mypy black isort faker emoji arrow pendulum
deepseek openai anthropic bittensor sqlalchemy seaborn plotly bokeh nltk textblob""".split()

NAME_RE = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", re.I)          # PEP 508 name
VER_RE = re.compile(r"^\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$")        # PEP 440 (public, simplified)
PYODIDE_BUILT = {"numpy", "pandas", "matplotlib", "scipy", "sympy", "scikit-learn", "pillow", "lxml", "regex", "pyyaml", "cryptography"}
IN_PYODIDE = sys.platform == "emscripten" or "pyodide" in sys.modules


# ---------------- pure logic ----------------
def normalize(name):
    """PEP 503 normalized name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_spec(spec):
    """'Name' or 'Name==1.2.3' -> (name, version or None). Raises ValueError."""
    spec = (spec or "").strip()
    if not spec or len(spec) > 120:
        raise ValueError("enter a package name (max 120 chars)")
    name, sep, ver = spec.partition("==")
    name, ver = name.strip(), ver.strip()
    if not NAME_RE.match(name) or len(name) > 100:
        raise ValueError(f"{name!r} is not a valid package name (letters, digits, . _ - only)")
    if sep:
        if not VER_RE.match(ver):
            raise ValueError(f"{ver!r} is not a valid version like 2.31.0")
        return name, ver
    return name, None


def near_misses(name):
    n = normalize(name)
    if n in POPULAR:
        return []
    return difflib.get_close_matches(n, POPULAR, n=3, cutoff=0.8)


def pypi_url(name, version=None):
    q = urllib.parse.quote(normalize(name), safe="")
    return PYPI + q + ("/" + urllib.parse.quote(version, safe="") if version else "") + "/json"


def pure_wheel(files):
    """True if any file is a pure-Python wheel micropip can install."""
    for f in files or []:
        fn = str((f or {}).get("filename", "")) if isinstance(f, dict) else ""
        if fn.endswith(".whl") and re.search(r"-(py3|py2\.py3)-none-any\.whl$", fn):
            return True
    return False


def summarize(data):
    """Pull the safe fields out of a PyPI JSON response."""
    if not isinstance(data, dict) or not isinstance(data.get("info"), dict):
        raise ValueError("unexpected response from PyPI")
    info = data["info"]
    clip = lambda v, n: "".join(c for c in str(v or "") if c.isprintable())[:n]
    return {
        "name": clip(info.get("name"), 100),
        "version": clip(info.get("version"), 50),
        "summary": clip(info.get("summary"), 200) or "(no summary)",
        "pure": pure_wheel(data.get("urls")),
        "yanked": bool(info.get("yanked")),
    }


# ---------------- network (pypi.org only) ----------------
def _fetch_sync(url):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "kpython-r4"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(MAX_BYTES + 1)
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, b""


async def _fetch_pyodide(url):
    from pyodide.http import pyfetch
    r = await asyncio.wait_for(pyfetch(url, headers={"Accept": "application/json"}), TIMEOUT)
    if not r.ok:
        return r.status, b""
    body = await asyncio.wait_for(r.bytes(), TIMEOUT)
    return r.status, body


async def fetch_json(url, fetcher=None):
    if not url.startswith(PYPI):
        raise ValueError("refusing: only https://pypi.org is allowed")
    if fetcher is not None:
        status, body = await fetcher(url)
    elif IN_PYODIDE:
        status, body = await _fetch_pyodide(url)
    else:
        status, body = await asyncio.get_running_loop().run_in_executor(None, _fetch_sync, url)
    if status == 404:
        raise LookupError("not found on PyPI")
    if status != 200:
        raise ConnectionError(f"PyPI returned HTTP {status}")
    if len(body) > MAX_BYTES:
        raise ValueError("response too large")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("PyPI sent invalid JSON")


async def lookup(name, version=None, fetcher=None):
    s = summarize(await fetch_json(pypi_url(name, version), fetcher))
    if version and s["version"] != version:
        raise LookupError(f"{name}=={version} not found")
    return s


# ---------------- reinstall list (the app's kp_pkgs) ----------------
# The app keeps kp_pkgs in the page's localStorage and reinstalls it when Python starts.
# Python runs in a Worker, which can't reach localStorage. If the app exposes
# kp_pkgs_get()/kp_pkgs_set(list) to Python, we use them. Otherwise we keep a mirror
# at /home/pyodide/.kp_pkgs.json and say how to add the entry in the Packages box.
def _hook(name):
    import builtins
    return getattr(builtins, name, None) or getattr(sys.modules.get("__main__"), name, None)


def _mirror_path():
    b = os.path.realpath(BASE_DIR)
    p = os.path.realpath(os.path.join(b, MIRROR))
    if not p.startswith(b + os.sep):
        raise ValueError("reinstall list path escapes the home folder")
    return p


def _valid_entry(x):
    return isinstance(x, str) and len(x) <= 120 and re.match(r"^[\w.\-\[\]=<>]+$", x) is not None


def reinstall_get():
    g = _hook("kp_pkgs_get")
    if g:
        lst = g()
        lst = list(lst.to_py() if hasattr(lst, "to_py") else lst)
    else:
        try:
            with open(_mirror_path(), encoding="utf-8") as f:
                lst = json.load(f)
        except (OSError, ValueError):
            lst = []
    return [x for x in lst if _valid_entry(x)] if isinstance(lst, list) else []


def reinstall_set(lst):
    lst = [x for x in lst if _valid_entry(x)]
    s = _hook("kp_pkgs_set")
    if s:
        s(lst)
        return True
    os.makedirs(os.path.dirname(_mirror_path()), exist_ok=True)
    with open(_mirror_path(), "w", encoding="utf-8") as f:
        json.dump(lst, f)
    return False


def add_pin(lst, name, version):
    """Replace any older entry for the same package with name==version."""
    n = normalize(name)
    keep = [x for x in lst if normalize(re.split(r"[=<>\[]", x, maxsplit=1)[0]) != n]
    return keep + [f"{name}=={version}"]


# ---------------- installed packages ----------------
def installed():
    try:
        import micropip  # Pyodide
        return sorted((k, str(getattr(v, "version", v))) for k, v in micropip.list().items())
    except Exception:
        from importlib import metadata
        out = {}
        for d in metadata.distributions():
            n = d.metadata.get("Name")
            if n:
                out[n] = d.version
        return sorted(out.items(), key=lambda kv: kv[0].lower())


# ---------------- interactive ----------------
def yes(prompt):
    return input(prompt + " (y/n): ").strip().lower() in ("y", "yes")


def show(s):
    print(f"  Name:    {s['name']}\n  Version: {s['version']}\n  Summary: {s['summary']}")
    if normalize(s["name"]) in PYODIDE_BUILT:
        print("  Wheel:   built into Pyodide: micropip/the Packages box loads Pyodide's own build")
    else:
        print("  Wheel:   " + ("pure Python (py3-none-any): works with micropip" if s["pure"] else "no pure-Python wheel: micropip probably can't install it"))
    if s["yanked"]:
        print("  WARNING: this release was yanked by its author.")


async def do_search(fetcher=None):
    print("PyPI has no search API, so this looks up one exact name.")
    name, ver = parse_spec(input("Package name: "))
    show(await lookup(name, ver, fetcher))


async def do_install(fetcher=None, installer=None):
    name, ver = parse_spec(input("Install (name or name==version): "))
    for m in near_misses(name):
        print(f"  ⚠️  '{name}' looks a lot like the popular package '{m}'. Typo-squats copy famous names to steal data.")
    s = await lookup(name, ver, fetcher)
    show(s)
    if not yes(f"Install {s['name']}=={s['version']}?"):
        print("Cancelled.")
        return False
    spec = f"{s['name']}=={s['version']}"
    if installer is None:
        try:
            import micropip
        except ImportError:
            print("micropip is only available inside the KPython app. Nothing installed.")
            return False
        installer = micropip.install
    await installer(spec)
    print(f"Installed {spec}.")
    used_app = reinstall_set(add_pin(reinstall_get(), s["name"], s["version"]))
    print("Added to the reinstall list." if used_app else
          f"Saved to {MIRROR}. To have the app reinstall it on startup, also type {spec} in Code ▸ 📦 Packages.")
    return True


def do_remove():
    lst = reinstall_get()
    if not lst:
        print("Reinstall list is empty.")
        return
    for i, x in enumerate(lst, 1):
        print(f"{i}. {x}")
    c = input("Number to remove: ").strip()
    if not c.isdigit() or not 1 <= int(c) <= len(lst):
        print("Invalid choice.")
        return
    item = lst[int(c) - 1]
    if yes(f"Remove {item} from the reinstall list? (It stays installed until Python restarts.)"):
        reinstall_set([x for x in lst if x != item])
        print("Removed.")


async def amain():
    print("=== Package Manager ===")
    while True:
        c = input("\n1 Installed  2 Look up on PyPI  3 Install  4 Reinstall list  5 Remove from list  t Self-tests  q Quit: ").strip().lower()
        try:
            if c in ("q", "quit", "exit"):
                break
            elif c == "1":
                for n, v in installed():
                    print(f"  {n} {v}")
            elif c == "2":
                await do_search()
            elif c == "3":
                await do_install()
            elif c == "4":
                print("\n".join("  " + x for x in reinstall_get()) or "  (empty)")
            elif c == "5":
                do_remove()
            elif c == "t":
                await self_tests_async()
            else:
                print("Pick 1-5, t or q.")
        except (ValueError, LookupError, ConnectionError, OSError, asyncio.TimeoutError) as e:
            print("Error:", e or type(e).__name__)
        except Exception as e:  # network/JS errors in the browser
            print(f"Error: {type(e).__name__}: {e}")


def main():
    if IN_PYODIDE:
        # Pyodide's event loop runs in the page; schedule the async menu on it.
        return asyncio.ensure_future(amain())
    asyncio.run(amain())


# ---------------- self-tests (offline, mocked network) ----------------
def run_self_tests():
    """Plain-python entry point (no event loop running)."""
    return asyncio.run(self_tests_async())


async def self_tests_async():
    global BASE_DIR
    import tempfile, shutil, builtins
    ok = fail = 0

    def check(c, label):
        nonlocal ok, fail
        ok, fail = (ok + 1, fail) if c else (ok, fail + 1)
        if not c:
            print("FAIL:", label)

    check(parse_spec("requests") == ("requests", None), "plain name")
    check(parse_spec(" Flask==3.0.2 ") == ("Flask", "3.0.2"), "pin")
    for bad in ("", "-bad", "a b", "x==", "x==1.0;rm", "../etc", "x==1.0 ; python_version", "a" * 130, "x>=1"):
        try:
            parse_spec(bad); check(False, f"accepted {bad!r}")
        except ValueError:
            check(True, "")
    check(normalize("Foo_Bar.baz") == "foo-bar-baz", "normalize")
    check("requests" in near_misses("reqeusts") and near_misses("requests") == [], "typosquat")
    check("bittensor" in near_misses("bitensor"), "typosquat 2")
    check(pypi_url("A_b", "1.0") == "https://pypi.org/pypi/a-b/1.0/json", "url")
    check(pure_wheel([{"filename": "x-1-py3-none-any.whl"}]) and not pure_wheel([{"filename": "x-1-cp312-cp312-win_amd64.whl"}, "junk", None]), "wheel")
    check(add_pin(["Requests==1", "six"], "requests", "2.0") == ["six", "requests==2.0"], "add_pin")

    good = json.dumps({"info": {"name": "demo", "version": "1.2.0", "summary": "A demo\x1b[31m"},
                       "urls": [{"filename": "demo-1.2.0-py3-none-any.whl"}]}).encode()

    async def fake(url):
        if "missing" in url: return 404, b""
        if "boom" in url: return 500, b""
        if "badjson" in url: return 200, b"{not json"
        if "huge" in url: return 200, b" " * (MAX_BYTES + 1)
        return 200, good

    async def go():
        s = await lookup("demo", fetcher=fake)
        check(s["name"] == "demo" and s["pure"] and "\x1b" not in s["summary"], "lookup")
        await lookup("demo", "1.2.0", fetcher=fake)
        for n, err in (("missing", LookupError), ("boom", ConnectionError), ("badjson", ValueError), ("huge", ValueError)):
            try:
                await lookup(n, fetcher=fake); check(False, n)
            except err:
                check(True, "")
        try:
            await lookup("demo", "9.9", fetcher=fake); check(False, "version mismatch")
        except LookupError:
            check(True, "")
        try:
            await fetch_json("https://evil.example/pypi/x/json", fake); check(False, "host check")
        except ValueError:
            check(True, "")
        # install flow with mocked input + installer
        answers = iter(["demo==1.2.0", "y"])
        real_input, done = builtins.input, []
        builtins.input = lambda p="": next(answers)
        try:
            async def inst(spec): done.append(spec)
            r = await do_install(fetcher=fake, installer=inst)
        finally:
            builtins.input = real_input
        check(r and done == ["demo==1.2.0"] and "demo==1.2.0" in reinstall_get(), "install flow + reinstall list")
        answers = iter(["demo", "n"])
        builtins.input = lambda p="": next(answers)
        try:
            r = await do_install(fetcher=fake, installer=inst)
        finally:
            builtins.input = real_input
        check(r is False and len(done) == 1, "install cancelled")

    global _hook
    old_hook, _hook = _hook, (lambda name: None)  # KPython v7: self-test uses a temp list, never the app's real reinstall list
    old = BASE_DIR
    BASE_DIR = tempfile.mkdtemp()
    try:
        await go()
        check(isinstance(installed(), list), "installed()")
    finally:
        shutil.rmtree(BASE_DIR, ignore_errors=True)
        BASE_DIR = old
        _hook = old_hook
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
