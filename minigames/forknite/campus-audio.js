'use strict';
// Fixed local state only. HTTP callers cannot choose a path, command or process.
const fs=require('fs');
function fallback(now){
 const d=new Date((now+8*3600)*1000),day=d.getUTCDay(),hour=d.getUTCHours()+d.getUTCMinutes()/60+d.getUTCSeconds()/3600;
 const start=day===3?15:day===6?13:null;
 return start!==null&&hour>=start&&hour<start+3 ? now+((start+3-hour)*3600) : 0;
}
function state(env=process.env,now=Date.now()/1000){
 const base={until:fallback(now),windows:[]};let fd;
 try{
  if(!/^[a-f0-9]{64}$/.test(env.LAN42_AUDIO_QUIET_FINGERPRINT||''))return base;
  fd=fs.openSync(env.LAN42_AUDIO_QUIET_PATH,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  const stat=fs.fstatSync(fd);
  if(!stat.isFile()||stat.size>32768||(stat.mode&0o077)||stat.uid!==process.getuid())return base;
  const s=JSON.parse(fs.readFileSync(fd,'utf8'));
  if(Object.keys(s).sort().join(',')!=='campus_id,fingerprint,issued,schema,scope,windows'||s.schema!==1||s.scope!=='lan42-audio'||s.campus_id!==64||s.fingerprint!==env.LAN42_AUDIO_QUIET_FINGERPRINT||!Number.isFinite(s.issued)||s.issued>now+120||!Array.isArray(s.windows)||s.windows.length>16)return base;
  let end=0;
  for(const w of s.windows){
   if(!w||Object.keys(w).sort().join(',')!=='end,reason,start'||!['exam','manual'].includes(w.reason)||!Number.isFinite(w.start)||!Number.isFinite(w.end)||w.end<=w.start||w.end-w.start>43200||w.start<s.issued-43200||w.end>s.issued+8*86400)return base;
   if(w.start<=now&&w.end>now)end=Math.max(end,w.end);
  }
  return {until:Math.max(base.until,end),windows:s.windows.filter(w=>w.end>now)};
 }catch(e){return base;}finally{if(fd!==undefined)fs.closeSync(fd);}
}
function quietUntil(env=process.env,now=Date.now()/1000){return state(env,now).until;}
module.exports={quietUntil,fallback,state};
