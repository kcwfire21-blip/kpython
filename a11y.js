/* KPython v9: accessibility pass (bot2help r7 review). Adds names, roles and live regions without changing behavior. */
(function(){
const L={pin:'Passcode',sel:'Open script','f-q':'Find','f-r':'Replace with','r-in':'Python console input',pkgname:'Package name','d-q':'Help topic','gh-tok':'GitHub personal access token','st-in':'Site URL to allow','eb-q':'Your yes/no question','tu-code':'Turtle code','dv-a':'First script','dv-b':'Second script','sn-filter':'Filter snippets by category',
 new:'New script',save:'Save script',snipbtn:'Snippets','f-prev':'Previous match','f-next':'Next match','f-x':'Close find bar',clr:'Clear output','r-up':'Previous command','r-down':'Next command','r-clr':'Clear console',stopbtn:'Stop Python',lockbtn:'Lock app','e-find':'Find and replace','e-goto':'Go to line','e-fsm':'Smaller text','e-fsp':'Bigger text','e-wrap':'Word wrap','e-imp':'Import .py file','e-share':'Export this file','pal-btn':'Search tools'};
for(const [id,n] of Object.entries(L)){const e=document.getElementById(id);if(e&&!e.getAttribute('aria-label'))e.setAttribute('aria-label',n)}
const pin=document.getElementById('pin');if(pin&&!pin.placeholder)pin.placeholder='Passcode';
const D={u:'Up',l:'Left',d:'Down',r:'Right'};document.querySelectorAll('.dpad button[data-d]').forEach(b=>b.setAttribute('aria-label',D[b.dataset.d]||b.dataset.d));
document.querySelectorAll('.dpad').forEach(d=>{d.setAttribute('role','group');d.setAttribute('aria-label','Game controls')});
const LOG={out:'Program output','r-out':'Console output','dv-out':'Dev tool output'};
for(const [id,n] of Object.entries(LOG)){const e=document.getElementById(id);if(e){e.setAttribute('role','log');e.setAttribute('aria-live','polite');e.setAttribute('aria-label',n)}}
['pystat','f-msg','gh-msg','st-msg','bk-msg'].forEach(id=>{const e=document.getElementById(id);if(e)e.setAttribute('role','status')});
const lm=document.getElementById('lmsg');if(lm)lm.setAttribute('role','alert');
['q-out','c-tipout','c-uout','gu-out','d-out'].forEach(id=>{const e=document.getElementById(id);if(e)e.setAttribute('aria-live','polite')});
const canv={'sn-c':'Snake game board','g2-c':'2048 game board','tu-c':'Turtle drawing'};for(const [id,n] of Object.entries(canv)){const e=document.getElementById(id);if(e){e.setAttribute('role','img');e.setAttribute('aria-label',n)}}
const tabs=document.getElementById('tabs');if(tabs){tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Sections');const sync=()=>tabs.querySelectorAll('button').forEach(b=>{b.setAttribute('role','tab');b.setAttribute('aria-selected',b.classList.contains('on')?'true':'false')});sync();new MutationObserver(sync).observe(tabs,{subtree:true,attributes:true,attributeFilter:['class']})}
const gs=document.getElementById('go-scan');if(gs){gs.setAttribute('role','button')}
try{const cm=window.KP&&KP.cm&&KP.cm();if(cm)cm.getInputField().setAttribute('aria-label','Python code editor')}catch(e){}
// input() rows: name the field after its prompt; toast is a status
new MutationObserver(ms=>{for(const m of ms)for(const n of m.addedNodes){if(n.nodeType!==1)continue;
 const i=n.matches?.('.inrow')?n.querySelector('input'):null;if(i&&!i.getAttribute('aria-label')){const prev=(n.previousSibling&&n.previousSibling.textContent||'').trim().split('\n').pop();i.setAttribute('aria-label',prev?('Answer: '+prev.slice(-80)):'Answer for input()')}
 if(n.id==='toast'){n.setAttribute('role','status')}}}).observe(document.body,{subtree:true,childList:true});
const t=document.getElementById('toast');if(t)t.setAttribute('role','status');
// lock screen: focus the passcode and make the rest inert while locked
const lock=document.getElementById('lock');if(lock){const upd=()=>{const on=!lock.hidden&&getComputedStyle(lock).display!=='none';['main','#top','#tabs'].forEach(s=>{const e=document.querySelector(s);if(e)e.inert=on});if(on&&pin)setTimeout(()=>pin.focus(),50)};upd();new MutationObserver(upd).observe(lock,{attributes:true,attributeFilter:['hidden','class','style']})}
})();
