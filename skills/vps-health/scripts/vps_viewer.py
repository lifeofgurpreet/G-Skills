#!/usr/bin/env python3
"""Attach a viewing machine to a known private investigation.

The agent owns the existing authorized SSH route. These commands export a short-
lived matching contract, describe the foreground forward and verify its local
HTTP result; they install no service, discover no credentials and run no SSH.
"""
from __future__ import annotations
import http.client
from pathlib import Path
import re
import shlex
import time

import vps_health as core
import vps_workspace as ws
import vps_agent as agent

SCHEMA='g-skills.viewer-handoff.v1'
FIELDS={'schema','issued_at','expires_at','run_id','plan_sha256','configuration_sha256',
        'subjects_sha256','expected_subjects','mode','server_port','viewer_port','source_version'}


def port(value):
    return ws.integer(value,1,65535,'viewer port')


def validate(value,now=None):
    if not isinstance(value,dict) or set(value)!=FIELDS or value.get('schema')!=SCHEMA:
        raise core.InvalidEvidence('use the exact private viewer handoff; unexpected fields are refused')
    if not isinstance(value['run_id'],str) or not re.fullmatch(r'[a-f0-9]{32}',value['run_id']):
        raise core.InvalidEvidence('invalid owned run identifier')
    for key in ('plan_sha256','configuration_sha256','subjects_sha256'):
        if not isinstance(value[key],str) or not re.fullmatch(r'[a-f0-9]{64}',value[key]):raise core.InvalidEvidence('invalid expected identity digest')
    port(value['server_port']);port(value['viewer_port'])
    ws.integer(value['expected_subjects'],1,100,'expected_subjects')
    if value['mode'] not in ('demo','local','prometheus') or not re.fullmatch(r'\d+\.\d+\.\d+',str(value['source_version'])):
        raise core.InvalidEvidence('invalid source mode/version')
    issued=core.finite(value['issued_at'],minimum=0);expires=core.finite(value['expires_at'],minimum=0)
    now=time.time() if now is None else core.finite(now,minimum=0)
    if not 0<expires-issued<=3600 or issued>now+30 or expires<=now:
        raise core.InvalidEvidence('viewer handoff is expired or its clock is inconsistent; obtain a fresh one from the authorized host')
    return value


def load(path):
    return validate(ws.read_private_json(Path(path),max_bytes=8192))


def handoff(root,out,valid_seconds=900):
    """Source-host operation. Observe the actual owned viewer before exporting."""
    ws.integer(valid_seconds,30,3600,'valid_seconds')
    output=ws.public_path(out)
    if output.exists() or output.is_symlink():raise FileExistsError('handoff output exists; no file will be overwritten')
    root,cfg=ws.config_load(root)
    if output==root or root in output.parents:raise core.InvalidEvidence('write the private handoff outside the observation workspace')
    verified=agent.verify_runtime(root)
    if verified.get('state')!='VERIFIED':raise core.InvalidEvidence('the source viewer is not verified; do not issue a connection handoff')
    state=agent.runtime_status(root);launch=agent._read(agent._safe_dir(root)/'launch.json',{})
    if state.get('run_id')!=verified['run_id'] or state.get('state')!='RUNNING' or not state.get('process_verified'):
        raise core.InvalidEvidence('source runtime changed while preparing viewer access')
    intent=launch.get('intent',{})
    if intent.get('configuration')!=agent.config_intent(cfg) or intent.get('source')!=agent.source_binding():
        raise core.InvalidEvidence('source configuration/code changed; review its owned plan')
    actual_port=port(int(verified['dashboard_url'].rsplit(':',1)[1][:-1]))
    now=time.time()
    value={'schema':SCHEMA,'issued_at':now,'expires_at':min(now+valid_seconds,core.stamp(state['deadline_utc'])),
           'run_id':state['run_id'],'plan_sha256':state['plan_sha256'],
           'configuration_sha256':core.digest(cfg),'subjects_sha256':core.digest(sorted(a['id'] for a in cfg['assets'])),
           'expected_subjects':len(cfg['assets']),'mode':cfg['mode'],'server_port':actual_port,
           'viewer_port':intent.get('viewer_port') or actual_port,'source_version':ws.VERSION}
    validate(value)
    core.save_json(output,value)
    return {'schema':'g-skills.viewer-handoff-result.v1','state':'HANDOFF_WRITTEN','path':str(output),
            'sha256':core.digest(value),'expires_at':core.iso(value['expires_at']),
            'connection_opened':False,'contains_credentials':False,'review_before_transfer':True,
            'note':'Transfer privately through the existing authorized route. This file matches an investigation; it is not a bearer token, SSH authentication or permission to contact a provider.'}


def plan(path,ssh_target):
    value=load(path)
    # A known SSH alias or user@hostname; never a URI, options or a shell command.
    if not isinstance(ssh_target,str) or not re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}@)?[A-Za-z0-9][A-Za-z0-9_.-]{0,252}',ssh_target):
        raise core.InvalidEvidence('supply one explicitly authorized SSH alias or user@hostname; options and commands are not targets')
    forward=f"127.0.0.1:{value['viewer_port']}:127.0.0.1:{value['server_port']}"
    argv=['ssh','-N','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
          '-o','ExitOnForwardFailure=yes','-o','ForkAfterAuthentication=no','-o','GatewayPorts=no','-o','ForwardAgent=no',
          '-o','ForwardX11=no','-o','PermitLocalCommand=no','-o','ControlMaster=no',
          '-o','ControlPath=none','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',
          '-o','ConnectTimeout=10','-L',forward,'--',ssh_target]
    return {'schema':'g-skills.viewer-plan.v1','state':'PLAN_ONLY','handoff_sha256':core.digest(value),
            'ssh_target':ssh_target,'ssh_argv':argv,'posix_command_example':shlex.join(argv),
            'browser_url':f"http://127.0.0.1:{value['viewer_port']}/",'run_id':value['run_id'],
            'ssh_connection_verified':False,'existing_ssh_configuration_applies':True,
            'external_actions_authorized':False,'private_observations_copied':False,
            'agent_next_steps':[
                'Confirm this is the user-approved SSH target and inspect only its trusted profile for unexpected configured forwards/proxy behavior. Host permission prompts still apply.',
                'Execute ssh_argv through the host terminal tool as a foreground owned task, not a detached unbounded service. Missing authentication, host-key trust or a busy local port is a blocker; do not bypass checks.',
                'Run viewer-verify with the same private handoff on this viewing machine, then open the returned local URL. A running ssh process alone is not proof of a working viewer.',
                'Close only this owned forwarding session when done. Do not kill an unrelated SSH connection or stop the remote collector just to close the browser path.'
            ],
            'limits':'A local CLI plan cannot verify SSH configuration, host identity or user authorization. A port forward is not reboot persistence. No credentials are discovered and no command is executed by this operation.'}


def verify(path):
    """Viewing-machine operation: exact HTTP identity, not remote /proc attestation."""
    expected=load(path)
    result={'schema':'g-skills.remote-viewer-verification.v1','state':'NOT_VERIFIED',
            'http_identity_matched':False,'run_id':expected['run_id'],
            'ssh_connection_verified':False,'remote_kernel_independently_verified':False,
            'service_health_verified':False,'provider_cause_proven':False,
            'external_actions_authorized':False,'read_only':True}
    url=f"http://127.0.0.1:{expected['viewer_port']}/"
    try:payload=agent.read_viewer(url)
    except (OSError,ValueError,http.client.HTTPException):return {**result,'reason':'local_forward_or_viewer_unavailable'}
    if not isinstance(payload,dict):return {**result,'reason':'unexpected_viewer_payload'}
    live=payload.get('agent_runtime');assets=payload.get('assets')
    if (payload.get('schema')!='g-skills.workspace-status.v1' or not isinstance(live,dict)
            or not isinstance(assets,list) or len(assets)>100 or not all(isinstance(a,dict) and isinstance(a.get('id'),str) for a in assets)):
        return {**result,'reason':'unexpected_viewer_payload'}
    identities=sorted(a['id'] for a in assets)
    if (payload.get('configuration_sha256')!=expected['configuration_sha256']
            or core.digest(identities)!=expected['subjects_sha256'] or len(identities)!=expected['expected_subjects']
            or payload.get('version')!=expected['source_version']
            or type(payload.get('expected_assets')) is not int or payload['expected_assets']!=expected['expected_subjects']
            or payload.get('mode')!=expected['mode'] or payload.get('synthetic') is not (expected['mode']=='demo')
            or live.get('run_id')!=expected['run_id'] or live.get('plan_sha256')!=expected['plan_sha256']
            or live.get('state')!='RUNNING' or live.get('process_verified') is not True):
        return {**result,'reason':'viewer_identity_mismatch'}
    stamp=payload.get('as_of');finished=time.time()
    if type(stamp) not in (float,int) or not 0<=stamp or not -30<=finished-stamp<=60:
        return {**result,'reason':'viewer_response_clock_or_freshness_invalid'}
    if finished>=expected['expires_at']:
        return {**result,'reason':'handoff_expired_during_readback'}
    return {**result,'state':'VIEWER_MATCHED','http_identity_matched':True,'browser_url':url,
            'synthetic':expected['mode']=='demo','expected_subjects':expected['expected_subjects'],
            'source_reports_owned_worker':True,'checked_at':core.iso(finished),
            'note':'This viewing machine reached the expected run, configuration and inventory. SSH trust is established by the separately checked native transport, not by this JSON receipt. Fresh HTTP is not fresh measurement coverage.'}


def register(sub):
    p=sub.add_parser('viewer-handoff',help='Privately export the verified source viewer identity; no tunnel or new collector')
    p.add_argument('--workspace',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--valid-seconds',type=int,default=900)
    p=sub.add_parser('viewer-plan',help='Describe an approved SSH forward from the viewing machine; do not execute it')
    p.add_argument('--handoff',required=True,type=Path);p.add_argument('--ssh-target',required=True)
    p=sub.add_parser('viewer-verify',help='Match the local browser path to a trusted source-host handoff')
    p.add_argument('--handoff',required=True,type=Path)


def dispatch(args):
    if args.cmd=='viewer-handoff':return handoff(args.workspace,args.out,args.valid_seconds)
    if args.cmd=='viewer-plan':return plan(args.handoff,args.ssh_target)
    if args.cmd=='viewer-verify':return verify(args.handoff)
    raise core.InvalidEvidence('unknown viewer command')
