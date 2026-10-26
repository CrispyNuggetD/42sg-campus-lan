'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let listener,removed=[];
const chrome={runtime:{onMessage:{addListener(fn){listener=fn;}}},tabs:{remove(id){removed.push(id);return Promise.resolve();}},downloads:{download(){throw Error('No download expected');}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),{chrome,URL});
const request={type:'lan42-signin-close',requested:true};
for(const url of ['https://profile-v3.intra.42.fr/','http://localhost:9999/signin-complete','http://127.0.0.1:31415/signin-complete','http://localhost:31415/other'])listener(request,{url,tab:{id:20}},()=>{});
assert.deepStrictEqual(removed,[]);
listener(request,{url:'http://localhost:31415/signin-complete',tab:{id:42}},()=>{});
assert.deepStrictEqual(removed,[42]); // Only the sending completion tab; never enumerate tabs.
let messages=[];
for(const query of ['', '?close=0','?close=1']){
 vm.runInNewContext(fs.readFileSync(__dirname+'/signin-close.js','utf8'),{URL,location:{href:'http://localhost:31415/signin-complete'+query},document:{readyState:'complete'},setTimeout:fn=>fn(),chrome:{runtime:{sendMessage:m=>messages.push(m)}}});
}
assert.strictEqual(messages.length,1);assert.strictEqual(messages[0].type,'lan42-signin-close');
console.log('PASS: close only opted-in local sign-in sender tab; unrelated tabs untouched');
