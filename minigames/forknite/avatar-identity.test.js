'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/public/index.html','utf8');
const renders=[],nodes={'.name':{textContent:''},'.sprite':{}};
const card={el:{querySelector:key=>nodes[key]},avatarSignature:null};
const context={players:[{id:1,name:'first',avatar:'/avatars/1?v=0'}],cards:[null,card],
 makeCard:()=>{throw Error('Unexpected new card');},renderAvatar:(sprite,urls,face,name)=>renders.push({urls,name}),
 faces:['face'],layout:()=>{}};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function names(){'),html.indexOf('async function refreshIdentity')),context);
context.names();
context.players=[{id:1,name:'second',avatar:'/avatars/1?v=0'}];
context.names();
assert.deepStrictEqual(renders.map(render=>render.name),['first','second']);
assert.equal(nodes['.name'].textContent,'#1 second');
console.log('PASS: avatar redraw follows diner identity even when the slot URL is unchanged');
