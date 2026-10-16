# KPython v4 worker helpers: user modules, REPL, docs. All files stay under /home/pyodide.
import sys, os, json, re, code, importlib, pydoc, io
HOME = '/home/pyodide'
os.chdir(HOME)
if HOME not in sys.path: sys.path.insert(0, HOME)
if HOME + '/kptools' not in sys.path: sys.path.append(HOME + '/kptools')
_kp_user_mods = set()
def _kp_modname(n):
    m = re.sub(r'\W+', '_', n.strip().lower().removesuffix('.py')).strip('_') or 'script'
    return ('_' + m) if m[0].isdigit() else m
def _kp_write_modules(files_json):
    """Write every saved script to /home/pyodide/<module>.py so `import other_script` works."""
    files = json.loads(files_json)
    for m in list(_kp_user_mods):
        sys.modules.pop(m, None)
    for name, src in files.items():
        m = _kp_modname(name)
        with open(os.path.join(HOME, m + '.py'), 'w') as f: f.write(src)
        _kp_user_mods.add(m)
    importlib.invalidate_caches()
_kp_repl_ns = {'__name__': '__console__', '__builtins__': __builtins__}
_kp_console = code.InteractiveConsole(_kp_repl_ns, filename='<console>')
def _kp_repl_push(line):
    return bool(_kp_console.push(line))
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
    sys.path.insert(0, HOME + '/kptools') if HOME + '/kptools' not in sys.path else None
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
async def _kp_run_code(code, ns, filename):
    from pyodide.code import eval_code_async
    builtins.kp_safe_path = _KP_SAFE_PATH   # v9: frozen shared path check
    builtins.input = _kp_input3
    try:
        return await eval_code_async(code, globals=ns, filename=filename)
    except KeyboardInterrupt as e:
        raise KPStopped("KeyboardInterrupt: " + str(e)) from None

# v9: remove a stray symlink left in ~ by the v8 log-analyzer self-test
try:
    _p = os.path.join(HOME, 'link.log')
    if os.path.islink(_p): os.remove(_p)
    import glob as _g, shutil as _sh
    for _d in _g.glob(os.path.join(HOME, 'tmp*')):
        if os.path.isdir(_d) and not os.path.islink(_d) and os.path.exists(os.path.join(_d, 'a.log')): _sh.rmtree(_d, ignore_errors=True)
except Exception:
    pass
