/* KPython v8: Dev tab sections + command palette. Page-side UI only. */
(function(){
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const GROUPS=[
 ['check','✅ Check & test',['selftestall','lint','tests','cover','testgen','types','metrics','secrets','audit']],
 ['edit','✏️ Edit & refactor',['format','rename','refactor','docgen','search','savedrepl','merge','patch']],
 ['run','⏱ Run & measure',['cells','profile','bench','compare','bigo','memory','debug']],
 ['learn','📖 Understand & learn',['tour','examples','outline','explain','imports','markdown','help','cheats','katas']],
 ['data','🗄 Data, web & time',['sql','http','apis','data','json','chart','logs','time','regex','codec','convert','templates']],
 ['proj','📦 Projects & files',['projects','ghimport','packages','board','snap','history','pwgen']]];
function groupDev(){const dev=document.getElementById('v-dev');if(!dev||dev.dataset.grouped)return;dev.dataset.grouped=1;
 let open;try{open=JSON.parse(localStorage.getItem('kp_devopen')||'["check"]');if(!Array.isArray(open))open=['check']}catch(e){open=['check']}
 const all=$$('[data-dev]',dev);const used=new Set();const holder=document.createElement('div');holder.id='dev-groups';
 const mk=(id,title,btns)=>{if(!btns.length)return;const d=document.createElement('details');d.className='card devgrp';d.dataset.g=id;d.open=open.includes(id);
  const s=document.createElement('summary');s.textContent=`${title} (${btns.length})`;const g=document.createElement('div');g.className='g2';btns.forEach(b=>g.appendChild(b));d.append(s,g);
  d.addEventListener('toggle',()=>localStorage.setItem('kp_devopen',JSON.stringify($$('details.devgrp',holder).filter(x=>x.open).map(x=>x.dataset.g))));holder.appendChild(d)};
 for(const [id,title,keys] of GROUPS){const bs=keys.map(k=>all.find(b=>b.dataset.dev===k&&!used.has(b))).filter(Boolean);bs.forEach(b=>used.add(b));mk(id,title,bs)}
 mk('other','🧰 Other',all.filter(b=>!used.has(b)));
 dev.insertBefore(holder,dev.firstElementChild);
 $$('.card',dev).forEach(c=>{if(c.closest('#dev-groups'))return;$$('.g2',c).forEach(g=>{if(!g.children.length)g.remove()});
  if(c.querySelector('button,select,input,iframe,textarea,[id]'))return;const h=c.querySelector('.hint');if(h&&/By the team/.test(h.textContent)){const t=c.querySelector('h3');if(t)t.textContent='Credits'}else if(!c.textContent.replace(c.querySelector('h3')?.textContent||'','').trim())c.remove()})}
const ALIAS={cells:'cell notebook jupyter run all add delete reorder move',merge:'conflict three way 3-way',bench:'benchmark speed timeit compare',selftestall:'self test all check everything',tour:'start welcome intro getting started tutorial',examples:'example samples demo learn',ghimport:'github import clone download repo',help:'guide docs manual how',
 'bk-undo':'undo restore deleted trash recover','bk-reset':'wipe erase reset','pal-btn':'search',lint:'check errors style',format:'pretty indent black',packages:'pip install micropip',sites:'allowed network domains whitelist'};
function aliasOf(el){return ALIAS[el.dataset.dev]||ALIAS[el.id]||(/Update|Offline/i.test(el.textContent)?'update reload refresh version':'')}
function items(){const out=[];const seen=new Set();
 const add=(el,where,go)=>{const t=(el.textContent||el.title||'').replace(/\s+/g,' ').trim();if(!t||t.length>60)return;const k=where+'|'+t;if(seen.has(k))return;seen.add(k);out.push({t,where,go,a:aliasOf(el)})};
 $$('#tabs button').forEach(b=>add(b,'Tab',()=>b.click()));
 $$('section.view').forEach(v=>{const where=(document.querySelector(`#tabs [data-v="${v.id}"]`)?.textContent||v.id).replace(/[^\w ]/g,'').trim();
  $$('button',v).forEach(b=>{if(b.closest('.inrow')||b.disabled||b.hidden||b.closest('[hidden]'))return;add(b,where,()=>{showView(v.id);const d=b.closest('details');if(d)d.open=true;
   const card=b.closest('.tool');if(card&&card.id&&!b.dataset.t){const chip=document.querySelector(`[data-t="${card.id}"]`);if(chip&&!card.classList.contains('on'))chip.click()}
   setTimeout(()=>{b.scrollIntoView({block:'center'});b.click()},60)})})});
 out.push({t:'Check for KPython update',where:'App',a:'update reload refresh version new',go:()=>{const u=document.getElementById('updbar');if(u){u.click();return}navigator.serviceWorker?.getRegistration().then(r=>r&&r.update()).then(()=>{const s=document.getElementById('offstat');alert('Checked for updates. '+(document.getElementById('updbar')?'An update is ready: tap the bar to reload.':'Status: '+(s?s.textContent:'')))})}});
 return out}
function score(q,t){q=q.toLowerCase();t=t.toLowerCase();if(!q)return 1;const i=t.indexOf(q);if(i>=0)return 1000-i;
 // every word of the query must appear; otherwise a tight fuzzy match (small gaps only) to avoid noise
 const ws=q.split(/\s+/).filter(Boolean);if(ws.length>1&&ws.every(w=>t.includes(w)))return 800;
 let s=0,j=0,run=0,gap=0;for(const c of q){if(c===' ')continue;const k=t.indexOf(c,j);if(k<0)return 0;if(j>0)gap+=k-j;run=k===j?run+1:0;s+=10+run*5-Math.min(k-j,9);j=k+1}
 return gap>q.length?0:s}
let pal,list,inp,cur=[],sel=0;
function render(){const q=inp.value.trim();cur=items().map(x=>({...x,s:Math.max(score(q,x.t),score(q,x.where+' '+x.t)*0.8,x.a?score(q,x.a)*0.9:0)})).filter(x=>x.s>0).sort((a,b)=>b.s-a.s).slice(0,40);sel=0;
 list.textContent='';cur.forEach((x,i)=>{const li=document.createElement('li');if(i===sel)li.className='on';const a=document.createElement('span');a.textContent=x.t;const w=document.createElement('small');w.textContent=x.where;li.append(a,w);li.onclick=()=>launch(i);list.appendChild(li)});
 if(!cur.length){const li=document.createElement('li');li.className='none';li.textContent='No match';list.appendChild(li)}}
function hl(){[...list.children].forEach((li,i)=>li.classList.toggle('on',i===sel));list.children[sel]?.scrollIntoView({block:'nearest'})}
function launch(i){const x=cur[i];if(!x||locked()){close();return}close();x.go()}
function locked(){const l=document.getElementById('lock');return l&&!l.hidden&&getComputedStyle(l).display!=='none'}
function openPal(){if(locked())return;pal.hidden=false;inp.value='';inp.focus();render()}
function close(){pal.hidden=true}
function build(){pal=document.createElement('div');pal.id='pal';pal.hidden=true;
 const box=document.createElement('div');box.className='pal-box';box.setAttribute('role','dialog');box.setAttribute('aria-label','Command palette');
 inp=document.createElement('input');inp.id='pal-in';inp.placeholder='Search every tool and button… (lint, sites, merge)';inp.autocomplete='off';inp.setAttribute('autocapitalize','off');inp.spellcheck=false;
 list=document.createElement('ul');list.id='pal-list';const h=document.createElement('p');h.className='hint';h.textContent='↑↓ move · Enter opens · Esc closes';
 box.append(inp,list,h);pal.appendChild(box);document.body.appendChild(pal);
 inp.oninput=render;inp.onkeydown=e=>{if(e.key==='ArrowDown'){sel=Math.min(sel+1,cur.length-1);hl();e.preventDefault()}else if(e.key==='ArrowUp'){sel=Math.max(sel-1,0);hl();e.preventDefault()}else if(e.key==='Enter'){launch(sel);e.preventDefault()}else if(e.key==='Escape')close()};
 pal.onclick=e=>{if(e.target===pal)close()};
 const b=document.createElement('button');b.id='pal-btn';b.title='Search tools (Ctrl/⌘+K)';b.textContent='🔎';const lk=document.getElementById('lockbtn');lk.parentNode.insertBefore(b,lk);b.onclick=openPal;
 document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();pal.hidden?openPal():close()}})}
groupDev();build();window.addEventListener('kp-lock',()=>{if(pal)close()});window.kpPalette={open:openPal,close,items,score};
})();
