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
assert(!html.includes("arena.style.transform='scale("),'Never shrink the entire table');
assert(!html.includes('frame.style.height='),'Rows must remain reachable through normal page scrolling');
console.log('Readable 100% cards and density reflow checks passed');

for(const count of [1,2,5,7,8,25,49,50]){
 for(const cols of [1,2,3,7,10]){
  const seats=context.tableSeats(count,cols);
  assert.equal(new Set(seats.map(s=>s.row+':'+s.column)).size,count);
  for(let i=1;i<count;i++)assert.equal(Math.abs(seats[i].row-seats[i-1].row)+Math.abs(seats[i].column-seats[i-1].column),1,'Consecutive diners stay next to each other');
  const points=seats.map(s=>({x:50+s.column*170,y:70+s.row*200}));
  const path=context.tableLoop(points,13,points[points.length-1].y+150);
  assert(path.endsWith('L '+points[0].x+' '+points[0].y),'The last fork returns to the first seat');
 }
}
assert(html.includes('id="table-layout"'));
console.log('Connected table: consecutive-seat adjacency, unique positions and last-to-first closure passed');
