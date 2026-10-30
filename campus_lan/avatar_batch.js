// Batch UI logic: retain unattempted logins when a shared service fails.
function unsupportedAvatarSelector(name){return /^(all|sg|42sg|(?:cohort|intake|i)\d*)$/i.test(name);}
async function runAvatarBatch(names,{call,log,progress=()=>{},wait=ms=>new Promise(r=>setTimeout(r,ms)),polls=240}){
 const counts={requested:names.length,skipped:0,failed:0,success:0};
 const seen=new Set();let opened=false;
 for(let i=0;i<names.length;i++){
  const name=names[i].toLowerCase();progress(i+1,names.length,name);
  let outcome,reason;
  try{
   if(unsupportedAvatarSelector(name)){outcome='skipped';reason='Expand this selector before saving photos';}
   else if(!/^[a-z0-9_.-]{1,32}$/.test(name)){outcome='skipped';reason='Invalid login format';}
   else if(seen.has(name)){outcome='skipped';reason='Duplicate login';}
   else{
    seen.add(name);
    let result;
    try{result=await call('/batch_one',JSON.stringify({login:name,photo_consent:true}));}
    catch(error){
     log({number:i+1,login:names[i],outcome:'deferred',reason:error.message||'Batch request failed'});
     return {...counts,opened,remaining:names.slice(i)};
    }
    if(result.status==='paused'){
     log({number:i+1,login:names[i],outcome:'deferred',reason:result.reason||'API lookup is still busy'});
     return {...counts,opened,remaining:names.slice(i)};
    }
    if(result.status==='skipped'){outcome='skipped';reason=result.reason||'No available photo';}
    else if(result.status==='cached'){outcome='success';reason='Photo cached';}
    else if(result.job){
     opened=true;let complete=false;
     for(let n=0;n<polls;n++){
      await wait(1500);
      const job=await call('/job_status',JSON.stringify({job:result.job}));
      if(job.status==='cached'){complete=true;break;}
      if(job.status!=='waiting_for_browser_save')throw Error('Photo import: '+job.status);
     }
     if(!complete)throw Error('Browser photo save timed out');
     outcome='success';reason='Browser photo imported';
    }else throw Error(result.reason||result.status||'No photo result returned');
   }
  }catch(error){outcome='failed';reason=error.message||'Request failed';}
  counts[outcome]++;log({number:i+1,login:names[i],outcome,reason});
 }
 return {...counts,opened};
}
if(typeof module!=='undefined')module.exports=runAvatarBatch;
