// This content script runs only on the local completion page, not Intra or other tabs.
(()=>{
 const url=new URL(location.href);
 if(url.origin!=='http://localhost:31415'||url.pathname!=='/signin-complete'||url.search!=='?close=1')return;
 const close=()=>setTimeout(()=>chrome.runtime.sendMessage({type:'lan42-signin-close',requested:true}),400);
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',close,{once:true});else close();
})();
