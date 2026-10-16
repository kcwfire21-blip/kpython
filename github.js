// GitHub panel. The token lives ONLY in this closure: not on window, not in storage, so Python's `js` module can't reach it.
(()=>{const F=window.fetch.bind(window),API='https://api.github.com';let token=null,sha=null,curFile=null;
const msg=t=>$('gh-msg').textContent=t;
function setStatus(user){$('gh-status').textContent=token?`Logged in as ${user||'?'} (token in memory only)`:'Not logged in. Public repos can be read without logging in.';$('gh-logout').hidden=!token;$('gh-logbox').style.display=token?'none':''}
function logout(){token=null;setStatus();msg('Logged out. Token wiped from memory.')}
window.addEventListener('kp-lock',()=>{if(token)logout()});
async function gh(path,opt={}){const h={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};if(token)h.Authorization='Bearer '+token;
 const r=await F(API+path,{...opt,headers:{...h,...(opt.headers||{})},cache:'no-store'});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error((d.message||r.status)+(r.status===401?' (bad or expired token)':''));return d}
$('gh-login').onclick=async()=>{const t=$('gh-tok').value.trim();$('gh-tok').value='';if(!t)return;token=t;msg('Checking token…');
 try{const me=await gh('/user');setStatus(me.login);msg('Logged in.')}catch(e){token=null;setStatus();msg('Login failed: '+e.message)}};
$('gh-logout').onclick=logout;
const repo=()=>{const r=$('gh-repo').value.trim().replace(/^https?:\/\/github\.com\//,'').replace(/\.git$/,'').replace(/\/+$/,'');if(!/^[\w.-]+\/[\w.-]+$/.test(r))throw new Error('Repo must look like owner/repo');return r};
const enc=p=>p.split('/').filter(Boolean).map(encodeURIComponent).join('/');
const ref=()=>$('gh-br').value.trim()?'?ref='+encodeURIComponent($('gh-br').value.trim()):'';
const b64d=b=>new TextDecoder().decode(Uint8Array.from(atob(b.replace(/\n/g,'')),c=>c.charCodeAt(0)));
const b64e=t=>{const u=new TextEncoder().encode(t);let s='';u.forEach(c=>s+=String.fromCharCode(c));return btoa(s)};
function showFile(on){$('gh-file').style.display=on?'block':'none';$('gh-fileacts').style.display=on?'flex':'none'}
async function open(){try{const r=repo(),p=$('gh-path').value.trim();msg('Loading…');if(!$('gh-br').value.trim()){const info=await gh('/repos/'+r);$('gh-br').value=info.default_branch}
 const d=await gh(`/repos/${r}/contents/${enc(p)}${ref()}`);
 if(Array.isArray(d)){showFile(false);curFile=null;d.sort((a,b)=>(a.type!=='dir')-(b.type!=='dir')||a.name.localeCompare(b.name));
  $('gh-list').innerHTML=d.map((it,i)=>`<div class="item"><span>${it.type==='dir'?'📁':'📄'} ${esc(it.name)}</span><button data-i="${i}">Open</button></div>`).join('')||'<p class="hint">Empty folder</p>';
  $('gh-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{$('gh-path').value=d[b.dataset.i].path;open()});msg(`${d.length} items`)}
 else{$('gh-list').innerHTML='';if(d.size>1e6)throw new Error('File too large to open here');$('gh-file').value=d.encoding==='base64'?b64d(d.content):'';sha=d.sha;curFile=d.path;showFile(true);msg(`${d.path} (${d.size} bytes)`)}}
 catch(e){if(/Not Found/.test(e.message)&&$('gh-path').value.trim()){showFile(true);$('gh-list').innerHTML='';$('gh-file').value='';sha=null;curFile=$('gh-path').value.trim();msg('Not found. Write content and Push to create this file.')}else msg('Error: '+e.message)}}
$('gh-open').onclick=open;$('gh-up').onclick=()=>{$('gh-path').value=$('gh-path').value.split('/').slice(0,-1).join('/');open()};
$('gh-toed').onclick=()=>{newScript(curFile.split('/').pop(),$('gh-file').value);showView('v-code')};
$('gh-fromed').onclick=()=>{$('gh-file').value=cm.getValue();msg('Loaded current script "'+cur+'" into the box. Push to save it to GitHub.')};
$('gh-run').onclick=()=>{if(!confirm(`Run downloaded file "${curFile}" from ${$('gh-repo').value}?\n\nOnly run code you trust.`))return;newScript(curFile.split('/').pop(),$('gh-file').value);showView('v-code');run()};
$('gh-push').onclick=async()=>{try{if(!token)throw new Error('Log in first');const r=repo(),p=($('gh-path').value.trim()||curFile||'').replace(/^\/+/,'');if(!p||p.endsWith('/'))throw new Error('Enter a file path');
 const br=$('gh-br').value.trim();if(!br)throw new Error('Open the repo first so the branch is known');
 const ans=prompt(`PUSH TO GITHUB\n\nRepo:   ${r}\nPath:   ${p}\nBranch: ${br}\n${sha&&p===curFile?'Updates the existing file.':'Creates a new file (or fails if it already exists).'}\n\nType yes to push:`);
 if((ans||'').trim().toLowerCase()!=='yes'){msg('Push cancelled.');return}
 const body={message:`Edit ${p} from KPython`,content:b64e($('gh-file').value),branch:br};if(sha&&p===curFile)body.sha=sha;
 const d=await gh(`/repos/${r}/contents/${enc(p)}`,{method:'PUT',body:JSON.stringify(body)});sha=d.content.sha;curFile=p;msg('✅ Pushed '+p+' ('+d.commit.sha.slice(0,7)+')')}
 catch(e){msg('Push failed: '+e.message)}};
setStatus();})();
