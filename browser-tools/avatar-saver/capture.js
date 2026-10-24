'use strict';
// This function is injected only after the user clicks the extension on a tab.
// It reads the displayed, same-origin image, not cookies or browser storage.
function captureDisplayedAvatar(){
 const url=new URL(location.href),job=new URLSearchParams(url.hash.slice(1)).get('lan42-import');
 if(url.protocol!=='https:'||url.hostname!=='cdn.intra.42.fr'||!job||!/^[a-f0-9]{32}$/.test(job))throw Error('Open a photo using the LAN42 admin panel’s one-click-save link first.');
 const image=Array.from(document.images).find(img=>img.complete&&img.naturalWidth>0&&img.naturalHeight>0&&new URL(img.currentSrc||img.src,location.href).origin===url.origin);
 if(!image)throw Error('No loaded photo found. Finish opening the image normally first; error/challenge pages cannot be saved.');
 const scale=Math.min(1,512/image.naturalWidth,512/image.naturalHeight),canvas=document.createElement('canvas');
 canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
 canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
 const data=canvas.toDataURL('image/png');
 if(!data.startsWith('data:image/png;base64,')||data.length>1398000)throw Error('Photo export failed or exceeds the size limit.');
 return {job,data};
}
if(typeof module!=='undefined')module.exports=captureDisplayedAvatar;
