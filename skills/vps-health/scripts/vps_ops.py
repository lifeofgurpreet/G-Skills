#!/usr/bin/env python3
"""Derived operator guidance. No repair, sender, background service or network.

Measurement and decision authority remain in vps_health/vps_workspace. This
module turns their results into bounded next actions, never new provider blame.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import sqlite3
import sys
import time
import urllib.parse

import vps_health as core

SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PROVIDER_SOURCES={
    'contabo':{'docs.contabo.com','help.contabo.com'},
    'hetzner':{'docs.hetzner.com'},'digitalocean':{'docs.digitalocean.com'},
    'akamai':{'techdocs.akamai.com'},'aws':{'docs.aws.amazon.com'},
    'vultr':{'docs.vultr.com'},'ovhcloud':{'www.ovhcloud.com'},'netcup':{'www.netcup.com'},
    'other':set()
}
PROVIDERS=set(PROVIDER_SOURCES)|{'unknown'}
ALLOWED_SOURCES=set().union(*PROVIDER_SOURCES.values())


def _review_date(value,now,maximum_age):
    # Missing metadata and future dates are not silently promoted by a newer
    # catalog-wide date. Rechecking references is a deliberate research action.
    try:
        if not isinstance(value,str) or len(value)!=10:raise ValueError('date shape')
        day=dt.datetime.strptime(value,'%Y-%m-%d').replace(tzinfo=dt.timezone.utc)
        if day.strftime('%Y-%m-%d')!=value:raise ValueError('date format')
    except (ValueError,TypeError):return None,'RECHECK_REQUIRED'
    age=(now-day.timestamp())/86400
    return value,'DATED_REFERENCE' if 0<=age<=maximum_age else 'RECHECK_REQUIRED'


def providers(name=None,now=None):
    if name is not None and name not in PROVIDERS:
        raise core.InvalidEvidence('unknown provider label; use other')
    data=core.read_json(core.ROOT/'assets/provider-catalog.json')
    if data.get('schema')!='g-skills.provider-reference.v1' or not isinstance(data.get('providers'),list):
        raise core.InvalidEvidence('provider reference is not the supported reviewed format')
    rows=data['providers'];ids=[p.get('id') for p in rows if isinstance(p,dict)]
    if len(ids)!=len(rows) or len(ids)!=len(set(ids)) or set(ids)!=set(PROVIDER_SOURCES):
        raise core.InvalidEvidence('provider reference identities are incomplete or duplicated')
    maximum=data.get('review_after_days')
    if type(maximum) is not int or not 1<=maximum<=365:raise core.InvalidEvidence('invalid reference review period')
    now=time.time() if now is None else core.finite(now,minimum=0)
    prepared=[]
    for provider in rows:
        for key in ('name','summary','not_a_promise','support_question'):
            value=provider.get(key)
            if not isinstance(value,str) or not 1<=len(value)<=2000:raise core.InvalidEvidence('incomplete provider guidance')
        for key in ('classes','check_next'):
            if not isinstance(provider.get(key),list) or not provider[key] or not all(isinstance(x,str) and 0<len(x)<=1000 for x in provider[key]):
                raise core.InvalidEvidence('invalid provider guidance list')
        item=dict(provider);all_sources=[]
        for key in ('facts','diagnostics'):
            facts=provider.get(key,[])
            if not isinstance(facts,list) or len(facts)>32:raise core.InvalidEvidence('invalid bounded provider source list')
            copied=[]
            for fact in facts:
                if not isinstance(fact,dict) or not all(isinstance(fact.get(k),str) and 0<len(fact[k])<=2000 for k in ('scope','kind','text','source')):
                    raise core.InvalidEvidence('incomplete source-backed provider fact')
                try:
                    url=urllib.parse.urlsplit(fact['source'])
                    valid=(url.scheme=='https' and url.hostname in PROVIDER_SOURCES[provider['id']]
                           and not url.username and not url.password and url.port in (None,443))
                except ValueError:valid=False
                if not valid:raise core.InvalidEvidence('unreviewed source for this provider')
                reviewed,state=_review_date(fact.get('reviewed_on'),now,maximum)
                record={**fact,'reviewed_on':reviewed,'review_state':state};copied.append(record);all_sources.append(record)
            item[key]=copied
        dated=[f['reviewed_on'] for f in all_sources if f['reviewed_on'] is not None]
        item['reviewed_on']=min(dated) if dated else None
        item['review_state']=('NO_PROVIDER_REFERENCE' if not all_sources else
            'RECHECK_REQUIRED' if any(f['review_state']=='RECHECK_REQUIRED' for f in all_sources) else 'DATED_REFERENCE')
        prepared.append(item)
    if name is not None:prepared=[p for p in prepared if p['id']==('other' if name=='unknown' else name)]
    sourced=[p for p in prepared if p['facts'] or p['diagnostics']]
    state='DATED_REFERENCE' if sourced and all(p['review_state']=='DATED_REFERENCE' for p in sourced) else 'RECHECK_REQUIRED'
    return {**data,'providers':prepared,'review_state':state,'review_basis':'Each fact or diagnostic source has its own review date; catalog edits do not refresh older sources.',
            'automatically_refreshed':False,'establishes_contract':False,'sources_fetched':False}


def timeline(points,start,end,policy,count=48):
    """A bounded evidence ribbon from full intervals, not downsampled chart dots.

    Each cell retains valid seconds, minimum and weighted mean. Unknown time is
    visible; selecting a cell only changes the chart view, never the decision.
    """
    if type(count) is not int or not 1<=count<=96 or end<=start:
        return []
    width=(end-start)/count
    cells=[{'start':start+i*width,'end':start+(i+1)*width,'valid_seconds':0.,'total':0.,'minimum':None} for i in range(count)]
    cursor=start
    for point in points:
        left=max(start,point['timestamp']-point['duration_seconds'],cursor)
        right=min(end,point['timestamp']);cursor=max(cursor,right)
        value=point.get('cpu_accounted_ratio')
        if right<=left or point.get('quality') or point.get('conflict') or value is None:
            continue
        index=min(count-1,max(0,int((left-start)/width)))
        while left<right and index<count:
            cell=cells[index];stop=min(right,cell['end'])
            if stop<=left:
                index+=1
                continue
            seconds=stop-left;cell['valid_seconds']+=seconds;cell['total']+=value*seconds
            cell['minimum']=value if cell['minimum'] is None else min(cell['minimum'],value)
            left=stop;index+=1
    for cell in cells:
        duration=cell['end']-cell['start'];coverage=min(1.,cell['valid_seconds']/duration)
        cell['coverage']=coverage;cell['mean']=cell.pop('total')/cell['valid_seconds'] if cell['valid_seconds'] else None
        cell['state']=('unknown' if not cell['valid_seconds'] else 'partial' if coverage<.75 else
                       'investigate' if cell['minimum']<policy['investigate_below'] else
                       'watch' if cell['minimum']<policy['acceptable_ratio'] else 'within')
    return cells


def _finding(node,kind,priority,title,reason,action,synthetic):
    identifier=core.digest({'node':node['id'],'epoch':node.get('epoch'), 'kind':kind,
                            'decision':node.get('decision'),'quality':sorted(node.get('holds',[]))})[:24]
    return {'id':identifier,'node':node['id'],'kind':kind,'priority':priority,'title':title,
            'reason':reason,'next_action':action,'last_observed':node.get('last_sample'),
            'evidence':{k:node.get(k) for k in ('mean','coverage','elapsed_hours','observed_hours','pressure','cfs')},
            'draft_eligible':not synthetic and node.get('decision')=='INVESTIGATE' and node.get('elapsed_hours',0)>=48 and node.get('coverage',0)>=.75,
            'provider_cause_proven':False,'contact_authorized':False}


def brief(value):
    """One prioritized item per subject. Quality issues beat performance bands.

    Identical evidence states have stable identities across display refreshes.
    Acknowledgment is deliberately a viewer concern, not an evidence mutation.
    """
    items=[];synthetic=value['synthetic']
    for node in value['assets']:
        decision=node['decision'];holds=set(node.get('holds',[]))
        if decision=='HOLD':
            if holds & {'epoch_changed_collect_new_evidence','conflicting_sample_values'}:
                args=('identity_or_conflict','urgent','Resolve the evidence boundary',
                      'The host binding changed or observations conflict. Earlier history cannot clear this hold.',
                      'Inspect the configured subject, host epoch and retained capture before collecting a new interval.')
            elif node.get('stale') or holds & {'latest_collection_failed','latest_collection_errors','latest_collection_no_samples'}:
                args=('collection_gap','urgent','Restore trustworthy collection',
                      'Recent evidence is missing, stale or failed. Old observations remain visible but are not current.',
                      'Run doctor, then inspect the collector schedule and its last error. Do not start a second collector.')
            elif 'no_samples' in holds:
                args=('start_collection','info','Collect the first measured interval',
                      'Setup creates a workspace; it does not start monitoring. Local collection needs two ticks.',
                      'Choose one explicitly approved collector: foreground watch, generated timer or your existing scheduler.')
            elif ('insufficient_coverage' in holds and node.get('query_timing')
                  and node['query_timing']['configured_evaluation_step_seconds']>node['query_timing']['rate_window_seconds']):
                args=('query_window_gap','info','Review the monitoring interval',
                      'The configured query step is longer than the fixed five-minute rate window. Waiting for more days does not fill those scheduled gaps.',
                      'Your agent should review the existing approved Prometheus plan and propose an interval of at most 300 seconds if suitable. Obtain any required new scope approval; do not modify a running collector or start a second one.')
            else:
                args=('collect_history','info','Let the evidence window develop',
                      'At least a day of sufficiently covered, current observations is required for this accounting screen.',
                      'Keep collecting; inspect gaps rather than extrapolating a short sample into a day.')
        elif decision=='INVESTIGATE':
            contended=node.get('context')=='CONTENTION_PRESENT'
            args=('performance_review','review','Separate demand from supply' if contended else 'Investigate the persistent shortfall',
                  'Low accounting and workload contention coexist; neither establishes who caused the shortage.' if contended else 'The full-window accounting mean is below the chosen investigation level. Service impact and plan terms still need checking.',
                  'Compare matching time windows of application latency/errors, workload concurrency, CPU limits and provider-plan context. Change one variable only in an approved experiment.')
        elif decision=='WATCH':
            args=('watch','info','Watch for meaningful service impact',
                  'The accounting screen is between your watch and investigation levels. A percentage alone is not a support trigger.',
                  'Compare with the normal workload pattern and service objectives; do not request a migration from this band alone.')
        elif node.get('context')=='CONTENTION_PRESENT':
            args=('workload_pressure','info','Good accounting can still hide a busy service',
                  'The accounting mean is within tolerance, but recorded pressure or throttling is elevated.',
                  'Check service latency, errors and affected workload limits. A good accounting percentage does not clear application health.')
        elif 'workload_context_sparse' in holds:
            args=('workload_context_gap','info','Check how much workload context was observed',
                  'CPU accounting and workload channels have different coverage or freshness. A quiet average cannot fill unmeasured time.',
                  'Inspect the pressure and throttling channel coverage and last observations in the same UTC window. Reuse approved monitoring; do not infer absence of guest limits or provider responsibility.')
        else:
            continue
        items.append(_finding(node,*args,synthetic))
    order={'urgent':0,'review':1,'info':2}
    items.sort(key=lambda item:(order[item['priority']],item['node'],item['kind']))
    return {'schema':'g-skills.operator-brief.v1','generated_at':value['generated_at'],'synthetic':synthetic,
            'expected_subjects':value['expected_assets'],'scope':'configured subjects, not a verified account census',
            'items':items,'counts':{level:sum(i['priority']==level for i in items) for level in order},
            'automatic_actions':False,'service_health_verified':False,'notification_scope':'current viewer session only',
            'instruction':'Acknowledging an item changes only its unread state, never a HOLD or measurement.'}


def runbook_steps(root,mode):
    entry=str(Path(__file__).with_name('vps_health.py'))
    def command(name,args,effect,approval=False):
        argv=[sys.executable,entry,name,'--workspace',str(root),*args]
        return {'name':name,'argv':argv,'display':shlex.join(argv),'effect':effect,'approval_required':approval}
    steps=[command('doctor',[],'Read local configuration and evidence; no collection or repairs.'),
           command('serve',[],'Open a read-only loopback viewer. Ctrl-C stops only the viewer.')]
    if mode!='demo':
        steps.insert(1,command('watch',['--approve-collection','--serve'],
            'One foreground collector; about 72 planned hours by default. Ctrl-C stops it. Do not combine with another collector.',True))
    steps.append(command('brief',[],'Print the same prioritized findings as the dashboard; no notification is sent.'))
    return steps


def doctor(path):
    """Read-only offline diagnosis. Unavailable inputs remain explicit findings.

    No cleanup, permission change, credential discovery, API request or service
    inspection is attempted. Collector freshness is not process-liveness proof.
    """
    import vps_workspace as workspace
    root=Path(path).expanduser().absolute()
    result={'schema':'g-skills.doctor.v1','read_only':True,'network_requests':0,'checks':[],
            'next_steps':[],'collector_process_running':None,'can_install_services':False,'verdict':'UNAVAILABLE'}
    checks=result['checks']
    def check(code,state,message):checks.append({'code':code,'state':state,'message':message})
    if not root.exists():
        check('workspace_missing','blocked','No workspace here. Bootstrap a new private demo or authorized host configuration first.')
        return result
    try:
        root,cfg=workspace.config_load(root)
        check('workspace_config','pass','Configuration is readable; the provider-contact mode remains manual.')
        workspace.chart_assets()
        check('chart_integrity','pass','Bundled chart files match their reviewed hashes.')
        with workspace.database(root,True) as db:
            deadline=time.monotonic()+1
            db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
            integrity=db.execute('PRAGMA quick_check(1)').fetchone()[0]
            if integrity!='ok':raise sqlite3.DatabaseError('integrity check failed')
        check('database_integrity','pass','The bounded read-only SQLite quick check passed.')
        value=workspace.status(root)
    except (core.InvalidEvidence,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
        check('workspace_unavailable','blocked','Cannot safely read configuration, chart assets or history. Preserve this directory; inspect permissions, files and the installed release. No repair was attempted.')
        return result
    result['next_steps']=runbook_steps(root,cfg['mode'])
    result['mode']=cfg['mode'];result['expected_subjects']=len(cfg['assets'])
    if cfg['mode']=='demo':
        check('synthetic_demo','info','This is a synthetic example, not a monitored server.')
    elif cfg['mode']=='local' and sys.platform!='linux':
        check('local_platform','blocked','Passive local collection requires Linux. Use a demo here or an explicitly configured existing Prometheus endpoint.')
    else:check('collection_route','pass','The selected collection mode is supported; no collection was started.')
    for key in ('token_env','loki_token_env'):
        if cfg.get(key):
            check(key,'pass' if os.environ.get(cfg[key]) else 'blocked',
                  'The named credential variable is present; its value is not inspected or printed.' if os.environ.get(cfg[key]) else 'The configured credential variable is absent in this process. Set it privately for the collector, not in a command or profile.')
    if cfg['mode']!='demo':
        if not value['stored_captures']:
            check('collection_not_started','attention','No captures retained yet. Choose and approve one collection route; bootstrap alone is not monitoring.')
        elif any(n['stale'] or n['decision']=='HOLD' for n in value['assets']):
            check('collection_evidence','attention','At least one subject is held or stale. The attention brief gives the specific reason.')
        else:check('collection_evidence','pass','Current recorded evidence passes the accounting-screen gates. Application health is still separate.')
    if any(a.get('provider','unknown') in ('unknown','other') or not a.get('plan') for a in cfg['assets']):
        check('plan_unverified','attention','Provider and exact plan are not recorded for every subject. Do not infer them from names or CPU count.')
    ratio=value['stored_bytes']/workspace.MAX_STORE_BYTES
    check('raw_storage_budget','attention' if ratio>=.8 else 'pass',
          f'{ratio:.0%} of the bounded compressed-capture budget used. Normalized SQLite storage is additional; no evidence is deleted automatically.')
    result['attention']=brief(value)
    result['verdict']='ATTENTION' if any(c['state'] in ('blocked','attention') for c in checks) else 'READY'
    result['source_sha256']=SOURCE_SHA256
    return result


def support_report(path=None):
    """Offline opt-in support projection. Never redact an unrestricted payload.

    Excludes paths, host/subject identifiers, exact observation times, provider
    plans, endpoints, token names/values, errors and raw captures by construction.
    Counts and software/source identifiers remain visible for user review.
    """
    import sqlite3
    import sys
    import time
    import vps_workspace as workspace
    import vps_agent as agent
    result={'schema':'g-skills.support-report.v1','skill':'vps-health',
        'version':workspace.VERSION,'python':f'{sys.version_info.major}.{sys.version_info.minor}',
        'platform':{'linux':'linux','darwin':'macos','win32':'windows'}.get(sys.platform,'other'),
        'source_sha256':{'operations':SOURCE_SHA256,'workspace':workspace.SELF_HASH,'collector':core.SOURCE_SHA256},
        'state':'SUMMARY_AVAILABLE','workspace':{'state':'NOT_REQUESTED'},
        'sent':False,'review_before_sharing':True,'real_host_qualification':False,'provider_fault_established':False,
        'includes':['software versions and source hashes','categorical checks','aggregate counts when readable'],
        'excludes':['paths and host identities','provider/account details','endpoints and credential variables',
                    'raw observations and errors','timestamps and run identifiers']}
    if path is None:return result
    w={'state':'UNAVAILABLE','mode':None,'configuration':'UNAVAILABLE','database':'UNAVAILABLE',
       'chart_assets':'NOT_CHECKED','expected_subjects':None,'capture_batches':None,'retained_points':None,
       'attempt_states':{},'runtime':'NOT_CHECKED','process_verified':False}
    result['workspace']=w
    try:
        root,cfg=workspace.config_load(path)
        w.update(mode=cfg['mode'],configuration='READABLE',expected_subjects=len(cfg['assets']))
    except (OSError,ValueError,KeyError,TypeError):
        result['state']='PARTIAL';return result
    try:
        workspace.chart_assets();w['chart_assets']='VERIFIED'
    except (OSError,ValueError,KeyError,TypeError):w['chart_assets']='UNAVAILABLE'
    try:
        with workspace.database(root,True) as db:
            deadline=time.monotonic()+1
            db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
            if db.execute('PRAGMA quick_check(1)').fetchone()[0]!='ok':raise ValueError('integrity')
            batches=db.execute('SELECT COUNT(*) FROM captures').fetchone()[0]
            points=db.execute('SELECT COUNT(*) FROM points').fetchone()[0]
            outcomes=db.execute("SELECT CASE WHEN outcome IN ('RECORDED','PARTIAL','ERROR') THEN outcome ELSE 'OTHER' END AS category,COUNT(*) FROM attempts GROUP BY category").fetchall()
        w.update(database='READABLE',capture_batches=batches,retained_points=points,
                 attempt_states={r[0]:r[1] for r in outcomes})
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):pass
    try:
        runtime=agent.runtime_status(root)
        allowed={'NOT_MANAGED','STARTING','RUNNING','STOP_REQUESTED','STOPPED','COMPLETED','FAILED','NEEDS_REVIEW','ORPHANED'}
        w['runtime']=runtime['state'] if runtime.get('state') in allowed else 'UNAVAILABLE'
        w['process_verified']=runtime.get('process_verified') is True
    except (OSError,ValueError,KeyError,TypeError):w['runtime']='UNAVAILABLE'
    ready=w['database']=='READABLE' and w['chart_assets']=='VERIFIED' and w['runtime']!='UNAVAILABLE'
    w['state']='READABLE' if ready else 'PARTIAL';result['state']='SUMMARY_AVAILABLE' if ready else 'PARTIAL'
    return result
