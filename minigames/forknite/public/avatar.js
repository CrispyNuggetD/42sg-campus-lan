'use strict';
// Photos come from the room server’s authenticated private cache.
function renderAvatar(sprite, urls, fallback, name) {
 const sources=Array.from(new Set(urls.filter(Boolean)));
 let attempt=0;
 function load(retry) {
  sprite.textContent='';
  const img=document.createElement('img');
  img.alt=name+' profile photo';
  img.onload=()=>{sprite.dataset.photo='loaded';};
  img.onerror=()=>{
   if(attempt+1<sources.length){attempt++;load(false);return;}
   sprite.dataset.photo='failed';sprite.textContent=fallback;
   const status=document.createElement('small');status.className='photo-status';status.textContent='Photo not cached — host: /admin';
   const open=document.createElement('a');open.textContent='Open photo';open.href=sources[0];open.target='_blank';open.rel='noopener noreferrer';
   const button=document.createElement('button');button.type='button';button.textContent='Reload cached photo';
   button.onclick=()=>{attempt=0;load(true);};
   sprite.append(status,open,document.createTextNode(' '),button);
  };
  sprite.dataset.photo='loading';
  sprite.append(img);
  // A failed CDN response may be cached. Retry a public URL with a fresh cache
  // key, while leaving URLs that already have query parameters untouched.
  const source=new URL(sources[attempt],location.href);
  if(retry&&!source.search)source.searchParams.set('forknite_retry',String(Date.now()));
  img.src=source.toString();
 }
 if(sources.length)load(false);else{sprite.dataset.photo='missing';sprite.textContent=fallback;}
}
if(typeof module!=='undefined')module.exports=renderAvatar;
