// KPython v4 Python worker: Pyodide runs here so Stop can interrupt or kill it.
const PY='https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
importScripts(PY+'pyodide.js');
let py=null,intr=null,ctl=null,dat=null,useSAB=false;
const post=(t,x={})=>postMessage({t,...x});
self.kpT=(...a)=>post('turtle',{a});
self.kpShowImg=b=>post('img',{b});
// input(): Atomics wait on a SharedArrayBuffer if cross-origin isolated, else a sync XHR the service worker answers
self.prompt=function(p){p=String(p??'');
 if(useSAB){Atomics.store(ctl,0,0);post('input',{p,mode:'sab'});Atomics.wait(ctl,0,0);
  const st=Atomics.load(ctl,0);if(st<0)return null;const n=Atomics.load(ctl,1);return new TextDecoder().decode(dat.slice(0,n))}
 const id=Math.random().toString(36).slice(2);post('input',{p,mode:'xhr',id});
 const x=new XMLHttpRequest();x.open('GET','./__kp_input?id='+id,false);x.send(null);
 if(x.status!==200)return null;const r=JSON.parse(x.responseText);return r.cancel?null:r.v};
async function init(m){
 if(m.sab){useSAB=true;intr=new Uint8Array(m.sab,0,1);ctl=new Int32Array(m.sab,4,2);dat=new Uint8Array(m.sab,12)}
 py=await loadPyodide({stdout:t=>post('out',{s:t}),stderr:t=>post('out',{s:t,c:'err'})});
 if(intr)py.setInterruptBuffer(intr);
 // persist /home/pyodide in IndexedDB so files (projects, SQLite dbs, CSVs) survive restarts
 try{py.FS.mkdirTree('/home/pyodide');py.FS.mount(py.FS.filesystems.IDBFS,{},'/home/pyodide');await new Promise(r=>py.FS.syncfs(true,r))}catch(err){post('out',{s:'File persistence off: '+err,c:'sys'})}
 await py.runPythonAsync(m.setup);await py.runPythonAsync(m.wsetup);
 try{py.FS.mkdirTree('/home/pyodide/kptools');for(const f of m.tools){const r=await fetch('tools/'+f);if(r.ok)py.FS.writeFile('/home/pyodide/kptools/'+f,await r.text())}}catch(err){post('out',{s:'Dev tools load: '+err,c:'err'})}
 for(const p of (m.pkgs||[])){try{if(m.native.includes(p.toLowerCase()))await py.loadPackage(p.toLowerCase());else{await py.loadPackage('micropip');await py.pyimport('micropip').install(p)}}catch(err){post('out',{s:'Reinstall '+p+' failed (offline?)',c:'sys'})}}
 post('ready',{v:py.version,sab:useSAB,units:py.runPython('list(UNITS)').toJs()})}
async function prep(code){try{await py.loadPackagesFromImports(code,{messageCallback:s=>post('out',{s,c:'sys'})})}catch(e){post('out',{s:'Package load: '+e.message,c:'err'})}
 if(/\bmatplotlib\b/.test(code)){await py.runPythonAsync('import matplotlib');py.globals.get('_kp_mpl_patch')()}}
const clean=t=>{const o=[];let skip=false;for(const l of t.split('\n')){if(/^  File "/.test(l))skip=/\/lib\/python3\d+\.zip\/_pyodide\//.test(l);else if(!/^\s/.test(l))skip=false;if(!skip)o.push(l)}return o.join('\n')};
const errMsg=e=>{const m=clean(String(e.message||e).trim());return /KeyboardInterrupt/.test(m)?(/input cancelled/.test(m)?'⏹ Stopped (input cancelled)':'⏹ KeyboardInterrupt: stopped'):m};
let syncT=0;const persist=()=>{clearTimeout(syncT);syncT=setTimeout(()=>{try{py.FS.syncfs(false,()=>{})}catch(_){}},300)};
onmessage=async e=>{const m=e.data;if(m.cmd==='init')return init(m).catch(err=>post('fail',{s:String(err)}));
 const done=(x)=>{try{py.runPython('import sys;sys.stdout.flush();sys.stderr.flush()')}catch(_){}post('done',{id:m.id,...x});persist()};
 if(intr)intr[0]=0;
 try{
  if(m.cmd==='run'){py.globals.get('_kp_write_modules')(JSON.stringify(m.files||{}));py.globals.get('_kp_reset_turtle')();await prep(m.code);
   const ns=py.globals.get('dict')();ns.set('__name__','__main__');ns.set('__file__','/home/pyodide/'+(m.fname||'main.py'));
   const r=await py.runPythonAsync(m.code,{globals:ns,filename:'/home/pyodide/'+(m.fname||'main.py')});
   if(r!==undefined&&r!==null&&!r.destroy)post('out',{s:String(r)});
   if(/\bmatplotlib\b/.test(m.code))py.globals.get('_kp_show')();ns.destroy();done({ok:true})}
  else if(m.cmd==='repl'){py.globals.get('_kp_write_modules')(JSON.stringify(m.files||{}));await prep(m.line);const more=py.globals.get('_kp_repl_push')(m.line);
   if(/\bmatplotlib\b/.test(m.line)||py.runPython("'matplotlib' in __import__('sys').modules"))py.globals.get('_kp_show')();done({ok:true,more})}
  else if(m.cmd==='call'){const r=py.globals.get(m.fn)(...m.args);done({ok:true,r:r?.toJs?r.toJs():r})}
  else if(m.cmd==='pkg'){if(m.native)await py.loadPackage(m.name,{messageCallback:s=>post('out',{s,c:'sys'})});else{await py.loadPackage('micropip');const mp=py.pyimport('micropip');await mp.install(m.name);mp.destroy()}done({ok:true})}
 }catch(err){done({ok:false,err:errMsg(err)})}};
