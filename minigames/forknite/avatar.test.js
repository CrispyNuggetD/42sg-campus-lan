'use strict';
const assert=require('assert'),render=require('./public/avatar');
function element(tag){return {tag,children:[],dataset:{},append(...nodes){this.children.push(...nodes);},set textContent(v){this.text=v;this.children=[];},get textContent(){return this.text;}};}
global.document={createElement:element,createTextNode:text=>({text})};global.location={href:'http://localhost:4242/'};
const sprite=element('div');render(sprite,['https://cdn.intra.42.fr/photo.jpg'],'cat','hnah');
assert.equal(sprite.dataset.photo,'loading');let image=sprite.children[0];assert.equal(typeof image.onerror,'function');image.onerror();
assert.equal(sprite.dataset.photo,'failed');assert.equal(sprite.children[1].href,'https://cdn.intra.42.fr/photo.jpg');
const retry=sprite.children.find(c=>c.tag==='button');retry.onclick();image=sprite.children[0];assert(image.src.includes('forknite_retry='));image.onload();assert.equal(sprite.dataset.photo,'loaded');
const alternate=element('div');render(alternate,['https://cdn.intra.42.fr/small.jpg','https://cdn.intra.42.fr/original.jpg'],'cat','hnah');alternate.children[0].onerror();assert.equal(alternate.children[0].src,'https://cdn.intra.42.fr/original.jpg');
console.log('PASS: image handlers, failed state, original link, retry, cache refresh, alternate URLs, successful state');
