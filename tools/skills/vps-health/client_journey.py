#!/usr/bin/env python3
"""Private acceptance fixtures for terminal-agent journeys; not another agent runner.

Check actual installed bytes, owned process/HTTP and retained evidence. A model's
success message is never a verdict. Client execution and human UX review remain
separate from this deterministic artifact check. No credentials or model calls.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[3]
MAX_BYTES=16*1024*1024
EXPECTED=['example-contended','example-offline','example-stable']


def digest(raw):return hashlib.sha256(raw).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        raise ValueError("trial HTTP readback must not follow redirects")


def load(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError('expected a bounded regular private input')
    return json.loads(path.read_text())


def private_write(path,value):
    raw=value.encode() if isinstance(value,str) else (json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as handle:handle.write(raw)


def prepare(archive,manifest,out):
    archive=Path(archive);out=Path(out).expanduser().absolute()
    if out.exists() or out.is_symlink():raise ValueError('use a new private trial directory')
    for p in (out,*out.parents):
        if (p/'.git').exists():raise ValueError('trial evidence must be outside a repository')
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size>MAX_BYTES:
        raise ValueError('use a bounded regular reviewed archive')
    raw=archive.read_bytes()
    if len(raw)>MAX_BYTES:raise ValueError('archive size limit')
    release=load(manifest)
    if release.get('skill')!='vps-health' or release.get('schema')!='g-skills.skill-release.v1':
        raise ValueError('select a reviewed independent VPS Health artifact')
    record=release['files'].get(archive.name,{})
    if record.get('sha256')!=digest(raw) or record.get('bytes')!=len(raw):raise ValueError('release artifact differs from its manifest')
    files={}
    with zipfile.ZipFile(archive) as z:
        if sum(f.file_size for f in z.infolist())>MAX_BYTES:raise ValueError('expanded archive size limit')
        for f in z.infolist():
            path=PurePosixPath(f.filename)
            if (not f.filename.startswith('vps-health/') or path.is_absolute() or '..' in path.parts
                    or f.filename in files or (f.external_attr>>16)&0o170000==0o120000):
                raise ValueError('unsafe or duplicate skill member')
            files[f.filename]=z.read(f)
    if 'vps-health/SKILL.md' not in files:raise ValueError('skill entry missing')
    out.mkdir(parents=True,mode=0o700)
    for name,data in files.items():
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    contract={'schema':'g-skills.client-journey.v1','id':uuid.uuid4().hex,'source_commit':release['commit'],
              'archive_sha256':digest(raw),'workspace':'workspace','maximum_duration_seconds':180,
              'files':{name:digest(data) for name,data in files.items()},'created_at':time.time(),
              'native_client_verified':False,'mode':'synthetic-only'}
    private_write(out/'trial.json',contract)
    private_write(out/'PROMPT.md',
        'Read this exact installed entry with the file tool: '+str(out/'vps-health/SKILL.md')+'. '
        'The skill is already located; do not search the whole host. Its CLI is '+str(out/'vps-health/scripts/vps_health.py')+'. '
        'Use the host permissions for that scoped CLI, not an unnecessary directory scan. '
        'This is a synthetic demonstration only. '
        'Create a new private demo workspace at '+str(out/'workspace')+' and start its managed loopback viewer '
        'for at most 180 seconds on an available port. That bounded synthetic setup is authorized for this trial. '
        'Do not collect this host, use provider/email/cloud tools, access credentials, change installed skill files '
        'or bypass a host permission/sandbox restriction. Perform routine steps yourself and verify the actual '
        'process and HTTP result. Report the actual URL and evidence limits, then leave the bounded worker for '
        'a separate-session resume/stop check. If required tools or permissions are unavailable, state BLOCKED; '
        'do not present an unexecuted command list as successful setup. Do not edit trial.json.\n')
    private_write(out/'RESUME.md',
        'Continue the existing synthetic workspace from its HANDOFF.md. Do not create or renew another run. '
        'Verify its current identity, inspect evidence, stop that exact run cooperatively and verify it stopped. '
        'Retain the existing observations. Do not contact services or weaken permissions. If its budget expired, '
        'report that fact instead of inventing an active monitor.\n')
    return {'trial':str(out),'state':'PREPARED_NOT_EXECUTED','native_client_verified':False}


def inspect_contract(root):
    root=Path(root).absolute()
    if root.is_symlink() or (root/'workspace').is_symlink():raise ValueError('trial and workspace must not be symbolic links')
    contract=load(root/'trial.json')
    if (contract.get('schema')!='g-skills.client-journey.v1' or contract.get('workspace')!='workspace'
            or not re.fullmatch('[a-f0-9]{32}',str(contract.get('id','')))
            or contract.get('maximum_duration_seconds')!=180):raise ValueError('invalid trial boundary')
    expected=contract.get('files')
    if not isinstance(expected,dict) or not 1<=len(expected)<=250:raise ValueError('invalid sealed source inventory')
    for name,sha in expected.items():
        rel=PurePosixPath(name)
        if not name.startswith('vps-health/') or rel.is_absolute() or '..' in rel.parts:raise ValueError('invalid sealed source path')
        path=root/name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes())!=sha:raise ValueError('installed skill changed after preparation')
    for path in (root/'vps-health').rglob('*'):
        if path.is_symlink():raise ValueError('symbolic link in installed fixture')
        if path.is_file() and '__pycache__' not in path.parts and path.relative_to(root).as_posix() not in expected:
            raise ValueError('unrecorded file in installed fixture')
    return root,contract


def run_cli(root,command):
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP')}
    env['PYTHONNOUSERSITE']='1'
    entry=root/'vps-health/scripts/vps_health.py'
    r=subprocess.run([sys.executable,str(entry),command,'--workspace',str(root/'workspace')],
                     cwd=root,env=env,text=True,capture_output=True,timeout=15)
    if r.returncode:raise ValueError('installed '+command+' did not complete')
    return json.loads(r.stdout)


def evidence(root):
    path=root/'workspace/history.sqlite3'
    if path.is_symlink() or not path.is_file():raise ValueError('retained database is missing')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2) as db:
        hashes=[r[0] for r in db.execute('SELECT hash FROM captures ORDER BY hash LIMIT 101')]
        if not hashes or len(hashes)>100:raise ValueError('unexpected synthetic capture count')
        count=db.execute('SELECT COUNT(*) FROM points').fetchone()[0]
    return {'capture_hashes':hashes,'point_count':count}


def check(root,phase,baseline=None):
    root,contract=inspect_contract(root)
    cfg=load(root/'workspace/workspace.json')
    if cfg.get('mode')!='demo' or sorted(a['id'] for a in cfg['assets'])!=EXPECTED or cfg.get('provider_contact')!='manual_only':
        raise ValueError('the authorized synthetic scope changed')
    state=run_cli(root,'agent-status');view=run_cli(root,'dashboard');stored=evidence(root)
    if not view.get('synthetic') or view.get('expected_assets')!=3:raise ValueError('actual viewer evidence scope differs')
    if not (root/'workspace/HANDOFF.md').is_file():raise ValueError('agent handoff missing')
    if phase=='running':
        if state.get('state')!='RUNNING' or state.get('process_verified') is not True:raise ValueError('owned runtime is not running')
        url=urllib.parse.urlsplit(state.get('dashboard_url',''))
        if url.scheme!='http' or url.hostname!='127.0.0.1' or not url.port or url.path!='/' or url.query or url.fragment or url.username:
            raise ValueError('dashboard must be the exact loopback runtime')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(state['dashboard_url']+'api/status',timeout=3) as response:
            data=response.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES:raise ValueError('unexpected live payload size')
        live=json.loads(data)
        if not live.get('synthetic') or live.get('agent_runtime',{}).get('run_id')!=state['run_id']:
            raise ValueError('HTTP and process receipts identify different runs')
        launch=load(root/'workspace/.agent/launch.json')
        if not 1<=launch['intent']['duration_seconds']<=contract['maximum_duration_seconds']:
            raise ValueError('worker exceeded the approved trial budget')
    elif phase=='stopped':
        prior=load(baseline) if baseline is not None else None
        if not prior or prior.get('phase')!='running' or prior.get('trial_id')!=contract['id']:
            raise ValueError('stop proof needs the matching prior running receipt')
        if state.get('process_verified') or state.get('state') not in ('STOPPED','COMPLETED'):
            raise ValueError('stop is not confirmed')
        if state.get('run_id')!=prior['run_id'] or stored!=prior['evidence']:
            raise ValueError('run identity or retained observations changed during continuation')
    else:raise ValueError('phase must be running or stopped')
    return {'schema':'g-skills.client-journey-result.v1','state':'ARTIFACT_VERIFIED','phase':phase,
            'trial_id':contract['id'],'run_id':state['run_id'],'source_commit':contract['source_commit'],
            'archive_sha256':contract['archive_sha256'],'checked_at':time.time(),'evidence':stored,
            'native_client_verified':False,'semantic_review_required':True,
            'client_execution_note':'Pair this artifact proof with the actual authorized client trace. A reported client name or success message is not execution evidence.',
            'publication_authorized':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('prepare');a.add_argument('--archive',required=True,type=Path);a.add_argument('--manifest',required=True,type=Path);a.add_argument('--out',required=True,type=Path)
    a=sub.add_parser('check');a.add_argument('--trial',required=True,type=Path);a.add_argument('--phase',choices=('running','stopped'),required=True);a.add_argument('--baseline',type=Path);a.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    try:
        if args.cmd=='prepare':result=prepare(args.archive,args.manifest,args.out)
        else:result=check(args.trial,args.phase,args.baseline);private_write(args.out,result)
        print(json.dumps(result,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,subprocess.SubprocessError) as exc:
        print(json.dumps({'state':'NOT_VERIFIED','reason':type(exc).__name__,'message':str(exc),'native_client_verified':False}));return 1

if __name__=='__main__':raise SystemExit(main())
