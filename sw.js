// KPython v4 service worker: offline cache + cross-origin isolation headers (for SharedArrayBuffer) + input() bridge fallback.
const C='kpython-v5';
const SHELL=['./','./index.html','./app.css','./app.js','./app4.js','./games.js','./github.js','./snippets.js','./worker.js','./kp_setup.py','./kp_worker.py','./manifest.json','./apple-touch-icon.png','./icon-192.png','./icon-512.png',
 ...['r3_eight_format','r3_dyno_regex','r3_forlor_json','r3_getback_codec','r3_drop_history','r3_bot3_debugger','r3_bot2_snippets','r3_bot2help_metrics','r3_bot_typecheck','r2_eight_lint','r2_dyno_tests','r2_forlor_http','r2_drop_diff','r2_getback_sql','r2_bot3_profile','r2_bot2help_data','r2_bot2_outline','r2_bot_projects'].map(n=>'./tools/'+n+'.py')];
const CM='https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/',PY='https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const CDN=[CM+'codemirror.min.css',CM+'theme/dracula.min.css',CM+'codemirror.min.js',CM+'mode/python/python.min.js',CM+'addon/edit/matchbrackets.min.js',CM+'addon/edit/closebrackets.min.js',
 CM+'addon/search/searchcursor.min.js',CM+'addon/hint/show-hint.min.js',CM+'addon/hint/show-hint.min.css',
 PY+'pyodide.js',PY+'pyodide.asm.js',PY+'pyodide.asm.wasm',PY+'python_stdlib.zip',PY+'pyodide-lock.json'];
const corsReq=u=>new Request(u,{mode:'cors',credentials:'omit'});
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(async c=>{await c.addAll(SHELL);await Promise.all(CDN.map(u=>c.add(corsReq(u)).catch(()=>{})))}));self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
function iso(res){if(!res||res.status===0||res.type==='opaqueredirect')return res;const h=new Headers(res.headers);
 h.set('Cross-Origin-Embedder-Policy','require-corp');h.set('Cross-Origin-Opener-Policy','same-origin');h.set('Cross-Origin-Resource-Policy','cross-origin');
 return new Response(res.body,{status:res.status,statusText:res.statusText,headers:h})}
// input() fallback when SharedArrayBuffer is unavailable: the worker does a sync XHR; the page posts the answer here.
const waiting={};
self.addEventListener('message',e=>{const d=e.data||{};if(d.kpInput&&waiting[d.kpInput]){waiting[d.kpInput](new Response(JSON.stringify({v:d.v,cancel:!!d.cancel}),{headers:{'Content-Type':'application/json'}}));delete waiting[d.kpInput]}});
const isCDN=u=>u.startsWith(CM)||u.startsWith(PY);
self.addEventListener('fetch',e=>{const r=e.request;const u=r.url;
 if(u.startsWith(self.location.origin)&&u.includes('/__kp_input')){const id=new URL(u).searchParams.get('id');e.respondWith(new Promise(res=>waiting[id]=res));return}
 if(r.method!=='GET')return;
 if(u.startsWith(self.location.origin)){ // app files: network first so updates land, cache fallback offline
  e.respondWith(fetch(r).then(res=>{if(res.ok){const cl=res.clone();caches.open(C).then(c=>c.put(r,cl))}return iso(res)}).catch(()=>caches.match(r,{ignoreSearch:true}).then(m=>iso(m||null)||caches.match('./index.html').then(iso))));return}
 if(isCDN(u)||u.includes('files.pythonhosted.org')||u.includes('pypi.org/pypi')){ // versioned CDN: cache first, fetched with CORS so it can be re-headed
  e.respondWith(caches.match(u).then(m=>m||fetch(corsReq(u)).then(res=>{if(res.ok){const cl=res.clone();caches.open(C).then(c=>c.put(u,cl))}return res})).then(iso))}});
