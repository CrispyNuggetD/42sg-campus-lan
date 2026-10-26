'use strict';
// No dependencies; compatible with the Node 12 installed on this campus machine.
const http = require('http'), fs = require('fs'), path = require('path');
const readline = require('readline'), spawn = require('child_process').spawn;
const crypto = require('crypto');
const auth = require('./auth')();
const avatarCache=require('./avatar-cache')(process.env.LAN42_AVATAR_CACHE||path.join(process.env.XDG_CACHE_HOME||path.join(require('os').homedir(),'.cache'),'42sg-campus-lan','avatars'));
const controlSecret=process.env.LAN42_FORKNITE_CONTROL||null;
const saboLookup = require('./sabo')(process.env);
let saboBusy = false;
const argv = process.argv.slice(2), split = argv.indexOf('--');
const options = split < 0 ? argv : argv.slice(0, split);
const args = split < 0 ? [] : argv.slice(split + 1);
function opt(key, fallback) { const i = options.indexOf(key); return i < 0 ? fallback : options[i + 1]; }
const piped = options.includes('--pipe'), storm = options.includes('--storm');
const rules=require('./rules');
const seating=require('./seating');
let settings=controlSecret?{...rules.presets.chill}:{die:Number(args[1]||130),eat:Number(args[2]||60),sleep:Number(args[3]||60),storm,shrink:Number(opt('--shrink','10')),meals:Number(args[4]||opt('--meals','3')),pause:4000};
let phase='waiting',stopping=false;
const binary = opt('--exec', null), port = Number(opt('--port', process.env.PORT || 4242));
const count = Number(opt('--count', args[0] || 50));
if (!Number.isInteger(count) || count < 1 || count > 500 || (!piped && (!binary || args.length < 4))) {
 console.error('Usage: node server.js --exec /path/philo [--storm] -- 50 130 60 60\n   or: ./philo 50 130 60 60 | node server.js --pipe --count 50'); process.exit(1);
}
if (!piped && (Number(args[0]) !== count || args.some(x => !/^\d+$/.test(x)) || args.length > 5 || args.some(x => Number(x) < 1))) { console.error('Invalid C arguments'); process.exit(1); }
if (storm && (!Number.isInteger(Number(opt('--shrink','10'))) || Number(opt('--shrink','10')) < 1 || !/^[1-9][0-9]*$/.test(opt('--meals','3')))) { console.error('Storm shrink and meals must be positive integers'); process.exit(1); }
const logdir = process.env.LAN42_FORKNITE_LOGDIR || path.join(__dirname, '.logs'); fs.mkdirSync(logdir, {recursive:true});
const session = new Date().toISOString().replace(/[:.]/g, '-') + '-' + process.pid;
const log = fs.createWriteStream(path.join(logdir, session + '.jsonl'), {flags:'wx'});
log.on('error', e => { console.error('Log failure:', e.message); shutdown(); });
const clients = new Set(), players = new Map(), events = [];
let round = 0, active = false, child = null, killed = false, deadline = settings.die, firstDeath = false, sequence = 0, timer;
function emit(type, data) {
 const event = {seq:++sequence, type, wall:Date.now(), ...data};
 log.write(JSON.stringify(event) + '\n');
 events.push(event); if (events.length > 100000) events.splice(0, 1000);
 const frame = 'data: ' + JSON.stringify(event) + '\n\n';
 clients.forEach(res => { if (res.writableLength > 1048576) { res.destroy(); clients.delete(res); } else res.write(frame); });
 return event;
}
function roster() { return Array.from(players, ([id,p]) => ({id,name:p.name,verified:Boolean(p.userId),avatar:(p.avatar||avatarCache.has(p.name))?'/avatars/'+id+'?v='+avatarCache.version(p.name):null,sabo:Boolean(p.sabo)})); }
function line(raw) {
 const m = raw.replace(/\x1b\[[0-9;]*m/g, '').match(/^\s*(\d+)\s+(\d+)\s+(has taken a fork|is eating|is sleeping|is thinking|died)\s*$/);
 if (!m || Number(m[2]) < 1 || Number(m[2]) > count) { emit('raw',{round,line:raw}); return; }
 const e = emit('move',{round,ms:Number(m[1]),id:Number(m[2]),action:m[3]});
 if (e.action === 'died') firstDeath = true;
}
function consume(stream, rawlog) {
 if (rawlog) stream.on('data', b => { rawlog.write(b); process.stdout.write(b); });
 const reader = readline.createInterface({input:stream, crlfDelay:Infinity}); reader.on('line', line); return reader;
}
function begin() {
 if (active || killed || piped || stopping) return;
 if(controlSecret && players.size<2){clearTimeout(timer);timer=null;phase='waiting for players';return;}
 if(controlSecret){
  const ordered=seating.shuffle(Array.from(players.values()));players.clear();const slots=new Map();
  ordered.forEach((p,i)=>{players.set(i+1,p);if(p.memberId)slots.set(p.memberId,i+1);});
  auth.reassign(slots);emit('players',{players:roster()});
 }
 clearTimeout(timer);timer=null; active = true;phase='running'; firstDeath = false; round++;
 const runargs = args.slice(); runargs[1] = String(deadline);
 if(controlSecret){runargs[2]=String(settings.eat);runargs[3]=String(settings.sleep);}
 if(controlSecret)runargs[0]=String(players.size);
 // Storm uses finite, complete native simulations. It never changes a running C process.
 if (settings.storm && runargs.length === 4) runargs.push(String(settings.meals));
 emit('round',{round,args:runargs,count:controlSecret?players.size:count,players:roster()});
 const rawlog = fs.createWriteStream(path.join(logdir, session + '-round-' + round + '.log'));
 rawlog.on('error', e => { console.error(e.message); shutdown(); });
 const command = options.includes('--buffered') ? binary : 'stdbuf';
 const commandArgs = options.includes('--buffered') ? runargs : ['-oL', binary].concat(runargs);
 child = spawn(command, commandArgs, {stdio:['ignore','pipe','pipe']});
 consume(child.stdout, rawlog);
 child.stderr.on('data', b => { process.stderr.write(b); emit('stderr',{round,line:b.toString()}); });
 child.on('error', e => emit('error',{round,message:e.message}));
 child.on('close', (code, signal) => {
  rawlog.end(); active = false; child = null;
  phase=stopping?'stopped':firstDeath?'finished':code===0&&!signal?'complete':'error';
  emit('end',{round,code,signal,death:firstDeath});
  if (settings.storm && !firstDeath && code === 0 && !signal && !killed && !stopping) {
   deadline = Math.max(1, deadline - settings.shrink);
   phase='between rounds';
   timer = setTimeout(begin, settings.pause);
  }
 });
}
async function sabo(logins) {
 if(saboBusy){console.error('Sabo lookup already running.');return;}
 if(!logins.length||logins.length>50){console.error('Usage: sabo thtay dthoo guoliu (up to 50 logins)');return;}
 saboBusy=true;
 try{for(const login of logins){
  try{
   if(Array.from(players.values()).some(p=>p.name.toLowerCase()===login.toLowerCase())){console.error(login+' is already in the lobby');continue;}
   if(players.size>=count){console.error('Lobby full');break;}
   const profile=await saboLookup(login);
   let id=1;while(id<=count&&players.has(id))id++;
   if(id>count){console.error('Lobby full');break;}
   players.set(id,{name:profile.login,avatar:profile.avatar,sabo:true,token:null,userId:null});
   emit('players',{players:roster()});console.error('SABO #'+id+' '+profile.login+' · offline stand-in');
  }catch(e){console.error('Sabo: '+e.message);}
  await new Promise(resolve=>setTimeout(resolve,600));
 }}finally{saboBusy=false;}
}
function maintenance(update) {
 if(killed) return;
 if(process.env.LAN42_FORKNITE_SUPERVISED!=='1'){console.error('Use sh lan42.sh forknite to enable /update and /restart.');return;}
 console.error('Restarting FORKNITE: current match and lobby will close.');
 // The LAN42 supervisor owns updates/relaunch; direct node launches receive a clear exit status.
 const finishedLog = new Promise(resolve=>log.once('finish',resolve));
 const current = child;
 const finishedChild = current ? new Promise(resolve=>current.once('close',resolve)) : Promise.resolve();
 shutdown();
 const killTimer = current ? setTimeout(()=>current.kill('SIGKILL'),2000) : null;
 Promise.all([finishedLog,finishedChild]).then(()=>{if(killTimer)clearTimeout(killTimer);process.exit(update?76:75);});
}
const index = fs.readFileSync(path.join(__dirname,'public/index.html'));
function json(res, code, value) { res.writeHead(code, {'Content-Type':'application/json','Cache-Control':'no-store'}); res.end(JSON.stringify(value)); }
const server = http.createServer(async (req,res) => {
 const url = new URL(req.url, 'http://localhost');
 if(req.method==='GET'&&url.pathname==='/health')return json(res,200,{ready:true});
 if(req.method==='POST'&&url.pathname==='/internal/room'){
  if(!controlSecret||!['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress)||req.headers.authorization!=='Bearer '+controlSecret)return json(res,403,{error:'Local LAN42 control only'});
  let body='';req.on('data',b=>{body+=b;if(body.length>32768)req.destroy();});req.on('end',()=>{try{
   const data=JSON.parse(body);
   if(data.action==='roster')return json(res,200,{players:roster()});
   if(data.action==='status')return json(res,200,{phase,round,players:players.size,deadline,settings});
   if(data.action==='configure'){
    if(active||timer)return json(res,409,{error:'Use /stop before changing timings or storm settings.'});
    const preset=data.preset&&rules.presets[data.preset];
    if(data.preset&&!preset)return json(res,400,{error:'Preset must be chill or chaos'});
    settings=rules.configure(preset?{...preset}:settings,data.patch||{});deadline=settings.die;
    emit('settings',{settings});return json(res,200,{phase,round,players:players.size,deadline,settings});
   }
   if(data.action==='diners'){
    if(active||timer)return json(res,409,{error:'Use /stop before changing diners.'});
    const target=data.count;
    if(!Number.isInteger(target)||target<2||target>count)return json(res,400,{error:'Choose a total between 2 and '+count+'.'});
    const real=Array.from(players.values()).filter(p=>!p.randomDiner).length;
    if(target<real)return json(res,400,{error:'Total cannot be smaller than the joined players and named sabo diners ('+real+').'});
    for(const [slot,p] of players)if(p.randomDiner)players.delete(slot);
    while(players.size<target){let slot=1;while(players.has(slot))slot++;
     players.set(slot,{name:'Diner-'+crypto.randomBytes(3).toString('hex'),sabo:true,randomDiner:true,token:null,userId:null});}
    emit('players',{players:roster()});return json(res,200,{count:players.size});
   }
   if(data.action==='sabo_profiles'){
    if(active||timer)return json(res,409,{error:'Use /stop before adding sabo diners.'});
    if(!Array.isArray(data.profiles)||data.profiles.length>count)throw Error();
    const added=[];
    for(const profile of data.profiles){
     if(typeof profile.login!=='string'||!/^[a-zA-Z0-9_.-]{1,32}$/.test(profile.login))throw Error();
     if(Array.from(players.values()).some(p=>p.name.toLowerCase()===profile.login.toLowerCase()))continue;
     let slot=1;while(slot<=count&&players.has(slot))slot++;if(slot>count)break;
     let avatar=profile.avatar||null;
     if(avatar){try{const u=new URL(avatar);if(u.protocol!=='https:'||!(u.hostname==='42.fr'||u.hostname.endsWith('.42.fr'))||u.username||u.password)avatar=null;}catch(e){avatar=null;}}
     players.set(slot,{name:profile.login,avatar,sabo:true,token:null,userId:null});added.push(profile.login);
    }
    emit('players',{players:roster()});return json(res,200,{added});
   }
   if(data.action==='sabo'){sabo(data.logins||[]);return json(res,200,{ok:true});}
   if(data.action==='start'){if(active||timer)return json(res,409,{error:'Tournament already running. Use /stop first.'});if(players.size<2)return json(res,400,{error:'At least two diners are needed. Invite a friend or use /sabo LOGIN.'});stopping=false;deadline=settings.die;begin();return json(res,200,{ok:true});}
   if(data.action==='stop'){stopping=true;clearTimeout(timer);timer=null;phase='stopped';if(child)child.kill();return json(res,200,{ok:true});}
   if(data.action!=='members'||!Array.isArray(data.members)||data.members.length>count)throw Error();
   const members=data.members,ids=new Set(members.map(m=>m.id));auth.revoke(ids);
   const previous=new Set(Array.from(players.values()).filter(p=>p.memberId).map(p=>p.memberId));
   if((active||timer)&&(previous.size!==ids.size||Array.from(previous).some(id=>!ids.has(id)))){stopping=true;clearTimeout(timer);timer=null;phase='stopped';if(child)child.kill();emit('notice',{message:'Room membership changed. Tournament stopped; host can /start again.'});}

   for(const [slot,p]of players)if(p.memberId&&!ids.has(p.memberId))players.delete(slot);
   const entries=[];
   for(const m of members){
    if(typeof m.id!=='string'||typeof m.name!=='string'||!/^[a-zA-Z0-9_.-]{1,32}$/.test(m.name))throw Error();
    let entry=Array.from(players).find(([slot,p])=>p.memberId===m.id),slot=entry&&entry[0];
    if(!slot){slot=1;while(slot<=count&&players.has(slot)&&!players.get(slot).sabo)slot++;if(slot>count)throw Error();}
    let avatar=m.avatar||null;if(avatar){try{const u=new URL(avatar);if(u.protocol!=='https:'||!(u.hostname==='42.fr'||u.hostname.endsWith('.42.fr')))avatar=null;}catch(e){avatar=null;}}
    const identity={id:m.id,login:m.name,verified:m.verified===true,avatar,slot};
    players.set(slot,{name:m.name,memberId:m.id,userId:m.verified?m.id:null,avatar,token:null});
    entries.push({id:m.id,ticket:auth.issue(identity),slot});
   }
   emit('players',{players:roster()});return json(res,200,{entries});
  }catch(e){return json(res,400,{error:e.message||'Invalid room control'});}});return;
 }

 try { if(await auth.handle(req,res,url)) return; } catch(e) { return json(res,500,{error:'Authentication unavailable; guest mode is available.'}); }
 if (req.method === 'GET' && url.pathname === '/') { res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}); return res.end(fs.readFileSync(path.join(__dirname,'public/index.html'))); }
 if(req.method==='GET'&&url.pathname==='/avatar.js'){res.writeHead(200,{'Content-Type':'application/javascript','Cache-Control':'no-store'});return res.end(fs.readFileSync(path.join(__dirname,'public/avatar.js')));}
 if(req.method==='GET'&&/^\/avatars\/\d+$/.test(url.pathname)){
  if(!auth.user(req))return json(res,403,{error:'Join the LAN42 room to view cached photos.'});
  const player=players.get(Number(url.pathname.split('/')[2]));
  if(!player)return json(res,404,{error:'No such room member'});
  try{const photo=avatarCache.read(player.name);res.writeHead(200,{'Content-Type':photo.type,'Content-Length':photo.bytes.length,'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store','Cross-Origin-Resource-Policy':'same-origin'});return res.end(photo.bytes);}
  catch(e){return json(res,404,{error:'Photo is not cached. The host can import it with /admin.'});}
 }
 if (req.method === 'GET' && url.pathname === '/events') {
  if (clients.size >= 200) return json(res,503,{error:'Audience full'});
  res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache','Connection':'keep-alive'});
  // A bounded history allows late viewers to replay fast matches after they finish.
  res.write('data: ' + JSON.stringify({type:'snapshot',count,players:roster(),events}) + '\n\n');
  clients.add(res); req.on('close',()=>clients.delete(res)); return;
 }
 if (req.method === 'POST' && url.pathname === '/join') {
  // Only same-origin browser submissions; joining never launches commands.
  if (req.headers.origin && req.headers.origin !== 'http://' + req.headers.host && req.headers.origin !== 'https://' + req.headers.host) return json(res,403,{error:'Origin rejected'});
  let body=''; req.on('data',b=>{ body+=b; if(body.length>1024) req.destroy(); });
  req.on('end',()=>{ try {
   const data=JSON.parse(body), identity=auth.user(req), id=identity?identity.slot:Number(data.id);
   const name=identity?identity.login:String(data.name || '').trim();
   if(!Number.isInteger(id)||id<1||id>count||name.length>(identity?32:20)||!/^[a-zA-Z0-9_-]{1,32}$/.test(name)) return json(res,400,{error:'Choose a valid slot and a 1–20 character nickname (letters, digits, _ or -).'});
   const old=players.get(id);
   if(old && old.memberId && (!identity||identity.id!==old.memberId))return json(res,409,{error:'This slot belongs to a LAN42 room member.'});
   if(old && !old.memberId && !old.sabo && (old.userId ? (!identity || identity.id!==old.userId) : old.token!==data.token)) return json(res,409,{error:'That philosopher is already claimed.'});
   const token=old ? old.token : crypto.randomBytes(24).toString('hex');
   players.set(id,{name,token,memberId:identity?identity.id:null,userId:identity&&identity.verified?identity.id:null,avatar:identity?identity.avatar:null}); emit('players',{players:roster()}); json(res,200,{id,token});
  } catch(e) {json(res,400,{error:'Invalid request'});} }); return;
 }
 json(res,404,{error:'Not found'});
});
let avatarRosterSignature='';
const avatarRefresh=setInterval(()=>{const current=roster(),signature=JSON.stringify(current);if(signature!==avatarRosterSignature){avatarRosterSignature=signature;if(players.size)emit('players',{players:current});}},2000);
const heartbeat=setInterval(()=>clients.forEach(res=>res.write(': heartbeat\n\n')),15000);
function shutdown() { if(killed)return; killed=true; clearTimeout(timer); clearInterval(heartbeat); clearInterval(avatarRefresh); if(child)child.kill('SIGTERM'); clients.forEach(r=>r.end()); server.close(); log.end(); }
process.on('SIGINT',shutdown); process.on('SIGTERM',shutdown);
server.listen(port,opt('--host','0.0.0.0'),()=>{
 console.error('\nFORKNITE → http://localhost:'+port+' | LAN: http://<this-machine-IP>:'+port+'\nLogs: '+logdir+'\n'+(piped?'Watching stdin; browsers can replay when it ends.':'Players join first. Type start + Enter here to run. Type stop to stop.'));
 if(piped){ active=true; round=1; emit('round',{round,count,args:[]}); consume(process.stdin,null).on('close',()=>{active=false;emit('end',{round,death:firstDeath});}); }
 else readline.createInterface({input:process.stdin}).on('line',s=>{ if(['/restart','restart','/update','update','/upgrade'].includes(s.trim())){maintenance(!['/restart','restart'].includes(s.trim()));return;} const words=s.trim().replace(/^\//,'').split(/\s+/); if(words[0]==='sabo')sabo(words.slice(1)); if(s.trim()==='start')begin(); if(s.trim()==='stop'){ clearTimeout(timer); if(child)child.kill('SIGTERM'); } });
});
