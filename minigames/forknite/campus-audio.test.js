'use strict';
const assert=require('assert'),fs=require('fs'),os=require('os'),path=require('path');
const {quietUntil,fallback}=require('./campus-audio');
const at=s=>Date.parse(s)/1000;
assert(fallback(at('2026-10-28T07:00:00Z'))>0); // Wed 15 SGT
assert.equal(fallback(at('2026-10-28T10:00:00Z')),0);
assert(fallback(at('2026-10-31T05:00:00Z'))>0); // Sat 13 SGT
assert.equal(fallback(at('2026-10-31T08:00:00Z')),0);
const root=fs.mkdtempSync(path.join(os.tmpdir(),'lan42-audio-')),file=path.join(root,'state.json'),now=at('2026-10-27T01:00:00Z'),pin='a'.repeat(64);
const env={LAN42_AUDIO_QUIET_PATH:file,LAN42_AUDIO_QUIET_FINGERPRINT:pin};
let state={schema:1,scope:'lan42-audio',campus_id:64,issued:now,fingerprint:pin,windows:[{start:now-60,end:now+60,reason:'exam'}]};
try{
 fs.writeFileSync(file,JSON.stringify(state),{mode:0o600});assert.equal(quietUntil(env,now),now+60);
 state.command='rm -rf';fs.writeFileSync(file,JSON.stringify(state));assert.equal(quietUntil(env,now),0);
 delete state.command;state.windows[0].end=now+50000;fs.writeFileSync(file,JSON.stringify(state));assert.equal(quietUntil(env,now),0);
 const link=path.join(root,'link');fs.symlinkSync(file,link);assert.equal(quietUntil({...env,LAN42_AUDIO_QUIET_PATH:link},now),0);
 console.log('PASS: SGT fallback, bounded read-only quiet state, injected fields and symlinks rejected');
}finally{for(const entry of fs.readdirSync(root))fs.unlinkSync(path.join(root,entry));fs.rmdirSync(root);}
