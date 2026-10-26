'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
function mime(bytes){if(bytes.slice(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))return 'image/png';if(bytes[0]===255&&bytes[1]===216&&bytes[2]===255)return 'image/jpeg';if(['GIF87a','GIF89a'].includes(bytes.slice(0,6).toString()))return 'image/gif';if(bytes.slice(0,4).toString()==='RIFF'&&bytes.slice(8,12).toString()==='WEBP')return 'image/webp';return null;}
module.exports=function(root){
 function filename(login){if(!root||!/^[a-zA-Z0-9_.-]{1,32}$/.test(login))return null;return path.join(root,crypto.createHash('sha256').update(login.toLowerCase()).digest('hex')+'.img');}
 function read(login){const file=filename(login);if(!file)throw Error('No cache');const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);try{const stat=fs.fstatSync(fd);if(!stat.isFile()||stat.size>1048576)throw Error('Invalid cache');const bytes=fs.readFileSync(fd);const type=mime(bytes);if(!type)throw Error('Invalid image');return {bytes,type};}finally{fs.closeSync(fd);}}
 function has(login){try{read(login);return true;}catch(e){return false;}}
 function version(login){try{return String(fs.statSync(filename(login)).mtimeMs);}catch(e){return '0';}}
 return {read,has,version};
};
module.exports.mime=mime;
