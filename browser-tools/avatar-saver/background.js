const savedPhotoTabs=new Set();
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(message.type==='lan42-signin-close'){
  if(!sender.url||!sender.tab||!Number.isInteger(sender.tab.id)||message.requested!==true)return;
  const url=new URL(sender.url);
  if(url.origin!=='http://localhost:31415'||url.pathname!=='/signin-complete')return;
  chrome.tabs.remove(sender.tab.id).then(()=>respond({closed:true}),()=>respond({closed:false}));return true;
 }
 if(!sender.url||!sender.tab||!Number.isInteger(sender.tab.id))return;
 const photo=new URL(sender.url);
 if(photo.origin!=='https://cdn.intra.42.fr'||!/^[a-f0-9]{32}$/.test(message.job)||new URLSearchParams(photo.hash.slice(1)).get('lan42-import')!==message.job)return;
 const key=sender.tab.id+':'+message.job;
 if(message.type==='lan42-photo-close'){
  if(!savedPhotoTabs.delete(key))return;
  chrome.tabs.remove(sender.tab.id).then(()=>respond({closed:true}),()=>respond({closed:false}));return true;
 }
 if(message.type!=='lan42-save'||typeof message.data!=='string'||!message.data.startsWith('data:image/png;base64,')||message.data.length>1398000)return;
 (async()=>{
  try{
   const id=await chrome.downloads.download({url:message.data,filename:'lan42-avatar-imports/'+message.job+'.png',saveAs:false,conflictAction:'overwrite'});
   for(let n=0;n<60;n++){
    const [download]=await chrome.downloads.search({id});
    if(download&&download.state==='interrupted')throw Error('Download interrupted');
    if(download&&download.state==='complete'){
     savedPhotoTabs.add(key);setTimeout(()=>savedPhotoTabs.delete(key),60000);
     respond({id,saved:true});return;
    }
    await new Promise(resolve=>setTimeout(resolve,500));
   }
   throw Error('Download completion timed out');
  }catch(error){respond({error:error.message||'Download failed'});}
 })();return true;
});
