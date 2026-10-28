'use strict';
function normalizeCampusStatus(value){
 if(!value||typeof value!=='object'||Object.keys(value).sort().join(',')!=='c1,c2,total,updated_at')return null;
 if(['total','c1','c2'].some(k=>!Number.isInteger(value[k])||value[k]<0||value[k]>10000)||value.total!==value.c1+value.c2||!Number.isFinite(value.updated_at)||value.updated_at<=0)return null;
 return {total:value.total,c1:value.c1,c2:value.c2,updated_at:value.updated_at};
}
function campusStatusLabel(value,now=Date.now()/1000){
 value=normalizeCampusStatus(value);if(!value)return 'Campus: unavailable';
 const age=Math.max(0,Math.floor(now-value.updated_at));
 return 'Campus: '+value.total+' online (C1:'+value.c1+' | C2:'+value.c2+') · '+(age>120?'stale ('+Math.floor(age/60)+'m)':age+'s ago');
}
if(typeof module!=='undefined')module.exports={normalizeCampusStatus,campusStatusLabel};
