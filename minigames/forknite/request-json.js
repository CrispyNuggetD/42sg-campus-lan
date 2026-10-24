'use strict';
const https=require('https');
module.exports=(url,options)=>new Promise((resolve,reject)=>{
 const req=https.request(url,options,res=>{let b='';res.setEncoding('utf8');res.on('data',x=>{b+=x;if(b.length>1048576)res.destroy(Error('Response too large'));});res.on('error',reject);res.on('end',()=>{try{if(res.statusCode<200||res.statusCode>=300)throw Error('API rejected request');resolve(JSON.parse(b));}catch(e){reject(e);}});});
 req.setTimeout(10000,()=>req.destroy(Error('Timeout')));req.on('error',reject);if(options.body)req.write(options.body);req.end();
});
