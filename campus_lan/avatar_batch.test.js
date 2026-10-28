'use strict';
const assert=require('assert'),run=require('./avatar_batch');
(async()=>{
 const rows=[],calls=[];
 const names=['missing-user','bad/input','no-photo','cached','browser','timeout','expired','interrupted','last','LAST'];
 const result=await run(names,{polls:2,wait:async()=>{},log:row=>rows.push(row),call:async(path,raw)=>{
  const data=JSON.parse(raw);calls.push([path,data]);
  if(path==='/job_status'){
   if(data.job==='browser')return {status:'cached'};
   if(data.job==='timeout')return {status:'waiting_for_browser_save'};
   return {status:'expired'};
  }
  if(data.login==='missing-user')throw Error('Profile unavailable');
  if(data.login==='no-photo')return {status:'skipped',reason:'No photo available'};
  if(data.login==='interrupted')throw Error('Network interrupted');
  if(['browser','timeout','expired'].includes(data.login))return {job:data.login};
  return {status:'cached'};
 }});
 assert.deepStrictEqual(result,{requested:10,skipped:3,failed:4,success:3,opened:true});
 assert.equal(rows.length,10);assert.equal(rows[0].outcome,'failed');assert.equal(rows[8].login,'last');assert.equal(rows[8].outcome,'success');
 assert(!calls.some(([,data])=>data.login==='bad/input'));
 assert.equal(calls.filter(([,data])=>data.login==='last').length,1);
 assert.equal(result.requested,result.skipped+result.failed+result.success);
 assert.deepStrictEqual(await run([],{call:()=>{throw Error('No request expected');},log:()=>{}}),{requested:0,skipped:0,failed:0,success:0,opened:false});
 const selectors=[];
 assert.deepStrictEqual(await run(['all','cohort1'],{call:()=>{throw Error('Selectors must not reach the API');},log:row=>selectors.push(row)}),{requested:2,skipped:2,failed:0,success:0,opened:false});
 assert(selectors.every(row=>row.reason.includes('Expand this selector')));
 console.log('PASS: batch continues after invalid logins, lookup/network errors, expired jobs and timeouts; exact totals and one log per input');
})().catch(error=>{console.error(error);process.exitCode=1;});
// Exercise the actual inline panel: query logins survive URL cleanup and errors
// remain visible alongside the final report, rather than replacing earlier rows.
const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(__dirname+'/avatar_admin.py','utf8');
const script=source.split('<script>')[1].split('</script>')[0].replace('AVATAR_BATCH_SCRIPT',fs.readFileSync(__dirname+'/avatar_batch.js','utf8')).replace('PHOTO_CONSENT','true');
const elements={};const element=id=>elements[id]||(elements[id]={value:'',textContent:'',before(){}});
let batchTask;
vm.runInNewContext(script,{URLSearchParams,URL,Blob:class {},console:{log(){}},location:{search:'?logins=missing-user+fixture-user',hash:'#key=fixture',pathname:'/'},history:{replaceState(){ /* Browser removes query here. */ }},document:{getElementById:element,createElement:()=>({click(){batchTask=this.onclick();}})},setInterval(){},setTimeout(fn){fn();},fetch:async(path,options)=>{
 const data=JSON.parse(options.body);
 let body;
 if(path==='/photo_permission')body={mode:'allow'};
 else if(path==='/downloads_directory')body={directory:'/tmp'};
 else if(path==='/expand')body={logins:data.names};
 else body=data.login==='missing-user'?{status:'failed',reason:'Profile lookup failed'}:{status:'cached'};
 return {ok:true,json:async()=>body};
}});
Promise.resolve().then(()=>batchTask).then(()=>{
 assert.equal(element('login').value,'missing-user fixture-user');
 assert(element('batch-log').textContent.includes('missing-user — failed: Profile lookup failed'));
 assert(element('batch-log').textContent.includes('fixture-user — success: Photo cached'));
 assert(element('status').textContent.includes('Requested 2, skipped 0, failed 1, success 1'));
 assert.equal(element('download-log').hidden,false);
 console.log('PASS: real panel retains launch inputs and prints per-login results plus downloadable summary');
}).catch(error=>{console.error(error);process.exitCode=1;});
