/* Presentation of existing evidence. No scores, thresholds, writes or network. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();else root.VpsView=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const finite=n=>typeof n==='number'&&Number.isFinite(n);
  const percent=(n,d=1)=>finite(n)?(n*100).toFixed(d)+'%':'Not measured';
  const hours=n=>finite(n)?n.toFixed(1)+' h':'Not measured';
  const routes=[['overview','Overview','Inspect nodes and the next useful check'],['attention','Attention','Prioritized findings and acknowledgments'],['evidence','Evidence','Daily history and observation coverage'],['activity','Collection','Actual collection attempts'],['agent','Agent','Owned runtime and capability needs'],['setup','Setup','Agent-owned setup and recovery'],['providers','Providers','Dated plan documentation']];
  const labels={WITHIN_TOLERANCE:'Within tolerance',WATCH:'Watch',INVESTIGATE:'Investigate',HOLD:'On hold'};

  function review(state,id){
    const node=state.assets.find(n=>n.id===id);
    if(!node)return null;
    const item=state.operator.items.find(i=>i.node===id)||null;
    return {
      id:node.id,decision:node.decision,label:labels[node.decision]||'Unknown',
      title:item?item.title:'Keep an eye on service impact',
      next:item?item.next_action:node.recommendation,
      reason:item?item.reason:'The accounting screen is within the chosen tolerance. Application latency, errors and throughput remain separate evidence.',
      source:item?'operator-brief':'retained-node-recommendation',
      itemId:item?.id||null,priority:item?.priority||'info',
      window:{start:node.window_start,end:node.window_end},
      coverage:node.coverage,observedHours:node.observed_hours,elapsedHours:node.elapsed_hours,
      mean:node.mean,execution:node.execution,pressure:node.pressure,cfs:node.cfs,
      stale:node.stale,lastSample:node.last_sample,holds:[...node.holds],
      context:node.context,provider:node.provider||'unknown',plan:node.plan||null,
      synthetic:state.synthetic,providerCauseProven:false,externalActionAuthorized:false
    };
  }

  function task(state,id){
    const r=review(state,id);if(!r)return null;
    return [
      'Read the installed vps-health/SKILL.md and references/operator-playbook.md.',
      r.synthetic?'SYNTHETIC DEMO: demonstrate the workflow only; this is not a real server.':'Use only this user-authorized private investigation. Keep the evidence private.',
      'Subject: '+r.id,
      'Recorded state: '+r.label+' ('+r.decision+').',
      'Full assessment window: '+r.window.start+' to '+r.window.end+'.',
      'Accounting mean: '+percent(r.mean)+'. Recorded coverage: '+percent(r.coverage,0)+'.',
      'Measured time: '+hours(r.observedHours)+' / '+hours(r.elapsedHours)+' elapsed.',
      'Workload context: execution '+percent(r.execution)+', CPU pressure '+percent(r.pressure)+', throttled periods '+percent(r.cfs)+'.',
      'Finding: '+r.title,
      'Next check: '+r.next,
      'Remaining limitations: '+(r.holds.length?r.holds.join(', '):'Application impact and purchased-plan behavior still need their own evidence.'),
      'The selected chart zoom is a view, not a new assessment window. Start by rechecking actual collection and these observations.',
      'Do routine authorized investigation yourself. Do not infer provider responsibility, change host settings, run active probes, connect an account or send a message from this handoff. Obtain any separately required user permission.',
      'Report verified facts, unresolved causes and the next useful action; do not claim a task was executed merely because it was copied.'
    ].join('\n');
  }

  function commands(state,query='',options={}){
    const q=String(query).trim().toLocaleLowerCase().slice(0,160);
    const items=[...state.assets.map(n=>({id:'node:'+n.id,kind:'node',target:n.id,title:n.id,
      detail:labels[n.decision]+' · '+hours(n.observed_hours)+' measured'})),
      ...routes.map(([id,title,detail])=>({id:'view:'+id,kind:'view',target:id,title:'Open '+title,detail})),
      {id:'action:export',kind:'action',target:'export',title:'Export private evidence',detail:'Save this retained snapshot locally; contains node details'}];
    if(options.live)items.push({id:'action:pause',kind:'action',target:'pause',title:options.paused?'Resume view updates':'Pause view updates',detail:'Only the viewer changes; the collector continues'});
    if(options.live)items.push({id:'action:support',kind:'action',target:'support',title:'Save minimal support report',detail:'Versions, categories and counts; no raw investigation'});
    const score=x=>x.title.toLocaleLowerCase()===q?0:x.title.toLocaleLowerCase().startsWith(q)?1:2;
    return items.filter(x=>!q||(x.title+' '+x.detail).toLocaleLowerCase().includes(q))
      .sort((a,b)=>q?score(a)-score(b)||a.title.localeCompare(b.title):0).slice(0,12);
  }
  return {review,task,commands,percent,hours,routes,labels};
});
