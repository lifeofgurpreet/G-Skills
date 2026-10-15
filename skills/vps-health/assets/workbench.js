/* Local view controls: navigation, frozen review and clipboard. No terminal execution or external actions. */
(function(){
 'use strict';
 const command=$('command-dialog'),reviewDialog=$('review-dialog'),search=$('command-search');
 let commandItems=[],activeCommand=0,returnFocus=null,pinnedTask=null;
 const restoreFocus=()=>{const target=returnFocus?.id?$(returnFocus.id):returnFocus;if(target?.isConnected&&!target.disabled)target.focus({preventScroll:true});else $('open-command').focus({preventScroll:true})};
 function pauseView(){
  ui.paused=!ui.paused;requestEpoch++;updateTransport();
  $('operator-feedback').textContent=ui.paused?'View paused at '+utc(state.as_of)+'. Collection continues independently. Refresh once or resume to see newer readings.':'View updates resumed. Collection was not stopped or restarted.';
  if(!ui.paused)refresh(true);
 }
 $('pause-view').addEventListener('click',pauseView);
 function showCommands(){
  if(reviewDialog.open)return;
  returnFocus=document.activeElement;search.value='';activeCommand=0;renderCommands();command.showModal();search.focus();
 }
 function selectCommand(index){
  activeCommand=Math.max(0,Math.min(commandItems.length-1,index));
  const options=[...$('command-results').children];
  options.forEach((node,i)=>node.setAttribute('aria-selected',String(i===activeCommand)));
  const selected=options[activeCommand];
  if(selected){search.setAttribute('aria-activedescendant',selected.id);selected.scrollIntoView({block:'nearest'})}
  else search.removeAttribute('aria-activedescendant');
 }
 function renderCommands(){
  const previous=commandItems[activeCommand]?.id;
  commandItems=VpsView.commands(state,search.value,{live,paused:ui.paused});
  const container=$('command-results');container.replaceChildren();
  commandItems.forEach((item,index)=>{
   const option=el('div','','command-result');option.id='command-result-'+index;option.setAttribute('role','option');option.setAttribute('aria-selected','false');
   const meta=el('span',item.kind==='node'?'NODE':item.kind==='view'?'VIEW':'ACTION','command-type');
   const body=el('span','');body.append(el('span',item.title,'command-name'),el('span',item.detail,'command-detail'));option.append(meta,body);
   option.addEventListener('click',()=>executeCommand(index));container.append(option);
  });
  $('command-empty').hidden=Boolean(commandItems.length);
  const preserved=commandItems.findIndex(i=>i.id===previous);selectCommand(preserved<0?0:preserved);
 }
 function executeCommand(index){
  const item=commandItems[index];if(!item)return;command.close();
  if(item.kind==='node'){setView('overview');location.hash='overview';chooseNode(item.target);returnFocus=$('node-selector');returnFocus.focus({preventScroll:true})}
  else if(item.kind==='view'){setView(item.target);location.hash=item.target;returnFocus=$('main');returnFocus.focus({preventScroll:true})}
  else if(item.target==='pause')pauseView();
  else if(item.target==='export')$('save-summary').click();
  else if(item.target==='support')$('save-support').click();
 }
 $('open-command').addEventListener('click',showCommands);
 $('close-command').addEventListener('click',()=>command.close());
 search.addEventListener('input',()=>{activeCommand=0;renderCommands()});
 search.addEventListener('keydown',event=>{
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();selectCommand(activeCommand+(event.key==='ArrowDown'?1:-1))}
  else if(event.key==='Enter'){event.preventDefault();executeCommand(activeCommand)}
  else if(event.key==='Escape'){event.preventDefault();command.close()}
 });
 command.addEventListener('close',restoreFocus);
 document.addEventListener('keydown',event=>{
  if(!event.isComposing&&(event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){
   event.preventDefault();if(command.open)command.close();else showCommands();
  }
 });
 function openReview(){
  const node=selected();if(!node)return;
  const r=VpsView.review(state,node.id);pinnedTask=VpsView.task(state,node.id);returnFocus=document.activeElement;
  $('review-subject').textContent=(r.synthetic?'SYNTHETIC / ':'PRIVATE / ')+r.id+' / '+r.label;
  $('review-finding').textContent=r.title;$('review-next').textContent=r.next;
  $('review-mean').textContent=VpsView.percent(r.mean);$('review-coverage').textContent=VpsView.percent(r.coverage,1);$('review-hours').textContent=VpsView.hours(r.observedHours);
  $('review-window').textContent='Full assessment: '+r.window.start+' → '+r.window.end;
  $('review-limits').replaceChildren(...r.holds.map(h=>el('li',holds[h]||h.replaceAll('_',' '))));
  if(!r.holds.length)$('review-limits').append(el('li','Application impact and plan terms require their own evidence.'));
  $('review-task').value=pinnedTask;$('review-feedback').textContent='';reviewDialog.querySelector('details').open=false;
  reviewDialog.showModal();$('review-title').focus();
 }
 $('open-case-review').addEventListener('click',openReview);
 $('close-review').addEventListener('click',()=>reviewDialog.close());
 reviewDialog.addEventListener('close',()=>{pinnedTask=null;restoreFocus()});
 $('copy-review-task').addEventListener('click',()=>{if(pinnedTask)VpsOperator.copyText(pinnedTask,{fallback:$('review-task'),feedback:$('review-feedback')})});
 $('copy-case-task').addEventListener('click',()=>{const node=selected();if(node)VpsOperator.copyText(VpsView.task(state,node.id))});
 // Some browser tab sequences visit browser chrome at native-dialog edges.
 // Keep the app's declared modal sequence inside the actual visible controls.
 for(const dialog of [command,reviewDialog])dialog.addEventListener('keydown',event=>{
  if(event.key!=='Tab')return;
  const controls=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex="0"]')]
    .filter(node=>node.getClientRects().length&&getComputedStyle(node).visibility!=='hidden');
  if(!controls.length)return;
  const active=document.activeElement,first=controls[0],last=controls[controls.length-1];
  if(event.shiftKey&&(active===first||active===dialog.querySelector('h2'))){event.preventDefault();last.focus()}
  else if(!event.shiftKey&&active===last){event.preventDefault();first.focus()}
 });
 for(const dialog of [command,reviewDialog])dialog.addEventListener('click',event=>{
  if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();
  if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();
 });
 const rail=document.querySelector('.rail'),menu=$('menu-toggle');
 function setMenu(open){rail.dataset.expanded=String(open);menu.setAttribute('aria-expanded',String(open))}
 menu.addEventListener('click',()=>setMenu(menu.getAttribute('aria-expanded')!=='true'));
 document.querySelectorAll('#primary-navigation a[data-view]').forEach(link=>link.addEventListener('click',()=>{
  if(window.matchMedia('(max-width:760px)').matches){setMenu(false);$('main').focus({preventScroll:true})}
 }));
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&menu.getAttribute('aria-expanded')==='true'&&!command.open&&!reviewDialog.open){setMenu(false);menu.focus()}
 });
 document.addEventListener('vps-status',()=>{if(command.open)renderCommands()});
})();
