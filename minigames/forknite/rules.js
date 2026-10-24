'use strict';
const presets={
 chill:{die:600,eat:100,sleep:100,storm:true,shrink:25,meals:3,pause:2000},
 chaos:{die:250,eat:60,sleep:60,storm:true,shrink:10,meals:3,pause:1000}
};
function configure(current,patch){
 const result={...current,...patch};
 if(typeof result.storm!=='boolean')throw Error('Storm must be on or off');
 const limits={die:[1,600000],eat:[1,600000],sleep:[1,600000],shrink:[1,600000],meals:[1,1000],pause:[0,60000]};
 for(const [field,[min,max]]of Object.entries(limits))if(!Number.isInteger(result[field])||result[field]<min||result[field]>max)throw Error(field+' must be an integer from '+min+' to '+max);
 for(const field of Object.keys(patch))if(!(field in presets.chill))throw Error('Unknown setting: '+field);
 return result;
}
module.exports={presets,configure};
