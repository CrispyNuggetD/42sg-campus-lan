'use strict';
const assert=require('assert'),create=require('./sabo');
(async()=>{
 let calls=[];
 const lookup=create({FORTYTWO_CLIENT_ID:'test',FORTYTWO_CLIENT_SECRET:'secret'},async(url,options)=>{
  calls.push({url,options});if(url.endsWith('/token'))return {access_token:'private',expires_in:3600};
  const login=url.split('/').pop();return {id:42,login,image:{link:login==='dthoo'?'https://evil.example/a.jpg':'https://cdn.intra.42.fr/'+login+'.jpg'}};
 });
 assert.deepStrictEqual(await lookup('thtay'),{login:'thtay',avatar:'https://cdn.intra.42.fr/thtay.jpg'});
 await lookup('thtay');assert.equal(calls.length,2);
 assert.equal((await lookup('dthoo')).avatar,null);assert.equal(calls.length,3);
 assert(calls[0].options.body.includes('grant_type=client_credentials'));
 assert.equal(calls[1].options.headers.Authorization,'Bearer private');
 await assert.rejects(lookup('../secret'));
 await assert.rejects(create({})('guoliu'),/Configure/);
 await assert.rejects(create({FORTYTWO_CLIENT_ID:'x',FORTYTWO_CLIENT_SECRET:'x'},async()=>{throw Error('offline');})('guoliu'));
 console.log('PASS: app token, lookup, cache, reuse, image filtering, invalid input, missing configuration, API failure');
})().catch(e=>{console.error(e);process.exitCode=1;});
