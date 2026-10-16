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

  const duration=n=>!finite(n)?'Not measured':n<60?n.toFixed(1)+' s':n<3600?(n/60).toFixed(1)+' min':(n/3600).toFixed(1)+' h';
  const coverage=n=>!finite(n)?'Not recorded':n>0&&n<.0001?'<0.01%':percent(n,n>0&&n<.01?2:1);
  function validTime(p){
    if(p==null)return true; // A legacy snapshot is incomplete, not silently healthy.
    const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x),positive=x=>finite(x)&&x>=0;
    const ratio=x=>x===null||positive(x)&&x<=1.02;
    if(!object(p)||p.schema!=='g-skills.time-evidence.v1'||p.provider_cause_proven!==false||p.contact_authorized!==false||p.new_measurements!==false)return false;
    if(!['window_start','window_end','window_seconds','observed_seconds','invalid_seconds','unobserved_seconds','missing_seconds'].every(k=>positive(p[k]))||p.window_end<p.window_start)return false;
    const close=(a,b)=>Math.abs(a-b)<Math.max(.01,p.window_seconds*1e-9);
    if(!close(p.window_end-p.window_start,p.window_seconds)||!close(p.observed_seconds+p.invalid_seconds+p.unobserved_seconds,p.window_seconds)||!close(p.missing_seconds,p.invalid_seconds+p.unobserved_seconds))return false;
    if(!object(p.qualification)||!positive(p.qualification.minimum_coverage)||p.qualification.minimum_coverage>1||!positive(p.qualification.fresh_for_seconds)||!object(p.channels))return false;
    const channel=c=>{
      if(!object(c)||!ratio(c.mean)||!positive(c.observed_seconds)||!positive(c.coverage)||c.coverage>1||typeof c.qualified!=='boolean'||typeof c.stale!=='boolean')return false;
      if(c.observed_seconds>p.window_seconds+.01||!close(c.coverage*p.window_seconds,c.observed_seconds))return false;
      if(!(c.last_sample===null||positive(c.last_sample))||!(c.age_seconds===null||positive(c.age_seconds)))return false;
      if(c.mean===null&&(c.observed_seconds!==0||c.qualified))return false;
      if(c.mean!==null&&(c.last_sample===null||c.age_seconds===null))return false;
      if(c.qualified&&c.age_seconds>p.qualification.fresh_for_seconds)return false;
      return !c.qualified||(c.mean!==null&&c.observed_seconds>0&&!c.stale&&c.coverage>=p.qualification.minimum_coverage);
    };
    if(!['accounted','execution','pressure','cfs'].every(k=>channel(p.channels[k])))return false;
    if(!close(p.channels.accounted.observed_seconds,p.observed_seconds))return false;
    if(!object(p.bands)||!['within_seconds','watch_seconds','investigate_seconds'].every(k=>positive(p.bands[k]))||!close(p.bands.within_seconds+p.bands.watch_seconds+p.bands.investigate_seconds,p.observed_seconds))return false;
    const e=p.episodes;
    if(!object(e)||!ratio(e.threshold)||!Number.isInteger(e.count)||e.count<0||!positive(e.longest_seconds)||!Array.isArray(e.longest)||e.longest.length>5||e.longest.length>e.count)return false;
    if(!e.longest.every(r=>object(r)&&positive(r.start)&&positive(r.end)&&r.start>=p.window_start&&r.end<=p.window_end&&r.end>r.start&&positive(r.seconds)&&close(r.end-r.start,r.seconds)&&ratio(r.minimum)&&ratio(r.mean)))return false;
    if(!Array.isArray(p.execution_bands)||p.execution_bands.length!==4||new Set(p.execution_bands.map(r=>r?.id)).size!==4)return false;
    if(!p.execution_bands.every(r=>object(r)&&['low','moderate','high','unknown'].includes(r.id)&&positive(r.seconds)&&ratio(r.accounted_mean)&&ratio(r.pressure_mean)&&ratio(r.cfs_mean)&&positive(r.pressure_seconds)&&positive(r.cfs_seconds)&&r.pressure_seconds<=r.seconds+.01&&r.cfs_seconds<=r.seconds+.01))return false;
    if(!close(p.execution_bands.reduce((n,r)=>n+r.seconds,0),p.observed_seconds))return false;
    const r=p.recent_change;
    if(!object(r)||!['INSUFFICIENT_EVIDENCE','OBSERVED_WINDOWS'].includes(r.state))return false;
    if(r.state==='INSUFFICIENT_EVIDENCE')return r.mean_delta===null;
    return finite(r.mean_delta)&&[r.previous,r.current].every(w=>object(w)&&finite(w.start)&&finite(w.end)&&w.end-w.start===3600&&w.qualified===true&&finite(w.mean))&&r.previous.end===r.current.start&&Math.abs(r.mean_delta-(r.current.mean-r.previous.mean))<1e-9;
  }
  function contextLines(profile){
    if(!profile)return ['Workload channel coverage is absent from this legacy snapshot. Read a current retained-evidence report before interpreting the compact means.'];
    return [['execution','Recorded execution'],['pressure','CPU pressure'],['cfs','Throttled periods']].map(([key,label])=>{
      const c=profile.channels[key];
      return label+': '+percent(c.mean)+' mean; '+duration(c.observed_seconds)+' measured ('+coverage(c.coverage)+' of the full window); '+
        (c.mean===null?'unmeasured':c.stale?'stale':c.qualified?'qualified time coverage':'sparse coverage')+'.';
    });
  }

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
      context:node.context,contextLines:contextLines(node.evidence_profile),provider:node.provider||'unknown',plan:node.plan||null,
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
      'Accounting mean: '+percent(r.mean)+'. Recorded coverage: '+percent(r.coverage,1)+'.',
      'Measured time: '+hours(r.observedHours)+' / '+hours(r.elapsedHours)+' elapsed.',
      ...r.contextLines,
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
      {id:'action:export',kind:'action',target:'export',title:'Export private snapshot',detail:'Save this retained snapshot locally; contains node details'}];
    if(options.live)items.push({id:'action:pause',kind:'action',target:'pause',title:options.paused?'Resume view updates':'Pause view updates',detail:'Only the viewer changes; the collector continues'});
    if(options.live)items.push({id:'action:support',kind:'action',target:'support',title:'Save minimal support report',detail:'Versions, categories and counts; no raw investigation'});
    const score=x=>x.title.toLocaleLowerCase()===q?0:x.title.toLocaleLowerCase().startsWith(q)?1:2;
    return items.filter(x=>!q||(x.title+' '+x.detail).toLocaleLowerCase().includes(q))
      .sort((a,b)=>q?score(a)-score(b)||a.title.localeCompare(b.title):0).slice(0,12);
  }
  return {review,task,commands,percent,hours,duration,coverage,validTime,contextLines,routes,labels};
});
