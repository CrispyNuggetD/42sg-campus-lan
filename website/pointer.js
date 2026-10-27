/* Local-only visual feedback; never move targets or intercept input. */
(()=>{
  const fine=matchMedia('(hover: hover) and (pointer: fine)');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const contrast=matchMedia('(forced-colors: active)');
  const key='lan42.pointer-effects';let enabled=true;
  try{enabled=localStorage.getItem(key)!=='off';}catch{}
  const pointer=document.createElement('div');pointer.className='lan-pointer';pointer.setAttribute('aria-hidden','true');document.body.append(pointer);
  const toggle=document.createElement('button');toggle.type='button';toggle.className='pointer-toggle';
  const tools=document.createElement('aside');tools.className='pointer-tools';tools.setAttribute('aria-label','Pointer preferences and open-source code');
  const source=document.createElement('a');source.href='https://github.com/CrispyNuggetD/RykerTorch-FOSS-Toolbox/tree/main/web-apps/adaptive-pointer';source.textContent='Get this effect ↗';source.className='pointer-source';
  tools.append(toggle,source);document.body.append(tools);document.documentElement.classList.add('has-pointer-tools');
  const eligible=()=>fine.matches&&!reduced.matches&&!contrast.matches;
  let x=0,y=0,inside=false,frame=0,last=0,current=null,goal=null;
  function hide(){inside=false;current=null;goal=null;last=0;pointer.classList.remove('visible','morphed','text-beam');document.documentElement.classList.remove('lan-pointer-active');if(frame)cancelAnimationFrame(frame);frame=0;}
  function settings(){hide();toggle.disabled=!eligible();toggle.setAttribute('aria-pressed',String(enabled&&eligible()));toggle.textContent='Pointer: '+(!eligible()?'Native':enabled?'On':'Off');toggle.title=eligible()?'Toggle adaptive pointer effects. Saved only in this browser.':'Native pointer used for touch, reduced motion or high contrast.';}
  toggle.addEventListener('click',()=>{enabled=!enabled;try{localStorage.setItem(key,enabled?'on':'off');}catch{}settings();});
  for(const query of [fine,reduced,contrast])query.addEventListener('change',settings);
  function update(element){
    if(!inside||!enabled||!eligible()||!(element instanceof Element)){hide();return;}
    const native=element.closest('select,iframe,video,audio,button:disabled,input:disabled,input[type="range"],input[type="color"],input[type="file"]');
    if(native){hide();return;}
    const target=element.closest('a[href],button:not(:disabled),summary,[role="button"]');
    const text=!target&&element.closest('input,textarea,[contenteditable="true"],p,li,td,th,h1,h2,h3,h4,label,pre,code');
    goal={x,y,w:text?3:14,h:text?23:14,r:text?1.5:7,t:text?1:0};
    if(target){
      const rects=[...target.getClientRects()];
      const box=rects.find(r=>y>=r.top&&y<=r.bottom&&x>=r.left&&x<=r.right)||target.getBoundingClientRect();
      goal={x:box.left+box.width/2,y:box.top+box.height/2,w:box.width+10,h:box.height+8,r:Math.min(14,(box.height+8)/2),t:0};
      if(target.dataset.pointerShape==='circle'){const size=Math.max(goal.w,goal.h);goal.w=size;goal.h=size;goal.r=size/2;}
    }
    pointer.classList.toggle('morphed',Boolean(target));pointer.classList.toggle('text-beam',Boolean(text));
    // A single shape and continuously interpolated centre preserve entry/exit continuity.
    if(!current){
      current={x,y,w:14,h:14,r:7,t:0};
      pointer.style.width='14px';pointer.style.height='14px';pointer.style.borderRadius='7px';
      pointer.style.transform=`translate3d(${x-7}px,${y-7}px,0)`;pointer.style.setProperty('--beam',0);
    }
    pointer.classList.add('visible');document.documentElement.classList.add('lan-pointer-active');schedule();
  }
  function paint(now){
    frame=0;if(!inside||!goal||!current||!enabled||!eligible()){hide();return;}
    const dt=last?Math.min(40,now-last):16;last=now;
    const ease=1-Math.exp(-dt/46);let moving=false;
    for(const key of ['x','y','w','h','r','t']){const difference=goal[key]-current[key];current[key]+=difference*ease;if(Math.abs(difference)>.04)moving=true;else current[key]=goal[key];}
    pointer.style.width=current.w+'px';pointer.style.height=current.h+'px';pointer.style.borderRadius=current.r+'px';
    pointer.style.transform=`translate3d(${current.x-current.w/2}px,${current.y-current.h/2}px,0)`;
    pointer.style.setProperty('--beam',current.t);
    if(moving)schedule();else last=0;
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(paint);}
  document.addEventListener('pointermove',event=>{if(event.pointerType!=='mouse'||!enabled||!eligible()){hide();return;}x=event.clientX;y=event.clientY;inside=true;update(event.target);},{passive:true});
  document.addEventListener('pointerout',event=>{if(!event.relatedTarget)hide();});
  document.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse')hide();});
  document.addEventListener('keydown',hide);
  window.addEventListener('blur',hide);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)hide();});
  // Re-evaluate the real hit target after layout changes without tearing down the shape.
  const relayout=()=>{if(inside)update(document.elementFromPoint(x,y));};
  window.addEventListener('scroll',relayout,{passive:true,capture:true});window.addEventListener('resize',relayout);
  settings();
})();
