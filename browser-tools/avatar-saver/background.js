chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(message.type==='lan42-signin-close'){
  if(!sender.url||!sender.tab||!Number.isInteger(sender.tab.id)||message.requested!==true)return;
  const url=new URL(sender.url);
  if(url.origin!=='http://localhost:31415'||url.pathname!=='/signin-complete')return;
  chrome.tabs.remove(sender.tab.id).then(()=>respond({closed:true}),()=>respond({closed:false}));return true;
 }
 if(!sender.url||new URL(sender.url).origin!=='https://cdn.intra.42.fr'||message.type!=='lan42-save'||!/^[a-f0-9]{32}$/.test(message.job)||typeof message.data!=='string'||!message.data.startsWith('data:image/png;base64,')||message.data.length>1398000)return;
 chrome.downloads.download({url:message.data,filename:'lan42-avatar-imports/'+message.job+'.png',saveAs:false,conflictAction:'overwrite'}).then(id=>respond({id}),()=>respond({error:'Download failed'}));return true;
});
