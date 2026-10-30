'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/public/index.html','utf8'),context={};
vm.createContext(context);
vm.runInContext(html.split('// TABLE_VIEW_START')[1].split('// TABLE_VIEW_END')[0],context);
for(const diners of [1,5,25,50]){
 const size=Math.max(650,Math.ceil(diners*200/Math.PI)+180);
 for(const [width,height] of [[320,480],[1280,650],[1920,900]]){
  const v=context.tableView(size,width,height);
  assert(v.width<=width+.001&&v.height<=height+.001,'Whole table must fit '+diners+' diners');
  assert(v.scale>0&&v.scale<=1);
 }
 const full=context.tableView(size,320,480,1);
 assert.equal(full.width,size);assert.equal(full.scale,1);
}
assert.equal(context.tableView(3364,1280,650,.5).width,1682);
assert(html.includes("new ResizeObserver(fitTable)"));
assert(html.includes('id="table-fit"'));
console.log('Table fit and manual zoom checks passed');
