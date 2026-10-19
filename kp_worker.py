# KPython v4 worker helpers: user modules, REPL, docs. All files stay under /home/pyodide.
import sys, os, json, re, code, importlib, pydoc, io
HOME = '/home/pyodide'
os.chdir(HOME)
KPTOOLS = '/kptools'  # v9.1: in-memory, hash-checked copies (re-written from the verified texts before every run)
# v11 (Drop #1): the stdlib and installed packages come BEFORE ~, so a file saved in ~ (json.py, json/, random.py…)
# can't shadow them; tool names are served only from /kptools by the finder below.
sys.path[:] = [p for p in sys.path if p not in ('', HOME, KPTOOLS)] + [HOME, KPTOOLS]
_KP_TOOL_NAMES = set()
class _KPToolFinder:
    """v11 (Drop #1): KPython tool modules (and any kp_* name) load ONLY from the verified /kptools copies."""
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        top = fullname.split('.')[0]
        if top in _KP_TOOL_NAMES or (top.startswith('kp_') and not top.startswith('kp_st_')):
            if '.' in fullname: raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
            f = os.path.join(KPTOOLS, top + '.py')
            if top in _KP_TOOL_NAMES and os.path.isfile(f):
                import importlib.util as _iu
                return _iu.spec_from_file_location(fullname, f)
            raise ModuleNotFoundError(f"No module named {fullname!r} (KPython tool names load only from the verified tools)", name=fullname)
        return None
    @classmethod
    def invalidate_caches(cls): pass
sys.meta_path.insert(0, _KPToolFinder)
def _kp_set_tools(names_json):
    _KP_TOOL_NAMES.clear(); _KP_TOOL_NAMES.update(n[:-3] for n in json.loads(names_json) if n.endswith('.py'))
builtins_ = __import__('builtins'); builtins_.kp_tool_names = lambda: sorted(_KP_TOOL_NAMES)
def _kp_reserved(m):
    """v11 (Drop #2): names a saved script may not take in ~ (stdlib, packages, KPython tools, kp_*)."""
    return (m in getattr(sys, 'stdlib_module_names', ()) or m in _KP_TOOL_NAMES or m.startswith(('kp_', '_kp'))
            or bool(re.match(r'r\d+_', m)) or m in ('pyodide', 'micropip', 'js', 'pyodide_js', 'numpy', 'pandas', 'matplotlib'))
try:
    import shutil as _sh0; _sh0.rmtree(HOME + '/kptools', ignore_errors=True)  # drop the old, Python-writable copy
except Exception: pass
_kp_user_mods = set()
def _kp_modname(n):
    m = re.sub(r'\W+', '_', n.strip().lower().removesuffix('.py')).strip('_') or 'script'
    return ('_' + m) if m[0].isdigit() else m
def _kp_write_modules(files_json):
    """Write every saved script to /home/pyodide/<module>.py so `import other_script` works."""
    files = json.loads(files_json)
    for m in list(_kp_user_mods):
        sys.modules.pop(m, None)
    _kp_user_mods.clear()
    for name, src in files.items():
        m = _kp_modname(name)
        if _kp_reserved(m): continue   # v11: never write ~/json.py, ~/kp_common.py, ~/r6_drop_merge.py …
        p = os.path.join(HOME, m + '.py')
        if os.path.islink(p): continue
        with open(p, 'w') as f: f.write(src)
        _kp_user_mods.add(m)
    importlib.invalidate_caches()
builtins_.kp_saved_mirrors = lambda: [os.path.join(HOME, m + '.py') for m in sorted(_kp_user_mods)]
_kp_repl_ns = {'__name__': '__console__', '__builtins__': __builtins__}
_kp_console = code.InteractiveConsole(_kp_repl_ns, filename='<console>')
_kp_repl_before = set()
def _kp_repl_push(line, job=0):
    global _kp_repl_before
    try: _kp_reassert()   # v10: the REPL path re-asserts the shared path check too
    except NameError: pass
    import asyncio
    try: _kp_repl_before = set(asyncio.all_tasks())
    except RuntimeError: _kp_repl_before = set()
    tok = _KP_JOB.set(int(job))   # v11 (Get back M1): bridge calls made by this line carry its job token
    try: return bool(_kp_console.push(line))
    finally: _KP_JOB.reset(tok)
async def _kp_repl_after():
    """v11 (Get back M1): tasks a console line started are cancelled too. Returns how many refused to stop."""
    return await _kp_cancel_left(_kp_repl_before)
def _kp_repl_reset():
    global _kp_console
    _kp_repl_ns.clear(); _kp_repl_ns.update({'__name__': '__console__', '__builtins__': __builtins__})
    _kp_console = code.InteractiveConsole(_kp_repl_ns, filename='<console>')
pydoc.pager = lambda text: print(pydoc.plain(text))
import builtins
def _kp_help(obj=None):
    if obj is None: print("Type help(obj), e.g. help(str.split) or help('json.dumps')"); return
    print(_kp_doc(obj) if isinstance(obj, str) else pydoc.plain(pydoc.render_doc(obj, title='%s')))
builtins.help = _kp_help
def _kp_doc(name):
    name = name.strip()
    if not name: return ''
    try:
        obj = pydoc.locate(name, forceload=False)
        if obj is None and name in _kp_repl_ns: obj = _kp_repl_ns[name]
        if obj is None:
            import builtins as b; obj = getattr(b, name, None)
        if obj is None: return f"No Python documentation found for {name!r}. Try a full path like json.dumps or os.path.join."
        return pydoc.plain(pydoc.render_doc(obj, title='%s'))[:60000]
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
def _kp_names():
    import keyword
    return json.dumps(sorted(set(keyword.kwlist + dir(builtins))))
# Dev tab glue: one-tap tools load the team's (security-patched) modules from /home/pyodide/kptools
def _kp_tool(mod):
    sys.path.insert(0, KPTOOLS) if KPTOOLS not in sys.path else None
    return importlib.import_module(mod)
def _kp_lint(src):
    _kp_tool('r2_eight_lint').report(src)
def _kp_tests(src, name):
    _kp_tool('r2_dyno_tests').run(src, _kp_modname(name))
def _kp_outline(src):
    m = _kp_tool('r2_bot2_outline')
    print("\n".join(m.outline(src)) or "(no classes or functions)")
    print("\n-- complexity --")
    for ln, n, s, r in m.complexity(src): print(f"L{ln}: {n}  {s} ({r})")
def _kp_rename(src, old, new):
    m = _kp_tool('r2_bot2_outline'); out, n = m.rename(src, old, new); print(f"Renamed {n} occurrence(s) of {old} -> {new}."); return out
def _kp_diff(a, b, na, nb, side):
    m = _kp_tool('r2_drop_diff')
    r = m.side_by_side(a, b) if side else m.unified(a, b, na, nb)
    print(r or "(no differences)")
def _kp_profile(src):
    m = _kp_tool('r2_bot3_profile'); print(m.profile_code(src))
# Never echo secrets typed into input() (e.g. an Authorization header in the HTTP tester)
_KP_SECRET = re.compile(r'^\s*(authorization|proxy-authorization|cookie|x-api-key|api-key|[\w-]*(token|secret|password)[\w-]*)\s*:', re.I)
def _kp_input2(prompt=''):
    sys.stdout.flush()
    if prompt: print(prompt, end='')
    sys.stdout.flush()
    v = js.prompt(str(prompt) or 'input()')
    if v is None:
        print(); raise KeyboardInterrupt('input cancelled')
    v = str(v)
    print(v.split(':', 1)[0] + ': ****(hidden)' if _KP_SECRET.match(v) else v)
    return v
import js
builtins.input = _kp_input2

def safe_path(p, base=HOME):
    """Shared KPython rule: resolve p and refuse anything outside /home/pyodide."""
    raw = os.path.normpath(os.path.join(base, str(p).strip()))
    full = os.path.realpath(raw)
    if full != base and not full.startswith(base + '/'):
        raise ValueError(f"refused: {p} is outside {base}")
    # v9 (Drop r7): refuse symlinks anywhere on the way, even ones that point inside ~
    cur = base
    for part in os.path.relpath(raw, base).split(os.sep) if raw != base else []:
        if part in ('', '.'): continue
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise ValueError(f"refused: {p} goes through a symlink")
    return full
builtins.kp_safe_path = safe_path
_KP_SAFE_PATH = safe_path   # private copy; re-asserted before every run so a script can't swap it for later tools

# ---- v5: round-3 team tools (security-patched copies in /home/pyodide/kptools) ----
_KP_TOKEN = re.compile(r"(eyJ[\w-]+\.[\w-]+\.[\w-]*|gh[pousr]_\w{20,}|github_pat_\w{20,}|sk-[\w-]{16,}|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,})")
_kp_prev_input = builtins.input
def _kp_input3(prompt=''):
    sys.stdout.flush()
    if prompt: print(prompt, end='')
    sys.stdout.flush()
    v = js.prompt(str(prompt) or 'input()')
    if v is None:
        print(); raise KeyboardInterrupt('input cancelled')
    v = str(v)
    if _KP_SECRET.match(v): shown = v.split(':', 1)[0] + ': ****(hidden)'
    else: shown = _KP_TOKEN.sub(lambda m: m.group(0)[:4] + '****(hidden)', v)
    print(shown)
    return v
builtins.input = _kp_input3
def _kp_format(src):
    return _kp_tool('r3_eight_format').format_code(src)
def _kp_debug(src):
    m = _kp_tool('r3_bot3_debugger')
    print("Step debugger (bot3). This RUNS your code. Commands: s step, n next, c continue, b N breakpoint, p locals, p EXPR, q quit, h help")
    m.Debugger(src).run()
def _kp_metrics(src):
    m = _kp_tool('r3_bot2help_metrics'); print(m.format_report(m.analyze(src)))
def _kp_types(src):
    _kp_tool('r3_bot_typecheck').report(src)
def _kp_snapshot(name, src, msg):
    m = _kp_tool('r3_drop_history'); rel = _kp_modname(name) + '.py'
    with open(safe_path(rel), 'w') as f: f.write(src)
    m.save_version(rel, msg or 'snapshot from KPython')
    m.list_versions(rel)

# ---- v6: History versions in backups (/home/pyodide/.history) ----
_KP_HIST = os.path.join(HOME, '.history')
def _kp_hist_dump():
    out = {}
    if os.path.isdir(_KP_HIST):
        for r, _, fs in os.walk(_KP_HIST):
            for f in fs:
                p = os.path.join(r, f)
                if os.path.getsize(p) <= 1_000_000:
                    with open(p, encoding='utf-8', errors='replace') as fh: out[os.path.relpath(p, _KP_HIST)] = fh.read()
    return json.dumps(out)
def _kp_hist_load(data_json):
    data = json.loads(data_json); n = 0
    if not isinstance(data, dict): return 0
    for rel, txt in list(data.items())[:5000]:
        if not isinstance(rel, str) or not isinstance(txt, str) or len(txt) > 1_000_000: continue
        full = os.path.realpath(os.path.join(_KP_HIST, rel))
        if not full.startswith(_KP_HIST + '/'): continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as fh: fh.write(txt)
        n += 1
    return n

# ---- v6: round-4 team tools ----
def _kp_cover(src):
    m = _kp_tool('r4_dyno_coverage'); print("Coverage (Dyno). This runs your code and its unittest tests.")
    import re as _re
    tests = 'pass' if 'TestCase' in src else ''
    if _re.search(r'^def test_\w*\(\s*\)', src, _re.M):  # pytest-style: also run plain test_ functions
        tests += ("\n_kp_r = [0, 0]\nfor _kp_n, _kp_f in list(globals().items()):\n"
                  "    if _kp_n.startswith('test_') and callable(_kp_f) and not isinstance(_kp_f, type):\n"
                  "        try:\n            _kp_f(); _kp_r[0] += 1\n"
                  "        except Exception as _kp_e:\n            _kp_r[1] += 1; print(f'FAIL {_kp_n}: {type(_kp_e).__name__}: {_kp_e}')\n"
                  "print(f'pytest-style tests: {_kp_r[0]} passed, {_kp_r[1]} failed')\n")
    exe, hits = m.cover(src, tests); print('\n'.join(m.report(src, exe, hits)))
def _kp_memory(src):
    m = _kp_tool('r4_bot3_memory')
    if m.tracemalloc is None: return
    print("Memory profile (bot3). This runs your code."); m.report(m.profile_source(src))
def _kp_docgen(src):
    new, n = _kp_tool('r4_bot_docgen').generate(src); return new
def _kp_secrets(files_json):
    m = _kp_tool('r4_getback_secrets'); files = json.loads(files_json); found = []
    for name, text in files.items():
        for ln, kind, sev, masked, fix in m.scan_text(text):
            found.append((name, ln, kind, sev, masked, fix))
    found.sort(key=lambda x: (m.SEV_ORDER[x[3]], x[0], x[1]))
    print(f"Secret scan (Get back) of {len(files)} saved script(s). Values are masked.")
    m.report(found, [])
def _kp_markdown(text):
    return _kp_tool('r4_eight_markdown').to_html(text)
def _kp_imports():
    m = _kp_tool('r4_bot2help_imports')
    import tempfile, shutil
    print("Import map of your saved scripts (bot2help).")
    import shutil
    d = os.path.join(HOME, '.kp_imap'); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for mod in sorted(_kp_user_mods):
        src = os.path.join(HOME, mod + '.py')
        if os.path.exists(src): shutil.copy(src, os.path.join(d, mod + '.py'))
    print(m.report(m.build_map(d)))
# Drop's package manager reads/writes the app's reinstall list through these hooks
def kp_pkgs_get(): return list(json.loads(js.kpPkgsGet()))
def kp_pkgs_set(lst): js.kpPkgsSet(json.dumps(list(lst)))
builtins.kp_pkgs_get, builtins.kp_pkgs_set = kp_pkgs_get, kp_pkgs_set


# ---- v7: friendly error when Allowed sites blocks a request ----
class KPBlockedError(ConnectionError):
    """Raised when a request is blocked by Tools > Allowed sites."""
builtins.KPBlockedError = KPBlockedError
_KP_DEFAULT_SITES = ['https://api.github.com', 'https://cdn.jsdelivr.net', 'https://pypi.org', 'https://files.pythonhosted.org']
def _kp_site_allowed(url):
    from urllib.parse import urlsplit
    import js, json
    u = urlsplit(str(url))
    if not u.scheme or not u.netloc:   # relative URL -> same origin
        return True, ''
    origin = f'{u.scheme}://{u.netloc}'.lower()
    if origin == str(js.location.origin).lower():
        return True, origin
    for s in _KP_DEFAULT_SITES + json.loads(js.kpSitesGet()):
        s = s.lower().rstrip('/')
        if s == origin:
            return True, origin
        if '*.' in s:
            pre, dom = s.split('*.', 1)
            if origin.startswith(pre) and origin[len(pre):].endswith('.' + dom):
                return True, origin
    return False, origin
def _kp_blocked(url, err):
    ok, origin = _kp_site_allowed(url)
    if ok:
        return err
    e = KPBlockedError(f"Blocked: {origin} isn't in Allowed sites. Add it in Tools > Allowed sites.")
    e.__cause__ = None
    return e
try:
    import pyodide.http as _ph
    _kp_open_url0, _kp_pyfetch0 = _ph.open_url, _ph.pyfetch
    def _kp_open_url(url, *a, **k):
        try:
            return _kp_open_url0(url, *a, **k)
        except Exception as err:
            raise _kp_blocked(url, err) from None
    async def _kp_pyfetch(url, *a, **k):
        try:
            return await _kp_pyfetch0(url, *a, **k)
        except Exception as err:
            raise _kp_blocked(url, err) from None
    _kp_open_url.__doc__, _kp_pyfetch.__doc__ = _kp_open_url0.__doc__, _kp_pyfetch0.__doc__
    _ph.open_url, _ph.pyfetch = _kp_open_url, _kp_pyfetch
except Exception:
    pass


# ---- v8: Stop / cancelled input() end the run cleanly ----
# Pyodide's event loop re-raises KeyboardInterrupt (a BaseException) out of the task, which showed up as an
# "Uncaught (in promise)" error in the console. Converting it here keeps the same message for the app.
class KPStopped(Exception):
    pass
import contextvars as _cv
_KP_JOB = _cv.ContextVar('kp_job', default=0)
def _kp_job_tok():
    """v11 (Get back M1): the job id of the run/console line whose code is executing right now (0 = none, e.g. a JS timer)."""
    return _KP_JOB.get()
async def _kp_cancel_left(before):
    import asyncio
    cur = asyncio.current_task()
    left = [t for t in asyncio.all_tasks() if t not in before and t is not cur and not t.done()]
    for t in left: t.cancel()
    for _ in range(3):
        if not any(not t.done() for t in left): break
        await asyncio.sleep(0)
    stuck = sum(1 for t in left if not t.done())
    if left: print(f"(stopped {len(left) - stuck} background task(s) this run left running)")
    return stuck
_KP_SYS_PATH0 = list(sys.path)
_KP_META0 = list(sys.meta_path)
def _kp_restore_import_state():
    """v11 (Drop #6): sys.path / sys.meta_path changes made by a run don't carry into later runs and tools."""
    sys.path[:] = _KP_SYS_PATH0 + [p for p in sys.path if p not in _KP_SYS_PATH0 and p.startswith('/lib/')]
    keep = [f for f in sys.meta_path if f not in _KP_META0 and type(f).__module__.split('.')[0] in ('pyodide', '_pyodide', 'micropip', 'importlib', '_frozen_importlib', '_frozen_importlib_external', 'setuptools', '_distutils_hack')]
    sys.meta_path[:] = [_KPToolFinder] + [f for f in _KP_META0 if f is not _KPToolFinder] + keep
def _kp_purge_tools():
    """v11 (Drop #4): tool modules are re-imported from the freshly re-written /kptools for every run."""
    for n in list(sys.modules):
        top = n.split('.')[0]
        if top in _KP_TOOL_NAMES or top.startswith('kp_st_'): sys.modules.pop(n, None)
def _kp_make_runner(_sp=safe_path, _inp=_kp_input3):
    # v10 (Get back L1): the private copies live in this closure, not in a __main__ global a script could reassign.
    # Note: kp_safe_path is a guard against mistakes, not a sandbox; code in the same interpreter can always get around it.
    import asyncio, posixpath, genericpath, shutil
    _code0, _real0, _islink0, _norm0 = _sp.__code__, posixpath.realpath, posixpath.islink, posixpath.normpath
    def reassert():
        # v11 (Drop #5): put back the path check AND the os.path functions it relies on if a script swapped them
        bad = []
        if _sp.__code__ is not _code0: _sp.__code__ = _code0; bad.append('kp_safe_path code')
        for mod in (posixpath, os.path):
            if mod.realpath is not _real0: mod.realpath = _real0; bad.append('os.path.realpath')
            if mod.islink is not _islink0: mod.islink = _islink0; bad.append('os.path.islink')
            if mod.normpath is not _norm0: mod.normpath = _norm0; bad.append('os.path.normpath')
        builtins.kp_safe_path = _sp
        if bad: print("⚠️ KPython restored " + ", ".join(sorted(set(bad))) + " (changed by an earlier run).")
    async def _kp_run_code(code, ns, filename, job=0):
        from pyodide.code import eval_code_async
        global _kp_left
        reassert(); _kp_purge_tools(); _kp_restore_import_state()
        builtins.input = _inp
        _kp_nav_input.n = 0          # v11 (Get back L6): every run starts with a fresh Cancel counter
        before = set(asyncio.all_tasks())
        tok = _KP_JOB.set(int(job))
        try:
            return await eval_code_async(code, globals=ns, filename=filename)
        except KeyboardInterrupt as e:
            raise KPStopped("KeyboardInterrupt: " + str(e)) from None
        finally:
            # v10/v11 (Get back M1/M2): background tasks a run left behind are cancelled; any that refuse make the app restart Python
            _KP_JOB.reset(tok)
            _kp_left = await _kp_cancel_left(before)
            _kp_restore_import_state()
            try:   # v11 (Drop #8): temp files don't pile up in the persistent ~/.kp_tmp
                for e in os.scandir(_TMP):
                    (shutil.rmtree(e.path, ignore_errors=True) if e.is_dir(follow_symlinks=False) else os.remove(e.path))
            except Exception: pass
    return _kp_run_code, reassert
_kp_left = 0
def _kp_take_left():
    global _kp_left
    n, _kp_left = _kp_left, 0
    return n
_kp_run_code, _kp_reassert = _kp_make_runner()
del _KP_SAFE_PATH

# v9: remove a stray symlink left in ~ by the v8 log-analyzer self-test
try:
    _p = os.path.join(HOME, 'link.log')
    if os.path.islink(_p): os.remove(_p)
    import glob as _g, shutil as _sh
    for _d in _g.glob(os.path.join(HOME, 'tmp*')):   # v11 (Drop #7): only tempfile-style names holding the old self-test's files
        if (re.fullmatch(r'tmp[a-z0-9_]{8}', os.path.basename(_d)) and os.path.isdir(_d) and not os.path.islink(_d)
                and os.path.exists(os.path.join(_d, 'a.log')) and set(os.listdir(_d)) <= {'a.log', 'b.log', 'link.log', 'sub'}):
            _sh.rmtree(_d, ignore_errors=True)
except Exception:
    pass

# v10: Cancel = back one level in Dev tools. A cancelled input() raises KPBack, which is BOTH an Exception and a
# KeyboardInterrupt, so the nearest handler in the tool (its menu loop's `except Exception`, or a local Cancel handler)
# takes it and the tool goes back one level. Two Cancels in a row with no answer in between end the tool.
class KPBack(KeyboardInterrupt):
    # v11 (Get back L6): a BaseException now, so a tool's `except Exception:` can't swallow it (no more "Error: ↩ cancelled").
    # The Dev-tab wrapper catches it and goes back to the tool's start menu; a second Cancel in a row ends the tool.
    def __str__(self): return "↩ cancelled, back to the menu"
builtins.KPBack = KPBack
def _kp_nav_input(prompt=""):
    try:
        v = _kp_nav_input.inner(prompt)
    except KeyboardInterrupt as e:
        if isinstance(e, KPBack) or "input cancelled" not in str(e): raise
        _kp_nav_input.n += 1
        if _kp_nav_input.n >= 2:
            _kp_nav_input.n = 0; raise KeyboardInterrupt("input cancelled")
        raise KPBack()
    _kp_nav_input.n = 0
    return v
_kp_nav_input.n = 0

# v10: temp files go under ~ (cleaned at start) so tools' temp folders pass the shared path check
try:
    import tempfile as _tf, shutil as _sh2
    _TMP = os.path.join(HOME, '.kp_tmp'); _sh2.rmtree(_TMP, ignore_errors=True); os.makedirs(_TMP, exist_ok=True)
    _tf.tempdir = _TMP
except Exception:
    pass

async def kp_request_site(origin, why=""):
    """v10: ASK the app to add a site to Allowed sites. Keivon confirms in the app (same rules as Tools > Allowed sites).
    Returns True if added; it applies after Python restarts (the app does that when the run ends)."""
    return bool(await js.kpSiteAsk(str(origin)[:200], str(why)[:120]))
builtins.kp_request_site = kp_request_site

def kp_editor_insert(text):
    """v11: ASK the app to insert text at the editor cursor. The app shows the text and Keivon confirms.
    Only works while a run is in progress; capped at 20,000 characters and 5 requests per run. Returns True if inserted."""
    text = str(text)
    if len(text) > 20000: raise ValueError("kp_editor_insert: text is over 20,000 characters")
    return bool(js.kpEditorInsert(text))
builtins.kp_editor_insert = kp_editor_insert

# ---- v11: files in ~ (Files tab list + backups) ----
_KP_HOME_SKIP_DIRS = {'.history', '.kp_tmp', '.kp_imap', '__pycache__', '.cache', '.local', '.config'}
_KP_TEXT_EXT = ('.py', '.txt', '.md', '.json', '.csv', '.tsv', '.toml', '.ini', '.cfg', '.yaml', '.yml', '.html', '.css', '.js', '.sql', '.log', '.xml', '.rst')
def _kp_home_walk():
    mir = set(builtins.kp_saved_mirrors())
    for r, ds, fs in os.walk(HOME):
        ds[:] = sorted(d for d in ds if d not in _KP_HOME_SKIP_DIRS and not os.path.islink(os.path.join(r, d)))
        for f in sorted(fs):
            p = os.path.join(r, f)
            if os.path.islink(p) or p in mir or not os.path.isfile(p): continue
            yield p, os.path.relpath(p, HOME)
def _kp_home_list():
    out = []
    for p, rel in _kp_home_walk():
        out.append({'p': rel, 'n': os.path.getsize(p), 't': rel.lower().endswith(_KP_TEXT_EXT)})
        if len(out) >= 2000: break
    return json.dumps(out)
def _kp_home_read(rel):
    p = safe_path(str(rel))
    if os.path.islink(p) or not os.path.isfile(p): return json.dumps({'err': 'not a file'})
    if os.path.getsize(p) > 2_000_000: return json.dumps({'err': 'over 2 MB'})
    import base64
    data = open(p, 'rb').read()
    try: return json.dumps({'t': data.decode('utf-8')})
    except UnicodeDecodeError: return json.dumps({'b': base64.b64encode(data).decode()})
def _kp_home_dump(limit=6_000_000):
    """Backup of the files Python tools keep in ~ (projects, SQLite databases, .tasks.json, job_apps.json …).
    Skips: saved-script copies (already in the backup), .history (backed up separately), temp/cache folders, files over 2 MB,
    and anything past 6 MB in total. Returns {"files": {...}, "skipped": [...]}."""
    import base64
    files, skipped, total = {}, [], 0
    for p, rel in _kp_home_walk():
        n = os.path.getsize(p)
        if n > 2_000_000 or total + n > limit: skipped.append(f"{rel} ({n // 1000} KB)"); continue
        data = open(p, 'rb').read(); total += n
        try: files[rel] = {'t': data.decode('utf-8')}
        except UnicodeDecodeError: files[rel] = {'b': base64.b64encode(data).decode()}
    return json.dumps({'files': files, 'skipped': skipped})
def _kp_home_load(data_json):
    import base64
    d = json.loads(data_json); n = 0; bad = []
    if not isinstance(d, dict): return json.dumps({'n': 0, 'bad': ['not a dict']})
    for rel, v in list(d.items())[:5000]:
        try:
            if not isinstance(rel, str) or not isinstance(v, dict): raise ValueError('bad entry')
            parts = rel.split('/')
            if any(x in ('', '.', '..') for x in parts) or parts[0] in _KP_HOME_SKIP_DIRS: raise ValueError('refused path')
            if len(parts) == 1 and rel.endswith('.py') and _kp_reserved(rel[:-3]): raise ValueError('reserved name')
            if len(parts) > 1 and _kp_reserved(parts[0].lower()): raise ValueError('reserved folder name')
            data = v['t'].encode('utf-8') if isinstance(v.get('t'), str) else base64.b64decode(v.get('b', ''), validate=True)
            if len(data) > 2_000_000: raise ValueError('too big')
            full = safe_path(rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if os.path.islink(full): raise ValueError('symlink')
            tmp = full + '.kpbak'
            if os.path.lexists(tmp): os.remove(tmp)
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, 'wb') as f: f.write(data)
            os.replace(tmp, full); n += 1
        except Exception as e:
            bad.append(f"{str(rel)[:60]}: {e}")
    return json.dumps({'n': n, 'bad': bad[:20]})
