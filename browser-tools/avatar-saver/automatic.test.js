'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const job='a'.repeat(32),url='https://cdn.intra.42.fr/photo.jpg#lan42-import='+job;
async function scenario(state){
 let listener,removed=[],searches=0;
 const chrome={runtime:{onMessage:{addListener(fn){listener=fn;}}},tabs:{remove(id){removed.push(id);return Promise.resolve();}},downloads:{download:async()=>7,search:async({id})=>{assert.equal(id,7);searches++;return [{state:searches===1?'in_progress':state}];}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),{chrome,URL,URLSearchParams,setTimeout:(fn,ms)=>{if(ms===500)fn();}});
 const sender={url,tab:{id:42}},close={type:'lan42-photo-close',job};
 listener(close,sender,()=>{});assert.deepStrictEqual(removed,[]);
 const result=await new Promise(resolve=>listener({type:'lan42-save',job,data:'data:image/png;base64,abc'},sender,resolve));
 if(state==='complete'){
  assert.equal(result.saved,true);assert.equal(searches,2);
  listener(close,{url:'https://example.com/#lan42-import='+job,tab:{id:42}},()=>{});
  listener(close,{url:url.replace(job,'b'.repeat(32)),tab:{id:42}},()=>{});
  listener(close,{url,tab:{id:43}},()=>{});assert.deepStrictEqual(removed,[]);
  await new Promise(resolve=>listener(close,sender,resolve));
  assert.deepStrictEqual(removed,[42]);
  listener(close,sender,()=>{});assert.deepStrictEqual(removed,[42]);
 }else{
  assert(result.error);listener(close,sender,()=>{});assert.deepStrictEqual(removed,[]);
 }
}
(async()=>{
 await scenario('complete');await scenario('interrupted');await scenario('in_progress');
 for(const saved of [true,false]){
  const messages=[];
  await vm.runInNewContext(fs.readFileSync(__dirname+'/automatic.js','utf8'),{URLSearchParams,location:{hash:'#lan42-import='+job},captureDisplayedAvatar:()=>({job,data:'data:image/png;base64,abc'}),chrome:{runtime:{sendMessage:async m=>{messages.push(m);return {saved};}}}});
  assert.deepStrictEqual(messages.map(m=>m.type),saved?['lan42-save','lan42-photo-close']:['lan42-save']);
 }
 console.log('PASS: close only the completed job sender; pending, failed and unrelated tabs stay open');
})().catch(error=>{console.error(error);process.exitCode=1;});
