// KPython v6 service worker: allowlisted offline cache, cross-origin isolation headers, pinned Pyodide hashes, worker CSP, input() bridge fallback.
const C='kpython-v6';
const SHELL=['./','./index.html','./app.css','./app.js','./app4.js','./games.js','./github.js','./snippets.js','./worker.js','./kp_setup.py','./kp_worker.py','./manifest.json','./apple-touch-icon.png','./icon-192.png','./icon-512.png',
 ...['r4_eight_markdown','r4_dyno_coverage','r4_forlor_convert','r4_getback_secrets','r4_drop_packages','r4_bot3_memory','r4_bot2_katas','r4_bot2help_imports','r4_bot_docgen','r3_eight_format','r3_dyno_regex','r3_forlor_json','r3_getback_codec','r3_drop_history','r3_bot3_debugger','r3_bot2_snippets','r3_bot2help_metrics','r3_bot_typecheck','r2_eight_lint','r2_dyno_tests','r2_forlor_http','r2_drop_diff','r2_getback_sql','r2_bot3_profile','r2_bot2help_data','r2_bot2_outline','r2_bot_projects'].map(n=>'./tools/'+n+'.py')];
const CM='https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/',PY='https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const CDN=[CM+'codemirror.min.css',CM+'theme/dracula.min.css',CM+'codemirror.min.js',CM+'mode/python/python.min.js',CM+'addon/edit/matchbrackets.min.js',CM+'addon/edit/closebrackets.min.js',
 CM+'addon/search/searchcursor.min.js',CM+'addon/hint/show-hint.min.js',CM+'addon/hint/show-hint.min.css',
 PY+'pyodide.js',PY+'pyodide.asm.js',PY+'pyodide.asm.wasm',PY+'python_stdlib.zip',PY+'pyodide-lock.json'];
// Pinned sha384 of the Pyodide core. pyodide-lock.json is pinned, and Pyodide checks every package against the sha256 in it.
const PIN={'pyodide.js':'i3R37b3tF+HWudsUf1VSEOY2YxwSNMqY8DQa9Z0O3xh+NkJ9o+yjcGyIi5huj+nB','pyodide.asm.js':'yZKhBBiP0ZceJh1RKKbMUfptsNLc0SyfFA4nZmJysRCsIJg0eYjy5Bonr0NN9U3X',
 'pyodide.asm.wasm':'UPLqVXovAmYvDGP3QsAICvyhkugIB8nhuGo3wgsxZD7DlcFDUSpYlRUfpwfq87uX','python_stdlib.zip':'PawoekFvzx+5AUUlZ8VtwwUSpml23vie0wrGq/euGJEkRjl0FXWCXytybeVgbK5c','pyodide-lock.json':'N3VHChchW0Cig+dw+pboPe9oVagcHuwzNGe4VFUqwaMPrEe/ewVorZ58G5lGQxHc'};
const WORKER_CSP="default-src 'none'; script-src 'self' "+PY+" 'wasm-unsafe-eval' 'unsafe-eval'; connect-src 'self' https://api.github.com "+PY+" https://pypi.org https://files.pythonhosted.org; img-src 'self' data: blob:";
const SHELL_URLS=new Set(SHELL.map(u=>new URL(u,self.location).href));
const corsReq=u=>new Request(u,{mode:'cors',credentials:'omit'});
async function sha384(buf){const d=await crypto.subtle.digest('SHA-384',buf);let s='';new Uint8Array(d).forEach(b=>s+=String.fromCharCode(b));return btoa(s)}
async function verified(u,res){const f=u.startsWith(PY)?u.slice(PY.length):null;if(!f||!PIN[f]||!res.ok)return res;
 const buf=await res.clone().arrayBuffer();if(await sha384(buf)!==PIN[f])return new Response('Integrity check failed for '+f,{status:502});return res}
async function getCDN(u){const res=await verified(u,await fetch(corsReq(u)));if(!res.ok)throw new Error(u+' '+res.status);return res}
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(async c=>{await c.addAll(SHELL);await Promise.all(CDN.map(u=>getCDN(u).then(r=>c.put(u,r)).catch(()=>{})))}));self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
function iso(res,same,url){if(!res||res.status===0||res.type==='opaqueredirect')return res;const h=new Headers(res.headers);
 h.set('Cross-Origin-Embedder-Policy','require-corp');h.set('Cross-Origin-Opener-Policy','same-origin');h.set('Cross-Origin-Resource-Policy',same?'same-origin':'cross-origin');
 if(same&&url&&/\/worker\.js$/.test(new URL(url).pathname))h.set('Content-Security-Policy',WORKER_CSP);
 return new Response(res.body,{status:res.status,statusText:res.statusText,headers:h})}
// input() fallback when SharedArrayBuffer is unavailable: the worker does a sync XHR; a page (WindowClient) posts the answer here. Times out after 10 min.
const waiting={};
const answer=(id,v,cancel)=>{const w=waiting[id];if(!w)return;clearTimeout(w.t);delete waiting[id];w.res(new Response(JSON.stringify({v,cancel:!!cancel}),{headers:{'Content-Type':'application/json'}}))};
async function cacheStatus(){const c=await caches.open(C);const miss=[];for(const u of SHELL)if(!(await c.match(new URL(u,self.location).href)))miss.push(u);for(const u of CDN)if(!(await c.match(u)))miss.push(u);return miss}
self.addEventListener('message',e=>{if(!(e.source&&e.source.type==='window'))return;const d=e.data||{};
 if(d.kpStatus&&e.ports[0]){cacheStatus().then(m=>e.ports[0].postMessage({ok:!m.length,missing:m.length,ver:C}));return}
 if(typeof d.kpInput==='string')answer(d.kpInput,String(d.v??''),d.cancel)});
const cacheable=u=>u.startsWith(PY)||u.startsWith(CM)||u.startsWith('https://files.pythonhosted.org/');
self.addEventListener('fetch',e=>{const r=e.request;const u=r.url;const same=u.startsWith(self.location.origin);
 if(same&&new URL(u).pathname.endsWith('/__kp_input')){const id=new URL(u).searchParams.get('id')||'';e.respondWith(new Promise(res=>{waiting[id]={res,t:setTimeout(()=>answer(id,'',true),600000)}}));return}
 if(r.method!=='GET')return;
 if(same){const key=new URL(u);key.search='';const listed=SHELL_URLS.has(key.href)||r.mode==='navigate';
  e.respondWith(fetch(r).then(res=>{if(res.ok&&listed&&!new URL(u).search){const cl=res.clone();caches.open(C).then(c=>c.put(r,cl))}return iso(res,true,u)})
   .catch(()=>caches.match(r).then(m=>m||(r.mode==='navigate'?caches.match(new URL('./index.html',self.location).href):null)).then(m=>m?iso(m,true,u):Response.error())));return}
 if(cacheable(u)){e.respondWith(caches.match(u).then(m=>m||getCDN(u).then(res=>{const cl=res.clone();caches.open(C).then(c=>c.put(u,cl));return res})).then(res=>iso(res,false,u)))}});
