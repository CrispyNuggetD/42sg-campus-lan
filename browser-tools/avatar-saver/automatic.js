// Only explicit, short-lived LAN42 import jobs activate automatic saving.
(async()=>{
 if(!/^[a-f0-9]{32}$/.test(new URLSearchParams(location.hash.slice(1)).get('lan42-import')||''))return;
 for(let i=0;i<120;i++){
  try{const result=captureDisplayedAvatar();const saved=await chrome.runtime.sendMessage({type:'lan42-save',...result});if(saved&&saved.saved)await chrome.runtime.sendMessage({type:'lan42-photo-close',job:result.job});return;}catch(e){await new Promise(r=>setTimeout(r,500));}
 }
})();
