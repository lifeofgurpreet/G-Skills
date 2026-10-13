/* Original local operator workflow. Rendering and acknowledgment never mutate evidence. */
const VpsOperator=(()=>{
 'use strict';
 const knownProviders=new Set(['contabo','hetzner','digitalocean','akamai','aws','other']);
 const origins=new Set(['docs.contabo.com','docs.hetzner.com','docs.digitalocean.com','techdocs.akamai.com','docs.aws.amazon.com']);
 let acknowledged=new Set(),storageKey='',desktopEnabled=false,seen=new Set(),lastState=null,setupMode='local';
 const make=(tag,text='',cls='')=>{const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;return node};
 const byId=id=>document.getElementById(id);
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
 const ratio=x=>x===null||finite(x)&&x>=0&&x<=1.02;
 const safeLink=url=>{try{const parsed=new URL(url);return parsed.protocol==='https:'&&origins.has(parsed.hostname)&&!parsed.username&&!parsed.password}catch{return false}};
 function valid(value){
  const b=value.operator,p=value.provider_reference;
  if(!b||b.schema!=='g-skills.operator-brief.v1'||!Array.isArray(b.items)||b.items.length>100||b.automatic_actions!==false||b.service_health_verified!==false)return false;
  if(!b.items.every(i=>/^[a-f0-9]{24}$/.test(i.id)&&value.assets.some(n=>n.id===i.node)&&['urgent','review','info'].includes(i.priority)&&typeof i.title==='string'&&typeof i.reason==='string'&&typeof i.next_action==='string'&&i.contact_authorized===false&&i.provider_cause_proven===false&&object(i.evidence)&&['mean','coverage','pressure','cfs'].every(k=>ratio(i.evidence[k]))&&['elapsed_hours','observed_hours'].every(k=>finite(i.evidence[k])&&i.evidence[k]>=0)&&typeof i.draft_eligible==='boolean'))return false;
  if(!p||typeof p.reviewed_on!=='string'||!['DATED_REFERENCE','RECHECK_REQUIRED'].includes(p.review_state)||p.schema!=='g-skills.provider-reference.v1'||!Array.isArray(p.providers)||p.providers.length!==6||p.establishes_contract!==false)return false;
  if(!p.providers.every(provider=>knownProviders.has(provider.id)&&typeof provider.name==='string'&&typeof provider.summary==='string'&&typeof provider.not_a_promise==='string'&&Array.isArray(provider.classes)&&provider.classes.every(c=>typeof c==='string')&&Array.isArray(provider.facts)&&provider.facts.every(f=>typeof f.text==='string'&&typeof f.scope==='string'&&typeof f.kind==='string'&&safeLink(f.source))&&Array.isArray(provider.check_next)&&provider.check_next.every(c=>typeof c==='string')))return false;
  const r=value.agent_runtime;
  if(!r||r.schema!=='g-skills.agent-runtime.v1'||!['NOT_MANAGED','STARTING','RUNNING','STOP_REQUESTED','STOPPED','COMPLETED','FAILED','NEEDS_REVIEW','ORPHANED'].includes(r.state)||typeof r.process_verified!=='boolean'||r.evidence_ready!==false)return false;
  if(r.dashboard_url&&!/^http:\/\/127\.0\.0\.1:\d{1,5}\/$/.test(r.dashboard_url))return false;
  if(!Array.isArray(r.requests)||r.requests.length>8||!r.requests.every(q=>object(q)&&typeof q.purpose==='string'&&typeof q.required_capability==='string'&&['NEEDS_CONNECTION','HOST_REPORTED_AVAILABLE','DECLINED'].includes(q.state)&&q.send_authorized===false))return false;
  if(r.events&&(!Array.isArray(r.events)||r.events.length>32||!r.events.every(e=>object(e)&&typeof e.at==='string'&&typeof e.code==='string')))return false;
  return value.assets.every(n=>n.timeline===undefined||Array.isArray(n.timeline)&&n.timeline.length<=96&&n.timeline.every(c=>finite(c.start)&&finite(c.end)&&c.end>c.start&&finite(c.coverage)&&c.coverage>=0&&c.coverage<=1&&['unknown','partial','within','watch','investigate'].includes(c.state)));
 }
 function syncStorage(value){
  const key='gskills-ack-'+value.configuration_sha256;
  if(key===storageKey)return;
  storageKey=key;acknowledged=new Set();seen=new Set();desktopEnabled=false;
  try{const stored=JSON.parse(sessionStorage.getItem(key)||'[]');if(Array.isArray(stored))acknowledged=new Set(stored.filter(id=>typeof id==='string'&&/^[a-f0-9]{24}$/.test(id)).slice(0,100))}catch{}
 }
 function acknowledge(item){
  acknowledged.add(item.id);
  const active=new Set(lastState.operator.items.map(i=>i.id));acknowledged=new Set([...acknowledged].filter(id=>active.has(id)));
  try{sessionStorage.setItem(storageKey,JSON.stringify([...acknowledged]))}catch{}
  renderInbox(lastState);byId('operator-feedback').textContent='Acknowledged in this tab. The evidence and any HOLD are unchanged.';
 }
 function inspect(node){setView('overview');location.hash='overview';chooseNode(node);byId('node-selector').focus({preventScroll:true})}
 function renderInbox(value){
  const items=value.operator.items,unread=items.filter(i=>!acknowledged.has(i.id));
  byId('attention-count').textContent=String(unread.length);
  byId('inbox-count').textContent=`${items.length} active findings · ${unread.length} unread`;
  const banner=byId('attention-banner');banner.hidden=items.length===0;
  if(items.length){byId('attention-title').textContent=items[0].title;byId('attention-copy').textContent=`${items[0].node} · ${items.length} active ${items.length===1?'finding':'findings'}. Start with evidence quality, not provider blame.`}
  const grid=byId('attention-items');grid.replaceChildren();
  if(!items.length){grid.append(make('p','No active attention items. This does not certify service latency, availability or provider performance.','empty'));return}
  for(const item of items){
   const article=make('article','','finding'+(acknowledged.has(item.id)?' acknowledged':''));article.dataset.priority=item.priority;
   const meta=make('div',item.node+' / '+item.priority,'finding-meta');article.append(meta,make('h3',item.title),make('p',item.reason));
   const evidence=make('div','','finding-evidence');
   evidence.append(make('span','Accounted '+pct(item.evidence.mean)),make('span','Coverage '+pct(item.evidence.coverage,0)),make('span',fixed(item.evidence.observed_hours)+'h observed'));
   article.append(evidence,make('p',item.next_action,'finding-next'));
   const actions=make('div','','finding-actions'),look=make('button','Inspect evidence','button primary');look.type='button';look.onclick=()=>inspect(item.node);
   const ack=make('button',acknowledged.has(item.id)?'Acknowledged':'Acknowledge','button');ack.type='button';ack.id='ack-'+item.id;ack.disabled=acknowledged.has(item.id);ack.onclick=()=>acknowledge(item);
   const handoff=make('button','Copy agent task','button');handoff.onclick=()=>copyTask(item);
   actions.append(look,ack,handoff);article.append(actions);grid.append(article);
  }
 }
 async function copyText(text){
  try{await navigator.clipboard.writeText(text);byId('operator-feedback').textContent='Copied locally. Nothing was executed or sent.'}
  catch{const box=byId('copy-fallback');box.hidden=false;box.value=text;box.focus();box.select();byId('operator-feedback').textContent='Clipboard unavailable. Copy the selected text manually.'}
 }
 function copyTask(item){
  const kind=lastState.synthetic?'This workspace is SYNTHETIC; demonstrate only.':'Use only the authorized private workspace.';
  const draft=item.draft_eligible?'If I explicitly request a draft, use draft-email with my observed service impact. Do not send it.':'Do not prepare a real performance complaint from this evidence. A plan clarification can be requested separately.';
  const task=`Read the installed vps-health/SKILL.md and its operator-playbook.md. ${kind}\nSubject: ${item.node}\nFinding: ${item.title}\nNext check: ${item.next_action}\nRun the read-only doctor first. Preserve captures and compare the same UTC window; do not change CPU limits, schedule a stress test, install a service or contact a provider. Report what is established and what is still unknown.\n${draft}`;
  copyText(task);
 }
 function renderProviders(value){
  const selected=byId('provider-filter').value,ref=value.provider_reference;
  byId('provider-review').textContent=`Documentation reviewed ${ref.reviewed_on} · ${ref.review_state==='RECHECK_REQUIRED'?'Recheck the linked primary sources before relying on them.':'Dated reference, not live policy verification.'}`;
  const grid=byId('provider-cards');grid.replaceChildren();
  for(const provider of ref.providers.filter(p=>selected==='all'||p.id===selected)){
   const card=make('article','','provider-card');card.append(make('span',provider.classes.join(' / '),'provider-class'),make('h3',provider.name),make('p',provider.summary));
   const details=make('details'),summary=make('summary','Read the plan distinctions');details.append(summary);
   for(const fact of provider.facts){const block=make('div','','policy-fact');block.append(make('strong',fact.scope+' · '+fact.kind.replaceAll('_',' ')),make('p',fact.text));const link=make('a','Primary documentation ↗');link.href=fact.source;link.target='_blank';link.rel='noopener noreferrer';block.append(link);details.append(block)}
   const list=make('ul');for(const check of provider.check_next)list.append(make('li',check));details.append(list);card.append(details,make('p',provider.not_a_promise,'policy-limit'));grid.append(card);
  }
 }
 const routes={
  local:{title:'One server. One private workspace.',intro:'Use this on the authorized Linux VPS. No Prometheus installation, root access or stress workload is required.',steps:[['Configure','Record an alias and the exact provider/plan when known. Bootstrap does not collect.'],['Approve one collector','Use the foreground loop or a reviewed timer, not both. Two local ticks form the first measured interval.'],['Inspect and retain','Run doctor, follow the evidence gaps, and keep application-impact notes alongside the same UTC window.']],command:'python3 scripts/vps_health.py bootstrap --mode local --node my-vps --workspace "$HOME/vps-health"\npython3 scripts/vps_health.py doctor --workspace "$HOME/vps-health"\n# Only after approving recurring passive collection:\npython3 scripts/vps_health.py watch --workspace "$HOME/vps-health" --approve-collection --serve'},
  prometheus:{title:'Bring the monitoring you already have.',intro:'Use an explicit expected-node profile and final trusted Prometheus/Loki endpoints. The profile is an inventory declaration, not cloud-account discovery.',steps:[['Bind the subjects','Use assets/profile.example.json as a starting point. Match each exporter label and preserve missing expected nodes.'],['Keep credentials private','Use named environment variables. Separate Prometheus and Loki tokens; never place values in a command.'],['Check before scheduling','Doctor diagnoses local setup. The first approved collect tests the actual endpoint. Start one schedule only after inspecting its results.']],command:'python3 scripts/vps_health.py bootstrap --mode prometheus --profile /private/profile.json --url https://metrics.example.invalid --token-env VPS_METRICS_TOKEN --workspace /private/vps-health\npython3 scripts/vps_health.py doctor --workspace /private/vps-health\n# Replace the example endpoint/profile and approve collection first.\npython3 scripts/vps_health.py collect --workspace /private/vps-health'},
  demo:{title:'Understand the workflow before connecting anything.',intro:'The example includes stable accounting, concurrent pressure and missing observations. It uses no credentials and never reads your CPU counters.',steps:[['Create the example','Bootstrap a new demo directory. Synthetic and real observations cannot share a workspace.'],['Use the controls','Inspect the timeline, linked charts and attention inbox. Acknowledge an item and see that the HOLD remains.'],['Choose a real route','Use a different workspace for local or existing-monitoring collection. Archive evidence instead of overwriting it.']],command:'python3 scripts/vps_health.py bootstrap --mode demo --workspace /tmp/vps-demo\npython3 scripts/vps_health.py serve --workspace /tmp/vps-demo\n# Ctrl-C closes the viewer. No collector is running.'}
 };
 function renderSetup(value){
  const route=routes[setupMode];byId('setup-title').textContent=route.title;byId('setup-intro').textContent=route.intro;byId('setup-command').textContent=route.command;
  document.querySelectorAll('[data-setup]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.setup===setupMode)));
  const list=byId('setup-steps');list.replaceChildren();for(const [title,copy]of route.steps){const li=make('li');li.append(make('strong',title),make('span',copy));list.append(li)}
  const checks=[['Workspace mode',value.synthetic?'Synthetic example — not a real host':value.mode],['Expected subjects',String(value.expected_assets)+' configured; not an independent account census'],['Retained observations',String(value.stored_captures)+' captures; '+fixed(value.stored_bytes/1048576)+' MiB compressed raw'],['Configured cadence',String(value.cadence_seconds||300)+' seconds. A refreshing viewer is not a running collector.'],['Remaining evidence gaps',value.assets.filter(n=>n.decision==='HOLD').length+' subjects on HOLD. Run doctor for configuration and database checks.']];
  const box=byId('setup-checks');box.replaceChildren();for(const [label,text]of checks){const div=make('div',label,'check-item');div.append(make('span',text));box.append(div)}
 }
 function renderRibbon(value){
  const node=selected();const ribbon=byId('evidence-ribbon');ribbon.replaceChildren();
  byId('ribbon-caption').textContent='48 evidence intervals · minimum + coverage';
  if(!node||!node.timeline?.length){byId('ribbon-detail').textContent='No interval evidence yet.';return}
  byId('ribbon-detail').textContent='Select an interval to inspect it. Stripes mean incomplete coverage; grey means unmeasured.';
  for(const [index,cell]of node.timeline.entries()){
   const button=make('button');button.type='button';button.dataset.state=cell.state;button.id='interval-'+index;button.tabIndex=index===0?0:-1;
   button.onkeydown=event=>{const offset={ArrowRight:1,ArrowLeft:-1,Home:-index,End:node.timeline.length-1-index}[event.key];if(offset===undefined)return;event.preventDefault();const next=Math.max(0,Math.min(node.timeline.length-1,index+offset));for(const b of ribbon.children)b.tabIndex=-1;const target=ribbon.children[next];target.tabIndex=0;target.focus()};
   const detail=`${utc(cell.start)} to ${utc(cell.end)} · minimum ${pct(cell.minimum)} · ${pct(cell.coverage,0)} covered`;
   button.setAttribute('aria-label',detail);button.title=detail;
   button.onfocus=button.onmouseenter=()=>byId('ribbon-detail').textContent=detail;
   button.onclick=()=>{ui.range='custom';ui.rangeBounds=[cell.start,cell.end];chartEngine?.setWindow(cell.start,cell.end);showWindow(node);byId('ribbon-detail').textContent=detail};
   ribbon.append(button);
  }
 }
 function notifyNew(value){
  const ids=new Set(value.operator.items.map(i=>i.id));
  const newItems=value.operator.items.filter(i=>!seen.has(i.id)&&!acknowledged.has(i.id)&&i.priority!=='info');
  if(desktopEnabled&&Notification.permission==='granted'&&newItems.length){
   try{
    const n=new Notification('VPS Health — new attention item',{body:'Open the local viewer to inspect the evidence. No provider action was taken.',tag:'gskills-attention'});
    n.onclick=()=>{window.focus();setView('attention');location.hash='attention';n.close()};
   }catch{desktopEnabled=false;byId('notification-status').textContent='Desktop notifications are unavailable in this browser. Findings remain in the local inbox.'}
  }
  seen=ids;
 }
 async function enableNotifications(){
  if(!live||!('Notification'in window)||!window.isSecureContext){byId('notification-status').textContent='Desktop notifications are unavailable here. The local attention inbox still works.';return}
  try{
   const permission=Notification.permission==='default'?await Notification.requestPermission():Notification.permission;
   desktopEnabled=permission==='granted';seen=new Set(lastState.operator.items.map(i=>i.id));
   byId('notification-status').textContent=desktopEnabled?'Enabled for new findings while this viewer is open. Closing it stops notifications.':'Permission not granted. Use the inbox; this skill does not install a background notifier.';
  }catch{byId('notification-status').textContent='This browser cannot display desktop notifications. Use the local inbox.'}
 }
 function renderAgent(value){
  const r=value.agent_runtime;
  byId('agent-state').textContent=r.state.replaceAll('_',' ');
  byId('agent-title').textContent=r.process_verified?'The owned worker is present.':r.state==='NOT_MANAGED'?'Ready for your coding agent.':'Read the recorded state before resuming.';
  byId('agent-summary').textContent=r.process_verified?'The process identity matches its recorded boot and start time. This is not proof of service health, complete history or an active chat session.':'No live owned worker is verified. Do not infer continued monitoring from a dashboard file or an old timestamp. Your agent should read agent-status and doctor, then resume only the approved plan.';
  const box=byId('agent-facts');box.replaceChildren();
  const facts=[['Run identity',r.run_id||'Not started'],['Configured deadline',r.deadline_utc||'No active budget'],['Completed collection cycles',String(r.cycles||0)],['Failed or partial cycles',String(r.failed_cycles||0)],['Next agent operation',(r.agent_next_action||'plan_workspace').replaceAll('_',' ')]];
  for(const [title,text]of facts){const node=make('div',title,'check-item');node.append(make('span',text));box.append(node)}
  byId('agent-stop-note').textContent='The agent stops only the current run identity through agent-stop. It does not kill arbitrary processes. The managed Linux worker can outlive the launching terminal session, but not a reboot or an execution platform terminating it. Private HANDOFF.md preserves the next steps.';
  const requests=byId('agent-requests');requests.replaceChildren();
  if(!r.requests.length)requests.append(make('p','No capability requests. Do not connect email or cloud services just because they exist.'));
  for(const request of r.requests){const item=make('div',request.required_capability+' · '+request.state.replaceAll('_',' '),'check-item');item.append(make('span',request.purpose));item.append(make('span',request.state==='NEEDS_CONNECTION'?'Your agent should discover a suitable current tool, then request native OAuth only if needed.':request.state==='DECLINED'?'Connection declined; do not repeatedly prompt or treat it as permission.':'Availability was reported by the host agent. Recheck it in the current session before use. Read/draft access never authorizes sending.'));requests.append(item)}
  const events=byId('agent-events');events.replaceChildren();
  if(!r.events?.length)events.append(make('p','No managed runtime events recorded.'));
  for(const event of [...(r.events||[])].reverse()){const row=make('div',event.code.replaceAll('_',' '),'check-item');row.append(make('span',event.at));events.append(row)}
 }

 function render(value){
  if(!valid(value))return;
  const active=document.activeElement?.id;syncStorage(value);lastState=value;
  const activeIds=new Set(value.operator.items.map(i=>i.id));
  acknowledged=new Set([...acknowledged].filter(id=>activeIds.has(id)));
  try{sessionStorage.setItem(storageKey,JSON.stringify([...acknowledged]))}catch{}
  renderInbox(value);renderSetup(value);renderProviders(value);renderRibbon(value);renderAgent(value);notifyNew(value);
  if(active&&byId(active)&&!byId(active).disabled)byId(active).focus({preventScroll:true});
 }
 byId('open-inbox').onclick=()=>{setView('attention');location.hash='attention'};
 byId('enable-notifications').onclick=enableNotifications;
 byId('provider-filter').onchange=()=>renderProviders(lastState);
 byId('copy-setup').onclick=()=>copyText(routes[setupMode].command);
 document.querySelectorAll('[data-setup]').forEach(b=>b.onclick=()=>{setupMode=b.dataset.setup;renderSetup(lastState)});
 byId('copy-draft-instructions').onclick=()=>copyText('Read references/correspondence.md in the installed vps-health skill. First verify the exact provider, plan, service impact and UTC evidence window. Only after my explicit drafting request, run draft-email with --approve-draft and --impact. Use --example for synthetic or incomplete evidence. Ask one concise question, distinguish observations from inference, and never send the message or authorize a reboot/migration.');
 document.addEventListener('vps-status',()=>render(state));
 render(state);
 return {valid,render};
})();
