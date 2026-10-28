'use strict';
// LAN42 is the only identity authority. No OAuth flow or 42 tokens in this game.
const crypto=require('crypto');
module.exports=function createAuth(){
 const tickets=new Map(),sessions=new Map();
 function prune(){for(const map of [tickets,sessions])for(const [k,v]of map)if(v.expires<Date.now())map.delete(k);}
 function user(req){prune();const item=(req.headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('forknite_session='));return item&&sessions.get(item.slice(17))?sessions.get(item.slice(17)).user:null;}
 function issue(identity){prune();if(tickets.size>=4096)tickets.delete(tickets.keys().next().value);const ticket=crypto.randomBytes(32).toString('hex');tickets.set(ticket,{user:identity,expires:Date.now()+60000});return ticket;}
 function revoke(ids){for(const map of [tickets,sessions])for(const [k,v]of map)if(!ids.has(v.user.id))map.delete(k);}
 function send(res,code,data){res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));}
 async function handle(req,res,url){
  if(req.method==='GET'&&url.pathname==='/auth/me'){send(res,200,{enabled:false,user:user(req)||null});return true;}
  if(req.method==='POST'&&url.pathname==='/auth/lan42'){
   if(!req.headers.origin||!['http://'+req.headers.host,'https://'+req.headers.host].includes(req.headers.origin)){send(res,403,{error:'Origin rejected'});return true;}
   try{
    const data=await new Promise((resolve,reject)=>{let b='';req.on('data',x=>{b+=x;if(b.length>1024){reject(Error());req.destroy();}});req.on('end',()=>{try{resolve(JSON.parse(b));}catch(e){reject(e);}});req.on('error',reject);});
    prune();const record=tickets.get(data.ticket);if(!record)throw Error();tickets.delete(data.ticket);
    const sid=crypto.randomBytes(32).toString('hex');sessions.set(sid,{user:record.user,expires:Date.now()+3600000});
    res.setHeader('Set-Cookie','forknite_session='+sid+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600'+(req.headers.origin.startsWith('https:')?'; Secure':''));send(res,200,{ok:true});
   }catch(e){send(res,400,{error:'Room entry expired. Rejoin the LAN42 room to reopen the browser.'});}return true;
  }
  if(url.pathname.startsWith('/auth/')){send(res,404,{error:'Sign in through LAN42, then join the room.'});return true;}
  return false;
 }
 function reassign(slots){for(const map of [tickets,sessions])for(const record of map.values())if(slots.has(record.user.id))record.user.slot=slots.get(record.user.id);}
 function setCampusAccess(access){for(const map of [tickets,sessions])for(const record of map.values())record.user.campusAccess=record.user.verified===true&&access.get(record.user.id)===true;}
 return {user,handle,issue,revoke,reassign,setCampusAccess};
};
