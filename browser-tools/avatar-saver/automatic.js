// Only explicit, short-lived LAN42 import jobs activate automatic saving.
(async()=>{
 if(!/^[a-f0-9]{32}$/.test(new URLSearchParams(location.hash.slice(1)).get('lan42-import')||''))return;
 for(let i=0;i<120;i++){
  try{const result=captureDisplayedAvatar();await chrome.runtime.sendMessage({type:'lan42-save',...result});return;}catch(e){await new Promise(r=>setTimeout(r,500));}
 }
})();
