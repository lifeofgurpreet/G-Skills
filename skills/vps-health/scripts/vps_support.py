#!/usr/bin/env python3
"""Create a private software-support draft from a bounded issue description.

No sender, connector discovery, account lookup or new measurements. This reuses
support_report's restricted diagnostics; supplied issue prose still needs review.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import unicodedata
import vps_health as core
import vps_ops as ops
import vps_workspace as ws

SCHEMA='g-skills.support-request.v1'


def text(value,name,maximum,multiline=False):
    if (not isinstance(value,str) or not value.strip() or len(value)>maximum
            or any(unicodedata.category(c).startswith('C') and not (multiline and c=='\n') for c in value)):
        raise core.InvalidEvidence(name+' must be bounded plain text; control characters are refused')
    return value.strip()


def validate(request):
    required={'schema','summary','observed','expected'}
    if (not isinstance(request,dict) or request.get('schema')!=SCHEMA or not required<=request.keys()
            or set(request)-required-{'question','steps'}):
        raise core.InvalidEvidence('use the support-request fields only; no recipients, attachments or send instructions')
    result={'schema':SCHEMA,'summary':text(request['summary'],'summary',120),
            'observed':text(request['observed'],'observed',2000,True),
            'expected':text(request['expected'],'expected',700,True),
            'question':text(request.get('question','Which diagnostic or recovery step should I try next?'),'question',300)}
    steps=request.get('steps',[])
    if not isinstance(steps,list) or len(steps)>5:raise core.InvalidEvidence('use at most five actual reproduction steps')
    result['steps']=[text(step,'reproduction step',300) for step in steps]
    return result


def quoted(value):
    return '\n'.join('> '+line for line in value.splitlines())


def diagnostics(report):
    """Choose bounded display fields, not arbitrary values from a future report."""
    if not isinstance(report,dict) or report.get('schema')!='g-skills.support-report.v1':
        raise core.InvalidEvidence('expected the existing minimal support-report contract')
    version=report.get('version');version=version if isinstance(version,str) and re.fullmatch(r'\d+\.\d+\.\d+',version) else 'UNKNOWN'
    python=report.get('python');python=python if isinstance(python,str) and re.fullmatch(r'\d+\.\d+',python) else 'UNKNOWN'
    platform=report.get('platform');platform=platform if isinstance(platform,str) and platform in ('linux','macos','windows','other') else 'UNKNOWN'
    state=report.get('state');state=state if isinstance(state,str) and state in ('SUMMARY_AVAILABLE','PARTIAL') else 'PARTIAL'
    workspace=report.get('workspace',{})
    if not isinstance(workspace,dict):workspace={}
    states={'NOT_REQUESTED','UNAVAILABLE','PARTIAL','READABLE','VERIFIED','NOT_CHECKED'}
    safe=lambda value:value if isinstance(value,str) and value in states else 'UNKNOWN'
    mode=workspace.get('mode');mode=mode if isinstance(mode,str) and mode in ('demo','local','prometheus') else 'NOT_RECORDED'
    lines=[f'VPS Health {version}; Python {python}; platform {platform}.',
           'Diagnostic summary: '+state+'.',
           'workspace: '+safe(workspace.get('state'))+'; configuration: '+safe(workspace.get('configuration','NOT_CHECKED'))+
           '; mode: '+mode+'; database: '+safe(workspace.get('database','NOT_CHECKED'))+'; chart_assets: '+safe(workspace.get('chart_assets','NOT_CHECKED'))+'.']
    counts=[]
    for field,label in [('expected_subjects','configured subjects'),('capture_batches','capture batches'),('retained_points','retained points')]:
        value=workspace.get(field)
        if type(value) is int and 0<=value<=10**12:counts.append(str(value)+' '+label)
    if counts:lines.append('; '.join(counts)+'.')
    return '\n'.join(lines),state,version


def compose(request,report):
    issue=validate(request);details,state,version=diagnostics(report)
    steps='\n\nObserved steps:\n'+'\n'.join(f'{index}. {step}' for index,step in enumerate(issue['steps'],1)) if issue['steps'] else ''
    draft=f'''LOCAL SOFTWARE SUPPORT DRAFT — NOT SENT
Recipient: [VPS Health skill maintainer; confirm the actual support channel]
Subject: VPS Health — {issue['summary']}

Hello,

Observed behavior (user-provided text):
{quoted(issue['observed'])}

Expected behavior (user-provided text):
{quoted(issue['expected'])}{steps}

Minimal software diagnostics:
{details}

Question:
{quoted(issue['question'])}

This is a software-support question, not a claim against a VPS provider.
No raw observations, environment, endpoint details or attachments were included automatically.
Please review the issue text for private details before sharing. It has not been automatically sanitized.
No message was sent, no account connected, and no server change or downtime is authorized.
'''
    return draft,{'diagnostics_state':state,'version':version,'words':len(draft.split())}


def create(args):
    if getattr(args,'approve_draft',False) is not True:
        raise core.InvalidEvidence('support-draft needs an explicit local drafting request via --approve-draft; nothing will be sent')
    out=ws.public_path(args.out)
    if out.exists() or out.is_symlink():raise FileExistsError('draft output exists; choose a new private file')
    root=ws.public_path(args.workspace) if args.workspace is not None else None
    if root is not None and (out==root or root in out.parents):
        raise core.InvalidEvidence('support draft output must be outside the observation workspace')
    request=validate(ws.read_private_json(Path(args.issue),max_bytes=16384))
    draft,metadata=compose(request,ops.support_report(root))
    raw=draft.encode('utf-8')
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as handle:
        handle.write(raw);handle.flush();os.fsync(handle.fileno())
    return {'schema':'g-skills.support-draft-result.v1','state':'LOCAL_DRAFT','draft':str(out),
            'sha256':hashlib.sha256(raw).hexdigest(),'draft_created':True,'recipient_kind':'skill-maintainer',
            'sent':False,'approved_to_send':False,'connector_needed_for_local_draft':False,
            'attachments':[],'free_text_requires_review':True,'new_measurements':False,
            'provider_cause_proven':False,**metadata,
            'next_action':'Review the actual text. Only a separate explicit request may authorize a mailbox or support-portal action through the host agent.'}


def register(sub):
    p=sub.add_parser('support-draft',help='Create a local software-support draft; no mailbox, provider contact or new collection')
    p.add_argument('--issue',required=True,type=Path,help='Private support-request JSON prepared by the agent from the actual user issue')
    p.add_argument('--out',required=True,type=Path,help='New private text file outside the workspace')
    p.add_argument('--workspace',type=Path,help='Optional existing workspace; missing or broken inputs stay explicit')
    p.add_argument('--approve-draft',action='store_true')
