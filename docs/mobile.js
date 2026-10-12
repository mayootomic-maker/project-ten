'use strict';
let installPrompt;
const installButton=document.querySelector('#install-app');
const installStatus=document.querySelector('#install-status');
installStatus.textContent=matchMedia('(display-mode: standalone)').matches?'Project Ten is installed.':'In Chrome: menu → Add to home screen → Install. The install button becomes available when your browser offers installation.';
installButton.disabled=true;
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;installButton.disabled=false;});
installButton.addEventListener('click',async()=>{if(!installPrompt)return;await installPrompt.prompt();const result=await installPrompt.userChoice;installStatus.textContent=result.outcome==='accepted'?'Installation accepted.':'Installation dismissed.';installPrompt=null;installButton.disabled=true;});
window.addEventListener('appinstalled',()=>{installStatus.textContent='Project Ten is installed.';installButton.disabled=true;});
document.querySelector('#open-alerts').addEventListener('click',()=>{
  const topic=document.querySelector('#alert-topic').value.trim();
  if(!/^[A-Za-z0-9_-]{24,100}$/.test(topic)){document.querySelector('#alert-status').textContent='Paste the long notification channel supplied in this conversation.';return;}
  window.open('https://ntfy.sh/'+encodeURIComponent(topic),'_blank','noopener,noreferrer');
  document.querySelector('#alert-topic').value='';
  document.querySelector('#alert-status').textContent='Subscribe in ntfy and allow notifications. Project Ten does not store your channel in this browser.';
});
window.addEventListener('project-ten-report',event=>{
  const data=event.detail;
  document.querySelector('#runtime-status').textContent=data.meta.runtime+' Latest pipeline processing: '+(data.meta.pipeline_metrics.processing_seconds??'unknown')+' seconds. Dashboard checks for updates every 15 seconds while visible; that does not increase cloud execution frequency.';
});
const offline=()=>{if(!navigator.onLine){document.querySelector('#freshness').textContent='Offline — saved observation, no live updates';}};
window.addEventListener('offline',offline);window.addEventListener('project-ten-report',offline);
if('serviceWorker' in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{installStatus.textContent='App installation unavailable; dashboard still works online.';});
