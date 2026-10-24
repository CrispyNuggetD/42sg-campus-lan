'use strict';
(async()=>{
 const status=document.getElementById('status');
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab||!tab.id)throw Error('No active photo tab.');
  const results=await chrome.scripting.executeScript({target:{tabId:tab.id},func:captureDisplayedAvatar});
  const result=results[0]&&results[0].result;
  if(!result||!/^[a-f0-9]{32}$/.test(result.job)||!result.data.startsWith('data:image/png;base64,'))throw Error('Photo capture did not complete.');
  const id=await chrome.downloads.download({url:result.data,filename:'lan42-avatar-imports/'+result.job+'.png',saveAs:false,conflictAction:'overwrite'});
  status.textContent='Download started. Waiting for Chrome to finish…';
  for(let n=0;n<60;n++){
   const [download]=await chrome.downloads.search({id});
   if(download&&download.state==='interrupted')throw Error('Download interrupted: '+(download.error||'check Chrome downloads'));
   if(download&&download.state==='complete'){
    status.textContent='Download complete:\n'+download.filename+'\n\nThis is the staging file, not yet confirmation of cache import. The open LAN42 admin panel must show “Photo cached automatically”. Its Chrome download folder must match this location.';
    return;
   }
   await new Promise(resolve=>setTimeout(resolve,500));
  }
  status.textContent='Chrome has not confirmed completion yet. Check Ctrl+J and the local admin panel.';
 }catch(e){status.textContent=e.message||'Could not save this photo.';}
})();
