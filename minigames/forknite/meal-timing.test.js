'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/public/index.html','utf8');
const context={};vm.createContext(context);
vm.runInContext(html.split('// MEAL_TIMING_START')[1].split('// MEAL_TIMING_END')[0],context);
const {mealWindow,observeMeal,mealTiming}=context;
const odd=mealWindow(5,100,100),even=mealWindow(4,100,100);
assert.equal(odd.expected,300);assert.equal(even.expected,200);
assert.equal(mealWindow(5,100,400).expected,500);
assert.equal(mealWindow(1,100,100),null);assert.equal(mealWindow(5,NaN,100),null);
let card={meals:1,lastMeal:0,lastDelay:0,dead:false};
assert.equal(mealTiming(card,101,600,odd).late,false); // One eat is normal waiting.
assert.equal(mealTiming(card,300,600,odd).late,false); // Five-seat clock's third slot is normal.
assert.equal(mealTiming(card,305,600,odd).late,false); // Scheduler grace.
assert.equal(mealTiming(card,306,600,odd).late,true);
assert.equal(mealTiming(card,250,600,even).late,true);
assert.equal(mealTiming(card,250,600,odd).late,false);
observeMeal(card,350,odd);
assert.equal(card.lastDelay,50);assert.equal(card.meals,2);
assert.equal(mealTiming(card,350,600,odd).color,'#ffad42'); // Late meal stays marked after it starts.
assert(mealTiming(card,350,600,odd).label.includes('+50ms late'));
observeMeal(card,650,odd);
assert.equal(mealTiming(card,650,600,odd).late,false); // Next on-time meal clears it.
assert.equal(mealTiming(card,650,600,odd).color,'#f38bd5');
assert(mealTiming(card,1000,600,odd).label.includes('overdue'));
card.dead=true;assert.equal(mealTiming(card,1000,600,odd).late,false);
assert.equal(mealTiming(card,1000,600,odd).remaining,0);
card.dead=false;assert.equal(mealTiming(card,1000,600,null).late,false);
assert.equal(mealTiming({...card,meals:0},0,600,odd).remaining,600);
// The running browser must use the timing helpers, not the previous meal-count-only paint.
assert(html.includes('observeMeal(c,e.ms,timingWindow)'));
assert(html.includes("classList.toggle('meal-late',timing.late)"));
assert(html.includes('if(roundActive&&!catchUp)sim+='));
console.log('PASS: five-seat clock allowance, full-cycle timing, persistent late-meal color, recovery, death and missing timings');
// Compile the complete browser script, and exercise its real event/render paths.
new vm.Script(html.split('<script>')[1].split('</script>')[0]);
const nodes={};let orange=false;
const element={style:{setProperty(key,value){nodes[key]=value;}},classList:{toggle(key,value){if(key==='meal-late')orange=value;}},querySelector(key){return nodes[key]||(nodes[key]={textContent:'Fixture diner',style:{}});}};
const rendered={el:element,meals:1,lastMeal:0,lastDelay:0,dead:false};
Object.assign(context,{count:2,cards:[null,rendered],timingWindow:odd,document:{hidden:true},foxAudio:{eat(){},death(){}},note(){},refreshIdentity(){},round:1,roundActive:true,catchUp:false,deadline:600,sim:350,last:0,paused:false,queue:[],cursor:0,requestAnimationFrame(){},$:key=>nodes[key]||(nodes[key]={value:'1',textContent:''})});
vm.runInContext(html.slice(html.indexOf('function apply(e){'),html.indexOf('const stream=new EventSource')),context);
context.apply({type:'move',id:1,action:'is eating',ms:350});
assert.equal(rendered.lastDelay,50);
context.apply({type:'end',round:1,code:0});
vm.runInContext(html.slice(html.indexOf('function tick(now){'),html.indexOf("$('#pause').onclick")),context);
context.tick(1000);assert.equal(context.sim,350);assert.equal(orange,true);assert.equal(nodes['--meal-color'],'#ffad42');
assert(nodes['.meal-timing'].textContent.includes('+50ms late'));
context.apply({type:'move',id:1,action:'is eating',ms:650});context.sim=650;context.tick(1100);
assert.equal(orange,false);assert.equal(nodes['--meal-color'],'#f38bd5');
console.log('PASS: actual browser meal events paint orange, recover next meal and freeze timing when native round ends');

// Five diners: the fifth eating start in a meal wave is purple even though a
// normal third eating slot is not overdue. Highlight the actual eater card.
function cardFixture(){
 const nodes={},flags={};return {nodes,flags,meals:0,lastMeal:0,lastDelay:0,dead:false,el:{style:{setProperty(k,v){nodes[k]=v;}},classList:{toggle(k,v){flags[k]=v;}},querySelector(k){return nodes[k]||(nodes[k]={textContent:'Fixture diner',style:{}});}}};
}
const wave=Array.from({length:5},cardFixture);context.cards=[null,...wave];context.count=5;
for(let i=0;i<5;i++){
 context.apply({type:'move',id:i+1,action:'is eating',ms:Math.floor(i/2)*100});
 if(i<4)context.apply({type:'move',id:i+1,action:'is sleeping',ms:Math.floor(i/2)*100+100});
}
context.sim=200;context.tick(1200);
assert.equal(wave.filter(c=>c.flags['odd-turn']).length,1);
assert.equal(wave[4].nodes['--meal-color'],'#bc8cff');assert.equal(wave[4].flags['meal-late'],false);
assert(wave[4].nodes['.meal-timing'].textContent.includes('Odd-table last turn'));
context.apply({type:'move',id:5,action:'is sleeping',ms:300});context.tick(1300);
assert.equal(wave[4].flags['odd-turn'],false);
// Even tables have no extra odd-table turn.
for(const c of wave)c.meals=1;
assert.equal(context.oddLastEater(wave,wave[4],4),false);
console.log('PASS: n=5 last eater gets a purple card/bar during its normal extra turn; sleeping and even-table cards do not');
