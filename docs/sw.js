'use strict';
const CACHE='project-ten-mobile-v1';
const SHELL=['./','./index.html','./style.css','./app.js','./mobile.js','./manifest.webmanifest','./icon-192.png','./icon-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('project-ten-mobile-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin||!url.pathname.startsWith(new URL(self.registration.scope).pathname))return;
  const scoped=url.pathname.slice(new URL(self.registration.scope).pathname.length);
  if(!['','index.html','style.css','app.js','mobile.js','manifest.webmanifest','icon-192.png','icon-512.png','paired_dashboard.json'].includes(scoped))return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{
      const response=await fetch(event.request);
      if(response.ok){
        if(scoped==='paired_dashboard.json'){
          const data=await response.clone().json();
          if(data.meta?.paper_only!==true||data.meta?.schema!==2||data.duos?.length!==50)return response;
        }
        await cache.put(event.request,response.clone());
      }
      return response;
    }catch(error){return await cache.match(event.request)||new Response('Offline; verified report unavailable',{status:503});}
  })());
});
