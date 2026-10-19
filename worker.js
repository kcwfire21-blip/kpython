// KPython v4 Python worker: Pyodide runs here so Stop can interrupt or kill it.
// v9.1 (Get back H1): Python must never reach CacheStorage (it could plant app files that the SW serves cache-first).
try{delete WorkerGlobalScope.prototype.caches}catch(e){}try{delete self.caches}catch(e){}
if(typeof caches!=='undefined')throw new Error('KPython: could not lock CacheStorage away from Python; refusing to start');
const PY='https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
// v11 (Get back M1): JS timers started while a job runs are recorded and cleared when it ends, so a callback from an
// earlier run can't fire inside a later one. Internal timers use the saved originals.
const _sT=self.setTimeout.bind(self),_cT=self.clearTimeout.bind(self),_sI=self.setInterval.bind(self),_cI=self.clearInterval.bind(self);
let JT=null;
self.setTimeout=function(f,ms,...a){let id;id=_sT(function(){if(JT)JT.delete(id);return typeof f==='function'?f.apply(this,arguments):undefined},ms,...a);if(JT)JT.add(id);return id};
self.setInterval=function(f,ms,...a){const id=_sI(f,ms,...a);if(JT)JT.add(id);return id};
self.clearTimeout=id=>{if(JT)JT.delete(id);_cT(id)};self.clearInterval=id=>{if(JT)JT.delete(id);_cI(id)};
const jobTimersStart=()=>{JT=new Set()};const jobTimersEnd=()=>{if(JT){for(const id of JT){_cT(id);_cI(id)}JT=null}};
importScripts(PY+'pyodide.js');
// A Stop (KeyboardInterrupt) also rejects Pyodide's internal webloop promise; it is already handled by the run, so don't report it as uncaught.
const isKI=x=>/KeyboardInterrupt/.test(String(x&&x.message||x));
self.addEventListener('unhandledrejection',e=>{if(isKI(e.reason))e.preventDefault()});
self.addEventListener('error',e=>{if(isKI(e.error)||isKI(e.message))e.preventDefault()});
// Report requests blocked by the Allowed-sites policy so the page can explain them.
self.addEventListener('securitypolicyviolation',e=>{if(/connect-src/.test(e.effectiveDirective||e.violatedDirective||'')){let o='';try{o=new URL(e.blockedURI).origin}catch(_){o=String(e.blockedURI||'')}post('blocked',{o,job:CUR})}});
let py=null,intr=null,ctl=null,dat=null,useSAB=false;
const post=(t,x={})=>postMessage({t,...x});
self.kpT=(...a)=>post('turtle',{a});
self.kpShowImg=b=>post('img',{b});
// input(): Atomics wait on a SharedArrayBuffer if cross-origin isolated, else a sync XHR the service worker answers
function blockAsk(t,o){
 if(useSAB){Atomics.store(ctl,0,0);post(t,{...o,mode:'sab'});Atomics.wait(ctl,0,0);
  const st=Atomics.load(ctl,0);if(st<0)return null;const n=Atomics.load(ctl,1);return new TextDecoder().decode(dat.slice(0,n))}
 const id=crypto.randomUUID();post(t,{...o,mode:'xhr',id});
 const x=new XMLHttpRequest();x.open('GET','./__kp_input?id='+id,false);x.send(null);
 if(x.status!==200)return null;const r=JSON.parse(x.responseText);return r.cancel?null:r.v}
self.prompt=p=>blockAsk('input',{p:String(p??'')});
// v11 (Get back M1): every bridge request carries the job token of the Python code that made it (a ContextVar set per run).
// A callback with no run behind it (JS timer, stray promise) has token 0 and is refused here; the page checks the token too.
const TOK=()=>{try{return Number(py.globals.get('_kp_job_tok')())}catch(e){return -1}};
const refuse=t=>{post('out',{s:'⛔ Refused a '+t+' request from code that is not part of the current run (e.g. a timer left from an earlier run).',c:'err'})};
// v11: snippet insert bridge. Python waits (like input()) while the app shows the text and asks Keivon.
let EDN=0;self.kpEditorInsert=text=>{const tok=TOK();if(!CUR||tok!==CUR){refuse('editor insert');return false}
 text=String(text);if(text.length>20000)return false;if(++EDN>5){post('out',{s:'⛔ Only 5 editor inserts per run.',c:'err'});return false}
 return blockAsk('edins',{text,job:tok})==='1'};
let PK=[];self.kpPkgsGet=()=>JSON.stringify(PK);self.kpPkgsSet=j=>{PK=JSON.parse(j);post('pkgs',{l:PK})};
let SITES=[],CUR=0;
// v7 saved-scripts bridge: Python can READ saved scripts, and can only ASK the page to change one; the page confirms with Keivon first.
self.kpSiteAsk=(o,why)=>sbr('siteask',{o:String(o),why:String(why||'')});
const SBR={};function sbr(t,o){const tok=TOK();return new Promise(r=>{if(!CUR||tok!==CUR){refuse(t==='siteask'?'site':'saved-scripts');r(t==='sget'?'{}':false);return}
 const id=crypto.randomUUID();SBR[id]=r;post(t,Object.assign({id,job:tok},o))})}
self.kpScriptsGet=(names)=>sbr('sget',names?{names:Array.from(names,String)}:{});self.kpScriptsSet=(name,text,why)=>sbr('sset',{name:String(name),text:String(text),why:String(why||'').slice(0,200)});
self.kpSitesGet=()=>JSON.stringify(SITES);
async function init(m){PK=m.pkgs||[];SITES=Array.isArray(m.sites)?m.sites.map(String):[];
 if(m.sab){useSAB=true;intr=new Uint8Array(m.sab,0,1);ctl=new Int32Array(m.sab,4,2);dat=new Uint8Array(m.sab,12)}
 py=await loadPyodide({stdout:t=>post('out',{s:t}),stderr:t=>post('out',{s:t,c:'err'})});
 // raw (unbuffered) stdout so a prompt without a newline shows before input() waits
 {const dec=new TextDecoder();py.setStdout({write:b=>{post('out',{s:dec.decode(b,{stream:true}),raw:1});return b.length}})}
 if(intr)py.setInterruptBuffer(intr);
 // persist /home/pyodide in IndexedDB so files (projects, SQLite dbs, CSVs) survive restarts
 try{py.FS.mkdirTree('/home/pyodide');py.FS.mount(py.FS.filesystems.IDBFS,{},'/home/pyodide');await new Promise(r=>py.FS.syncfs(true,r))}catch(err){post('out',{s:'File persistence off: '+err,c:'sys'})}
 await py.runPythonAsync(m.setup);await py.runPythonAsync(m.wsetup);
 post('ready',{v:py.version,sab:useSAB,units:py.runPython('list(UNITS)').toJs()});
 // r8 perf (bot3): saved packages reinstall in parallel AFTER ready; prep() waits for them
 PKGP=(async()=>{const L=(m.pkgs||[]).map(String),nat=L.filter(p=>m.native.includes(p.toLowerCase())).map(p=>p.toLowerCase()),pip=L.filter(p=>!m.native.includes(p.toLowerCase()));
  const fail=p=>post('out',{s:'Reinstall '+p+' failed (offline?)',c:'sys'});
  await Promise.all([nat.length?py.loadPackage(nat).catch(()=>fail(nat.join(', '))):null,
   pip.length?py.loadPackage('micropip').then(()=>py.pyimport('micropip').install(pip)).catch(()=>fail(pip.join(', '))):null])})();
 // v9 perf: Dev tools load in parallel after ready (runs wait for them, see TOOLSP)
 // v9.1 (Get back M1): tools live in /kptools on MEMFS (not the persistent ~), read-only, and only files the SW verified against its hash manifest are written.
 TOOLSP=(async()=>{const bad=[];try{try{py.FS.mkdirTree('/kptools')}catch(e){}
  const get=async f=>{const r=await fetch('tools/'+f);if(!r.ok||r.headers.get('X-KP-Verified')!=='1')throw new Error(r.status);return r.text()};
  const res=await Promise.allSettled(m.tools.map(async f=>{let t;try{t=await get(f)}catch(e){t=await get(f)}TXT[f]=t}));
  res.forEach((r,i)=>{if(r.status==='rejected')bad.push(m.tools[i])});py.globals.get('_kp_set_tools')(JSON.stringify(Object.keys(TXT)));writeTools()}catch(err){bad.push(String(err))}
  if(bad.length)post('out',{s:'⚠️ Dev tools not loaded (missing or failed the integrity check): '+bad.join(', '),c:'err'})})()}
let TOOLSP=null,PKGP=null;const TXT={};
// v11 (Drop #4): Python runs as uid 0, so file modes don't protect /kptools. Before EVERY run the tools are re-written
// from the texts the SW verified (held here in JS, out of Python's reach) and tool modules are re-imported.
function writeTools(){const FS=py.FS;try{FS.mkdirTree('/kptools')}catch(e){}
 try{const st=FS.lstat('/kptools');if(FS.isLink(st.mode)||!FS.isDir(st.mode)){try{FS.unlink('/kptools')}catch(_){FS.rmdir('/kptools')}FS.mkdirTree('/kptools')}}catch(e){}
 try{FS.chmod('/kptools',0o755)}catch(e){}
 try{for(const n of FS.readdir('/kptools'))if(n!=='.'&&n!=='..'&&!Object.hasOwn(TXT,n)){try{FS.chmod('/kptools/'+n,0o644);FS.unlink('/kptools/'+n)}catch(_){}}}catch(e){}
 for(const [f,txt] of Object.entries(TXT)){const p='/kptools/'+f;let same=false;try{same=FS.readFile(p,{encoding:'utf8'})===txt&&!FS.isLink(FS.lstat(p).mode)}catch(e){}
  if(!same){try{FS.chmod(p,0o644)}catch(e){}try{FS.unlink(p)}catch(e){}FS.writeFile(p,txt)}try{FS.chmod(p,0o444)}catch(e){}}
 try{FS.chmod('/kptools',0o555)}catch(e){}}
async function prep(code){if(PKGP)await PKGP;
 if(/\bsqlite3\b|r2_getback_sql|selftest|r8_bot2_examples/.test(code)){try{await py.loadPackage('sqlite3')}catch(e){}}  // v10: Dev tools and self-tests need sqlite3
 try{await py.loadPackagesFromImports(code,{messageCallback:s=>post('out',{s,c:'sys'})})}catch(e){post('out',{s:'Package load: '+e.message,c:'err'})}
 if(/\bmatplotlib\b/.test(code)){await py.runPythonAsync('import matplotlib');py.globals.get('_kp_mpl_patch')()}}
const clean=t=>{const o=[];let skip=false;for(const l of t.split('\n')){if(/^  File "/.test(l))skip=/\/lib\/python3\d+\.zip\/_pyodide\//.test(l)||/, in _kp_run_code$/.test(l);else if(!/^\s/.test(l))skip=false;if(!skip)o.push(l)}return o.join('\n')};
const errMsg=e=>{const m=clean(String(e.message||e).trim());return /KeyboardInterrupt/.test(m)?(/input cancelled/.test(m)?'⏹ Stopped (input cancelled)':'⏹ KeyboardInterrupt: stopped'):m};
let syncT=0;const persist=()=>{_cT(syncT);syncT=_sT(()=>{try{py.FS.syncfs(false,()=>{})}catch(_){}},300)};
onmessage=async e=>{const m=e.data;if(m.cmd==='pkgsync'){PK=Array.isArray(m.l)?m.l.map(String):PK;return}if(m.cmd==='sres'){const r=SBR[m.id];delete SBR[m.id];if(r)r(m.v);return}if(m.cmd==='init')return init(m).catch(err=>post('fail',{s:String(err)}));if(TOOLSP)await TOOLSP;CUR=m.id;EDN=0;
 if(m.cmd==='run'||m.cmd==='repl'){try{writeTools()}catch(e){}jobTimersStart()}
 const done=(x)=>{try{py.runPython('import sys;sys.stdout.flush();sys.stderr.flush()')}catch(_){}jobTimersEnd();
  let left=0;try{left=py.globals.get('_kp_take_left')()}catch(_){}CUR=0;post('done',{id:m.id,...x,restart:left>0});persist()};
 if(intr)intr[0]=0;
 try{
  if(m.cmd==='run'){py.globals.get('_kp_write_modules')(JSON.stringify(m.files||{}));py.globals.get('_kp_reset_turtle')();await prep(m.code);
   const ns=py.globals.get('dict')();ns.set('__name__','__main__');ns.set('__file__','/home/pyodide/'+(m.fname||'main.py'));
   const runner=py.globals.get('_kp_run_code');const r=await runner(m.code,ns,'/home/pyodide/'+(m.fname||'main.py'),m.id);runner.destroy();
   if(r!==undefined&&r!==null&&!r.destroy)post('out',{s:String(r)});
   if(/\bmatplotlib\b/.test(m.code))py.globals.get('_kp_show')();ns.destroy();done({ok:true})}
  else if(m.cmd==='repl'){py.globals.get('_kp_write_modules')(JSON.stringify(m.files||{}));await prep(m.line);const more=py.globals.get('_kp_repl_push')(m.line,m.id);
   try{const n=await py.globals.get('_kp_repl_after')();if(n)py.globals.set('_kp_left',n)}catch(_){}
   if(/\bmatplotlib\b/.test(m.line)||py.runPython("'matplotlib' in __import__('sys').modules"))py.globals.get('_kp_show')();done({ok:true,more})}
  else if(m.cmd==='call'){const r=py.globals.get(m.fn)(...m.args);done({ok:true,r:r?.toJs?r.toJs():r})}
  else if(m.cmd==='pkg'){if(m.native)await py.loadPackage(m.name,{messageCallback:s=>post('out',{s,c:'sys'})});else{await py.loadPackage('micropip');const mp=py.pyimport('micropip');await mp.install(m.name);mp.destroy()}done({ok:true})}
 }catch(err){done({ok:false,err:errMsg(err)})}};
