# r8_drop_ghimport.py - import a public GitHub repo into ~/<repo> using CORS-safe endpoints (trees API + raw/blobs), no zipball (Drop, KPython r8)
"""Why not the zipball: api.github.com/.../zipball answers 302 to codeload.github.com, which only sends
Access-Control-Allow-Origin: https://render.githubusercontent.com, so a browser fetch from the app fails.
This tool lists files with GET api.github.com/repos/{o}/{r}/git/trees/{ref}?recursive=1 (ACAO: *) and downloads each
file from raw.githubusercontent.com (ACAO: *, no API quota) when that site is in Allowed sites, otherwise from
api.github.com/repos/{o}/{r}/git/blobs/{sha} (ACAO: *, default-allowed, but each file uses 1 of 60 requests/hour).
Standard library only. No tokens, no exec. Writes only under /home/pyodide/<dest>, after you confirm."""
import asyncio, base64, json, os, re, sys, time
from urllib.parse import quote

BASE_DIR = "/home/pyodide"
API, RAW = "https://api.github.com", "https://raw.githubusercontent.com"
ALLOWED_HOSTS = {"api.github.com", "raw.githubusercontent.com"}
MAX_FILES, MAX_FILE, MAX_TOTAL, MAX_DEPTH = 300, 500_000, 5_000_000, 8
MAX_TREE_BYTES = 8_000_000
BIN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z",
           ".tar", ".whl", ".egg", ".so", ".dll", ".dylib", ".exe", ".bin", ".pyc", ".pyo", ".class", ".jar", ".o", ".a",
           ".mp3", ".mp4", ".wav", ".ogg", ".mov", ".avi", ".ttf", ".otf", ".woff", ".woff2", ".eot", ".psd", ".sqlite", ".db",
           ".npy", ".npz", ".pkl", ".parquet", ".xlsx", ".docx", ".pptx"}
IN_PYODIDE = "pyodide" in sys.modules or sys.platform == "emscripten"

OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


class GHError(Exception):
    pass


# ---------- validation ----------
def valid_owner(s):
    return bool(OWNER_RE.match(s or ""))


def valid_repo(s):
    return bool(REPO_RE.match(s or "")) and s not in (".", "..") and not s.endswith(".git")


def valid_ref(s):
    if not s or not REF_RE.match(s):
        return False
    if s.startswith(("-", "/", ".")) or s.endswith(("/", ".", ".lock")):
        return False
    return ".." not in s and "//" not in s and "/." not in s and "@{" not in s


def parse_repo(text):
    """'owner/repo', 'owner/repo@ref' or a github.com URL (optionally /tree/<ref>) -> (owner, repo, ref|None)."""
    t = (text or "").strip()
    m = re.match(r"^https://github\.com/(.+)$", t)
    ref = None
    if m:
        t = m.group(1).rstrip("/")
        parts = t.split("/")
        if len(parts) >= 4 and parts[2] == "tree":
            ref = "/".join(parts[3:])
        t = "/".join(parts[:2])
    elif "://" in t:
        raise GHError("Only https://github.com/... links (or owner/repo) are accepted.")
    if "@" in t:
        t, ref = t.split("@", 1)
    if t.endswith(".git"):
        t = t[:-4]
    if t.count("/") != 1:
        raise GHError("Repo must look like owner/repo")
    o, r = t.split("/")
    if not valid_owner(o):
        raise GHError(f"Invalid owner name: {o!r}")
    if not valid_repo(r):
        raise GHError(f"Invalid repo name: {r!r}")
    if ref is not None and not valid_ref(ref):
        raise GHError(f"Invalid branch/tag/commit: {ref!r}")
    return o, r, ref


def check_url(url):
    """https only, verified hosts only, and (in the app) only if Allowed sites permits it."""
    from urllib.parse import urlsplit
    u = urlsplit(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS or u.port or u.username:
        raise GHError(f"Refused URL: {url}")
    if not site_allowed(f"https://{u.hostname}"):
        raise GHError(f"Blocked: https://{u.hostname} isn't in Allowed sites. Add it in Tools > Allowed sites.")
    return url


def site_allowed(origin):
    """Read-only check against the app's Allowed sites (never changes them). Outside the app: everything allowed."""
    if not IN_PYODIDE:
        return True
    try:
        import __main__
        f = getattr(__main__, "_kp_site_allowed", None)
        if f:
            return bool(f(origin + "/")[0])
    except Exception:
        pass
    return origin == API  # api.github.com is a built-in default; assume nothing else


# ---------- paths ----------
def _local_safe_path(p, base=None):
    base = base or BASE_DIR
    raw = os.path.normpath(os.path.join(base, str(p).strip()))
    full = os.path.realpath(raw)
    if full != base and not full.startswith(base + "/"):
        raise ValueError(f"refused: {p} is outside {base}")
    cur = base
    for part in (os.path.relpath(raw, base).split(os.sep) if raw != base else []):
        if part in ("", "."):
            continue
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise ValueError(f"refused: {p} goes through a symlink")
    return full


def safe_join(dest, rel):
    """Validate a repo path and resolve it under ~/<dest> via kp_safe_path (app) or the same rule locally."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel or rel.startswith("/") or ":" in rel.split("/")[0][:2]:
        raise ValueError(f"bad path {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"bad path {rel!r}")
    if any(p.lower() == ".history" for p in parts) or dest.lower() == ".history":
        raise ValueError(f"refused .history path {rel!r}")
    if len(parts) > MAX_DEPTH:
        raise ValueError(f"too deep ({len(parts)} > {MAX_DEPTH}): {rel}")
    if BASE_DIR == "/home/pyodide":
        try:
            sp = kp_safe_path  # noqa: F821  (provided by the app)
        except NameError:
            sp = _local_safe_path
    else:
        sp = _local_safe_path
    full = sp(os.path.join(dest, rel)) if sp is not _local_safe_path else sp(os.path.join(dest, rel), BASE_DIR)
    root = os.path.realpath(os.path.join(BASE_DIR, dest))
    if not full.startswith(root + "/"):
        raise ValueError(f"refused: {rel} escapes {dest}")
    return full


# ---------- fetch ----------
async def _fetch_urllib(url):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, headers={"User-Agent": "KPython-ghimport", "Accept": "application/vnd.github+json"})

    def go():
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(MAX_TREE_BYTES + 1)
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read(65536)
    return go()


async def _fetch_pyodide(url):
    from pyodide.http import pyfetch
    # raw.githubusercontent.com fails CORS preflight (OPTIONS 403): send custom headers only to the API
    hdr = {"Accept": "application/vnd.github+json"} if url.startswith(API + "/") else {}
    r = await pyfetch(url, headers=hdr, cache="no-store")
    h = {}
    try:
        for k in ("x-ratelimit-remaining", "x-ratelimit-reset", "retry-after", "content-length"):
            v = r.js_response.headers.get(k)
            if v is not None:
                h[k] = str(v)
    except Exception:
        pass
    return r.status, h, await r.bytes()


FETCH = None  # tests replace this with a mock: async (url) -> (status, headers, bytes)


async def get(url):
    check_url(url)
    f = FETCH or (_fetch_pyodide if IN_PYODIDE else _fetch_urllib)
    try:
        st, h, body = await f(url)
    except GHError:
        raise
    except Exception as e:
        name = type(e).__name__
        if name == "KPBlockedError":
            raise GHError(str(e))
        raise GHError(f"Network error for {url.split('?')[0]}: {e}. (Offline, or blocked by Allowed sites?)")
    if st in (403, 429) and (h.get("x-ratelimit-remaining") == "0" or st == 429 or b"rate limit" in body[:500].lower()):
        msg = "GitHub rate limit reached (60 requests/hour without login)."
        reset = h.get("x-ratelimit-reset")
        if reset and reset.isdigit():
            msg += " Try again after " + time.strftime("%H:%M", time.localtime(int(reset))) + " (your local time)."
        elif h.get("retry-after", "").isdigit():
            msg += f" Try again in {h['retry-after']} s."
        raise GHError(msg)
    if st == 404:
        raise GHError("Not found: check owner/repo and branch (private repos can't be imported without a token).")
    if st == 409:
        raise GHError("The repository is empty.")
    if st != 200:
        raise GHError(f"GitHub answered HTTP {st} for {url.split('?')[0]}")
    if len(body) > MAX_TREE_BYTES:
        raise GHError("Response too large.")
    return body, h


async def get_json(url):
    body, h = await get(url)
    try:
        return json.loads(body.decode("utf-8")), h
    except Exception:
        raise GHError("GitHub sent something that isn't JSON.")


# ---------- planning ----------
def is_binary_name(path):
    return os.path.splitext(path)[1].lower() in BIN_EXT


def is_binary_data(b):
    if b"\x00" in b[:8192]:
        return True
    try:
        b.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def plan(tree, dest):
    """tree: GitHub trees JSON. Returns (files[(path, sha, size, full)], skipped{reason: [paths]})."""
    files, skipped, total = [], {}, 0

    def skip(reason, p):
        skipped.setdefault(reason, []).append(p)
    if tree.get("truncated"):
        skip("tree truncated by GitHub (repo too big; only part listed)", "*")
    for e in tree.get("tree", []) if isinstance(tree.get("tree"), list) else []:
        if not isinstance(e, dict):
            continue
        p, t, mode = e.get("path"), e.get("type"), str(e.get("mode", ""))
        if t == "tree":
            continue
        if t == "commit" or mode == "160000":
            skip("submodule", p); continue
        if mode == "120000":
            skip("symlink", p); continue
        if t != "blob" or not isinstance(p, str):
            skip("unknown entry", p); continue
        size = e.get("size") if isinstance(e.get("size"), int) else MAX_FILE + 1
        sha = e.get("sha", "")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(sha)):
            skip("bad sha", p); continue
        try:
            full = safe_join(dest, p)
        except ValueError as ex:
            skip("unsafe or too deep path", f"{p} ({ex})"); continue
        if is_binary_name(p):
            skip("binary", p); continue
        if size > MAX_FILE:
            skip(f"over {MAX_FILE // 1000} KB", p); continue
        if len(files) >= MAX_FILES:
            skip(f"over {MAX_FILES} files", p); continue
        if total + size > MAX_TOTAL:
            skip(f"over {MAX_TOTAL // 1_000_000} MB total", p); continue
        total += size
        files.append((p, sha, size, full))
    return files, skipped


def raw_url(o, r, ref, path):
    return f"{RAW}/{quote(o)}/{quote(r)}/{quote(ref, safe='/')}/{quote(path, safe='/')}"


async def download(o, r, ref, f, use_raw):
    p, sha, size, _ = f
    if use_raw:
        body, _ = await get(raw_url(o, r, ref, p))
    else:
        d, _ = await get_json(f"{API}/repos/{quote(o)}/{quote(r)}/git/blobs/{sha}")
        if d.get("encoding") != "base64":
            raise GHError(f"unexpected blob encoding for {p}")
        body = base64.b64decode(d.get("content", ""))
    if len(body) > MAX_FILE:
        raise GHError(f"{p} is larger than expected")
    if re.fullmatch(r"[0-9a-f]{40}", sha or "") and git_blob_sha(body) != sha:   # v11: content must match the tree
        raise GHError(f"{p}: downloaded content doesn't match the repository (git blob hash mismatch); nothing more written")
    return body


def git_blob_sha(data):
    """git's blob id: sha1(b"blob <len>\\0" + data)."""
    import hashlib
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def atomic_write(full, data):
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if os.path.islink(full):
        raise ValueError("refused: target is a symlink")
    tmp = full + ".kptmp"
    if os.path.lexists(tmp):          # v11 (Get back L7): never follow something planted at the temp name
        if os.path.isdir(tmp) and not os.path.islink(tmp):
            raise ValueError("refused: temp name is a folder")
        os.remove(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, full)


def reserved_name(name):
    """v11 (Drop #3): a folder in ~ named like a stdlib module, a KPython tool or kp_* could shadow it on import."""
    import builtins as _b
    n = (name or "").strip().lower().replace("-", "_")
    tools = set()
    try: tools = set(getattr(_b, "kp_tool_names", lambda: ())())
    except Exception: pass
    std = set(getattr(sys, "stdlib_module_names", ()))
    return n in std or n in tools or n.startswith(("kp_", "_kp")) or bool(re.match(r"r\d+_", n))


# ---------- main flow ----------
async def import_repo(spec, dest=None, ask=input, out=print):
    o, r, ref = parse_repo(spec)
    if ref is None:
        info, _ = await get_json(f"{API}/repos/{o}/{r}")
        ref = info.get("default_branch") or ""
        if not valid_ref(ref):
            raise GHError("Couldn't read the default branch.")
    if not dest and reserved_name(r):
        dest = "gh_" + r
        out(f"  (saving into ~/{dest}: a folder named {r!r} could shadow a Python module)")
    dest = dest or r
    if reserved_name(dest):
        raise GHError(f"Folder name {dest!r} is reserved (Python module or KPython tool name); pick another, e.g. gh_{dest}")
    if not valid_repo(dest) or dest.lower() == ".history":
        raise GHError(f"Invalid destination folder {dest!r}")
    root = safe_join(dest, "x")[:-2]
    tree, h = await get_json(f"{API}/repos/{o}/{r}/git/trees/{quote(ref, safe='/')}?recursive=1")
    files, skipped = plan(tree, dest)
    use_raw = site_allowed(RAW)
    calls = 0 if use_raw else len(files)
    remaining = h.get("x-ratelimit-remaining")
    new = [f for f in files if not os.path.exists(f[3])]
    exist = [f for f in files if os.path.exists(f[3])]
    out(f"\n{o}/{r} @ {ref}  ->  {root}")
    out(f"  {len(files)} text files, {sum(f[2] for f in files) / 1000:.1f} KB  ({len(new)} new, {len(exist)} already exist)")
    for reason, ps in skipped.items():
        out(f"  skipped {len(ps)} ({reason}): " + ", ".join(map(str, ps[:5])) + (" …" if len(ps) > 5 else ""))
    if use_raw:
        out("  Downloads from raw.githubusercontent.com (no API quota used).")
    else:
        out(f"  Downloads via the GitHub API: {calls} requests" + (f" (you have {remaining} left this hour)." if remaining else ".")
            + "\n  Tip: add https://raw.githubusercontent.com in Tools > Allowed sites to avoid the quota.")
        import builtins as _b
        if IN_PYODIDE and FETCH is None and hasattr(_b, "kp_request_site") and ask("  Ask the app to add raw.githubusercontent.com to Allowed sites? (applies after Python restarts at the end of this run) (y/N): ").strip().lower() in ("y", "yes"):
            if await _b.kp_request_site(RAW, "GitHub import: download files without using the API quota"):
                out("  Added. Python restarts when this run ends; import again after that to use it (this run keeps using the API).")
            else:
                out("  Not added.")
        if remaining and remaining.isdigit() and int(remaining) < calls:
            out("  ⚠️ Not enough quota for all files; the import will stop partway with a rate-limit message.")
    if not files:
        out("Nothing to import."); return 0
    a = ask("Import these files? [y/N] ").strip().lower()
    if a != "y":
        out("Cancelled. Nothing written."); return 0
    overwrite = False
    if exist:
        a = ask(f"{len(exist)} file(s) already exist. o=overwrite them, s=skip them, c=cancel [s]: ").strip().lower() or "s"
        if a == "c":
            out("Cancelled. Nothing written."); return 0
        overwrite = a == "o"
    todo = files if overwrite else new
    written, skipped_bin, names = 0, 0, []
    for i, f in enumerate(todo, 1):
        body = await download(o, r, ref, f, use_raw)
        if is_binary_data(body):
            skipped_bin += 1; continue
        full = safe_join(dest, f[0])  # re-check right before writing
        if os.path.exists(full) and not overwrite:
            continue
        atomic_write(full, body)
        written += 1; names.append(f[0])
        if i % 25 == 0:
            out(f"  … {i}/{len(todo)}")
    out(f"Done: wrote {written} file(s) to ~/{dest}" + (f", skipped {skipped_bin} binary" if skipped_bin else "") + ".")
    for n in names[:60]: out(f"  ~/{dest}/{n}")
    if len(names) > 60: out(f"  … and {len(names) - 60} more")
    if names: out("  They're in Files › 📂 Files in ~ (the .py ones can also be opened as scripts with Import).")
    return written


async def amain():
    print("GitHub import (public repos, no login). Example: octocat/Hello-World  or  owner/repo@branch")
    spec = input("Repo: ").strip()
    if not spec:
        return
    dest = input("Folder in ~ (Enter = repo name): ").strip() or None
    try:
        await import_repo(spec, dest)
    except (GHError, ValueError) as e:
        print("⛔", e)


def main():
    if IN_PYODIDE:
        return asyncio.ensure_future(amain())
    if "--test" in sys.argv:
        return self_test()
    asyncio.run(amain())


# ---------- self-tests (mocked fetches) ----------
async def _aself_test():
    import tempfile, shutil
    global BASE_DIR, FETCH
    ok = 0

    def t(c, m):
        nonlocal ok
        if not c:
            raise AssertionError(m)
        ok += 1
    for s in ["octocat", "a-b", "A1"]:
        t(valid_owner(s), s)
    for s in ["-a", "a-", "a--b", "a_b", "", "x" * 40, "a/b"]:
        t(not valid_owner(s), s)
    for s in ["Hello-World", "a.b_c", ".github"]:
        t(valid_repo(s), s)
    for s in ["..", ".", "a/b", "a b", "x.git", ""]:
        t(not valid_repo(s), s)
    for s in ["main", "feature/x", "v1.2.3", "a" * 40]:
        t(valid_ref(s), s)
    for s in ["../x", "a..b", "-x", "/a", "a/", "a//b", "a.lock", "a@{1}", "a b", "x/.y", ""]:
        t(not valid_ref(s), s)
    t(parse_repo("https://github.com/o/r/tree/dev/x") == ("o", "r", "dev/x"), "url tree")
    t(parse_repo("o/r.git") == ("o", "r", None), ".git")
    t(parse_repo("o/r@v1") == ("o", "r", "v1"), "@ref")
    for bad in ["http://github.com/o/r", "https://evil.com/o/r", "o", "o/r/x", "o/r@..", "../r"]:
        try:
            parse_repo(bad); t(False, "accepted " + bad)
        except GHError:
            ok += 1
    for bad in ["http://api.github.com/x", "https://evil.com/", "https://api.github.com.evil.com/", "https://u@api.github.com/",
                "https://codeload.github.com/x", "https://api.github.com:444/"]:
        try:
            check_url(bad); t(False, "url " + bad)
        except GHError:
            ok += 1
    t(raw_url("o", "r", "dev/x", "a b/#c.py") == RAW + "/o/r/dev/x/a%20b/%23c.py", "raw quoting")

    d = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    old = BASE_DIR
    BASE_DIR = os.path.realpath(d)
    try:
        for bad in ["../x", "/etc/passwd", "a/../../x", ".history/x", "a/.HISTORY/b", "a//b", "a\\b", "x\x00", "/".join(["d"] * 9), ""]:
            try:
                safe_join("r", bad); t(False, "path " + repr(bad))
            except ValueError:
                ok += 1
        os.makedirs(os.path.join(BASE_DIR, "r"))
        os.symlink(outside, os.path.join(BASE_DIR, "r", "lnk"))
        try:
            safe_join("r", "lnk/x.py"); t(False, "symlink dir")
        except ValueError:
            ok += 1
        t(safe_join("r", "a/b.py") == os.path.join(BASE_DIR, "r", "a", "b.py"), "good path")

        S = lambda c: ("%040x" % c)
        tree = {"truncated": False, "tree": [
            {"path": "README.md", "type": "blob", "mode": "100644", "sha": S(1), "size": 12},
            {"path": "src", "type": "tree", "mode": "040000", "sha": S(2)},
            {"path": "src/app.py", "type": "blob", "mode": "100644", "sha": S(3), "size": 20},
            {"path": "logo.png", "type": "blob", "mode": "100644", "sha": S(4), "size": 10},
            {"path": "big.txt", "type": "blob", "mode": "100644", "sha": S(5), "size": MAX_FILE + 1},
            {"path": "lib", "type": "commit", "mode": "160000", "sha": S(6)},
            {"path": "ln", "type": "blob", "mode": "120000", "sha": S(7), "size": 5},
            {"path": "../evil.py", "type": "blob", "mode": "100644", "sha": S(8), "size": 3},
            {"path": ".history/x", "type": "blob", "mode": "100644", "sha": S(9), "size": 3},
            {"path": "bin.dat", "type": "blob", "mode": "100644", "sha": S(10), "size": 4},
        ]}
        blobs = {"README.md": b"hello world\n", "src/app.py": b"print('hi')\n", "bin.dat": b"\x00\x01\x02\x03"}
        for _e in tree["tree"]:
            if _e["path"] in blobs: _e["sha"] = git_blob_sha(blobs[_e["path"]])
        t(git_blob_sha(b"hello world\n") == "3b18e512dba79e4c8300dd08aeb37f8e728b8dad", "git blob sha")
        t(reserved_name("json") and reserved_name("kp_common") and reserved_name("r6_drop_merge") and not reserved_name("Spoon-Knife"), "reserved names")
        calls = []

        async def mock(url):
            calls.append(url)
            if url == f"{API}/repos/o/r":
                return 200, {}, json.dumps({"default_branch": "main"}).encode()
            if url.startswith(f"{API}/repos/o/r/git/trees/main"):
                return 200, {"x-ratelimit-remaining": "55"}, json.dumps(tree).encode()
            if url.startswith(f"{API}/repos/o/limited/"):
                return 403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1900000000"}, b'{"message":"API rate limit exceeded"}'
            if url.startswith(f"{API}/repos/o/r/git/blobs/"):
                sha = url.rsplit("/", 1)[1]
                p = next(e["path"] for e in tree["tree"] if e["sha"] == sha)
                return 200, {}, json.dumps({"encoding": "base64", "content": base64.b64encode(blobs[p]).decode()}).encode()
            if url.startswith(RAW + "/o/r/main/"):
                return 200, {}, blobs[url[len(RAW + "/o/r/main/"):]]
            return 404, {}, b"{}"
        FETCH = mock
        files, sk = plan(tree, "r")
        t([f[0] for f in files] == ["README.md", "src/app.py", "bin.dat"], "plan files")
        for k in ("submodule", "symlink", "binary"):
            t(k in sk, "skip " + k)
        t(len(sk["unsafe or too deep path"]) == 2, "unsafe skipped")
        many = {"tree": [{"path": f"f{i}.py", "type": "blob", "mode": "100644", "sha": S(i), "size": 100_000} for i in range(400)]}
        f2, sk2 = plan(many, "r")
        t(len(f2) == 50 and any("MB total" in k for k in sk2), "total cap")
        many = {"tree": [{"path": f"f{i}.py", "type": "blob", "mode": "100644", "sha": S(i), "size": 1} for i in range(400)]}
        t(len(plan(many, "r")[0]) == MAX_FILES, "count cap")

        logs = []
        t((await import_repo("o/r", ask=lambda p: "n", out=logs.append)) == 0, "decline")
        t(not os.path.exists(os.path.join(BASE_DIR, "r", "README.md")), "nothing written on decline")
        n = (await import_repo("o/r", ask=lambda p: "y", out=logs.append))
        t(n == 2, f"wrote 2, got {n}")
        t(open(os.path.join(BASE_DIR, "r", "src", "app.py"), "rb").read() == b"print('hi')\n", "content")
        t(not os.path.exists(os.path.join(BASE_DIR, "r", "bin.dat")), "binary data skipped")
        t(IN_PYODIDE or any("raw.githubusercontent.com" in c for c in calls), "raw used under python3")
        with open(os.path.join(BASE_DIR, "r", "README.md"), "w") as fh:
            fh.write("mine")
        (await import_repo("o/r", ask=lambda p: "y" if "Import" in p else "s", out=logs.append))
        t(open(os.path.join(BASE_DIR, "r", "README.md")).read() == "mine", "skip existing")
        (await import_repo("o/r", ask=lambda p: "y" if "Import" in p else "o", out=logs.append))
        t(open(os.path.join(BASE_DIR, "r", "README.md")).read() == "hello world\n", "overwrite")
        # blobs API fallback (raw not in Allowed sites)
        global site_allowed
        real_sa = site_allowed
        site_allowed = lambda origin: origin == API
        try:
            calls.clear()
            (await import_repo("o/r", dest="r2", ask=lambda p: "y", out=logs.append))
            t(all(c.startswith(API) for c in calls) and os.path.exists(os.path.join(BASE_DIR, "r2", "src", "app.py")), "blob fallback")
            try:
                (await get(raw_url("o", "r", "main", "README.md"))); t(False, "raw not blocked")
            except GHError as e:
                t("Allowed sites" in str(e), "blocked msg")
        finally:
            site_allowed = real_sa
        try:
            (await import_repo("o/limited@main", ask=lambda p: "y", out=logs.append)); t(False, "rate limit")
        except GHError as e:
            t("rate limit" in str(e), "rate msg")
        try:
            (await import_repo("o/nope@main", ask=lambda p: "y", out=logs.append)); t(False, "404")
        except GHError as e:
            t("Not found" in str(e), "404 msg")
        try:
            (await import_repo("o/r", dest=".history", ask=lambda p: "y", out=logs.append)); t(False, "dest .history")
        except GHError:
            ok += 1
        t(is_binary_data(b"\xff\xfe\x00") and not is_binary_data("héllo".encode()), "binary detect")
    finally:
        BASE_DIR = old
        FETCH = None
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)
    print(f"All {ok} self-tests passed.")
    return True



# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---

def self_test():
    """Sync entry; inside the app (event loop already running) it returns the coroutine for the runner to await."""
    c = _aself_test()
    try:
        asyncio.get_running_loop()
        return c
    except RuntimeError:
        return asyncio.run(c)


try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()

