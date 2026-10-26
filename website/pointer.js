/* Local-only, progressive enhancement. Native targets and click events are unchanged. */
(()=>{
  const fine=matchMedia('(hover: hover) and (pointer: fine)');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const contrast=matchMedia('(forced-colors: active)');
  const key='lan42.pointer-effects';
  let enabled=true;
  try{enabled=localStorage.getItem(key)!=='off';}catch{}
  const pointer=document.createElement('div');
  pointer.className='lan-pointer';pointer.setAttribute('aria-hidden','true');
  document.body.append(pointer);
  const toggle=document.createElement('button');
  toggle.type='button';toggle.className='pointer-toggle';
  (document.querySelector('footer')||document.body).append(toggle);
  let target=null,frame=0,x=0,y=0,inside=false;
  const eligible=()=>fine.matches&&!reduced.matches&&!contrast.matches;
  function hide(){pointer.classList.remove('visible','morphed');document.documentElement.classList.remove('lan-pointer-active');target=null;}
  function settings(){
    hide();toggle.disabled=!eligible();
    toggle.setAttribute('aria-pressed',String(enabled&&eligible()));
    toggle.textContent='Pointer effects: '+(!eligible()?'System default':enabled?'On':'Off');
    toggle.title=eligible()?'Toggle adaptive pointer effects. Saved only in this browser.':'Native pointer used for touch, reduced motion or high contrast.';
  }
  toggle.addEventListener('click',()=>{
    enabled=!enabled;try{localStorage.setItem(key,enabled?'on':'off');}catch{}
    settings();
  });
  for(const query of [fine,reduced,contrast])query.addEventListener('change',settings);
  function paint(){
    frame=0;
    if(!inside||!enabled||!eligible()){hide();return;}
    let left=x-5,top=y-5,width=10,height=10,radius=999;
    if(target){
      if(!target.isConnected){hide();return;}
      const box=target.getBoundingClientRect();
      left=box.left-5;top=box.top-4;width=box.width+10;height=box.height+8;
      radius=Math.min(14,height/2);
    }
    pointer.style.width=width+'px';pointer.style.height=height+'px';
    pointer.style.borderRadius=radius+'px';pointer.style.transform=`translate3d(${left}px,${top}px,0)`;
    pointer.classList.toggle('morphed',Boolean(target));pointer.classList.add('visible');
    document.documentElement.classList.add('lan-pointer-active');
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(paint);}
  document.addEventListener('pointermove',event=>{
    if(event.pointerType!=='mouse'||!enabled||!eligible()){hide();return;}
    x=event.clientX;y=event.clientY;
    const element=event.target instanceof Element?event.target:null;
    target=element?.closest('button:not(:disabled),nav a,a.button,summary')||null;
    // Preserve text selection, editable fields, ordinary links and native controls.
    const native=element?.closest('input,textarea,select,[contenteditable],pre,code,p,li,td,th,h1,h2,h3,a,button:disabled,video,audio,iframe');
    inside=Boolean(element)&&(!native||Boolean(target));
    if(inside)schedule();else hide();
  },{passive:true});
  document.addEventListener('pointerout',event=>{if(!event.relatedTarget){inside=false;hide();}});
  document.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse'){inside=false;hide();}});
  document.addEventListener('keydown',()=>{inside=false;hide();});
  window.addEventListener('blur',()=>{inside=false;hide();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){inside=false;hide();}});
  // On scrolling/resizing restore the native cursor until the next real movement.
  window.addEventListener('scroll',()=>{inside=false;hide();},{passive:true,capture:true});
  window.addEventListener('resize',()=>{inside=false;hide();});
  settings();
})();
