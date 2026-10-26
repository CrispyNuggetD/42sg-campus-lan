/* Optional copy controls: commands remain selectable without JavaScript. */
(()=>{
  if(!navigator.clipboard?.writeText)return;
  const status=document.getElementById('copy-status');
  document.querySelectorAll('[data-copy-command],[data-copy-source]').forEach(button=>{
    button.hidden=false;
    const label=button.innerHTML;let reset;
    button.addEventListener('click',async()=>{
      const value=button.dataset.copyCommand||document.getElementById(button.dataset.copySource)?.textContent.trim();
      if(!value)return;
      try{
        await navigator.clipboard.writeText(value);
        button.textContent='Copied';
        status.textContent=button.dataset.copyCommand?'Copied '+value+' — paste it into LAN42.':'Setup copied — paste it into your terminal.';
      }catch{button.textContent='Select text';status.textContent='Automatic copy is unavailable. Select the command text and copy it manually.';}
      clearTimeout(reset);reset=setTimeout(()=>{button.innerHTML=label;},1800);
    });
  });
})();
