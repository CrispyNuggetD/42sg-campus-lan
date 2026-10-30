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
  if(v.columns>1)assert(v.columns*v.cardWidth+(v.columns-1)*v.gap<=width-62);
  previousColumns=v.columns;
 }
}
assert.equal(context.tableView(1280).cardWidth,160);
assert(html.includes('let tableZoom=1,tableLayout='),'Initial table view must be 100%');
assert(html.includes("tableLayout='round'"),'Default layout must seat diners around a table');
for(const count of [1,2,5,7,8,25,49,50]){
 const g=context.roundTable(count,160,240);
 assert.equal(g.seats.length,count);
 for(const p of g.seats){
  assert(p.x-80>=0&&p.x+80<=g.size&&p.y-120>=0&&p.y+120<=g.size,'Every card stays inside the scrollable scene');
  assert(Math.abs(Math.hypot(p.x-g.center,p.y-g.center)-g.radius)<.001,'Every diner sits around the same table');
 }
 for(let i=0;i<count;i++)for(let j=i+1;j<count;j++){
  const a=g.seats[i],b=g.seats[j];assert(Math.abs(a.x-b.x)>=160||Math.abs(a.y-b.y)>=240,'Diner cards never overlap');
 }
 if(count>2){
  const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y),expected=distance(g.seats[0],g.seats[1]);
  assert(Math.abs(distance(g.seats[count-1],g.seats[0])-expected)<.001,'Last and first are physically adjacent, just like every other pair');
 }
}
assert(html.includes('id="table-layout"'));
console.log('Round table: perimeter seating, last-to-first adjacency, no overlap and reachable scene bounds passed');
