// KPython allowed-sites validator, shared by the page and the service worker.
// Returns {origin, kind} where kind is 'ok' | 'ip' | 'local' (localhost / Tailscale 100.64.0.0/10), or {error}.
const KP_SITES_MAX=50;
// Shared hosting suffixes: anyone can get a subdomain, so *.<suffix> would allow strangers' sites.
const KP_SHARED_SUFFIX=['github.io','co.uk','com.au','herokuapp.com','workers.dev','pages.dev','vercel.app','netlify.app','ngrok-free.app','ngrok.io','trycloudflare.com','appspot.com','cloudfront.net','amazonaws.com'];
function kpParseSite(input){const s=String(input||'').trim().toLowerCase().replace(/\/+$/,'');
 if(s.length>200)return{error:'Too long'};
 if(/^http:\/\//.test(s))return{error:'Only https:// sites are allowed'};
 const m=/^https:\/\/(\*\.)?([a-z0-9.-]+)(?::(\d{1,5}))?$/.exec(s);
 if(!m)return{error:'Use an https origin only, like https://api.example.com (no path, no query)'};
 const wild=!!m[1],host=m[2],port=m[3];
 if(port&&(+port<1||+port>65535))return{error:'Bad port'};
 if(/\.\.|^[.-]|[.-]$/.test(host))return{error:'Bad host name'};
 const ip=/^\d{1,3}(\.\d{1,3}){3}$/.test(host);
 if(ip){if(wild)return{error:'Wildcards are not allowed on IP addresses'};const p=host.split('.').map(Number);if(p.some(x=>x>255))return{error:'Bad IP address'};
  if(p[0]===0||(p[0]===169&&p[1]===254))return{error:'That address range is not allowed'};
  const ts=p[0]===100&&p[1]>=64&&p[1]<=127,lo=p[0]===127,priv=p[0]===10||(p[0]===172&&p[1]>=16&&p[1]<=31)||(p[0]===192&&p[1]===168);return{origin:'https://'+host+(port?':'+port:''),kind:(ts||lo||priv)?'local':'ip'}}
 const labels=host.split('.');if(labels.some(l=>!l||l.length>63||!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(l)))return{error:'Bad host name'};
 if(host==='localhost'){if(wild)return{error:'No wildcard on localhost'};return{origin:'https://localhost'+(port?':'+port:''),kind:'local'}}
 if(labels.length<2)return{error:'Use a full domain like api.example.com'};
 if(/^\d+$/.test(labels[labels.length-1]))return{error:'Bad host name'};
 if(wild&&KP_SHARED_SUFFIX.includes(host))return{error:'Wildcards on shared hosting domains (like *.github.io) are not allowed; add the exact site instead'};
 return{origin:'https://'+(wild?'*.':'')+host+(port?':'+port:''),kind:'ok'}}
// Validate a stored list: keep only entries that parse and normalize identically; dedupe; cap length.
function kpCleanSites(list){if(!Array.isArray(list))return[];const out=[];for(const x of list){if(typeof x!=='string')continue;const r=kpParseSite(x);if(r.origin&&r.origin===x&&!out.includes(x))out.push(x);if(out.length>=KP_SITES_MAX)break}return out}
