'use strict';
const requestJSON=require('./request-json');
module.exports=function createSabo(env,api=requestJSON){
 let token=null,expires=0;
 const cache=new Map();
 return async function lookup(login){
  if(!/^[a-zA-Z0-9_-]{1,32}$/.test(login))throw Error('Invalid Intra login');
  if(!env.FORTYTWO_CLIENT_ID||!env.FORTYTWO_CLIENT_SECRET)throw Error('Configure FORTYTWO_CLIENT_ID and FORTYTWO_CLIENT_SECRET first');
  login=login.toLowerCase();
  const cached=cache.get(login);if(cached&&cached.expires>Date.now())return cached.profile;
  if(!token||expires<Date.now()){
   const body=new URLSearchParams({grant_type:'client_credentials',client_id:env.FORTYTWO_CLIENT_ID,client_secret:env.FORTYTWO_CLIENT_SECRET,scope:'public'}).toString();
   const result=await api('https://api.intra.42.fr/oauth/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','Content-Length':Buffer.byteLength(body)},body});
   if(typeof result.access_token!=='string'||!result.access_token)throw Error('42 did not return an app token');
   token=result.access_token;expires=Date.now()+Math.max(1,(Number(result.expires_in)||300)-30)*1000;
  }
  let profile;
  try{profile=await api('https://api.intra.42.fr/v2/users/'+encodeURIComponent(login),{method:'GET',headers:{Authorization:'Bearer '+token}});}catch(e){token=null;throw Error('42 lookup failed for '+login+' (check login, permissions, or API limits)');}
  if(!profile.id||typeof profile.login!=='string'||!/^[a-zA-Z0-9_-]{1,32}$/.test(profile.login))throw Error('Invalid 42 profile');
  let avatar=profile.image&&(profile.image.versions&&profile.image.versions.small||profile.image.link)||null;
  if(avatar){try{const u=new URL(avatar);if(u.protocol!=='https:'||!(u.hostname==='42.fr'||u.hostname.endsWith('.42.fr'))||u.username||u.password)avatar=null;}catch(e){avatar=null;}}
  const result={login:profile.login,avatar};
  cache.set(login,{expires:Date.now()+3600000,profile:result});return result;
 };
};
