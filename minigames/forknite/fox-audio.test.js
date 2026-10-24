'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/public/index.html','utf8');
const source=html.split('// FOX_AUDIO_START')[1].split('// FOX_AUDIO_END')[0];
const create=vm.runInNewContext(source+';createFoxAudio');
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
