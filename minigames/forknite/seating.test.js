'use strict';
const assert=require('assert'),{shuffle}=require('./seating');
const people=[{id:1},{id:2},{id:3},{id:4}];
for(let i=0;i<100;i++){
 const result=shuffle(people);assert.notStrictEqual(result[0],people[0]);
 assert.deepStrictEqual(result.map(x=>x.id).sort(),[1,2,3,4]);assert.strictEqual(people[0].id,1);
}
assert.deepStrictEqual(shuffle([]),[]);assert.deepStrictEqual(shuffle([people[0]]),[people[0]]);
console.log('PASS: randomized seat IDs preserve all identities and rotate seat 1');
