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
    full = os.path.realpath(os.path.join(base, str(p).strip()))
    if full != base and not full.startswith(base + '/'):
        raise ValueError(f"refused: {p} is outside {base}")
    return full
builtins.kp_safe_path = safe_path

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
    exe, hits = m.cover(src, 'pass' if 'TestCase' in src else ''); print('\n'.join(m.report(src, exe, hits)))
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
