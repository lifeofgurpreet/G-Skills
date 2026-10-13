#!/usr/bin/env python3
"""Bounded, agent-owned local runtime; no model loop, root service or sender.

The host coding agent chooses targets and obtains actual user authorization.
Plan hashes bind the requested operations; they are not authentication or proof
of human consent. Runtime files are private, and the HTTP viewer remains read-only.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import uuid

import vps_health as core
import vps_workspace as ws

SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
STATES={'STARTING','RUNNING','STOP_REQUESTED','STOPPED','COMPLETED','FAILED','NEEDS_REVIEW'}
TERMINAL={'STOPPED','COMPLETED','FAILED','NEEDS_REVIEW'}
CLIENTS={'generic','codex','claude-code','cursor'}
CAPABILITIES={'mail.read','mail.draft','mail.send','browser.open','host.access'}
CHILDREN={}


def linux_required():
    if sys.platform!='linux':raise core.InvalidEvidence('managed runtime currently qualifies Linux; use an authorized Linux host or an existing foreground route')


def source_binding():
    import vps_forensics as forensic
    return {'agent':SOURCE_SHA256,'workspace':ws.SELF_HASH,'collector':core.SOURCE_SHA256,'guest_context':forensic.SOURCE_SHA256}


def config_intent(cfg):
    return {key:value for key,value in cfg.items() if key not in ('created_at','version')}


def _safe_dir(root,create=False):
    path=root/'.agent'
    if path.is_symlink():raise core.InvalidEvidence('managed state directory must not be a symbolic link')
    if create:
        path.mkdir(mode=0o700,exist_ok=True)
    if path.exists() and (not path.is_dir() or path.stat().st_uid!=os.getuid() or path.stat().st_mode&0o077):
        raise core.InvalidEvidence('managed state must be a private directory owned by this user')
    return path


def _read(path,default=None):
    if path.is_symlink():raise core.InvalidEvidence('managed state file must not be a symbolic link')
    if not path.exists():return default
    if not path.is_file() or path.stat().st_size>256*1024:
        raise core.InvalidEvidence('managed state is not a bounded regular file')
    return core.read_json(path)


def _atomic(path,value):
    if path.is_symlink():raise core.InvalidEvidence('refusing a symbolic-link state target')
    ws.atomic(path,core.canonical(value))


def process_identity(pid):
    """Linux process start ticks + boot identity; reused PIDs are not our worker."""
    if type(pid) is not int or pid<=0 or sys.platform!='linux':return None
    try:
        with open(f'/proc/{pid}/stat','rb') as handle:text=handle.read(4096).decode()
        tail=text[text.rfind(')')+2:].split()
        if len(tail)<20 or tail[0]=='Z':return None
        with open('/proc/sys/kernel/random/boot_id','rb') as handle:boot=handle.read(128).decode().strip()
        return {'boot':boot,'start':tail[19]}
    except (OSError,ValueError,IndexError,UnicodeError):return None


@contextlib.contextmanager
def _lock(path,create=True):
    linux_required()
    import fcntl
    flags=os.O_RDWR|os.O_NOFOLLOW|(os.O_CREAT if create else 0)
    fd=os.open(path,flags,0o600)
    try:
        if os.fstat(fd).st_mode&0o077:raise core.InvalidEvidence('runtime lock has unsafe permissions')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise core.InvalidEvidence('workspace runtime is already starting or running') from None
        yield fd
    finally:os.close(fd)


@contextlib.contextmanager
def collection_lock(root):
    """Keep actual collector exclusivity beyond an expiring DB lease on Linux."""
    if sys.platform!='linux':
        yield  # Portable foreground paths retain their existing SQLite lease.
        return
    with _lock(root/'.collection.lock'):
        yield


def _requests(folder):
    data=_read(folder/'requests.json',{'requests':[]})
    if not isinstance(data,dict) or not isinstance(data.get('requests'),list) or len(data['requests'])>8:
        raise core.InvalidEvidence('invalid bounded capability-request list')
    for r in data['requests']:
        if (not isinstance(r,dict) or not re.fullmatch('[a-f0-9]{24}',str(r.get('id','')))
                or r.get('required_capability') not in CAPABILITIES
                or r.get('state') not in ('NEEDS_CONNECTION','HOST_REPORTED_AVAILABLE','DECLINED')
                or r.get('send_authorized') is not False):
            raise core.InvalidEvidence('malformed capability request')
    return data['requests']


def _run_locked(folder):
    path=folder/'run.lock'
    if not path.exists():return False
    try:
        with _lock(path,False):return False
    except core.InvalidEvidence as exc:
        if str(exc)=='workspace runtime is already starting or running':return True
        raise


def plan(args):
    root=ws.public_path(args.workspace)
    seconds=ws.integer(args.duration_seconds,1,7*86400,'duration_seconds')
    port=ws.integer(args.port,0,65535,'port')
    client=getattr(args,'client','generic')
    if client not in CLIENTS:raise core.InvalidEvidence('unsupported client label')
    needs=[]
    if sys.platform!='linux':needs.append({'code':'runtime_platform','actor':'agent','question':'Use the authorized Linux target, or the existing portable foreground viewer. No Linux target may be guessed.'})
    exists=(root/'workspace.json').is_file()
    if root.exists() and not exists:raise core.InvalidEvidence('destination exists without a valid workspace; preserve it and choose a new private path')
    if exists:
        _,cfg=ws.config_load(root)
        if args.mode not in ('auto',cfg['mode']):raise core.InvalidEvidence('existing workspace uses another collection mode; do not overwrite it')
        if any(getattr(args,key,None) for key in ('profile','url','loki_url')):
            raise core.InvalidEvidence('existing workspace already defines endpoints and scope; changing them needs an explicit new workspace')
    elif args.mode=='auto':
        return {'schema':'g-skills.agent-plan.v1','ready':False,'needs':[{'code':'target_scope','actor':'agent','question':'Identify the user-authorized host or existing monitoring route; select demo, local or prometheus explicitly.'}],
                'workspace':str(root),'external_actions_authorized':False,'plan_sha256':None}
    else:cfg=ws.bootstrap_config(args)
    if cfg['mode']=='local' and sys.platform!='linux' and not needs:
        needs.append({'code':'runtime_platform','actor':'agent','question':'Passive host collection requires Linux.'})
    for key in ('token_env','loki_token_env'):
        name=cfg.get(key)
        if name and not os.environ.get(name):
            needs.append({'code':'credential_variable','actor':'user_authentication','variable':name,
                          'question':'Use the existing approved credential mechanism for the collector; do not ask the user to paste a secret into chat.'})
    predecessor=None
    folder=_safe_dir(root)
    if folder.exists():
        previous=_read(folder/'launch.json')
        if previous:
            if not isinstance(previous,dict) or not re.fullmatch('[a-f0-9]{32}',str(previous.get('run_id',''))):
                raise core.InvalidEvidence('invalid previous runtime; preserve it for inspection')
            predecessor=previous['intent'].get('predecessor_run') if _run_locked(folder) else previous['run_id']
    intent={'schema':'g-skills.agent-intent.v1','workspace':str(root),'configuration':config_intent(cfg),
            'predecessor_run':predecessor,
            'duration_seconds':seconds,'port':port,'source':source_binding()}
    return {'schema':'g-skills.agent-plan.v1','ready':not needs,'needs':needs,'intent':intent,
            'plan_sha256':core.digest(intent),'operation':'reuse_workspace' if exists else 'create_private_workspace',
            'scope':{'mode':cfg['mode'],'subjects':[a['id'] for a in cfg['assets']],'account_census_verified':False},
            'human_decision':'Approve these targets, private workspace, collection duration and read scopes once. OAuth or later external actions remain separate.',
            'agent_work':['validate_scope','create_or_reuse_workspace','start_owned_worker_and_loopback_viewer','verify_runtime','observe_and_report','stop_at_deadline_or_request'],
            'external_actions_authorized':False,'persistence':'detached Linux process, not reboot recovery; the execution platform may terminate it',
            'deadline_semantics':'No new collection cycle starts after the budget; an in-flight bounded read can finish first.'}


def runtime_status(path):
    root=ws.public_path(path);folder=_safe_dir(root)
    result={'schema':'g-skills.agent-runtime.v1','state':'NOT_MANAGED','process_verified':False,
            'evidence_ready':False,'connected_services':False,'external_actions_authorized':False}
    if not folder.exists():return {**result,'requests':[],'agent_next_action':'plan_workspace'}
    requests=_requests(folder)
    result['requests']=requests
    result['agent_next_action']='resolve_host_capability' if any(r['state']=='NEEDS_CONNECTION' for r in requests) else 'plan_workspace'
    doc=_read(folder/'status.json')
    if doc is None:return {**result,'state':'STARTING' if _run_locked(folder) else 'NOT_MANAGED'}
    if not isinstance(doc,dict) or doc.get('schema')!='g-skills.agent-state.v1' or doc.get('state') not in STATES or not re.fullmatch('[a-f0-9]{32}',str(doc.get('run_id',''))):
        raise core.InvalidEvidence('invalid managed runtime record; preserve it for inspection')
    child=CHILDREN.get(doc['run_id'])
    if child:child.poll()  # Reap only a child actually launched by this process.
    alive=process_identity(doc.get('pid'))
    verified=alive is not None and alive==doc.get('process_identity')
    state=doc['state']
    if state not in TERMINAL and not verified and not _run_locked(folder):state='ORPHANED'
    result.update({key:doc.get(key) for key in ('run_id','pid','started_at','deadline_utc','updated_at','dashboard_url','cycles','failed_cycles','events','plan_sha256','last_event')})
    result.update(state=state,process_verified=verified,
                  progress_scope='local worker actions, not proof that an AI agent is still connected',
                  persistence='ends at deadline; no boot or process-supervisor restart')
    result['agent_next_action']=('inspect_runtime_failure' if state in ('FAILED','ORPHANED','NEEDS_REVIEW') else
                                 'resolve_host_capability' if any(r['state']=='NEEDS_CONNECTION' for r in requests) else
                                 'inspect_evidence' if state in TERMINAL else 'monitor_existing_run')
    return result


def handoff(root,status=None):
    root,cfg=ws.config_load(root)
    d=runtime_status(root) if status is None else status
    path=root/'HANDOFF.md'
    if path.is_symlink():raise core.InvalidEvidence('handoff path cannot be a symbolic link')
    entry=str(Path(__file__).with_name('vps_health.py'))
    commands={name:shlex.join([sys.executable,entry,name,'--workspace',str(root)]) for name in ('agent-status','doctor','brief')}
    stop=shlex.join([sys.executable,entry,'agent-stop','--workspace',str(root),'--run-id',str(d.get('run_id','REQUIRES_CURRENT_RUN_ID'))])
    text=f"""# Private agent handoff

The coding agent owns routine setup and verification. The human approves scope,
authentication and external actions, not shell syntax. This file contains local
state, not fresh permission to change targets or contact a provider.

Mode: {cfg['mode']}. Runtime: {d['state']}. Run: {d.get('run_id','none')}.
Dashboard: {d.get('dashboard_url') or 'not verified yet'}
Deadline: {d.get('deadline_utc') or 'not running'}.

Use `agent-status` to recheck actual process identity before claiming it is alive.
The dashboard reports runtime and evidence separately. A previous completed worker
is not a multi-day observation or provider verdict. Do not start a second collector.

```sh
{commands['agent-status']}
{commands['doctor']}
{commands['brief']}
# Stop only this owned run, never an arbitrary PID:
{stop}
```

If a connector is needed, inspect the current host agent's tool registry. Use its
approved discovery/authentication flow for only the needed capability. A local
request record is not a connected service. Never paste tokens, install an untrusted
server, bypass permission prompts or infer mail-send permission from a read/draft
connection. Current requests are visible in `agent-status` and the dashboard.

Preserve the private database and captures. Keep provider-account discovery,
service impact and external actions as explicit remaining tasks. Installation of a
system service, reboot recovery, stress workload, migration and provider messages
require their own authorization. No such action is performed by this worker.
"""
    ws.atomic(path,text.encode())


def _guard_config(root,cfg,runtime_id=None):
    folder=_safe_dir(root)
    if not folder.exists():return
    if _run_locked(folder):
        launch=_read(folder/'launch.json')
        if not isinstance(launch,dict) or runtime_id!=launch.get('run_id'):
            raise core.InvalidEvidence('managed worker owns collection; do not run another watch, timer or collect')
        if config_intent(cfg)!=launch['intent']['configuration']:
            raise core.InvalidEvidence('managed target/configuration changed; stop and review a new plan')


def start(args):
    linux_required()
    p=plan(args)
    if not p['ready']:raise core.InvalidEvidence('agent plan has unresolved target/platform/credential needs')
    if args.approve_plan!=p['plan_sha256']:
        raise core.InvalidEvidence('start requires --approve-plan matching the current bounded plan; the agent must obtain actual user authorization first')
    root=Path(p['intent']['workspace'])
    if not root.exists():ws.bootstrap(args)
    root,cfg=ws.config_load(root)
    folder=_safe_dir(root,True)
    try:
        lock_context=_lock(folder/'run.lock');fd=lock_context.__enter__()
    except core.InvalidEvidence as exc:
        if str(exc)!='workspace runtime is already starting or running':raise
        # The owner may hold the inherited lock before its first status write.
        # Attach to that matching in-flight launch, not a second worker or a
        # falsely different plan inferred from an absent startup receipt.
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            current=runtime_status(root);launch=_read(folder/'launch.json',{})
            if (current.get('plan_sha256')==p['plan_sha256'] and current.get('run_id')==launch.get('run_id')
                    and current['state']!='STARTING'):
                return current
            if current.get('process_verified') and launch.get('plan_sha256')!=p['plan_sha256']:
                raise core.InvalidEvidence('another active run owns a different plan; inspect and explicitly stop it first') from None
            time.sleep(.05)
        raise core.InvalidEvidence('matching worker startup is not yet verified; recheck agent-status before retrying') from None
    try:
        with collection_lock(root), ws.database(root,True) as db:
            if ws.get_state(db,'collector_lease',{}).get('until',0)>time.time():
                raise core.InvalidEvidence('an existing collection is in progress; retry instead of competing')
        run_id=uuid.uuid4().hex
        launch={'schema':'g-skills.agent-launch.v1','run_id':run_id,'intent':p['intent'],'plan_sha256':p['plan_sha256']}
        _atomic(folder/'launch.json',launch)
        env={key:value for key,value in os.environ.items() if key in ('PATH','HOME','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','TMPDIR') or key in (cfg.get('token_env'),cfg.get('loki_token_env'))}
        command=[sys.executable,str(Path(__file__).with_name('vps_health.py')),'_agent-worker','--workspace',str(root),'--run-id',run_id,'--lock-fd',str(fd)]
        # Hold the SAME open-file-description lock across launch; no stale PID
        # takeover or concurrent-start gap. The parent never sends a signal.
        proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              cwd=str(Path(__file__).parent),env=env,start_new_session=True,close_fds=True,pass_fds=(fd,))
        CHILDREN[run_id]=proc
    finally:lock_context.__exit__(None,None,None)
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        d=runtime_status(root)
        if d.get('run_id')==run_id and d['state'] in ('RUNNING',*TERMINAL):
            handoff(root,d);return d
        if proc.poll() is not None:
            break
        time.sleep(.05)
    d=runtime_status(root)
    if d.get('run_id')!=run_id:raise core.InvalidEvidence('worker did not establish its runtime record; inspect workspace, do not claim it started')
    handoff(root,d)
    return d


def stop(path,run_id,wait=5):
    linux_required();root,cfg=ws.config_load(path)
    if not re.fullmatch('[a-f0-9]{32}',str(run_id)):raise core.InvalidEvidence('stop needs the exact current run identity')
    d=runtime_status(root)
    if d.get('run_id')!=run_id:raise core.InvalidEvidence('stop identity differs from the current managed run')
    if d['state'] in TERMINAL and not d['process_verified']:return d
    if not d['process_verified'] and d['state']=='ORPHANED':return d
    _atomic(_safe_dir(root)/'stop.json',{'run_id':run_id,'requested_at':core.iso(time.time())})
    deadline=time.monotonic()+max(0,min(15,wait))
    while time.monotonic()<deadline:
        d=runtime_status(root)
        if not d['process_verified'] and d['state'] in TERMINAL:break
        time.sleep(.05)
    if d['process_verified']:d={**d,'state':'STOP_REQUESTED','stop_note':'Cooperative stop pending; no signal or forced termination was used.'}
    handoff(root,d)
    return d


def worker(path,run_id,fd):
    """One bounded worker; interruption is cooperative, collection is sequential."""
    linux_required()
    import fcntl
    root,cfg=ws.config_load(path);folder=_safe_dir(root)
    # An inherited descriptor, correct lock file and launch identity are required.
    info=os.fstat(fd);expected=(folder/'run.lock').stat()
    if (info.st_dev,info.st_ino)!=(expected.st_dev,expected.st_ino):raise core.InvalidEvidence('worker lock does not belong to this workspace')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    launch=_read(folder/'launch.json');intent=launch['intent']
    if run_id!=launch['run_id'] or core.digest(intent)!=launch['plan_sha256'] or intent['source']!=source_binding() or intent['configuration']!=config_intent(cfg):
        raise core.InvalidEvidence('worker launch no longer matches approved source/configuration')
    now=time.time();budget=intent['duration_seconds'];deadline=time.monotonic()+budget
    state={'schema':'g-skills.agent-state.v1','state':'STARTING','run_id':run_id,'pid':os.getpid(),
           'process_identity':process_identity(os.getpid()),'started_at':core.iso(now),'deadline_utc':core.iso(now+budget),
           'updated_at':core.iso(now),'dashboard_url':None,'cycles':0,'failed_cycles':0,'events':[],
           'plan_sha256':launch['plan_sha256'],'last_event':'starting'}
    def save(code=None):
        state['updated_at']=core.iso(time.time())
        if code:
            state['last_event']=code;state['events'].append({'at':state['updated_at'],'code':code});state['events']=state['events'][-32:]
        _atomic(folder/'status.json',state)
    server=None;thread=None
    save('runtime_starting')
    try:
        server=ws.make_server(root,intent['port']);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        state.update(state='RUNNING',dashboard_url=f'http://127.0.0.1:{server.server_port}/');save('viewer_verified');handoff(root,runtime_status(root))
        next_collection=0.;next_heartbeat=0.
        while time.monotonic()<deadline:
            if _read(folder/'stop.json',{}).get('run_id')==run_id:
                state['state']='STOPPED';save('stop_requested');break
            _,current=ws.config_load(root)
            if config_intent(current)!=intent['configuration']:
                state['state']='NEEDS_REVIEW';save('configuration_changed');break
            tick=time.monotonic()
            if cfg['mode']!='demo' and tick>=next_collection:
                state['cycles']+=1;save('collection_started')
                try:
                    result=ws.collect(root,runtime_id=run_id)
                    partial=bool(result.get('source_errors'));state['failed_cycles']+=partial
                    save('collection_partial' if partial else 'collection_completed')
                except (ValueError,OSError,sqlite3.Error):
                    state['failed_cycles']+=1;save('collection_failed')
                next_collection=time.monotonic()+cfg['interval_seconds']
            if tick>=next_heartbeat:save();next_heartbeat=tick+1
            time.sleep(min(.2,max(.001,deadline-time.monotonic())))
        else:state['state']='COMPLETED';save('bounded_runtime_completed')
    except (OSError,ValueError,sqlite3.Error):
        state['state']='FAILED';save('runtime_failed')
    finally:
        if server:server.shutdown();server.server_close()
        if thread:thread.join(2)
        save();handoff(root,{**state,'process_verified':False})
        os.close(fd)
    return {'state':state['state'],'run_id':run_id}


def connection_request(path,capability,purpose,client='generic'):
    linux_required()
    if capability not in CAPABILITIES or client not in CLIENTS:
        raise core.InvalidEvidence('unknown host capability or client')
    if not isinstance(purpose,str) or not 1<=len(purpose)<=300 or any(ord(c)<32 for c in purpose):
        raise core.InvalidEvidence('purpose must be a short explicit task without secrets or control characters')
    root,cfg=ws.config_load(path);folder=_safe_dir(root,True)
    request={'id':core.digest({'capability':capability,'purpose':purpose,'client':client})[:24],
             'required_capability':capability,'purpose':purpose,'client':client,'state':'NEEDS_CONNECTION',
             'connected':False,'send_authorized':False,
             'agent_next_step':'Inspect the current host tool registry; reuse an authorized matching tool. Otherwise search its approved connector catalog and guide native OAuth for only this capability. A local request cannot grant access.',
             'human_step':'Authenticate or approve the requested scope in the host client only when needed.',
             'scope_limit':'Read, draft and send are distinct. Recheck tools after connecting and obtain fresh approval for external changes.'}
    with _lock(folder/'requests.lock'):
        data={'requests':_requests(folder)}
        previous=next((r for r in data['requests'] if r['id']==request['id']),None)
        if previous:return previous
        if len(data['requests'])>=8:raise core.InvalidEvidence('request budget reached; reconcile existing needs before adding more')
        data['requests'].append(request);_atomic(folder/'requests.json',data)
    handoff(root)
    return request


def resolve_request(path,request_id,outcome,tool_id=None,receipt_ref=None):
    """Record the host agent's result; not OAuth or independent permission proof."""
    linux_required()
    if outcome not in ('available','declined'):
        raise core.InvalidEvidence('capability outcome must be available or declined')
    if outcome=='available' and any(not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_.:-]{1,100}',value) for value in (tool_id,receipt_ref)):
        raise core.InvalidEvidence('use an opaque tool/result reference, never URLs, tokens or tool response bodies')
    root,cfg=ws.config_load(path);folder=_safe_dir(root,True)
    with _lock(folder/'requests.lock'):
        requests=_requests(folder);item=next((r for r in requests if r['id']==request_id),None)
        if item is None:raise core.InvalidEvidence('unknown capability request identity')
        item.update(state='HOST_REPORTED_AVAILABLE' if outcome=='available' else 'DECLINED',
                    connected=False,host_reported_available=outcome=='available',verification='host_agent_report_not_independent_tool_access',
                    recheck_in_current_session=True,tool_id=tool_id if outcome=='available' else None,
                    receipt_ref=receipt_ref if outcome=='available' else None,send_authorized=False)
        _atomic(folder/'requests.json',{'requests':requests})
    handoff(root)
    return item


def register(sub):
    for name in ('agent-plan','agent-start'):
        p=sub.add_parser(name,help='Read-only bounded plan' if name=='agent-plan' else 'Apply an approved plan and launch/reuse one managed worker')
        p.add_argument('--workspace',required=True,type=Path);p.add_argument('--mode',choices=('auto','demo','local','prometheus'),default='auto')
        p.add_argument('--node',default='my-vps');p.add_argument('--profile',type=Path);p.add_argument('--url');p.add_argument('--loki-url')
        p.add_argument('--token-env');p.add_argument('--loki-token-env');p.add_argument('--allow-http',action='store_true')
        p.add_argument('--interval',type=int,default=300);p.add_argument('--acceptable',type=float,default=.9);p.add_argument('--investigate-below',type=float,default=.8)
        p.add_argument('--provider',choices=('unknown','other','contabo','hetzner','digitalocean','akamai','aws'),default='unknown');p.add_argument('--plan')
        p.add_argument('--duration-seconds',type=int,default=72*3600);p.add_argument('--port',type=int,default=0)
        p.add_argument('--client',choices=sorted(CLIENTS),default='generic');p.add_argument('--approve-plan')
    p=sub.add_parser('agent-status',help='Read actual owned-process state and pending agent needs');p.add_argument('--workspace',required=True,type=Path)
    p=sub.add_parser('agent-stop',help='Request cooperative stop for the exact owned run');p.add_argument('--workspace',required=True,type=Path);p.add_argument('--run-id',required=True)
    p=sub.add_parser('agent-request',help='Persist a host-native capability need, not a connection or consent');p.add_argument('--workspace',required=True,type=Path);p.add_argument('--capability',choices=sorted(CAPABILITIES),required=True);p.add_argument('--purpose',required=True);p.add_argument('--client',choices=sorted(CLIENTS),default='generic')
    p=sub.add_parser('agent-resolve',help='Record a host-reported capability result; not permission to send');p.add_argument('--workspace',required=True,type=Path);p.add_argument('--request-id',required=True);p.add_argument('--outcome',choices=('available','declined'),required=True);p.add_argument('--tool-id');p.add_argument('--receipt-ref')
    p=sub.add_parser('_agent-worker',help=__import__('argparse').SUPPRESS);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--run-id',required=True);p.add_argument('--lock-fd',type=int,required=True)


def dispatch(args):
    if args.cmd=='agent-plan':return plan(args)
    if args.cmd=='agent-start':return start(args)
    if args.cmd=='agent-status':return runtime_status(args.workspace)
    if args.cmd=='agent-stop':return stop(args.workspace,args.run_id)
    if args.cmd=='agent-request':return connection_request(args.workspace,args.capability,args.purpose,args.client)
    if args.cmd=='agent-resolve':return resolve_request(args.workspace,args.request_id,args.outcome,args.tool_id,args.receipt_ref)
    if args.cmd=='_agent-worker':return worker(args.workspace,args.run_id,args.lock_fd)
    raise core.InvalidEvidence('unrecognized agent operation')
