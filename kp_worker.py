# KPython v4 worker helpers: user modules, REPL, docs. All files stay under /home/pyodide.
import sys, os, json, re, code, importlib, pydoc, io
HOME = '/home/pyodide'
os.chdir(HOME)
if HOME not in sys.path: sys.path.insert(0, HOME)
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
