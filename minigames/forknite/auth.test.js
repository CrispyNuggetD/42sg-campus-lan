'use strict';
const assert=require('assert'),create=require('./auth');
function res(){return{headers:{},setHeader(k,v){this.headers[k]=v;},writeHead(code,h){this.code=code;Object.assign(this.headers,h);},end(b){this.body=b;}};}
(async()=>{
 const auth=create(),identity={id:'42',login:'hnah',verified:true,avatar:null,slot:1};
 const ticket=auth.issue(identity);
 const {EventEmitter}=require('events');
 async function redeem(value,origin='http://localhost:4242'){
  const req=new EventEmitter();req.method='POST';req.headers={origin,host:'localhost:4242'};const out=res();
  const done=auth.handle(req,out,new URL('http://localhost/auth/lan42'));
  req.emit('data',JSON.stringify({ticket:value}));req.emit('end');await done;return out;
 }
 assert.equal((await redeem(ticket,'http://evil.example')).code,403);
 const r=await redeem(ticket);assert.equal(r.code,200);
 const cookie=r.headers['Set-Cookie'].split(';')[0];assert.deepStrictEqual(auth.user({headers:{cookie}}),identity);
 assert.equal((await redeem(ticket)).code,400);
 auth.revoke(new Set());assert.equal(auth.user({headers:{cookie}}),null);
 const x=res();await auth.handle({method:'GET',headers:{}},x,new URL('http://localhost/auth/42'));assert.equal(x.code,404);
 console.log('PASS: LAN42 identity only, browser origin, one-use ticket, cookie, room-leave revocation, no second OAuth');
})().catch(e=>{console.error(e);process.exitCode=1;});
