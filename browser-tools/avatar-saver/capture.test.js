'use strict';
const assert=require('assert'),capture=require('./capture');
global.location={href:'https://cdn.intra.42.fr/photo.jpg#lan42-import='+'a'.repeat(32)};
let size=null;
global.document={images:[{complete:true,naturalWidth:1024,naturalHeight:512,src:'https://cdn.intra.42.fr/photo.jpg'}],createElement:()=>({getContext:()=>({drawImage:(image,x,y,w,h)=>{size=[w,h];}}),toDataURL:()=> 'data:image/png;base64,iVBORw0KGgo='})};
assert.equal(capture().job,'a'.repeat(32));assert.deepStrictEqual(size,[512,256]);
global.location.href='https://attacker.example/photo.jpg#lan42-import='+'a'.repeat(32);assert.throws(capture);
global.location.href='https://cdn.intra.42.fr/photo.jpg#lan42-import='+'a'.repeat(32);global.document.images=[];assert.throws(capture);
console.log('PASS: explicit import job, correct CDN, loaded image only, bounded pixel capture');
