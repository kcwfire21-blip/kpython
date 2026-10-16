const C='kpython-v1';const SHELL=['./','./index.html','./manifest.json','./apple-touch-icon.png','./icon-192.png','./icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL)));self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{if(res.ok&&(e.request.url.startsWith(self.location.origin)||e.request.url.includes('cdn.jsdelivr.net'))){const cl=res.clone();caches.open(C).then(c=>c.put(e.request,cl))}return res})))});
