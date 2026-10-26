'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/public/index.html','utf8');
const source=html.split('// FOX_AUDIO_START')[1].split('// FOX_AUDIO_END')[0];
let wall=Date.parse('2026-10-27T01:00:00Z');class ClockDate extends Date{static now(){return wall;}}
const create=vm.runInNewContext(source+';createFoxAudio',{Date:ClockDate});
let played=[],clock=0;
class AudioMock{constructor(src){this.src=src;}play(){played.push(this);return Promise.resolve();}pause(){this.paused=true;}}
const audio=create(['fox1','fox2'],AudioMock,()=>0,()=>clock);
audio.eat();assert.equal(played.length,0);
assert.equal(audio.toggle(),true);assert.equal(played.length,1);assert.equal(played[0].volume,.2);
audio.eat();assert.equal(played.length,1);
clock=201;audio.eat();assert.equal(played.length,2);
clock=402;audio.eat();assert.equal(played.length,2);
played[0].onended();audio.eat();assert.equal(played.length,3);
audio.setVolume(.1);assert.equal(played[2].volume,.1);
assert.equal(audio.toggle(),false);assert(played[2].paused);audio.eat();assert.equal(played.length,3);
assert.equal((html.match(/data:audio\/ogg;base64,/g)||[]).length,5);
console.log('PASS: opt-in fox audio, eating triggers, volume, cooldown, overlap limit, mute, five bundled variants');
let deathPlayed=[];
class DeathAudio{constructor(src){this.src=src;}play(){deathPlayed.push(this);return Promise.resolve();}pause(){this.paused=true;}}
const deathAudio=create(['eat'],DeathAudio,()=>0,()=>0,['death']);
deathAudio.death();assert.equal(deathPlayed.length,0);
deathAudio.toggle();deathAudio.death();assert.equal(deathPlayed.length,2);assert.equal(deathPlayed[1].src,'death');assert(deathPlayed[0].paused);
deathAudio.toggle();assert(deathPlayed[1].paused);
const pools=html.match(/const foxAudio=createFoxAudio\((\[.*?\]),Audio,Math.random,\(\)=>performance.now\(\),(\[.*?\])\);/);
assert(pools);const eating=JSON.parse(pools[1]),dying=JSON.parse(pools[2]);assert.equal(eating.length,3);assert.equal(dying.length,2);assert(eating.every(x=>!dying.includes(x)));
console.log('PASS: death only on enabled cue, priority over chewing, mute, separate eating/death pools');
const quietAudio=create(['eat'],DeathAudio,()=>0,()=>0,['death']);
const beforeQuiet=deathPlayed.length;quietAudio.setQuiet(wall/1000+60);quietAudio.toggle();quietAudio.eat();quietAudio.death();assert.equal(deathPlayed.length,beforeQuiet);
quietAudio.setQuiet(0);assert.equal(deathPlayed.length,beforeQuiet);quietAudio.death();assert.equal(deathPlayed.length,beforeQuiet+1);
console.log('PASS: quiet overlay blocks eating/death/toggle playback and never auto-plays on release');

const fallbackAudio=create(['eat'],DeathAudio,()=>0,()=>0,['death']);wall=Date.parse('2026-10-31T05:00:00Z');const beforeFallback=deathPlayed.length;fallbackAudio.toggle();fallbackAudio.death();assert.equal(deathPlayed.length,beforeFallback);wall=Date.parse('2026-10-31T08:00:00Z');fallbackAudio.death();assert.equal(deathPlayed.length,beforeFallback+1);console.log('PASS: browser inbuilt Saturday quiet works without its server');

wall=Date.parse('2026-10-27T01:00:00Z');const queueAudio=create(['eat'],DeathAudio,()=>0,()=>0,['death']);const qStart=wall/1000+60;assert(queueAudio.setWindows([{start:qStart,end:qStart+10800,reason:'exam'}]));queueAudio.toggle();wall+=61000;const beforeQueued=deathPlayed.length;queueAudio.death();assert.equal(deathPlayed.length,beforeQueued);assert.equal(queueAudio.setWindows([{start:wall/1000,end:wall/1000+60,reason:'exam',command:'malicious'}]),false);console.log('PASS: future exam queue mutes offline replay and rejects injected window fields');
