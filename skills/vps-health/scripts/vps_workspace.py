#!/usr/bin/env python3
"""Private persistent workspaces for VPS health. No sender or host installer.

One-node /proc continuity and existing Prometheus collection share a retained
SQLite history. Dashboard state is derived, never the evidence authority.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import gzip
import hashlib
import html
import http.server
import json
import math
import os
from pathlib import Path
import re
import shlex
import sqlite3
import sys
import threading
import time
import urllib.parse
import uuid

import vps_health as core

VERSION = '0.2.0'
SCHEMA = 'g-skills.workspace.v1'
SELF_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MAX_STORE_BYTES = 256 * 1024 * 1024
COMMANDS = ('bootstrap','collect','watch','dashboard','serve','export','schedule','draft-email','capabilities')
SQL = '''
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS captures (
 hash TEXT PRIMARY KEY, observed REAL NOT NULL, bytes INTEGER NOT NULL, body BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS points (
 subject TEXT NOT NULL, epoch TEXT NOT NULL, ts REAL NOT NULL, duration REAL NOT NULL,
 hash TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(subject,epoch,ts));
CREATE TABLE IF NOT EXISTS conflicts (
 subject TEXT NOT NULL, epoch TEXT NOT NULL, ts REAL NOT NULL, PRIMARY KEY(subject,epoch,ts));
CREATE TABLE IF NOT EXISTS attempts (
 id TEXT PRIMARY KEY, observed REAL NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL);
'''


def fail(message):
    raise core.InvalidEvidence(message)


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        fail(f'{name} must be an integer from {low} to {high}')
    return value


def atomic(path, data):
    """Replace derived state only; captures themselves are content addressed."""
    path = Path(path)
    if path.is_symlink(): fail('refusing symbolic-link output')
    tmp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        fd = os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd,'wb') as handle:
            handle.write(data);handle.flush();os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists(): tmp.unlink()


def public_path(path):
    path = Path(path).expanduser().absolute()
    if path.is_symlink(): fail('workspace must not be a symbolic link')
    for part in (path,*path.parents):
        if part == core.ROOT:
            fail('choose a private workspace outside the installed skill folder')
    return path.resolve()


def config_load(path):
    root=public_path(path)
    if not root.is_dir() or (root/'workspace.json').is_symlink(): fail('workspace not found; run bootstrap first')
    cfg=core.read_json(root/'workspace.json')
    if not isinstance(cfg,dict) or cfg.get('schema')!=SCHEMA: fail('unsupported workspace schema')
    if cfg.get('mode') not in ('local','prometheus','demo'): fail('unknown workspace mode')
    integer(cfg.get('interval_seconds'),60,3600,'interval_seconds')
    integer(cfg.get('history_days'),1,14,'history_days')
    policy=cfg.get('policy',{})
    a=core.finite(policy.get('acceptable_ratio'),minimum=.5,maximum=1)
    b=core.finite(policy.get('investigate_below'),minimum=.1,maximum=1)
    if b>=a: fail('investigate_below must be less than acceptable_ratio')
    assets=cfg.get('assets')
    if not isinstance(assets,list) or not 1<=len(assets)<=100: fail('workspace requires 1-100 expected assets')
    ids=[core.alias(item.get('id')) for item in assets]
    if len(ids)!=len(set(ids)): fail('duplicate expected asset identity')
    for item in assets:
        core.alias(item.get('epoch','initial'))
    if cfg['mode']=='local' and len(assets)!=1: fail('local mode supports one host; use existing Prometheus for a fleet')
    if cfg['mode']=='prometheus':
        core.endpoint(cfg.get('prometheus_url',''),cfg.get('allow_http') is True)
        if cfg.get('loki_url'):core.endpoint(cfg['loki_url'],cfg.get('allow_http') is True)
        for item in assets:
            if not isinstance(item.get('instance'),str):fail('Prometheus assets need an instance label')
        if len({a['instance'] for a in assets})!=len(assets):fail('ambiguous exporter identity')
    for name in ('token_env','loki_token_env'):
        if cfg.get(name) and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,100}',cfg[name]):fail('credentials must be named environment variables, never values')
    if cfg.get('provider_contact')!='manual_only':fail('workspace cannot authorize automatic provider contact')
    return root,cfg


@contextlib.contextmanager
def database(root, readonly=False):
    path=root/'history.sqlite3'
    if path.is_symlink() or not path.is_file():fail('history database missing or symbolic; bootstrap a valid workspace')
    if readonly:
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)
    else:
        db=sqlite3.connect(path,timeout=2)
    try:
        db.row_factory=sqlite3.Row
        yield db
    finally:db.close()


def get_state(db,key,default=None):
    row=db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
    return core.decode(row['value']) if row else default


def set_state(db,key,value):
    db.execute('INSERT OR REPLACE INTO state VALUES (?,?)',(key,core.canonical(value).decode()))


def subject_binding(cfg,node):
    asset=next(a for a in cfg['assets'] if a['id']==node)
    return core.digest({'mode':cfg['mode'],'endpoint':cfg.get('prometheus_url'),
                        'asset':{k:asset.get(k) for k in ('id','instance','epoch','provider','plan')}})


def _epoch(cfg,capture):
    asset=next(a for a in cfg['assets'] if a['id']==capture['subject']['id'])
    # A boot fingerprint is a discontinuity guard, NOT proof no live migration occurred.
    boot=capture.get('source',{}).get('boot_fingerprint')
    return core.digest({'binding':subject_binding(cfg,asset['id']),'owner_epoch':asset.get('epoch','initial'),'kind':capture['source']['kind'],
                        'method':capture['source'].get('tool_sha256','unknown'),'boot':boot})


def ingest(root,cfg,captures,observed=None):
    """Atomic, idempotent capture import; overlapping scrapes do not add hours."""
    now=time.time() if observed is None else core.finite(observed,minimum=0)
    if not isinstance(captures,list) or not 1<=len(captures)<=100:fail('expected 1-100 captures')
    expected={a['id'] for a in cfg['assets']};seen=set()
    for capture in captures:
        start,end=core.validate_capture(capture)
        node=capture['subject']['id']
        if node not in expected or node in seen:fail('unexpected or duplicated capture subject')
        if end>now+5:fail('future observation refused')
        if (capture['source']['kind']=='synthetic') != (cfg['mode']=='demo'):fail('synthetic and real evidence cannot share a workspace')
        seen.add(node)
    raw=core.canonical(captures)
    if len(raw)>core.MAX_BYTES:fail('capture batch exceeds 8 MiB; narrow the collection range or asset set')
    packed=gzip.compress(raw,mtime=0);digest=hashlib.sha256(raw).hexdigest()
    with database(root) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM captures WHERE hash=?',(digest,)).fetchone():return {'imported':False,'hash':digest}
        used=db.execute('SELECT COALESCE(SUM(bytes),0) FROM captures').fetchone()[0]
        if used+len(packed)>MAX_STORE_BYTES:fail('256 MiB raw-capture budget reached; archive this workspace and bootstrap a new one. No data deleted.')
        db.execute('INSERT INTO captures VALUES (?,?,?,?)',(digest,now,len(packed),packed))
        for capture in captures:
            node=capture['subject']['id'];epoch=_epoch(cfg,capture)
            latest=get_state(db,'latest:'+node,{})
            end=core.stamp(capture['end'])
            if end>=latest.get('end',0):
                set_state(db,'latest:'+node,{'epoch':epoch,'end':end,'observed':now,'errors':capture['errors'],
                        'kind':capture['source']['kind'],'samples':len(capture['samples']),'binding':subject_binding(cfg,node), 'owner_epoch':next(a.get('epoch','initial') for a in cfg['assets'] if a['id']==node)})
            for point in capture['samples']:
                ts=point['timestamp'];body=core.canonical(point).decode();h=core.digest(point)
                capture_start=core.stamp(capture['start'])
                observed_duration=min(point['duration_seconds'],max(0,min(ts,end)-capture_start))
                prior=db.execute('SELECT hash FROM points WHERE subject=? AND epoch=? AND ts=?',(node,epoch,ts)).fetchone()
                if prior and prior[0]!=h:
                    db.execute('INSERT OR IGNORE INTO conflicts VALUES (?,?,?)',(node,epoch,ts))
                elif not prior:
                    db.execute('INSERT INTO points VALUES (?,?,?,?,?,?)',(node,epoch,ts,observed_duration,h,body))
                else:
                    db.execute('UPDATE points SET duration=MAX(duration,?) WHERE subject=? AND epoch=? AND ts=?',(observed_duration,node,epoch,ts))
        errors=sum(bool(c['errors']) for c in captures)
        db.execute('INSERT INTO attempts VALUES (?,?,?,?)',(uuid.uuid4().hex,now,'PARTIAL' if errors else 'RECORDED',f'{len(captures)} subjects; {errors} source-error records'))
    return {'imported':True,'hash':digest,'subjects':len(captures)}


def demo_seed(cfg,now):
    end=math.floor(now/300)*300;start=end-3*86400
    result=[]
    for index,asset in enumerate(cfg['assets']):
        c=core.new_capture(asset['id'],'synthetic',start,end,300)
        c['source']['label']='SYNTHETIC DEMO — not a real host'
        for i in range(1,865):
            if index==2 and i>560:continue
            value=(.96 if index==0 else .85 if i<400 else .74)+.015*math.sin(i/17)
            c['samples'].append({'timestamp':start+i*300,'duration_seconds':300,'quality':[],
                'cpu_accounted_ratio':value,'executing_ratio':.45 if index==0 else .72,
                'steal_ratio':0.,'cpu_pressure_ratio':.01 if index==0 else .18,'cfs_throttled_periods_ratio':0. if index==0 else .12})
        result.append(c)
    return result


def bootstrap(args):
    root=public_path(args.workspace)
    if root.exists():fail('workspace exists; use dashboard or collect, or choose a new private path')
    interval=integer(args.interval,60,3600,'--interval')
    assets=[{'id':core.alias(args.node),'epoch':'initial'}]
    if args.mode=='demo':assets=[{'id':n,'epoch':'demo'} for n in ('example-stable','example-contended','example-offline')]
    if args.mode=='prometheus':
        if not args.profile or not args.url:fail('Prometheus bootstrap requires --profile and --url')
        assets=core.profile_load(args.profile)['assets']
    elif args.profile or args.url or args.loki_url:fail('--profile/--url/--loki-url apply only to --mode prometheus')
    cfg={'schema':SCHEMA,'version':VERSION,'mode':args.mode,'created_at':core.iso(time.time()),'assets':assets,
         'interval_seconds':interval,'history_days':3,'policy':{'acceptable_ratio':args.acceptable,'investigate_below':args.investigate_below},
         'provider_contact':'manual_only','prometheus_url':core.endpoint(args.url,args.allow_http) if args.url else None,
         'loki_url':core.endpoint(args.loki_url,args.allow_http) if args.loki_url else None,
         'allow_http':args.allow_http,'token_env':args.token_env,'loki_token_env':args.loki_token_env}
    # Validate a prospective configuration before creating persistent state.
    core.finite(args.acceptable,minimum=.5,maximum=1);core.finite(args.investigate_below,minimum=.1,maximum=1)
    if args.investigate_below>=args.acceptable:fail('--investigate-below must be lower than --acceptable')
    root.mkdir(parents=True,mode=0o700)
    try:
        atomic(root/'workspace.json',core.canonical(cfg));config_load(root)
        path=root/'history.sqlite3';fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        db=sqlite3.connect(path)
        try:db.executescript(SQL);db.commit()
        finally:db.close()
        if args.mode=='demo':ingest(root,cfg,demo_seed(cfg,time.time()))
        render(root)
    except Exception:
        # Preserve a failed bootstrap for inspection instead of deleting a path.
        raise
    return {'workspace':str(root),'mode':args.mode,'configuration_only':args.mode!='demo',
            'dashboard':str(root/'dashboard.html'),
            'next_command':f'python3 {shlex.quote(str(Path(__file__).with_name("vps_health.py")))} '+
                           (f'serve --workspace {shlex.quote(str(root))}' if args.mode=='demo' else f'watch --workspace {shlex.quote(str(root))} --approve-collection --serve'),
            'notes':'No service installed. Demo data is synthetic. Real collection requires the explicit next command.'}


def collect(root, lookback_hours=1):
    root,cfg=config_load(root);now=time.time()
    integer(lookback_hours,1,168,'lookback_hours')
    # A database write lock serializes snapshots and prevents overlapping collectors.
    with database(root) as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            lease=get_state(db,'collector_lease',{})
            if lease.get('until',0)>now:fail('another collection holds the workspace lease; retry after it completes')
            lease_id=uuid.uuid4().hex;set_state(db,'collector_lease',{'id':lease_id,'until':now+300});db.commit()
        except Exception:db.rollback();raise
    current_snapshot=None
    try:
        if cfg['mode']=='demo':fail('demo is offline; start a real workspace for live collection')
        if cfg['mode']=='local':
            if sys.platform!='linux':fail('local collection requires Linux; use demo or Prometheus here')
            with database(root,True) as db:previous=get_state(db,'previous_snapshot')
            current=core.cpu_snapshot();hz=os.sysconf('SC_CLK_TCK')
            end=current['wall_end_ns']/1e9
            start=previous['wall_end_ns']/1e9 if previous else end
            c=core.new_capture(cfg['assets'][0]['id'],'passive-linux',start,end,cfg['interval_seconds'])
            c['source'].update(boot_fingerprint=current['boot_fingerprint'],kernel=os.uname().release,user_hz=hz)
            if previous:
                try:
                    # A gap >1h starts a new unqualified interval, never a fake day's sample.
                    duration=(current['end_ns']-previous['start_ns'])/1e9
                    if duration>3600 or end<start:
                        c['start']=c['end'];c['errors'].append('clock_or_long_sampling_gap; baseline reset')
                    else:
                        c['samples']=[core.local_interval(previous,current,hz,cfg['interval_seconds'])]
                except core.InvalidEvidence:c['start']=c['end'];c['errors'].append('counter_interval_invalid; baseline reset')
            else:c['notes'].append('first baseline only; next collection measures the intervening interval')
            c['raw']['snapshots']=[p for p in (previous,current) if p]
            captures=[c]
            current_snapshot=current
        else:
            token=os.environ.get(cfg['token_env']) if cfg.get('token_env') else None
            loki_token=os.environ.get(cfg['loki_token_env']) if cfg.get('loki_token_env') else None
            if cfg.get('token_env') and not token or cfg.get('loki_token_env') and not loki_token:fail('named token environment variable missing; nothing sent')
            step=cfg['interval_seconds'];end=math.floor(now/step)*step
            captures=core.collect_prometheus({'assets':cfg['assets']},cfg['prometheus_url'],end-lookback_hours*3600,end,step,token,cfg.get('loki_url'),loki_token)
        result=ingest(root,cfg,captures,now)
        if current_snapshot is not None:
            with database(root) as db,db:set_state(db,'previous_snapshot',current_snapshot)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        with database(root) as db,db:
            # Do not persist endpoint/credential-bearing exception text.
            db.execute('INSERT INTO attempts VALUES (?,?,?,?)',(uuid.uuid4().hex,now,'ERROR',type(exc).__name__))
        raise
    finally:
        with database(root) as db,db:
            current=get_state(db,'collector_lease',{})
            if current.get('id')==lease_id:db.execute('DELETE FROM state WHERE key=?',('collector_lease',))
        render(root)
    return {**result,'dashboard':str(root/'dashboard.html'),'source_errors':sum(len(c['errors']) for c in captures)}


def weighted(points,start,end):
    """Union-weight bounded sample intervals: duplicate windows add no time."""
    result={'represented':0.,'below_acceptable':0.,'below_attention':0.,'totals':{},'weights':{}}
    cursor=start
    for p in points:
        right=min(p['timestamp'],end);left=max(start,p['timestamp']-p['duration_seconds'],cursor)
        weight=max(0,right-left);cursor=max(cursor,right)
        if p.get('quality') or p.get('conflict') or p.get('cpu_accounted_ratio') is None or not 0<=p['cpu_accounted_ratio']<=1.02:continue
        result['represented']+=weight
        for key in ('cpu_accounted_ratio','executing_ratio','cpu_pressure_ratio','cfs_throttled_periods_ratio'):
            value=p.get(key)
            if value is not None:
                result['totals'][key]=result['totals'].get(key,0)+value*weight
                result['weights'][key]=result['weights'].get(key,0)+weight
    result['means']={k:v/result['weights'][k] for k,v in result['totals'].items() if result['weights'][k]}
    return result


def status(root,now=None,days=None):
    root,cfg=config_load(root);now=time.time() if now is None else now
    days=integer(days if days is not None else cfg['history_days'],1,14,'history days')
    begin=now-days*86400;assets=[]
    with database(root,True) as db:
        batch_stats=db.execute('SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM captures').fetchone()
        attempts=[dict(r) for r in db.execute('SELECT observed,outcome,detail FROM attempts ORDER BY observed DESC,id DESC LIMIT 20')]
        for asset in cfg['assets']:
            node=asset['id'];latest=get_state(db,'latest:'+node,{})
            epoch_changed=bool(latest) and (latest.get('owner_epoch','initial')!=asset.get('epoch','initial') or latest.get('binding')!=subject_binding(cfg,node))
            sql='''SELECT p.body,p.duration,CASE WHEN c.ts IS NULL THEN 0 ELSE 1 END AS conflict FROM points p
            LEFT JOIN conflicts c ON c.subject=p.subject AND c.epoch=p.epoch AND c.ts=p.ts
            WHERE p.subject=? AND p.epoch=? AND p.ts>=? AND p.ts<=? ORDER BY p.ts LIMIT 100001'''
            rows=db.execute(sql,(node,'' if epoch_changed else latest.get('epoch',''),begin,now)).fetchall()
            if len(rows)>100000:fail('too many points for dashboard window; reduce history_days')
            points=[dict(core.decode(r['body']),duration_seconds=r['duration'],conflict=bool(r['conflict'])) for r in rows]
            start=max(begin,min((p['timestamp']-p['duration_seconds'] for p in points),default=now))
            w=weighted(points,start,now);means=w['means'];mean=means.get('cpu_accounted_ratio');span=now-start
            coverage=w['represented']/span if span>0 else 0
            last_sample=max((p['timestamp'] for p in points if p['duration_seconds']>0 and p.get('cpu_accounted_ratio') is not None and not p.get('quality') and not p['conflict']),default=None)
            age=None if last_sample is None else now-last_sample
            stale=last_sample is not None and age>max(120,cfg['interval_seconds']*2.5)
            no_latest_samples=bool(latest) and not latest.get('samples')
            holds=['identity_plan_and_service_impact_not_independently_verified','controlled_repeats_not_established']
            if epoch_changed:holds.append('epoch_changed_collect_new_evidence')
            failed_latest=bool(attempts) and attempts[0]['outcome']=='ERROR'
            if failed_latest:holds.append('latest_collection_failed')
            if not points:holds.append('no_samples')
            if span<86400:holds.append('less_than_24_hours')
            if coverage<.75:holds.append('insufficient_coverage')
            if stale:holds.append('stale_collection')
            if no_latest_samples:holds.append('latest_collection_no_samples')
            if latest.get('errors'):holds.append('latest_collection_errors')
            if any(p['conflict'] for p in points):holds.append('conflicting_sample_values')
            if means.get('cfs_throttled_periods_ratio') is None:holds.append('workload_limits_unknown')
            pressure=means.get('cpu_pressure_ratio');cfs=means.get('cfs_throttled_periods_ratio')
            context='CONTENTION_PRESENT' if pressure is not None and pressure>.1 or cfs is not None and cfs>.05 else 'CONTEXT_INCOMPLETE' if pressure is None or cfs is None else 'NO_HIGH_PRESSURE_IN_RECORDED_CONTEXT'
            observed='NOT_MEASURED' if mean is None else 'WITHIN_TOLERANCE' if mean>=cfg['policy']['acceptable_ratio'] else 'WATCH' if mean>=cfg['policy']['investigate_below'] else 'INVESTIGATE'
            decision='HOLD' if epoch_changed or failed_latest or no_latest_samples or not points or span<86400 or coverage<.75 or stale or latest.get('errors') or any(p['conflict'] for p in points) else observed
            action=('Restore collection and inspect gaps before interpreting performance.' if decision=='HOLD' else
                    'Within the chosen accounting tolerance. Check application latency/errors separately.' if observed=='WITHIN_TOLERANCE' else
                    'Observe and correlate workload/service impact; this percentage alone is not a support escalation.' if observed=='WATCH' else
                    'Investigate sustained shortfall alongside workload limits and pressure. Provider cause is not established.')
            daily=[];day=math.floor(start/86400)*86400
            while day<now and len(daily)<=15:
                end=min(day+86400,now);d=weighted(points,max(day,start),end)
                daily.append({'date':core.iso(day)[:10],'accounted_mean':d['means'].get('cpu_accounted_ratio'),
                              'coverage':d['represented']/max(1,end-max(day,start)),'complete_utc_day':day>=start and day+86400<=now})
                day+=86400
            stride=max(1,math.ceil(len(points)/600))
            history=[{'t':p['timestamp'],'value':p.get('cpu_accounted_ratio') if not p.get('quality') and not p['conflict'] else None,'quality':bool(p.get('quality') or p['conflict'])} for p in points[::stride]]
            assets.append({'id':node,'observed':observed,'decision':decision,'context':context,'mean':mean,
                           'execution':means.get('executing_ratio'),'pressure':pressure,'cfs':cfs,'coverage':coverage,
                           'elapsed_hours':span/3600,'observed_hours':w['represented']/3600,'window_start':core.iso(start),'window_end':core.iso(now),'last_sample':last_sample,'last_capture_end':latest.get('end'),
                           'age_seconds':age,'stale':stale,'points':len(points),'holds':holds,
                           'recommendation':action,'daily':daily,'history':history,'epoch':latest.get('epoch'),
                           'provider_cause_proven':False,'send_authorized':False})
    return {'schema':'g-skills.workspace-status.v1','version':VERSION,'generated_at':core.iso(now),'as_of':now,
            'synthetic':cfg['mode']=='demo','mode':cfg['mode'],'policy':cfg['policy'],'window_days':days,
            'expected_assets':len(cfg['assets']),'scope':'configured subjects only; not a verified provider-account census',
            'assets':assets,'collection_attempts':attempts,'stored_captures':batch_stats[0],'stored_bytes':batch_stats[1],
            'configuration_sha256':core.digest(cfg),'code_hashes':{'workspace':SELF_HASH,'collector':core.SOURCE_SHA256},'contact_provider':False}


def page(value,live=False):
    template=(core.ROOT/'assets/workspace-dashboard.html').read_text()
    data=core.canonical(value).decode().replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return template.replace('/*STATUS_JSON*/',data).replace('/*LIVE_MODE*/','true' if live else 'false').encode()


def render(root):
    value=status(root)
    atomic(root/'status.json',core.canonical(value))
    atomic(root/'dashboard.html',page(value))
    # Daily summaries are derived and replaceable; immutable raw captures remain in SQLite.
    daily=root/'daily';daily.mkdir(mode=0o700,exist_ok=True)
    if daily.is_symlink():fail('daily output must not be a symbolic link')
    dates=sorted({d['date'] for a in value['assets'] for d in a['daily']})
    for date in dates:
        output={'schema':'g-skills.daily.v1','date':date,'generated_at':value['generated_at'],'synthetic':value['synthetic'],
                'assets':[{'id':a['id'],**d} for a in value['assets'] for d in a['daily'] if d['date']==date],
                'interpretation':'derived UTC rollup; incomplete first/current days are marked; never a provider verdict'}
        atomic(daily/(date+'.json'),core.canonical(output))
    return value


def markdown_summary(value):
    def pct(number):
        return 'unmeasured' if number is None else f'{number:.1%}'
    lines=['# VPS health workspace', '',
           'SYNTHETIC DEMO — not real server observations.' if value['synthetic'] else 'Private measured-accounting summary; not provider attribution.',
           'As of: '+value['generated_at'], '',
           '| Subject | Decision | Accounted mean | Coverage | Observed / elapsed hours | Context |',
           '|---|---|---:|---:|---:|---|']
    for node in value['assets']:
        lines.append(f"| {node['id']} | {node['decision']} | {pct(node['mean'])} | {pct(node['coverage'])} | {node['observed_hours']:.1f} / {node['elapsed_hours']:.1f} | {node['context']} |")
    lines += ['', 'Policy: '+str(round(value['policy']['acceptable_ratio']*100))+'% acceptable; investigate below '+str(round(value['policy']['investigate_below']*100))+'%. These are not contract guarantees.']
    for node in value['assets']:
        lines += ['', '## '+node['id'], node['recommendation'],
                  'UTC range: '+node['window_start']+' to '+node['window_end'],
                  'Evidence limitations: '+', '.join(node['holds'])]
    lines += ['', 'This is not a full raw replay archive. Keep the private workspace database and source version.',
              'No provider contact, service-health certificate or host action is authorized by this report.']
    return ('\n'.join(lines)+'\n').encode()


def export(root,out):
    root,cfg=config_load(root);value=status(root);out=Path(out)
    if out.exists():fail('export destination exists; choose a new directory to preserve evidence')
    out.mkdir(parents=True,mode=0o700)
    atomic(out/'status.json',core.canonical(value));atomic(out/'dashboard.html',page(value));atomic(out/'report.md',markdown_summary(value))
    with database(root,True) as db:
        refs=[dict(r) for r in db.execute('SELECT hash,observed,bytes FROM captures ORDER BY observed,hash')]
    atomic(out/'capture-index.json',core.canonical(refs))
    atomic(out/'manifest.json',core.canonical({'schema':'g-skills.workspace-export.v1','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},
                        'note':'summary export; full replay requires the private workspace database. Hashes are not independent attestation.'}))
    return {'out':str(out),'files':5,'contains_credentials':False,'private':True}


def make_server(root,port=8765):
    root,cfg=config_load(root);integer(port,0,65535,'port')
    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)
        def log_message(self,*args):pass
        def do_GET(self):
            self.connection.settimeout(5)
            expected=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected or self.headers.get('Origin') not in (None,'http://'+expected):
                self.send_error(403,'Use the printed loopback URL');return
            path=urllib.parse.urlsplit(self.path).path
            if path not in ('/','/api/status') or '?' in self.path:
                self.send_error(404);return
            try:
                value=status(root);data=page(value,True) if path=='/' else core.canonical(value)
                if len(data)>core.MAX_BYTES:raise ValueError('response bound')
            except (ValueError,OSError,sqlite3.Error):
                self.send_error(503,'Workspace unavailable; check the local collector');return
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8' if path=='/' else 'application/json')
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer');self.send_header('Cross-Origin-Resource-Policy','same-origin')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    # Loopback-only, read-only convenience server, not an internet-facing service.
    server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.timeout=5
    return server


def watch(args):
    if not args.approve_collection:fail('watch needs --approve-collection; bootstrap alone never enables recurring reads')
    root,cfg=config_load(args.workspace)
    if cfg['mode']=='demo':fail('demo history is frozen; use serve, not watch')
    integer(args.cycles,1,10080,'--cycles')
    if args.cycles*cfg['interval_seconds']>7*86400:fail('watch is bounded to seven planned days; reduce --cycles or use a reviewed user timer')
    server=make_server(root,args.port) if args.serve else None
    if server:
        threading.Thread(target=server.serve_forever,daemon=True).start()
        print(f'Dashboard: http://127.0.0.1:{server.server_port}/',file=sys.stderr,flush=True)
    count=0;errors=0
    try:
        for i in range(args.cycles):
            started=time.monotonic()
            try:result=collect(root);errors+=bool(result.get('source_errors'));count+=1
            except (ValueError,OSError,sqlite3.Error):errors+=1;print('Collection failed; inspect dashboard and source access. No catch-up fan-out.',file=sys.stderr,flush=True)
            if i+1<args.cycles:time.sleep(max(1,cfg['interval_seconds']-(time.monotonic()-started)))
    except KeyboardInterrupt:
        pass
    finally:
        if server:server.shutdown();server.server_close()
    return {'completed_cycles':count,'failed_or_partial_cycles':errors,'automatic_contact':False}


def schedule(root,out):
    root,cfg=config_load(root)
    if cfg['mode']=='demo':fail('demo cannot be scheduled')
    out=Path(out)
    if out.exists():fail('schedule output exists; choose a new directory')
    paths=(str(root),sys.executable,str(Path(__file__).with_name('vps_health.py')))
    if any(any(c in p for c in ('\n','\r','\x00')) for p in paths):fail('unsupported control character in service path')
    quote=lambda s:'"'+s.replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'
    name='gskills-vps-'+hashlib.sha256(str(root).encode()).hexdigest()[:10]
    service=f'''[Unit]\nDescription=G-Skills passive VPS collection (user-approved)\n[Service]\nType=oneshot\nUMask=0077\nWorkingDirectory={quote(str(root))}\nEnvironmentFile=-{quote(str(root/'credentials.env'))}\nExecStart={quote(sys.executable)} {quote(paths[2])} collect --workspace {quote(str(root))}\nTimeoutStartSec=240\nNoNewPrivileges=yes\n'''
    timer=f'''[Unit]\nDescription=G-Skills collection cadence\n[Timer]\nOnStartupSec=15\nOnUnitActiveSec={cfg['interval_seconds']}s\nAccuracySec=1s\nPersistent=false\nUnit={name}.service\n[Install]\nWantedBy=timers.target\n'''
    out.mkdir(parents=True,mode=0o700);atomic(out/(name+'.service'),service.encode());atomic(out/(name+'.timer'),timer.encode())
    return {'generated_only':True,'installed':False,'unit':name,'directory':str(out),
            'review':'Inspect both files; user-systemd requires Linux and an active user manager. No login-linger change is made.',
            'enable_after_explicit_approval':f'mkdir -p ~/.config/systemd/user && cp {shlex.quote(str(out/name))}.service {shlex.quote(str(out/name))}.timer ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now {name}.timer',
            'stop':f'systemctl --user disable --now {name}.timer','credentials':'Optional private credentials.env sets only your named token variables; chmod 600; never commit it.'}


def draft_email(args):
    if not args.approve_draft:fail('draft-email needs --approve-draft; monitoring cannot authorize correspondence')
    root,cfg=config_load(args.workspace);value=status(root)
    if value['synthetic'] and not args.example:fail('demo data cannot become a real provider draft; add --example for a clearly labelled template')
    node=next((n for n in value['assets'] if n['id']==args.node),None)
    if node is None:fail('unknown --node; use dashboard to list configured identities')
    if not args.example and (node['decision']!='INVESTIGATE' or node['coverage']<.75 or node['elapsed_hours']<48):
        fail('insufficient sustained sub-threshold evidence for this template; keep investigating, or use --example for a non-sendable example')
    if not args.impact or len(args.impact)>500 or any(c in args.impact for c in ('\r','\x00')):fail('--impact must describe observed service impact in at most 500 characters')
    mean='not measured' if node['mean'] is None else f"{node['mean']:.1%}"
    text=('EXAMPLE ONLY — SYNTHETIC OR INCOMPLETE; DO NOT SEND\n\n' if args.example else 'DRAFT FOR HUMAN REVIEW — NOT SENT\n\n')
    text+=f'''Subject: Review request for [provider VM reference]\n\nHello,\n\nWe observed {args.impact.strip()}\nFor our internal alias {args.node}, the guest CPU-accounting screen averaged {mean} over {node['window_start']} to {node['window_end']} ({node['elapsed_hours']:.1f} hours; {node['coverage']:.0%} observed coverage). This is an accounting estimate, not a contractual entitlement or proof of a host fault. Workload context: {node['context'].lower().replace('_',' ')}.\n\nPlease review the host-side scheduling/resource evidence for the attached UTC window. Do not reboot or migrate without our separate agreement. We can supply the private measurements and confound checks.\n\nThank you.\n'''
    out=Path(args.out)
    if out.exists() or out.is_symlink():fail('draft output exists; choose a new private file')
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(text)
    return {'draft':str(out),'sent':False,'approved_to_send':False,'example':args.example,'words':len(text.split()),'caveat':'Review identities, time range, context and contract before deciding to send.'}


def learning_proposal(root,out):
    """Only whitelisted aggregate gaps leave this private workspace."""
    root,cfg=config_load(root);value=status(root)
    allowed={'epoch_changed_collect_new_evidence','latest_collection_failed','no_samples',
             'less_than_24_hours','insufficient_coverage','stale_collection','latest_collection_no_samples',
             'latest_collection_errors','conflicting_sample_values','workload_limits_unknown'}
    import collections
    with database(root,True) as db:
        hashes=[row[0] for row in db.execute('SELECT hash FROM captures ORDER BY hash')]
    result={'schema':'g-skills.lesson-proposal.v1','state':'PROPOSED_NOT_APPLIED',
            'source_capture_hash':core.digest(hashes),'analyzer_hash':SELF_HASH,
            'state_counts':dict(collections.Counter(a['decision'] for a in value['assets'])),
            'known_gap_counts':dict(collections.Counter(gap for a in value['assets'] for gap in a['holds'] if gap in allowed)),
            'required_review':['reproduce with a synthetic non-identifying fixture','add a failing regression',
                               'fix owning implementation','run safety and privacy tests','maintainer approves versioned change'],
            'can_change_policy':False,'can_contact_provider':False,'can_publish':False}
    core.save_json(out,result)
    return result


def register(sub):
    a=sub.add_parser('bootstrap',help='Create a private workspace; no service install or real collection')
    a.add_argument('--workspace',required=True,type=Path);a.add_argument('--mode',choices=('demo','local','prometheus'),default='demo')
    a.add_argument('--node',default='my-vps');a.add_argument('--profile',type=Path);a.add_argument('--url');a.add_argument('--loki-url')
    a.add_argument('--token-env');a.add_argument('--loki-token-env');a.add_argument('--allow-http',action='store_true')
    a.add_argument('--interval',type=int,default=300);a.add_argument('--acceptable',type=float,default=.9);a.add_argument('--investigate-below',type=float,default=.8)
    for name in ('collect','dashboard','serve','watch','export','schedule','draft-email'):
        a=sub.add_parser(name,help={'collect':'One bounded passive/metrics collection','dashboard':'Refresh/read retained history','serve':'Read-only loopback dashboard; no collection','watch':'Explicit foreground collection with finite cycles','export':'New immutable summary export','schedule':'Generate user timer files; never install','draft-email':'Explicit local review draft; never send'}[name])
        a.add_argument('--workspace',required=True,type=Path)
        if name=='collect':a.add_argument('--lookback-hours',type=int,default=1)
        if name in ('serve','watch'):a.add_argument('--port',type=int,default=8765)
        if name=='watch':
            a.add_argument('--cycles',type=int,default=864);a.add_argument('--approve-collection',action='store_true');a.add_argument('--serve',action='store_true')
        if name in ('export','schedule','draft-email'):a.add_argument('--out',type=Path,required=True)
        if name=='draft-email':
            a.add_argument('--node',required=True);a.add_argument('--impact',required=True);a.add_argument('--approve-draft',action='store_true');a.add_argument('--example',action='store_true')
    sub.add_parser('capabilities',help='Machine-readable command/safety contract')


def dispatch(args):
    if args.cmd=='bootstrap':return bootstrap(args)
    if args.cmd=='capabilities':return {'version':VERSION,'commands':sorted(set(COMMANDS)|{'demo','collect-local','collect-prometheus','report','verify','compare','learn'}),'default_mode':'synthetic demo','privacy':'local workspace only','can_send_email':False,'can_install_services':False,'can_stress_test':False,'exit_codes':{'0':'command completed; not a healthy/causal verdict','2':'invalid input, safety refusal or operation error'},'next':'bootstrap --workspace PRIVATE_NEW_DIRECTORY --mode demo'}
    if args.cmd=='collect':return collect(args.workspace,args.lookback_hours)
    if args.cmd=='dashboard':return render(config_load(args.workspace)[0])
    if args.cmd=='watch':return watch(args)
    if args.cmd=='export':return export(args.workspace,args.out)
    if args.cmd=='schedule':return schedule(args.workspace,args.out)
    if args.cmd=='draft-email':return draft_email(args)
    server=make_server(args.workspace,args.port)
    print(f'Read-only dashboard: http://127.0.0.1:{server.server_port}/ (Ctrl-C to stop)',file=sys.stderr,flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return {'stopped':True,'collected':False}
