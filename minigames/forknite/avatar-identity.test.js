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
const replay={history:[],queue:[],seq:0,players:[],count:0,cursor:0,catchUp:false,
 build:()=>{},names:()=>{},$:()=>({textContent:''})};
let stream;
replay.EventSource=function(){stream={};return stream;};
vm.createContext(replay);
vm.runInContext(html.slice(html.indexOf('const stream=new EventSource'),html.indexOf('function tick(now){')),replay);
const events=[{seq:1,type:'round',round:1,count:4},{seq:2,type:'end',round:1},
 {seq:3,type:'round',round:30,count:6},{seq:4,type:'end',round:30}];
stream.onmessage({data:JSON.stringify({type:'snapshot',count:50,players:Array(6).fill({name:'current'}),events})});
assert.equal(replay.players.length,6);
assert.equal(replay.queue.length,2);
assert.equal(replay.queue[0].round,30);
assert.equal(replay.catchUp,true);
assert.equal(replay.history.length,4);
console.log('PASS: photos redraw by identity and reload catches up to the latest round');
