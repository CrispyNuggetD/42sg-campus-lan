'use strict';
const assert=require('assert'),fs=require('fs'),os=require('os'),path=require('path'),crypto=require('crypto'),factory=require('./avatar-cache');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'lan42-photo-'));
try{const cache=factory(root),name=crypto.createHash('sha256').update('hnah').digest('hex')+'.img';fs.writeFileSync(path.join(root,name),Buffer.from([137,80,78,71,13,10,26,10]));assert.equal(cache.read('hnah').type,'image/png');assert.equal(cache.has('../secret'),false);fs.writeFileSync(path.join(root,name),'<html>403</html>');assert.equal(cache.has('hnah'),false);console.log('PASS: private cache reads, type detection, no traversal, no HTML');}finally{for(const f of fs.readdirSync(root))fs.unlinkSync(path.join(root,f));fs.rmdirSync(root);}
