#!/usr/bin/env python3
"""Time-qualified descriptions of retained observations; no collector or verdict.

All summaries consume the same ordered, clipped, non-overlapping intervals used
by the workspace mean. Missing channel time is never borrowed from another
channel. Low recorded execution is not low demand or proof of provider fault.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import vps_health as core

SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
SCHEMA='g-skills.time-evidence.v1'
FIELDS={'accounted':'cpu_accounted_ratio','execution':'executing_ratio',
        'pressure':'cpu_pressure_ratio','cfs':'cfs_throttled_periods_ratio'}
MIN_COVERAGE=.75  # Reuse the existing evidence-coverage preference, not a CPU floor.


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=1.02


def valid(point):
    return not(point.get('quality') or point.get('conflict')) and number(point.get('cpu_accounted_ratio'))


def intervals(points,start,end):
    """First retained interval owns overlapping time, including invalid time.

    Identical timestamps contribute no extra duration; conflict marking remains
    the ingestion owner's responsibility. No interpolation across a gap occurs.
    """
    core.finite(start,minimum=0);core.finite(end,minimum=start,maximum=start+14*86400+5)
    if not isinstance(points,list) or len(points)>100000:
        raise core.InvalidEvidence('time evidence needs at most 100000 ordered points')
    cursor=start;previous=None
    for point in points:
        if not isinstance(point,dict):raise core.InvalidEvidence('observation must be an object')
        stamp=core.finite(point.get('timestamp'),minimum=0)
        duration=core.finite(point.get('duration_seconds'),minimum=0,maximum=3600)
        if previous is not None and stamp<previous:raise core.InvalidEvidence('observation times must not decrease')
        previous=stamp
        left=max(start,stamp-duration,cursor);right=min(stamp,end);cursor=max(cursor,right)
        if right>left:yield left,right,point


def channel_stats(segments,start,end,cadence):
    totals={key:0. for key in FIELDS};seconds={key:0. for key in FIELDS};last={key:None for key in FIELDS}
    for left,right,point in segments:
        if not valid(point):continue
        for key,field in FIELDS.items():
            value=point.get(field)
            if number(value):
                weight=right-left;totals[key]+=value*weight;seconds[key]+=weight;last[key]=right
    span=end-start;fresh_for=max(120.,cadence*2.5);result={}
    for key in FIELDS:
        coverage=min(1.,seconds[key]/span) if span else 0.
        stale=last[key] is not None and end-last[key]>fresh_for
        result[key]={'mean':totals[key]/seconds[key] if seconds[key] else None,
                     'observed_seconds':seconds[key],'coverage':coverage,'last_sample':last[key],
                     'age_seconds':end-last[key] if last[key] is not None else None,'stale':stale,
                     'qualified':bool(seconds[key] and coverage>=MIN_COVERAGE and not stale)}
    return result


def weighted(points,start,end):
    """Compatibility projection for the original workspace aggregation owner."""
    totals={};weights={};represented=0.
    for left,right,point in intervals(points,start,end):
        if not valid(point):continue
        weight=right-left;represented+=weight
        for field in FIELDS.values():
            value=point.get(field)
            if number(value):
                totals[field]=totals.get(field,0.)+value*weight
                weights[field]=weights.get(field,0.)+weight
    return {'represented':represented,'below_acceptable':0.,'below_attention':0.,'totals':totals,
            'weights':weights,'means':{key:total/weights[key] for key,total in totals.items() if weights[key]}}


def summarize(points,start,end,policy,cadence):
    core.finite(cadence,minimum=.2,maximum=3600)
    acceptable=core.finite(policy['acceptable_ratio'],minimum=0,maximum=1)
    investigate=core.finite(policy['investigate_below'],minimum=0,maximum=acceptable)
    if investigate>=acceptable:raise core.InvalidEvidence('investigation threshold must be below tolerance')
    segments=list(intervals(points,start,end));channels=channel_stats(segments,start,end,cadence)
    bands={'within_seconds':0.,'watch_seconds':0.,'investigate_seconds':0.}
    bins={key:{'id':key,'seconds':0.,'_total':0.,'_pressure':0.,'pressure_seconds':0.,'_cfs':0.,'cfs_seconds':0.}
          for key in ('low','moderate','high','unknown')}
    invalid=0.;covered=0.;run=None;top=[];count=0;longest=0.
    def finish():
        nonlocal run,count,longest,top
        if run is None:return
        count+=1;longest=max(longest,run['seconds']);run['mean']=run.pop('_total')/run['seconds']
        top=sorted([*top,run],key=lambda row:(-row['seconds'],row['start']))[:5];run=None
    for left,right,point in segments:
        seconds=right-left;covered+=seconds
        if not valid(point):invalid+=seconds;finish();continue
        value=point['cpu_accounted_ratio']
        band='within_seconds' if value>=acceptable else 'watch_seconds' if value>=investigate else 'investigate_seconds'
        bands[band]+=seconds
        if value<investigate:
            if run is not None and left!=run['end']:finish()
            if run is None:run={'start':left,'end':right,'seconds':0.,'minimum':value,'_total':0.}
            run['end']=right;run['seconds']+=seconds;run['_total']+=value*seconds;run['minimum']=min(run['minimum'],value)
        else:finish()
        execution=point.get('executing_ratio')
        key='unknown' if not number(execution) else 'low' if execution<.25 else 'moderate' if execution<.75 else 'high'
        bucket=bins[key];bucket['seconds']+=seconds;bucket['_total']+=value*seconds
        for channel,field in (('pressure','cpu_pressure_ratio'),('cfs','cfs_throttled_periods_ratio')):
            metric=point.get(field)
            if number(metric):bucket['_'+channel]+=metric*seconds;bucket[channel+'_seconds']+=seconds
    finish()
    for bucket in bins.values():
        bucket['accounted_mean']=bucket.pop('_total')/bucket['seconds'] if bucket['seconds'] else None
        for channel in ('pressure','cfs'):
            total=bucket.pop('_'+channel);weight=bucket[channel+'_seconds']
            bucket[channel+'_mean']=total/weight if weight else None
    recent={'state':'INSUFFICIENT_EVIDENCE','window_seconds':3600,'mean_delta':None,'previous':None,'current':None}
    if start<=end-7200:
        windows=[]
        for a,b in ((end-7200,end-3600),(end-3600,end)):
            stats=channel_stats(intervals(points,a,b),a,b,cadence)['accounted']
            windows.append({'start':a,'end':b,**stats})
        recent['previous'],recent['current']=windows
        if all(window['qualified'] for window in windows):
            recent.update(state='OBSERVED_WINDOWS',mean_delta=windows[1]['mean']-windows[0]['mean'])
    observed=channels['accounted']['observed_seconds'];unobserved=max(0.,end-start-covered)
    return {'schema':SCHEMA,'window_start':start,'window_end':end,'window_seconds':end-start,
            'observed_seconds':observed,'invalid_seconds':invalid,'unobserved_seconds':unobserved,
            'missing_seconds':invalid+unobserved,'channels':channels,'bands':bands,
            'episodes':{'threshold':investigate,'count':count,'longest_seconds':longest,'longest':top},
            'execution_bands':list(bins.values()),'execution_boundaries':[.25,.75],
            'recent_change':recent,'qualification':{'minimum_coverage':MIN_COVERAGE,'fresh_for_seconds':max(120.,cadence*2.5)},
            'method':'Retained non-overlapping observation intervals, not sample counts or chart pixels. Recorded execution is not demand; CFS period fractions are not CPU time lost.',
            'provider_cause_proven':False,'contact_authorized':False,'new_measurements':False}


def report(workspace,subject,start,end):
    """Read-only bounded report of the active retained epoch, not past live state."""
    import vps_workspace as ws
    root,cfg=ws.config_load(workspace);core.alias(subject)
    if subject not in {item['id'] for item in cfg['assets']}:
        raise core.InvalidEvidence('subject is not in the declared workspace')
    core.finite(start,minimum=0);core.finite(end,minimum=start,maximum=start+14*86400)
    if end<=start:raise core.InvalidEvidence('choose a nonempty report window')
    with ws.database(root,True) as db:
        db.execute('BEGIN')  # Summary and provenance read the same immutable snapshot.
        value=ws.status(root,now=end,window_start=start,_read_db=db)
        if value['configuration_sha256']!=core.digest(cfg):
            raise core.InvalidEvidence('workspace configuration changed during report; retry a fresh read')
        selected=next(item for item in value['assets'] if item['id']==subject)
        rows=db.execute('SELECT DISTINCT hash FROM points WHERE subject=? AND epoch=? AND ts>=? AND ts<=? ORDER BY hash LIMIT 4097',
                        (subject,'' if 'epoch_changed_collect_new_evidence' in selected['holds'] else selected['epoch'] or '',start,end)).fetchall()
    return {'schema':'g-skills.time-report.v1','subject':subject,'synthetic':value['synthetic'],
            'requested_window':{'start':core.iso(start),'end':core.iso(end)},'active_epoch':selected['epoch'],
            'profile':selected['evidence_profile'],'accounting_decision':selected['decision'],
            'workload_context':selected['context'],'limitations':selected['holds'],
            'configuration_sha256':value['configuration_sha256'],'code_hashes':value['code_hashes'],
            'observation_hashes':[row['hash'] for row in rows[:4096]],'observation_hashes_truncated':len(rows)>4096,
            'source_semantics':'Stored sample-payload hashes, not raw capture hashes; effective durations and conflict markers remain in the database. Active retained epoch only. Current source/ingestion holds are not a reconstruction of what the monitor reported in the past. Interval averages are clipped at window edges, not remeasured sub-intervals.',
            'read_only':True,'new_measurements':False,'provider_cause_proven':False,'contact_authorized':False,
            'privacy':'Contains a private node label, UTC window and observation summaries. Not a minimal support report or a raw evidence archive.'}


def register(sub):
    p=sub.add_parser('evidence-report',help='Private time-qualified report from retained intervals; no new collection')
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--node',required=True)
    p.add_argument('--start',required=True,help='Timezone-aware ISO date/time')
    p.add_argument('--end',required=True,help='Timezone-aware ISO date/time, at most 14 days after start')
    p.add_argument('--out',type=Path,help='New private JSON outside the installed skill and observation workspace')


def dispatch(args):
    import vps_workspace as ws
    start=core.stamp(args.start);end=core.stamp(args.end)
    output=ws.public_path(args.out) if args.out else None
    root=ws.public_path(args.workspace)
    if output is not None:
        if output==root or root in output.parents:
            raise core.InvalidEvidence('report output must be outside the retained workspace')
        if output.exists() or output.is_symlink():raise FileExistsError('report output exists; nothing overwritten')
    value=report(root,args.node,start,end)
    if output is not None:core.save_json(output,value)
    return value
