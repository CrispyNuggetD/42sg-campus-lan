'use strict';
const assert=require('assert'),{presets,configure}=require('./rules');
assert.deepStrictEqual(presets.chill,{die:600,eat:100,sleep:100,storm:true,shrink:25,meals:3,pause:2000});
assert.equal(configure(presets.chill,{storm:false}).storm,false);
assert.equal(configure(presets.chill,{pause:0}).pause,0);
for(const patch of [{die:0},{meals:0},{shrink:0},{sleep:-1},{storm:'yes'},{unknown:2}])assert.throws(()=>configure(presets.chill,patch));
console.log('PASS: forgiving storm defaults, settings validation, single-run mode');
