const $=id=>document.getElementById(id),LS=localStorage;
const J=(k,d)=>{try{const v=JSON.parse(LS.getItem(k));return v??d}catch(e){return d}},S=(k,v)=>LS.setItem(k,JSON.stringify(v));
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=n=>'$'+(+n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
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
let dirtyT;cm.on('change',()=>{clearTimeout(dirtyT);dirtyT=setTimeout(()=>{if(cur){scripts[cur]=cm.getValue();persist()}},600)});
function refresh(){if(!(cur in scripts))cur=Object.keys(scripts)[0]||'';$('sel').innerHTML=Object.keys(scripts).map(n=>`<option>${esc(n)}</option>`).join('');$('sel').value=cur;cm.setValue(scripts[cur]||'');cm.clearHistory();persist()}
$('sel').onchange=()=>{scripts[cur]=cm.getValue();cur=$('sel').value;refresh()};
$('save').onclick=()=>{if(!cur)return $('new').click();scripts[cur]=cm.getValue();persist();log('Saved '+cur,'sys')};
function newScript(name,code){let n=name,i=2;while(n in scripts)n=name+' '+i++;if(cur)scripts[cur]=cm.getValue();scripts[n]=code;cur=n;refresh();return n}
$('new').onclick=()=>{const n=prompt('Script name?');if(n)newScript(n,'print("hi")\n')};
$('snipbtn').onclick=()=>{showView('v-files');setTimeout(()=>$('snip-list').scrollIntoView({behavior:'smooth'}),50)};

/* keybar */
const KEYS=[['⇥','    '],[':',':'],['( )','()',1],['[ ]','[]',1],['{ }','{}',1],['" "','""',1],["' '","''",1],['=','='],['#','# '],['.','.'],[',',','],['←','L'],['→','R'],['↶','U']];
$('keybar').innerHTML=KEYS.map((k,i)=>`<button data-i="${i}">${k[0]}</button>`).join('');
$('keybar').querySelectorAll('button').forEach(b=>{b.addEventListener('mousedown',e=>e.preventDefault());b.addEventListener('touchstart',e=>{e.preventDefault();b.click()},{passive:false});b.onclick=()=>{const k=KEYS[b.dataset.i];
 if(k[1]==='L')cm.execCommand('goCharLeft');else if(k[1]==='R')cm.execCommand('goCharRight');else if(k[1]==='U')cm.undo();
 else{const sel=cm.getSelection();if(k[2]&&sel){cm.replaceSelection(k[1][0]+sel+k[1][1])}else{cm.replaceSelection(k[1]);if(k[2])cm.execCommand('goCharLeft')}}cm.focus()}});
function placeKeybar(){const kb=$('keybar'),vv=window.visualViewport;if(cm.hasFocus()&&vv&&window.innerHeight-vv.height>120){kb.classList.add('float');kb.style.top=(vv.offsetTop+vv.height-kb.offsetHeight)+'px'}else{kb.classList.remove('float');kb.style.top=''}}
cm.on('focus',()=>setTimeout(placeKeybar,300));cm.on('blur',()=>setTimeout(placeKeybar,100));if(window.visualViewport){visualViewport.addEventListener('resize',placeKeybar);visualViewport.addEventListener('scroll',placeKeybar)}

/* ---------- output ---------- */
let outEl=null;
function log(t,c){const o=outEl||$('out');const s=document.createElement('span');if(c)s.className=c;s.textContent=t+'\n';o.appendChild(s);if(!outEl)s.scrollIntoView({block:'nearest'})}
window.kpShowImg=b64=>{const i=new Image();i.src='data:image/png;base64,'+b64;(outEl||$('out')).appendChild(i)};
$('clr').onclick=()=>$('out').textContent='';

/* turtle target */
let tuCanvas=null;
window.kpT=(op,...a)=>{if(!tuCanvas){tuCanvas=document.createElement('canvas');tuCanvas.width=600;tuCanvas.height=600;tuCanvas.style.background='#010409';(outEl||$('out')).appendChild(tuCanvas);clearT(tuCanvas)}
 const c=tuCanvas,x=c.getContext('2d'),W=c.width/2,H=c.height/2,sc=c.width/400;const P=(px,py)=>[W+px*sc,H-py*sc];
 if(op==='reset'||op==='clear')clearT(c);else if(op==='bg'){c.dataset.bg=a[0];clearT(c)}
 else if(op==='line'){x.strokeStyle=a[4];x.lineWidth=a[5]*sc;x.lineCap='round';x.beginPath();x.moveTo(...P(a[0],a[1]));x.lineTo(...P(a[2],a[3]));x.stroke()}
 else if(op==='dot'){x.fillStyle=a[3];x.beginPath();x.arc(...P(a[0],a[1]),a[2]*sc/2,0,7);x.fill()}
 else if(op==='text'){x.fillStyle=a[3];x.font=(16*sc)+'px sans-serif';x.fillText(a[2],...P(a[0],a[1]))}};
function clearT(c){const x=c.getContext('2d');x.fillStyle=c.dataset.bg||'#010409';x.fillRect(0,0,c.width,c.height)}

/* ---------- Python ---------- */

let py=null,running=false;
const pyReady=(async()=>{try{py=await loadPyodide();py.setStdout({batched:t=>log(t)});py.setStderr({batched:t=>log(t,'err')});
 await py.runPythonAsync(await (await fetch('kp_setup.py')).text());
 $('run').disabled=false;$('run').textContent='▶ Run';$('pystat').textContent='Python '+py.version;$('pystat').classList.add('ok');log('Python '+py.version+' ready','sys');
 $('c-unit').innerHTML=py.runPython('list(UNITS)').toJs().map(k=>`<option>${k}</option>`).join('');return py}
 catch(e){$('run').textContent='Python failed to load';$('pystat').textContent='Python offline';log(String(e),'err');throw e}})();
async function runPy(code,{target=null,turtle=null}={}){await pyReady;if(running){toast('Python is busy');return}running=true;
 outEl=target;tuCanvas=turtle;try{py.globals.get('_kp_reset_turtle')();
  try{await py.loadPackagesFromImports(code,{messageCallback:m=>log(m,'sys')})}catch(e){log('Package load: '+e.message,'err')}
  if(/matplotlib/.test(code)){await py.runPythonAsync('import matplotlib');py.globals.get('_kp_mpl_patch')()}
  const ns=py.globals.get('dict')();ns.set('__name__','__main__');
  const r=await py.runPythonAsync(code,{globals:ns});if(r!==undefined&&r!==null&&!(r.destroy))log(String(r));
  if(/matplotlib/.test(code))py.globals.get('_kp_show')();ns.destroy();return true}
 catch(e){const m=String(e.message||e).trim();log(/KeyboardInterrupt: input cancelled/.test(m)?'⏹ Stopped (input cancelled)':m,'err');return false}
 finally{try{py.runPython('import sys;sys.stdout.flush();sys.stderr.flush()')}catch(e){}outEl=null;tuCanvas=null;running=false}}
async function run(){scripts[cur]=cm.getValue();persist();log('— run '+cur+' —','sys');$('run').disabled=true;const t0=performance.now();
 const ok=await runPy(cm.getValue());log(`— ${ok?'done':'error'} in ${((performance.now()-t0)/1000).toFixed(2)}s —`,'sys');$('run').disabled=false}
$('run').onclick=run;
function pycall(name,...a){return py.globals.get(name)(...a)}
function toast(t){log(t,'sys')}

/* packages */
async function installPkg(name){name=name.trim();if(!name)return;showView('v-code');log('Installing '+name+'…','sys');await pyReady;
 try{if(['numpy','pandas','matplotlib','scipy','sympy','scikit-learn','pillow'].includes(name.toLowerCase()))await py.loadPackage(name.toLowerCase(),{messageCallback:m=>log(m,'sys')});
  else{await py.loadPackage('micropip');const mp=py.pyimport('micropip');await mp.install(name);mp.destroy()}
  log('✅ '+name+' installed. import it in your script.','sys');const l=J('kp_pkgs',[]);if(!l.includes(name)){l.push(name);S('kp_pkgs',l)}}
 catch(e){log('❌ '+name+': '+String(e.message||e).split('\n').slice(-2).join(' '),'err')}}
$('pkginst').onclick=()=>installPkg($('pkgname').value);
document.querySelectorAll('.qp').forEach(b=>b.onclick=()=>installPkg(b.dataset.p));

/* ---------- Tools ---------- */
const EXTRAS=["Windows (interior)",40,"Fridge / microwave",25,"Restroom deep clean",35,"Carpet vacuum deep",30,"Trash haul-away",20,"Floor mop & shine",45];
let exH='';for(let i=0;i<EXTRAS.length;i+=2)exH+=`<label><input type="checkbox" value="${EXTRAS[i]}">${EXTRAS[i]} +$${EXTRAS[i+1]}</label>`;$('q-extras').innerHTML=exH;
$('q-go').onclick=async()=>{await pyReady;const ex=[...$('q-extras').querySelectorAll('input:checked')].map(i=>i.value);
 $('q-out').textContent=pycall('make_invoice',$('q-client').value,$('q-sqft').value,$('q-rate').value,$('q-freq').value,JSON.stringify(ex),$('q-notes').value)};
async function shareText(title,text){if(!text)return;if(navigator.share){try{await navigator.share({title,text});return}catch(e){if(e.name==='AbortError')return}}await copyText(text)}
async function copyText(t){try{await navigator.clipboard.writeText(t);alert('Copied!')}catch(e){prompt('Copy this:',t)}}
$('q-copy').onclick=()=>copyText($('q-out').textContent);$('q-share').onclick=()=>shareText('Invoice',$('q-out').textContent);

// hours
$('h-date').value=today();$('h-rate').value=LS.getItem('kp_rate')||'18.00';
function shiftHours(s){let[a,b]=[s.start,s.end].map(t=>{const[h,m]=t.split(':');return +h*60+ +m});if(b<=a)b+=1440;return Math.max(0,(b-a-(+s.brk||0))/60)}
function weekKey(d){const x=new Date(d+'T12:00');const dow=(x.getDay()+6)%7;x.setDate(x.getDate()-dow);return x.toISOString().slice(0,10)}
function renderHours(){const L=J('kp_hours',[]).sort((a,b)=>b.date.localeCompare(a.date)),wk={};L.forEach(s=>(wk[weekKey(s.date)]??=[]).push(s));
 $('h-list').innerHTML=Object.keys(wk).sort().reverse().map(k=>{const ss=wk[k];const hrs=ss.reduce((t,s)=>t+shiftHours(s),0);const reg=Math.min(hrs,40),ot=Math.max(hrs-40,0);
  const avg=ss.reduce((t,s)=>t+shiftHours(s)*s.rate,0)/(hrs||1);const pay=reg*avg+ot*avg*1.5;
  return `<div class="wk">Week of ${k}: ${hrs.toFixed(2)} h${ot?` (${ot.toFixed(2)} OT)`:''} · ${money(pay)}</div>`+ss.map(s=>`<div class="item"><span>${s.date} ${s.start}–${s.end}<br><small class="hint">${shiftHours(s).toFixed(2)} h @ ${money(s.rate)}</small></span><span>${money(shiftHours(s)*s.rate)} <button data-id="${s.id}">✕</button></span></div>`).join('')}).join('')||'<p class="hint">No shifts yet.</p>';
 $('h-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(confirm('Delete shift?')){S('kp_hours',J('kp_hours',[]).filter(s=>s.id!=b.dataset.id));renderHours()}})}
$('h-add').onclick=()=>{const s={id:Date.now(),date:$('h-date').value||today(),start:$('h-start').value,end:$('h-end').value,brk:+$('h-brk').value||0,rate:+$('h-rate').value||0};
 if(!s.start||!s.end)return alert('Enter start and end');LS.setItem('kp_rate',$('h-rate').value);const L=J('kp_hours',[]);L.push(s);S('kp_hours',L);renderHours()};
// budget
$('b-date').value=today();
function renderBudget(){const L=J('kp_budget',[]).sort((a,b)=>a.date.localeCompare(b.date)||a.id-b.id);let bal=0,inc=0,exp=0;
 const rows=L.map(e=>{const v=e.type==='in'?e.amt:-e.amt;bal+=v;e.type==='in'?inc+=e.amt:exp+=e.amt;return `<div class="item"><span>${e.date} ${esc(e.desc)}</span><span><b class="${e.type==='in'?'amt-in':'amt-out'}">${e.type==='in'?'+':'−'}${money(e.amt)}</b> <small class="hint">${money(bal)}</small> <button data-id="${e.id}">✕</button></span></div>`});
 $('b-sum').innerHTML=`Balance <span class="${bal>=0?'amt-in':'amt-out'}" style="color:${bal>=0?'var(--ok)':'var(--bad)'}">${money(bal)}</span> · in ${money(inc)} · out ${money(exp)}`;
 $('b-list').innerHTML=rows.reverse().join('')||'<p class="hint">No entries yet.</p>';
 $('b-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(confirm('Delete entry?')){S('kp_budget',J('kp_budget',[]).filter(s=>s.id!=b.dataset.id));renderBudget()}})}
$('b-add').onclick=()=>{const amt=Math.abs(+$('b-amt').value);if(!amt)return alert('Enter an amount');const L=J('kp_budget',[]);L.push({id:Date.now(),type:$('b-type').value,amt,desc:$('b-desc').value||($('b-type').value==='in'?'Income':'Expense'),date:$('b-date').value||today()});S('kp_budget',L);$('b-amt').value='';$('b-desc').value='';renderBudget()};
// miles
$('m-date').value=today();$('m-rate').value=LS.getItem('kp_mrate')||'0.70';
function renderMiles(){const L=J('kp_miles',[]).sort((a,b)=>b.date.localeCompare(a.date));const r=+$('m-rate').value||0;const tot=L.reduce((t,m)=>t+m.mi,0);const yr=new Date().getFullYear()+'';const ytd=L.filter(m=>m.date.startsWith(yr)).reduce((t,m)=>t+m.mi,0);
 $('m-sum').textContent=`Total ${tot.toFixed(1)} mi · ${yr}: ${ytd.toFixed(1)} mi ≈ ${money(ytd*r)} deduction`;
 $('m-list').innerHTML=L.map(m=>`<div class="item"><span>${m.date} ${esc(m.why)}</span><span>${m.mi.toFixed(1)} mi <button data-id="${m.id}">✕</button></span></div>`).join('')||'<p class="hint">No trips yet.</p>';
 $('m-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(confirm('Delete trip?')){S('kp_miles',J('kp_miles',[]).filter(s=>s.id!=b.dataset.id));renderMiles()}})}
$('m-rate').onchange=()=>{LS.setItem('kp_mrate',$('m-rate').value);renderMiles()};
$('m-add').onclick=()=>{const mi=+$('m-mi').value;if(!mi)return alert('Enter miles');const L=J('kp_miles',[]);L.push({id:Date.now(),date:$('m-date').value||today(),mi,why:$('m-why').value||'Trip'});S('kp_miles',L);$('m-mi').value='';$('m-why').value='';renderMiles()};
// calc
$('c-tipgo').onclick=async()=>{await pyReady;$('c-tipout').textContent=pycall('tip_calc',$('c-bill').value,$('c-tip').value,$('c-ppl').value)};
$('c-ugo').onclick=async()=>{await pyReady;$('c-uout').textContent=pycall('convert',$('c-val').value,$('c-unit').value)};
document.querySelectorAll('[data-snip]').forEach(b=>b.onclick=()=>{const s=SNIPPETS.find(x=>x.name.startsWith(b.dataset.snip));newScript(s.name+' ('+s.by+')',s.code);showView('v-code');run()});
function renderTools(){renderHours();renderBudget();renderMiles()}

/* ---------- Fun (Python bits) ---------- */
const GUESS='import random\nsecret = random.randint(1, 100)\ntries = 0\nprint("I\'m thinking of a number from 1 to 100.")\nwhile True:\n    g = input("Your guess (q to quit): ").strip()\n    if g.lower() == "q":\n        print(f"It was {secret}."); break\n    if not g.isdigit():\n        print("Numbers only!"); continue\n    tries += 1\n    g = int(g)\n    if g < secret: print(f"{g}: higher ⬆️")\n    elif g > secret: print(f"{g}: lower ⬇️")\n    else:\n        print(f"🎉 {g} is right! {tries} tries."); break';
$('gu-go').onclick=()=>{$('gu-out').textContent='';runPy(GUESS,{target:$('gu-out')})};
$('eb-go').onclick=async()=>{const b=$('eb-ball');b.classList.remove('shake');void b.offsetWidth;b.classList.add('shake');$('eb-a').textContent='…';
 let a;try{await pyReady;a=pycall('eight_ball')}catch(e){a=['Yes.','No.','Ask again later.'][Math.random()*3|0]}setTimeout(()=>$('eb-a').textContent=a,500)};
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
const cats=[...new Set(SNIPPETS.map(s=>s.cat))];$('sn-filter').innerHTML+=cats.map(c=>`<option>${c}</option>`).join('');
function renderSnips(){const f=$('sn-filter').value;$('snip-list').innerHTML=SNIPPETS.map((s,i)=>(!f||s.cat===f)?`<div class="snip"><b>${esc(s.name)}</b><span class="by">${s.by!=='KPython'?'🤖 by '+esc(s.by)+(s.cat!=='Team'?' · '+esc(s.cat):''):esc(s.cat)}</span><div class="row"><button data-i="${i}" data-a="open">Open</button><button data-i="${i}" data-a="run" class="pri">▶ Run</button></div></div>`:'').join('');
 $('snip-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{const s=SNIPPETS[b.dataset.i];newScript(s.name+(s.by!=='KPython'?' ('+s.by+')':''),s.code);showView('v-code');if(b.dataset.a==='run')run()})}
$('sn-filter').onchange=renderSnips;

/* backup */
const DATA_KEYS=['kp_hours','kp_budget','kp_miles','kp_rate','kp_mrate','kp_turtle','kp_hi','kp_pkgs'];
function exportData(){if(cur)scripts[cur]=cm.getValue();persist();const d={app:'KPython',version:2,exported:new Date().toISOString(),scripts,cur,data:{}};DATA_KEYS.forEach(k=>{const v=LS.getItem(k);if(v!==null)d.data[k]=v});return d}
$('bk-exp').onclick=async()=>{const txt=JSON.stringify(exportData(),null,1),name=`kpython-backup-${today()}.json`;const file=new File([txt],name,{type:'application/json'});
 if(navigator.canShare&&navigator.canShare({files:[file]})){try{await navigator.share({files:[file],title:name});$('bk-msg').textContent='Shared '+name;return}catch(e){if(e.name==='AbortError')return}}
 const a=document.createElement('a');a.href=URL.createObjectURL(file);a.download=name;document.body.appendChild(a);a.click();a.remove();$('bk-msg').textContent='Downloaded '+name};
function importData(d){if(!d||d.app!=='KPython'||typeof d.scripts!=='object')throw new Error('Not a KPython backup');
 scripts={...scripts,...d.scripts};cur=d.cur in scripts?d.cur:cur;Object.entries(d.data||{}).forEach(([k,v])=>{if(DATA_KEYS.includes(k))LS.setItem(k,v)});refresh();renderTools();renderFiles();return Object.keys(d.scripts).length}
$('bk-imp').onclick=()=>$('bk-file').click();
$('bk-file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const d=JSON.parse(await f.text());if(!confirm('Import this backup? Scripts with the same name will be replaced and tool data overwritten.'))return;$('bk-msg').textContent=`Imported ${importData(d)} scripts + tool data.`}catch(err){$('bk-msg').textContent='Import failed: '+err.message}e.target.value=''};
$('bk-reset').onclick=()=>{if(!confirm('Erase ALL scripts and tool data? (Your passcode stays.) Export a backup first!'))return;if(prompt('Type RESET to confirm')!=='RESET')return;
 DATA_KEYS.forEach(k=>LS.removeItem(k));scripts={...STARTERS};cur=Object.keys(scripts)[0];refresh();renderTools();renderFiles();$('bk-msg').textContent='All data reset.'};

refresh();renderTools();renderSnips();setupLock();
if('serviceWorker'in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('sw.js');
window.KP={exportData,importData,runPy,pyReady};
