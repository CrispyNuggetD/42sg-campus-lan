'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/public/index.html','utf8'),context={};
vm.createContext(context);
vm.runInContext(html.split('// TABLE_VIEW_START')[1].split('// TABLE_VIEW_END')[0],context);
for(const width of [280,320,768,1280,1920]){
 let previousColumns=Infinity;
 for(const zoom of [.5,.75,1,1.5]){
  const v=context.tableView(width,zoom);
  assert(v.cardWidth>=120&&v.photo>=40,'Cards and pictures remain visible when zoomed out');
  assert(v.columns>=1&&v.columns<=previousColumns,'Zoom out adds columns instead of shrinking text');
  if(v.columns>1)assert(v.columns*v.cardWidth+(v.columns-1)*v.gap<=width-30);
  previousColumns=v.columns;
 }
}
assert.equal(context.tableView(1280).cardWidth,160);
assert(html.includes('let tableZoom=1;'),'Initial table view must be 100%');
assert(!html.includes("arena.style.transform='scale("),'Never shrink the entire table');
assert(!html.includes('frame.style.height='),'Rows must remain reachable through normal page scrolling');
console.log('Readable 100% cards and density reflow checks passed');
