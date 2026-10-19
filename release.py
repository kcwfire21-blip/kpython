#!/usr/bin/env python3
"""KPython release step (v9.1, Get back H1/M3): writes the sha384 manifest of every app file into sw.js and
derives the cache name from it, so ANY change to an app file changes sw.js (and phones get the update bar).
Run before every commit:  python3 release.py   (check-only: python3 release.py --check)"""
import base64, hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sw = open(os.path.join(ROOT, 'sw.js')).read()
base = re.search(r"const BASEV='([^']+)'", sw).group(1)
shell = re.search(r"const SHELL=\[(.*?)\];", sw, re.S).group(1)
files = re.findall(r"'\./([^']+)'", shell)
# v11 (Get back L4): tool names come straight from the SHELL tools array (r10_*, r11_* … included)
arr = re.search(r"\.\.\.\[(.*?)\]\.map\(n=>'\./tools/'\+n\+'\.py'\)", shell, re.S)
tools = re.findall(r"'([A-Za-z_]\w*)'", arr.group(1)) if arr else []
if not tools: sys.exit('release.py: could not read the tools list from SHELL in sw.js')
files += ['tools/' + t + '.py' for t in tools]
missing = [f for f in files if f not in ('', 'sw.js') and not f.endswith('/') and not os.path.isfile(os.path.join(ROOT, f))]
if missing: sys.exit('release.py: SHELL lists files that do not exist: ' + ', '.join(missing))
appjs = open(os.path.join(ROOT, 'app.js')).read()
m = re.search(r"const TOOLS=\[(.*?)\];", appjs, re.S)
page = {x[:-3] for x in re.findall(r"'([\w]+\.py)'", m.group(1))} if m else set()
if page != set(tools):
    sys.exit('release.py: TOOLS in app.js and the SHELL tools in sw.js differ: ' + ', '.join(sorted(page ^ set(tools))))
H = {}
for f in files:
    if f in ('', 'sw.js') or f.endswith('/'): continue
    H[f] = base64.b64encode(hashlib.sha384(open(os.path.join(ROOT, f), 'rb').read()).digest()).decode()
H[''] = H['index.html']   # './' is index.html
unhashed = [t for t in tools if 'tools/' + t + '.py' not in H]
if unhashed: sys.exit('release.py: tools without a hash: ' + ', '.join(unhashed))
tag = hashlib.sha256(json.dumps(H, sort_keys=True).encode()).hexdigest()[:8]
new = re.sub(r"const C=.*?;", f"const C=BASEV+'-{tag}';", sw, count=1)
new = re.sub(r"const HASH=\{.*?\};", "const HASH=" + json.dumps(H, sort_keys=True, separators=(',', ':')) + ";", new, count=1, flags=re.S)
if '--check' in sys.argv:
    sys.exit(0 if new == sw else print('sw.js manifest is stale: run python3 release.py') or 1)
open(os.path.join(ROOT, 'sw.js'), 'w').write(new)
print(f"cache {base}-{tag}, {len(H)} files hashed")
