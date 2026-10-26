'use strict';
const crypto=require('crypto');
// Shuffle identities before assigning the native C philosopher IDs. Avoid keeping
// the same identity in seat 1 on consecutive rounds when more than one plays.
exports.shuffle=function(values, random=()=>crypto.randomBytes(4).readUInt32BE(0)/4294967296){
 const out=values.slice();
 for(let i=out.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[out[i],out[j]]=[out[j],out[i]];}
 if(out.length>1&&out[0]===values[0]){const j=1+Math.floor(random()*(out.length-1));[out[0],out[j]]=[out[j],out[0]];}
 return out;
};
