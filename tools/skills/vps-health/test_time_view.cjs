const test=require('node:test');
const assert=require('node:assert/strict');
const view=require('../../../skills/vps-health/assets/view-model.js');
function profile(){
 const full={mean:.96,observed_seconds:259200,coverage:1,last_sample:259200,age_seconds:0,stale:false,qualified:true};
 const sparse={mean:0,observed_seconds:300,coverage:300/259200,last_sample:259200,age_seconds:0,stale:false,qualified:false};
 const empty={mean:null,observed_seconds:0,coverage:0,last_sample:null,age_seconds:null,stale:false,qualified:false};
 return {schema:'g-skills.time-evidence.v1',window_start:0,window_end:259200,window_seconds:259200,observed_seconds:259200,invalid_seconds:0,unobserved_seconds:0,missing_seconds:0,
 channels:{accounted:{...full},execution:{...full,mean:.2},pressure:{...sparse},cfs:{...sparse}},
 bands:{within_seconds:259200,watch_seconds:0,investigate_seconds:0},episodes:{threshold:.8,count:0,longest_seconds:0,longest:[]},
 execution_bands:['low','moderate','high','unknown'].map(id=>({id,seconds:id==='low'?259200:0,accounted_mean:id==='low'?.96:null,pressure_mean:id==='low'?0:null,cfs_mean:id==='low'?0:null,pressure_seconds:id==='low'?300:0,cfs_seconds:id==='low'?300:0})),
 recent_change:{state:'INSUFFICIENT_EVIDENCE',window_seconds:3600,mean_delta:null,previous:null,current:null},
 qualification:{minimum_coverage:.75,fresh_for_seconds:750},provider_cause_proven:false,contact_authorized:false,new_measurements:false};
}
function state(p=profile()){
 return {synthetic:true,operator:{items:[]},assets:[{id:'example-node',decision:'WITHIN_TOLERANCE',window_start:'1970-01-01T00:00:00Z',window_end:'1970-01-04T00:00:00Z',coverage:1,observed_hours:72,elapsed_hours:72,mean:.96,execution:.2,pressure:0,cfs:0,stale:false,last_sample:259200,holds:['workload_context_sparse'],context:'CONTEXT_INCOMPLETE',recommendation:'Check the real channel coverage',evidence_profile:p}]};
}
test('actual sparse channel profile is accepted, not normalized to full coverage',()=>{const p=profile();assert.equal(view.validTime(p),true);assert.match(view.contextLines(p)[1],/5.0 min measured \(0.12%/);assert.match(view.contextLines(p)[1],/sparse coverage/)});
test('zero means and absent means have different captions',()=>{const p=profile();p.channels.pressure={mean:null,observed_seconds:0,coverage:0,last_sample:null,age_seconds:null,stale:false,qualified:false};assert.equal(view.validTime(p),true);assert.match(view.contextLines(p)[1],/Not measured/);assert.match(view.contextLines(p)[2],/0.0% mean/)});
test('tiny positive coverage is not rounded to a healthy zero',()=>{assert.equal(view.coverage(.000001),'<0.01%');assert.equal(view.coverage(0),'0.0%');assert.equal(view.coverage(null),'Not recorded')});
test('legacy absent profile does not fabricate channel qualification',()=>{assert.equal(view.validTime(undefined),true);assert.equal(view.validTime(null),true);assert.match(view.contextLines(null)[0],/absent.*legacy/)});
test('private agent handoff contains per-channel denominators without changing decision',()=>{const s=state();const before=structuredClone(s);const t=view.task(s,'example-node');assert.match(t,/WITHIN_TOLERANCE/);assert.match(t,/Throttled periods: 0.0% mean; 5.0 min measured \(0.12%/);assert.match(t,/Do not infer provider responsibility/);assert.deepEqual(s,before)});
test('a stale contextual mean is labeled stale even when accounting is current',()=>{const p=profile();p.channels.cfs.stale=true;p.channels.cfs.age_seconds=3600;p.channels.cfs.last_sample-=3600;assert.equal(view.validTime(p),true);assert.match(view.contextLines(p)[2],/stale/)});
test('reassuring flags cannot override insufficient channel coverage',()=>{const p=profile();p.channels.cfs.qualified=true;assert.equal(view.validTime(p),false)});
test('extra observed time and missing duration inflation are refused',()=>{const p=profile();p.observed_seconds++;assert.equal(view.validTime(p),false);const q=profile();q.missing_seconds++;assert.equal(view.validTime(q),false)});
test('out-of-bounds or impossible channel coverage is refused',()=>{for(const change of [{coverage:2},{observed_seconds:-1},{observed_seconds:Infinity},{mean:'0'},{coverage:.5}]){const p=profile();Object.assign(p.channels.pressure,change);assert.equal(view.validTime(p),false)}});
test('duration buckets cannot add unobserved time to healthy bands',()=>{const p=profile();p.bands.within_seconds+=100;assert.equal(view.validTime(p),false)});
test('execution grouping remains a disjoint complete partition',()=>{const p=profile();p.execution_bands[1].id='low';assert.equal(view.validTime(p),false);const q=profile();q.execution_bands[0].seconds--;assert.equal(view.validTime(q),false)});
test('pressure-time grouping cannot exceed its execution bucket',()=>{const p=profile();p.execution_bands[1].pressure_seconds=1;assert.equal(view.validTime(p),false)});
test('run endpoints must fit the full assessment and recorded duration',()=>{const p=profile();p.episodes={threshold:.8,count:1,longest_seconds:300,longest:[{start:259000,end:259300,seconds:300,mean:.7,minimum:.6}]};assert.equal(view.validTime(p),false)});
test('insufficient recent history has no invented numeric improvement',()=>{const p=profile();p.recent_change.mean_delta=.2;assert.equal(view.validTime(p),false)});
test('unqualified recent-window metadata cannot be shown as an established change',()=>{const p=profile();p.recent_change={state:'OBSERVED_WINDOWS',mean_delta:.2,previous:{start:0,end:3600,mean:.7,qualified:false},current:{start:3600,end:7200,mean:.9,qualified:true}};assert.equal(view.validTime(p),false)});
test('profiles never extend action or provider-attribution authority',()=>{for(const key of ['provider_cause_proven','contact_authorized','new_measurements']){const p=profile();p[key]=true;assert.equal(view.validTime(p),false)}});

test('qualified channels need actual last-observation age, not a truthy label',()=>{for(const change of [{last_sample:null},{age_seconds:null},{age_seconds:751}]){const p=profile();Object.assign(p.channels.accounted,change);assert.equal(view.validTime(p),false)}});
test('a recent delta must match adjacent one-hour values already supplied',()=>{const p=profile();p.recent_change={state:'OBSERVED_WINDOWS',mean_delta:.2,previous:{start:0,end:3600,mean:.7,qualified:true},current:{start:3600,end:7200,mean:.9,qualified:true}};assert.equal(view.validTime(p),true);p.recent_change.mean_delta=.8;assert.equal(view.validTime(p),false)});
