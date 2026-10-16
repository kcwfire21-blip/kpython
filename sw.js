const C='kpython-v3';
const SHELL=['./','./index.html','./app.css','./app.js','./games.js','./github.js','./snippets.js','./kp_setup.py','./manifest.json','./apple-touch-icon.png','./icon-192.png','./icon-512.png'];
const CM='https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/',PY='https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const CDN=[CM+'codemirror.min.css',CM+'theme/dracula.min.css',CM+'codemirror.min.js',CM+'mode/python/python.min.js',CM+'addon/edit/matchbrackets.min.js',CM+'addon/edit/closebrackets.min.js',
 PY+'pyodide.js',PY+'pyodide.asm.js',PY+'pyodide.asm.wasm',PY+'python_stdlib.zip',PY+'pyodide-lock.json'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(async c=>{await c.addAll(SHELL);await Promise.all(CDN.map(u=>c.add(u).catch(()=>{})))}));self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
const isCDN=u=>u.startsWith(CM)||u.startsWith(PY);
self.addEventListener('fetch',e=>{const r=e.request;if(r.method!=='GET')return;const u=r.url;
 if(u.startsWith(self.location.origin)){ // app files: network first so updates land, cache fallback offline
  e.respondWith(fetch(r).then(res=>{if(res.ok){const cl=res.clone();caches.open(C).then(c=>c.put(r,cl))}return res}).catch(()=>caches.match(r,{ignoreSearch:true}).then(m=>m||caches.match('./index.html'))));return}
 if(isCDN(u)||u.includes('files.pythonhosted.org')||u.includes('pypi.org/pypi')){ // versioned CDN: cache first
  e.respondWith(caches.match(r).then(m=>m||fetch(r).then(res=>{if(res.ok){const cl=res.clone();caches.open(C).then(c=>c.put(r,cl))}return res})))}});
