const $=id=>document.getElementById(id),LS=localStorage;
const J=(k,d)=>{try{const v=JSON.parse(LS.getItem(k));return v??d}catch(e){return d}},S=(k,v)=>LS.setItem(k,JSON.stringify(v));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>((+n||0)<0?'-$':'$')+Math.abs(+n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const today=()=>{const d=new Date();return new Date(d-d.getTimezoneOffset()*6e4).toISOString().slice(0,10)};
// haptic-feel feedback
document.addEventListener('pointerdown',e=>{const b=e.target.closest('button');if(!b)return;b.classList.add('tap');if(navigator.vibrate)navigator.vibrate(8);setTimeout(()=>b.classList.remove('tap'),120)});

/* ---------- lock (unchanged storage: kp_pass) ---------- */
async function sha(t){const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(t));return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('')}
const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join(''),unhex=h=>new Uint8Array(h.match(/../g).map(x=>parseInt(x,16)));
async function pbkdf2(pass,salt,iter){const k=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),'PBKDF2',false,['deriveBits']);return hex(await crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt,iterations:iter},k,256))}
async function makeHash(pass){const salt=crypto.getRandomValues(new Uint8Array(16)),it=310000;return `pbkdf2$${it}$${hex(salt)}$${await pbkdf2(pass,salt,it)}`}
async function checkPass(pass,stored){if(stored.startsWith('pbkdf2$')){const[,it,salt,h]=stored.split('$');return await pbkdf2(pass,unhex(salt),+it)===h}
 if(await sha(pass)===stored){LS.setItem('kp_pass',await makeHash(pass));return true}return false} // legacy SHA-256 -> migrate on success
function setupLock(){window.dispatchEvent(new Event('kp-lock'));const h=LS.getItem('kp_pass');$('lmsg').textContent=h?'Enter passcode':'Create a passcode (4+ characters)';$('lock').style.display='flex';$('pin').value='';$('pin').focus()}
$('lbtn').onclick=async()=>{const v=$('pin').value,h=LS.getItem('kp_pass');$('lbtn').disabled=true;try{
 if(!h){if(v.length<4)return $('lmsg').textContent='Use at least 4 characters';LS.setItem('kp_pass',await makeHash(v));$('lock').style.display='none'}
 else if(await checkPass(v,h))$('lock').style.display='none';else{$('lmsg').textContent='Wrong passcode';$('pin').value='';$('lock').animate([{transform:'translateX(-10px)'},{transform:'translateX(10px)'},{transform:'none'}],200)}}finally{$('lbtn').disabled=false}};
$('pin').onkeydown=e=>{if(e.key==='Enter')$('lbtn').click()};$('lockbtn').onclick=setupLock;

/* ---------- tabs ---------- */
function showView(id){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on',v.id===id));document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.v===id));if(id==='v-code')setTimeout(()=>cm.refresh(),0);if(id==='v-files')renderFiles();scrollTo(0,0)}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>showView(b.dataset.v));
function chips(box){const c=$(box);c.querySelectorAll('button').forEach(b=>b.onclick=()=>{c.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));c.parentElement.querySelectorAll('.tool').forEach(t=>t.classList.toggle('on',t.id===b.dataset.t));window.dispatchEvent(new CustomEvent('subtab',{detail:b.dataset.t}))})}
chips('toolchips');chips('funchips');

/* ---------- scripts (kp_scripts / kp_cur kept) ---------- */
const STARTERS={"Hello World":'name = input("What\'s your name? ")\nprint(f"Hello, {name}! Python is running on your phone.")',
"Cleaning Quote":'# Quote + tip calculator for my cleaning business\nsqft = float(input("Square feet: ") or 1500)\nrate = float(input("Rate per sq ft ($): ") or 0.10)\nvisits = int(input("Visits per month: ") or 4)\nper_visit = max(sqft * rate, 75)\nmonthly = per_visit * visits\nprint(f"Per visit: ${per_visit:,.2f}")\nprint(f"Monthly ({visits} visits): ${monthly:,.2f}")\nfor pct in (15, 18, 20):\n    print(f"  {pct}% tip on one visit: ${per_visit*pct/100:,.2f}")',
"Interview Countdown":'from datetime import datetime, timezone, timedelta\nct = timezone(timedelta(hours=-5))\ndeadline = datetime(2026, 10, 18, 23, 59, tzinfo=ct)\nleft = deadline - datetime.now(ct)\nif left.total_seconds() > 0:\n    h, m = divmod(int(left.total_seconds())//60, 60)\n    print(f"US Foods interview due in {h//24}d {h%24}h {m}m")\nelse:\n    print("Deadline passed")'};
let scripts=J('kp_scripts',null)||{...STARTERS},cur=LS.getItem('kp_cur')||Object.keys(scripts)[0];
const persist=()=>{LS.setItem('kp_scripts',JSON.stringify(scripts));LS.setItem('kp_cur',cur)};

const cm=CodeMirror.fromTextArea($('code'),{mode:'python',theme:'dracula',lineNumbers:true,indentUnit:4,tabSize:4,smartIndent:true,matchBrackets:true,autoCloseBrackets:true,lineWrapping:false,inputStyle:'contenteditable',
 extraKeys:{Tab:c=>c.somethingSelected()?c.indentSelection('add'):c.replaceSelection('    '),'Shift-Tab':c=>c.indentSelection('subtract'),'Ctrl-Enter':()=>run(),'Cmd-Enter':()=>run()}});
let dirtyT;const setDirty=d=>{$('save').textContent=d?'💾•':'💾';$('save').title=d?'Unsaved changes (autosaves in a moment)':'Saved'};
cm.on('change',(c,ch)=>{if(ch.origin==='setValue')return;setDirty(true);clearTimeout(dirtyT);dirtyT=setTimeout(()=>{if(cur){scripts[cur]=cm.getValue();persist();setDirty(false)}},600)});
function refresh(){if(!(cur in scripts))cur=Object.keys(scripts)[0]||'';$('sel').innerHTML=Object.keys(scripts).map(n=>`<option>${esc(n)}</option>`).join('');$('sel').value=cur;cm.setValue(scripts[cur]||'');cm.clearHistory();persist();if(typeof setDirty==='function')setDirty(false)}
$('sel').onchange=()=>{scripts[cur]=cm.getValue();cur=$('sel').value;refresh()};
$('save').onclick=()=>{if(!cur)return $('new').click();clearTimeout(dirtyT);scripts[cur]=cm.getValue();persist();setDirty(false);log('Saved '+cur,'sys')};
function newScript(name,code){let n=name,i=2;while(n in scripts)n=name+' '+i++;if(cur)scripts[cur]=cm.getValue();scripts[n]=code;cur=n;refresh();return n}
$('new').onclick=()=>{const n=prompt('Script name?','Untitled');if(n===null)return;newScript(n.trim()||'Untitled','print("hi")\n');toast2('Created "'+cur+'"');cm.focus()};
$('snipbtn').onclick=()=>{showView('v-files');setTimeout(()=>$('snip-list').scrollIntoView({behavior:'smooth'}),50)};

/* keybar */
const KEYS=[['⇥','    '],[':',':'],['( )','()',1],['[ ]','[]',1],['{ }','{}',1],['" "','""',1],["' '","''",1],['=','='],['_','_'],['#','# '],['.','.'],[',',','],['←','L'],['→','R'],['↶','U']];
$('keybar').innerHTML=KEYS.map((k,i)=>`<button data-i="${i}">${k[0]}</button>`).join('');
$('keybar').querySelectorAll('button').forEach(b=>{b.addEventListener('mousedown',e=>e.preventDefault());b.addEventListener('touchstart',e=>{e.preventDefault();b.click()},{passive:false});b.onclick=()=>{const k=KEYS[b.dataset.i];
 if(k[1]==='L')cm.execCommand('goCharLeft');else if(k[1]==='R')cm.execCommand('goCharRight');else if(k[1]==='U')cm.undo();
 else{const sel=cm.getSelection();if(k[2]&&sel){cm.replaceSelection(k[1][0]+sel+k[1][1])}else{cm.replaceSelection(k[1]);if(k[2])cm.execCommand('goCharLeft')}}cm.focus()}});
function placeKeybar(){const kb=$('keybar'),vv=window.visualViewport;if(cm.hasFocus()&&vv&&window.innerHeight-vv.height>120){kb.classList.add('float');kb.style.top=(vv.offsetTop+vv.height-kb.offsetHeight)+'px'}else{kb.classList.remove('float');kb.style.top=''}}
cm.on('focus',()=>setTimeout(placeKeybar,300));cm.on('blur',()=>setTimeout(placeKeybar,100));if(window.visualViewport){visualViewport.addEventListener('resize',placeKeybar);visualViewport.addEventListener('scroll',placeKeybar)}

/* ---------- output ---------- */
let outEl=null;
function log(t,c){const o=outEl||$('out');const s=document.createElement('span');if(c)s.className=c;if(c==='err')linkify(s,t+'\n');else s.textContent=t+'\n';o.appendChild(s);o.scrollTop=o.scrollHeight}
window.kpShowImg=b64=>{const i=new Image();i.src='data:image/png;base64,'+b64;(outEl||$('out')).appendChild(i)};
$('clr').onclick=()=>{if(inputMsg){dropOut=true;obuf=[];answerInput(null)}$('out').textContent=''};

/* turtle target */
let tuCanvas=null;
window.kpT=(op,...a)=>{if(!tuCanvas){tuCanvas=document.createElement('canvas');tuCanvas.width=600;tuCanvas.height=600;tuCanvas.style.background='#010409';(outEl||$('out')).appendChild(tuCanvas);clearT(tuCanvas)}
 const c=tuCanvas,x=c.getContext('2d'),W=c.width/2,H=c.height/2,sc=c.width/400;const P=(px,py)=>[W+px*sc,H-py*sc];
 if(op==='reset'||op==='clear')clearT(c);else if(op==='bg'){c.dataset.bg=a[0];clearT(c)}
 else if(op==='line'){x.strokeStyle=a[4];x.lineWidth=a[5]*sc;x.lineCap='round';x.beginPath();x.moveTo(...P(a[0],a[1]));x.lineTo(...P(a[2],a[3]));x.stroke()}
 else if(op==='dot'){x.fillStyle=a[3];x.beginPath();x.arc(...P(a[0],a[1]),a[2]*sc/2,0,7);x.fill()}
 else if(op==='text'){x.fillStyle=a[3];x.font=(16*sc)+'px sans-serif';x.fillText(a[2],...P(a[0],a[1]))}};
function clearT(c){const x=c.getContext('2d');x.fillStyle=c.dataset.bg||'#010409';x.fillRect(0,0,c.width,c.height)}

/* ---------- Python (v4: runs in a Web Worker so Stop works) ---------- */
const TOOLS=['r4_eight_markdown.py','r4_dyno_coverage.py','r4_forlor_convert.py','r4_getback_secrets.py','r4_drop_packages.py','r4_bot3_memory.py','r4_bot2_katas.py','r4_bot2help_imports.py','r4_bot_docgen.py','r3_eight_format.py','r3_dyno_regex.py','r3_forlor_json.py','r3_getback_codec.py','r3_drop_history.py','r3_bot3_debugger.py','r3_bot2_snippets.py','r3_bot2help_metrics.py','r3_bot_typecheck.py','r2_eight_lint.py','r2_dyno_tests.py','r2_forlor_http.py','r2_drop_diff.py','r2_getback_sql.py','r2_bot3_profile.py','r2_bot2help_data.py','r2_bot2_outline.py','r2_bot_projects.py'];
const modname=n=>{let m=n.trim().toLowerCase().replace(/\.py$/,'').replace(/\W+/g,'_').replace(/^_+|_+$/g,'')||'script';return /^\d/.test(m)?'_'+m:m};
let W=null,running=false,SAB=null,INTR=null,CTL=null,DAT=null,pend={},seq=0,setupTxt=null,wsetupTxt=null,readyRes,pyReady,pyVer='';
function newReady(){pyReady=new Promise(r=>readyRes=r)}newReady();
async function startWorker(){newReady();if(typeof syncSites==="function")await syncSites().catch(()=>{});$('pystat').textContent='Loading Python…';$('pystat').classList.remove('ok');setRunBtns();
 if(!setupTxt){setupTxt=await (await fetch('kp_setup.py')).text();wsetupTxt=await (await fetch('kp_worker.py')).text()}
 if(self.crossOriginIsolated&&typeof SharedArrayBuffer!=='undefined'){SAB=new SharedArrayBuffer(12+65536);INTR=new Uint8Array(SAB,0,1);CTL=new Int32Array(SAB,4,2);DAT=new Uint8Array(SAB,12)}
 W=new Worker('worker.js');W.onmessage=onW;W.onerror=e=>log('Worker error: '+(e.message||e),'err');
 W.postMessage({cmd:'init',pkgs:J('kp_pkgs',[]),native:['numpy','pandas','matplotlib','scipy','sympy','scikit-learn','pillow'],sab:SAB,setup:setupTxt,wsetup:wsetupTxt,tools:TOOLS})}
/* batched plain stdout: one DOM write per frame, pane keeps the last MAXL lines */
let obuf=[],oraf=0,dropOut=false;const MAXL=5000;
function bufOut(s){obuf.push(s);if(!oraf)oraf=requestAnimationFrame(flushOut)}
function flushOut(){if(oraf){cancelAnimationFrame(oraf);oraf=0}if(!obuf.length)return;const o=outEl||$('out');const t=obuf.join('\n')+'\n';obuf=[];
 const s=document.createElement('span');s.textContent=t;o.appendChild(s);trimOut(o);o.scrollTop=o.scrollHeight}
function trimOut(o){let n=0;for(const c of o.childNodes)if(!c.classList?.contains('trimnote'))n+=(c.textContent.match(/\n/g)||[]).length;
 while(n>MAXL&&o.firstChild){const c=o.firstChild;const k=(c.textContent.match(/\n/g)||[]).length;if(n-k<MAXL&&c.nodeType===1&&c.tagName==='SPAN'){const ls=c.textContent.split('\n');c.textContent=ls.slice(n-MAXL).join('\n');n=MAXL;break}n-=k;c.remove()}
 if(n>=MAXL){o.querySelector('.trimnote')?.remove();const s=document.createElement('span');s.className='sys trimnote';s.textContent='(older output trimmed to last '+MAXL+' lines)\n';o.prepend(s)}}
function onW(e){const m=e.data;
 if(m.t==='out'&&dropOut)return;if(m.t==='out'&&!m.c){bufOut(m.s);return}flushOut();
 if(m.t==='out')log(m.s,m.c);else if(m.t==='img')kpShowImg(m.b);else if(m.t==='turtle')kpT(...m.a);
 else if(m.t==='input')askInput(m);
 else if(m.t==='blocked'){log(`Blocked: ${m.o} isn't in Allowed sites. Add it in Tools > Allowed sites.`,'err')}
 else if(m.t==='sites'||m.kpSites||m.kpGetSites){console.warn('Rejected: Python tried to change Allowed sites');log('⛔ Rejected: scripts cannot change Allowed sites.','err')}
 else if(m.t==='pkgs'){const l=Array.isArray(m.l)?m.l.filter(s=>typeof s==='string'&&/^[\w.\-\[\]=<>]{1,120}$/.test(s)):[];S('kp_pkgs',l)}
 else if(m.t==='ready'){pyVer=m.v;$('pystat').textContent='Python '+m.v+(m.sab?'':' ·');$('pystat').title=m.sab?'Stop interrupts in place':'Stop restarts Python';$('pystat').classList.add('ok');
  $('c-unit').innerHTML=m.units.map(k=>`<option>${esc(k)}</option>`).join('');readyRes();setRunBtns();log('Python '+m.v+' ready'+(m.sab?'':' (compat mode: Stop restarts Python)'),'sys')}
 else if(m.t==='fail'){$('pystat').textContent='Python offline';$('run').textContent='Python failed to load';log(m.s,'err')}
 else if(m.t==='done'){dropOut=false;const p=pend[m.id];delete pend[m.id];if(p)p(m)}}
function wcall(msg){return new Promise(res=>{const id=++seq;pend[id]=res;W.postMessage({...msg,id})})}
function allFiles(){if(cur)scripts[cur]=cm.getValue();return scripts}
/* inline input() box inside the output area */
let inputMsg=null;
function askInput(m){inputMsg=m;const o=outEl||$('out');const row=document.createElement('div');row.className='inrow';
 row.innerHTML='<span class="inp">›</span><input autocapitalize="off" autocorrect="off" spellcheck="false"><button class="pri">↵</button><button>✕</button>';
 o.appendChild(row);const inp=row.querySelector('input');const fin=v=>{row.remove();answerInput(v)};
 inp.onkeydown=e=>{if(e.key==='Enter')fin(inp.value)};row.querySelectorAll('button')[0].onclick=()=>fin(inp.value);row.querySelectorAll('button')[1].onclick=()=>fin(null);
 setTimeout(()=>{inp.focus();row.scrollIntoView({block:'nearest'})},30)}
function answerInput(v){const m=inputMsg;inputMsg=null;if(!m)return;
 if(m.mode==='sab'){if(v!==null){const b=new TextEncoder().encode(v).slice(0,65536);DAT.set(b);Atomics.store(CTL,1,b.length)}Atomics.store(CTL,0,v===null?-1:1);Atomics.notify(CTL,0)}
 else navigator.serviceWorker.controller?.postMessage({kpInput:m.id,v:v??'',cancel:v===null})}
async function stopPy(){if(!running)return;log('⏹ Stopping…','sys');$('stop').textContent='Stopping…';$('stopbtn').textContent='…';document.querySelectorAll('.inrow').forEach(r=>r.remove());
 if(inputMsg)answerInput(null);
 if(INTR){INTR[0]=2;const t=Date.now();while(running&&Date.now()-t<1000)await new Promise(r=>setTimeout(r,50));if(!running)return}
 hardRestart()}
function hardRestart(){W.terminate();Object.values(pend).forEach(p=>p({ok:false,err:'⏹ Stopped. Python was restarted (console variables were cleared).'}));pend={};inputMsg=null;startWorker()}
function setRunBtns(){const busy=running;$('run').disabled=busy;$('run').textContent=busy?'Running…':'▶ Run';$('stop').hidden=!busy;$('stopbtn').hidden=!busy;if(!busy){$('stop').textContent='⏹ Stop';$('stopbtn').textContent='⏹'}$('r-go').disabled=busy}
async function job(msg,{target=null,turtle=null}={}){await pyReady;if(running){toast('Python is busy. Tap ⏹ Stop first.');return {ok:false}}running=true;setRunBtns();outEl=target;tuCanvas=turtle;
 try{const r=await wcall(msg);if(!r.ok&&r.err)log(r.err,'err');return r}finally{outEl=null;tuCanvas=null;running=false;setRunBtns()}}
async function runPy(code,o={}){const r=await job({cmd:'run',code,files:allFiles(),fname:'__kp_run__.py'},o);return r.ok}
async function run(){try{cm.display.input.forceCompositionEnd?.();cm.display.input.poll?.()}catch(e){}clearTimeout(dirtyT);if(typeof setDirty==='function')setDirty(false);scripts[cur]=cm.getValue();persist();clearErr();log('— run '+cur+' —','sys');const t0=performance.now();
 const r=await job({cmd:'run',code:cm.getValue(),files:allFiles(),fname:modname(cur)+'.py'});log(`— ${r.ok?'done':(/Stopped|KeyboardInterrupt/.test(r.err||'')?'stopped':'error')} in ${((performance.now()-t0)/1000).toFixed(2)}s —`,'sys')}
$('run').onclick=run;$('stop').onclick=stopPy;$('stopbtn').onclick=stopPy;
async function pycall(fn,...args){await pyReady;if(running)return 'Python is busy (tap ⏹ Stop).';const r=await wcall({cmd:'call',fn,args});return r.ok?r.r:'Error: '+r.err}
function toast(t){log(t,'sys')}
function toast2(t){let d=$('toast');if(!d){d=document.createElement('div');d.id='toast';document.body.appendChild(d)}d.textContent=t;d.classList.add('on');clearTimeout(d._t);d._t=setTimeout(()=>d.classList.remove('on'),2200)}
setTimeout(startWorker,0); // after app4.js (syncSites) has loaded

/* packages */
async function installPkg(name){name=name.trim();if(!name)return;showView('v-code');log('Installing '+name+'…','sys');
 const native=['numpy','pandas','matplotlib','scipy','sympy','scikit-learn','pillow'].includes(name.toLowerCase());
 const r=await job({cmd:'pkg',name:native?name.toLowerCase():name,native});
 if(r.ok){log('✅ '+name+' installed. import it in your script.','sys');const l=J('kp_pkgs',[]);if(!l.includes(name)){l.push(name);S('kp_pkgs',l)}}}
$('pkginst').onclick=()=>installPkg($('pkgname').value);
document.querySelectorAll('.qp').forEach(b=>b.onclick=()=>installPkg(b.dataset.p));

/* ---------- Tools ---------- */
const EXTRAS=["Windows (interior)",40,"Fridge / microwave",25,"Restroom deep clean",35,"Carpet vacuum deep",30,"Trash haul-away",20,"Floor mop & shine",45];
let exH='';for(let i=0;i<EXTRAS.length;i+=2)exH+=`<label><input type="checkbox" value="${EXTRAS[i]}">${EXTRAS[i]} +$${EXTRAS[i+1]}</label>`;$('q-extras').innerHTML=exH;
$('q-go').onclick=async()=>{await pyReady;const ex=[...$('q-extras').querySelectorAll('input:checked')].map(i=>i.value);
 $('q-out').textContent=await pycall('make_invoice',$('q-client').value,$('q-sqft').value,$('q-rate').value,$('q-freq').value,JSON.stringify(ex),$('q-notes').value)};
async function shareText(title,text){if(!text)return;if(navigator.share){try{await navigator.share({title,text});return}catch(e){if(e.name==='AbortError')return}}await copyText(text)}
async function copyText(t){try{await navigator.clipboard.writeText(t);alert('Copied!')}catch(e){prompt('Copy this:',t)}}
$('q-copy').onclick=()=>copyText($('q-out').textContent);$('q-share').onclick=()=>shareText('Invoice',$('q-out').textContent);

// hours
$('h-date').value=today();$('h-rate').value=LS.getItem('kp_rate')||'18.00';
function shiftHours(s){let[a,b]=[s.start,s.end].map(t=>{const[h,m]=t.split(':');return +h*60+ +m});if(b<=a)b+=1440;return Math.max(0,(b-a-(+s.brk||0))/60)}
function weekKey(d){const x=new Date(d+'T12:00');const dow=(x.getDay()+6)%7;x.setDate(x.getDate()-dow);return x.toISOString().slice(0,10)}
function renderHours(){const L=J('kp_hours',[]).filter(s=>s&&/^\d{4}-\d\d-\d\d$/.test(s.date)&&/^\d\d:\d\d$/.test(s.start)&&/^\d\d:\d\d$/.test(s.end)).sort((a,b)=>b.date.localeCompare(a.date)),wk={};L.forEach(s=>(wk[weekKey(s.date)]??=[]).push(s));
 $('h-list').innerHTML=Object.keys(wk).sort().reverse().map(k=>{const ss=wk[k];const hrs=ss.reduce((t,s)=>t+shiftHours(s),0);const reg=Math.min(hrs,40),ot=Math.max(hrs-40,0);
  const avg=ss.reduce((t,s)=>t+shiftHours(s)*s.rate,0)/(hrs||1);const pay=reg*avg+ot*avg*1.5;
  return `<div class="wk">Week of ${esc(k)}: ${hrs.toFixed(2)} h${ot?` (${ot.toFixed(2)} OT)`:''} · ${money(pay)}</div>`+ss.map(s=>`<div class="item"><span>${esc(s.date)} ${esc(s.start)}–${esc(s.end)}<br><small class="hint">${shiftHours(s).toFixed(2)} h @ ${money(s.rate)}</small></span><span>${money(shiftHours(s)*s.rate)} <button data-id="${esc(s.id)}">✕</button></span></div>`).join('')}).join('')||'<p class="hint">No shifts yet.</p>';
 $('h-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(confirm('Delete shift?')){S('kp_hours',J('kp_hours',[]).filter(s=>s.id!=b.dataset.id));renderHours()}})}
$('h-add').onclick=()=>{const s={id:Date.now(),date:$('h-date').value||today(),start:$('h-start').value,end:$('h-end').value,brk:+$('h-brk').value||0,rate:+$('h-rate').value||0};
 if(!s.start||!s.end)return alert('Enter start and end');LS.setItem('kp_rate',$('h-rate').value);const L=J('kp_hours',[]);L.push(s);S('kp_hours',L);renderHours()};
// budget
$('b-date').value=today();
function renderBudget(){const L=J('kp_budget',[]).filter(e=>e&&typeof e.date==='string'&&isFinite(e.amt)).sort((a,b)=>a.date.localeCompare(b.date)||a.id-b.id);let bal=0,inc=0,exp=0;
 const rows=L.map(e=>{const v=e.type==='in'?e.amt:-e.amt;bal+=v;e.type==='in'?inc+=e.amt:exp+=e.amt;return `<div class="item"><span>${esc(e.date)} ${esc(e.desc)}</span><span><b class="${e.type==='in'?'amt-in':'amt-out'}">${e.type==='in'?'+':'−'}${money(e.amt)}</b> <small class="hint" title="running balance">bal ${money(bal)}</small> <button data-id="${esc(e.id)}">✕</button></span></div>`});
 $('b-sum').innerHTML=`Balance <span class="${bal>=0?'amt-in':'amt-out'}" style="color:${bal>=0?'var(--ok)':'var(--bad)'}">${money(bal)}</span> · in ${money(inc)} · out ${money(exp)}`;
 $('b-list').innerHTML=rows.reverse().join('')||'<p class="hint">No entries yet.</p>';
 $('b-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(confirm('Delete entry?')){S('kp_budget',J('kp_budget',[]).filter(s=>s.id!=b.dataset.id));renderBudget()}})}
$('b-add').onclick=()=>{const amt=Math.abs(+$('b-amt').value);if(!amt)return alert('Enter an amount');const L=J('kp_budget',[]);L.push({id:Date.now(),type:$('b-type').value,amt,desc:$('b-desc').value||($('b-type').value==='in'?'Income':'Expense'),date:$('b-date').value||today()});S('kp_budget',L);$('b-amt').value='';$('b-desc').value='';renderBudget()};
// miles
$('m-date').value=today();$('m-rate').value=LS.getItem('kp_mrate')||'0.70';
function renderMiles(){const L=J('kp_miles',[]).filter(m=>m&&typeof m.date==='string'&&isFinite(m.mi)).map(m=>({...m,mi:+m.mi})).sort((a,b)=>b.date.localeCompare(a.date));const r=+$('m-rate').value||0;const tot=L.reduce((t,m)=>t+m.mi,0);const yr=new Date().getFullYear()+'';const ytd=L.filter(m=>m.date.startsWith(yr)).reduce((t,m)=>t+m.mi,0);
 $('m-sum').textContent=`Total ${tot.toFixed(1)} mi · ${yr}: ${ytd.toFixed(1)} mi ≈ ${money(ytd*r)} deduction`;
 $('m-list').innerHTML=L.map(m=>`<div class="item"><span>${esc(m.date)} ${esc(m.why)}</span><span>${(+m.mi||0).toFixed(1)} mi <button data-id="${esc(m.id)}">✕</button></span></div>`).join('')||'<p class="hint">No trips yet.</p>';
 $('m-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(confirm('Delete trip?')){S('kp_miles',J('kp_miles',[]).filter(s=>s.id!=b.dataset.id));renderMiles()}})}
$('m-rate').onchange=()=>{LS.setItem('kp_mrate',$('m-rate').value);renderMiles()};
$('m-add').onclick=()=>{const mi=+$('m-mi').value;if(!mi)return alert('Enter miles');const L=J('kp_miles',[]);L.push({id:Date.now(),date:$('m-date').value||today(),mi,why:$('m-why').value||'Trip'});S('kp_miles',L);$('m-mi').value='';$('m-why').value='';renderMiles()};
// calc
$('c-tipgo').onclick=async()=>{await pyReady;$('c-tipout').textContent=await pycall('tip_calc',$('c-bill').value,$('c-tip').value,$('c-ppl').value)};
$('c-ugo').onclick=async()=>{await pyReady;$('c-uout').textContent=await pycall('convert',$('c-val').value,$('c-unit').value)};
document.querySelectorAll('[data-snip]').forEach(b=>b.onclick=()=>{const s=SNIPPETS.find(x=>x.name.startsWith(b.dataset.snip));newScript(s.name+' ('+s.by+')',s.code);showView('v-code');run()});
function renderTools(){for(const f of [renderHours,renderBudget,renderMiles])try{f()}catch(e){console.error(e)}}

/* ---------- Fun (Python bits) ---------- */
const GUESS='import random\nsecret = random.randint(1, 100)\ntries = 0\nprint("I\'m thinking of a number from 1 to 100.")\nwhile True:\n    g = input("Your guess (q to quit): ").strip()\n    if g.lower() == "q":\n        print(f"It was {secret}."); break\n    if not g.isdigit():\n        print("Numbers only!"); continue\n    tries += 1\n    g = int(g)\n    if g < secret: print(f"{g}: higher ⬆️")\n    elif g > secret: print(f"{g}: lower ⬇️")\n    else:\n        print(f"🎉 {g} is right! {tries} tries."); break';
$('gu-go').onclick=()=>{$('gu-out').textContent='';runPy(GUESS,{target:$('gu-out')})};
$('eb-go').onclick=async()=>{const b=$('eb-ball');b.classList.remove('shake');void b.offsetWidth;b.classList.add('shake');$('eb-a').textContent='…';
 let a;try{await pyReady;a=await pycall('eight_ball');if(/^Error|busy/.test(a))throw 0}catch(e){a=['Yes.','No.','Ask again later.'][Math.random()*3|0]}setTimeout(()=>$('eb-a').textContent=a,500)};
const TU_DEFAULT='import turtle\nt = turtle.Turtle()\nt.bgcolor("#0b1020")\ncolors = ["#ff595e", "#ffca3a", "#8ac926", "#1982c4", "#6a4c93"]\nfor i in range(36):\n    t.color(colors[i % 5])\n    t.circle(80)\n    t.left(10)';
$('tu-code').value=LS.getItem('kp_turtle')||TU_DEFAULT;
$('tu-go').onclick=()=>{LS.setItem('kp_turtle',$('tu-code').value);const c=$('tu-c');c.width=c.height=640;clearT(c);runPy($('tu-code').value,{target:document.createElement('div'),turtle:c}).then(ok=>{if(!ok)alert('Turtle code error, check it in the Code tab')})};
$('tu-rand').onclick=()=>{const n=3+(Math.random()*6|0),a=360/n+(Math.random()*8-4).toFixed(1)*1;$('tu-code').value=`import turtle, random\nt = turtle.Turtle()\nt.bgcolor("#000")\nfor i in range(${60+(Math.random()*80|0)}):\n    t.color("#%02x%02x%02x" % (random.randint(80,255), random.randint(80,255), random.randint(80,255)))\n    t.forward(i * ${(1+Math.random()*2).toFixed(1)})\n    t.left(${a.toFixed(1)})`;$('tu-go').click()};

/* ---------- Files ---------- */
function renderFiles(){$('f-list').innerHTML=Object.keys(scripts).map(n=>`<div class="item"><span>${esc(n)}</span><span><button data-a="open">Open</button> <button data-a="dup">⧉</button> <button data-a="ren">✎</button> <button data-a="del">🗑</button></span></div>`).join('')||'<p class="hint">No scripts.</p>';
 $('f-list').querySelectorAll('.item').forEach((it,i)=>{const n=Object.keys(scripts)[i];it.querySelectorAll('button').forEach(b=>b.onclick=()=>{if(cur)scripts[cur]=cm.getValue();const a=b.dataset.a;
  if(a==='open'){cur=n;refresh();showView('v-code')}else if(a==='dup'){newScript(n+' copy',scripts[n]);renderFiles()}
  else if(a==='ren'){const m=prompt('New name',n);if(m&&m!==n&&!(m in scripts)){scripts[m]=scripts[n];delete scripts[n];if(cur===n)cur=m;refresh();renderFiles()}}
  else if(a==='del'&&confirm('Delete '+n+'?')){delete scripts[n];if(cur===n)cur='';refresh();renderFiles()}})})}
const cats=[...new Set(SNIPPETS.map(s=>s.cat))];$('sn-filter').innerHTML+=cats.map(c=>`<option>${esc(c)}</option>`).join('');
function renderSnips(){const f=$('sn-filter').value;$('snip-list').innerHTML=SNIPPETS.map((s,i)=>(!f||s.cat===f)?`<div class="snip"><b>${esc(s.name)}</b><span class="by">${s.by!=='KPython'?'🤖 by '+esc(s.by)+(s.cat!=='Team'?' · '+esc(s.cat):''):esc(s.cat)}</span><div class="row"><button data-i="${i}" data-a="open">Open</button><button data-i="${i}" data-a="run" class="pri">▶ Run</button></div></div>`:'').join('');
 $('snip-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{const s=SNIPPETS[b.dataset.i];newScript(s.name+(s.by!=='KPython'?' ('+s.by+')':''),s.code);showView('v-code');if(b.dataset.a==='run')run()})}
$('sn-filter').onchange=renderSnips;

/* backup */
const DATA_KEYS=['kp_sites','kp_hours','kp_budget','kp_miles','kp_rate','kp_mrate','kp_turtle','kp_hi','kp_pkgs'];
function exportData(){if(cur)scripts[cur]=cm.getValue();persist();const d={app:'KPython',version:2,exported:new Date().toISOString(),scripts,cur,data:{}};DATA_KEYS.forEach(k=>{const v=LS.getItem(k);if(v!==null)d.data[k]=v});return d}
$('bk-exp').onclick=async()=>{const bd=exportData();try{const h=await pycall('_kp_hist_dump');if(typeof h==='string'&&h.startsWith('{'))bd.history=JSON.parse(h)}catch(e){}const txt=JSON.stringify(bd,null,1),name=`kpython-backup-${today()}.json`;const file=new File([txt],name,{type:'application/json'});
 if(navigator.canShare&&navigator.canShare({files:[file]})){try{await navigator.share({files:[file],title:name});$('bk-msg').textContent='Shared '+name;return}catch(e){if(e.name==='AbortError')return}}
 const a=document.createElement('a');a.href=URL.createObjectURL(file);a.download=name;document.body.appendChild(a);a.click();a.remove();$('bk-msg').textContent='Downloaded '+name};
const VALID={kp_hours:x=>Array.isArray(x)&&x.every(s=>s&&/^\d{4}-\d\d-\d\d$/.test(s.date)&&/^\d\d:\d\d$/.test(s.start)&&/^\d\d:\d\d$/.test(s.end)&&isFinite(s.rate)&&isFinite(s.id)),
 kp_budget:x=>Array.isArray(x)&&x.every(e=>e&&/^\d{4}-\d\d-\d\d$/.test(e.date)&&['in','out'].includes(e.type)&&isFinite(e.amt)&&isFinite(e.id)&&typeof e.desc==='string'),
 kp_miles:x=>Array.isArray(x)&&x.every(m=>m&&/^\d{4}-\d\d-\d\d$/.test(m.date)&&isFinite(m.mi)&&isFinite(m.id)&&typeof m.why==='string'),
 kp_sites:x=>Array.isArray(x)&&kpCleanSites(x).length===x.length,
 kp_pkgs:x=>Array.isArray(x)&&x.every(p=>typeof p==='string'&&/^[\w.\-\[\]=<>]+$/.test(p))};
function validKey(k,v){if(typeof v!=='string')return false;if(!VALID[k])return true;try{return VALID[k](JSON.parse(v))}catch(e){return false}}
function importData(d){if(!d||d.app!=='KPython'||typeof d.scripts!=='object'||Array.isArray(d.scripts)||!Object.values(d.scripts).every(v=>typeof v==='string'))throw new Error('Not a valid KPython backup');
 scripts={...scripts,...d.scripts};cur=d.cur in scripts?d.cur:cur;const bad=[];Object.entries(d.data||{}).forEach(([k,v])=>{if(DATA_KEYS.includes(k)){if(validKey(k,v))LS.setItem(k,v);else bad.push(k)}});if(bad.length)alert('Skipped invalid data: '+bad.join(', '));refresh();renderTools();renderFiles();return Object.keys(d.scripts).length}
$('bk-imp').onclick=()=>$('bk-file').click();
$('bk-file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const d=JSON.parse(await f.text());if(!confirm('Import this backup? Scripts with the same name will be replaced and tool data overwritten.'))return;$('bk-msg').textContent=`Imported ${importData(d)} scripts + tool data.`;if(d.data&&'kp_sites'in d.data&&typeof applySites==='function')applySites('Imported Allowed sites');if(d.history&&typeof d.history==='object'){const n=await pycall('_kp_hist_load',JSON.stringify(d.history));$('bk-msg').textContent+=` ${+n||0} history files.`};toast2($('bk-msg').textContent)}catch(err){$('bk-msg').textContent='Import failed: '+err.message}e.target.value=''};
$('bk-reset').onclick=()=>{if(!confirm('Erase ALL scripts and tool data? (Your passcode stays.) Export a backup first!'))return;if(prompt('Type RESET to confirm')!=='RESET')return;
 DATA_KEYS.forEach(k=>LS.removeItem(k));scripts={...STARTERS};cur=Object.keys(scripts)[0];refresh();renderTools();renderFiles();$('bk-msg').textContent='All data reset.'};

refresh();renderTools();renderSnips();setupLock();
if('serviceWorker'in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('sw.js');
window.KP={exportData,importData,runPy,get pyReady(){return pyReady},stopPy,cm:()=>cm};
