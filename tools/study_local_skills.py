#!/usr/bin/env python3
"""Index an explicitly supplied local skill library into a PRIVATE study plan.

Offline only. Does not install, invoke or copy skill bodies. INDEXED is not READ,
APPLIED or VERIFIED. The maintainer must make those transitions with evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=512*1024
MAX_SKILLS=1000
NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z')


def inspect(root: Path, terms: set[str]) -> list[dict]:
    root=root.expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('skill root must be a directory')
    paths=sorted(root.glob('*/SKILL.md'))
    if len(paths)>MAX_SKILLS:raise ValueError('too many skill entries; choose a narrower root')
    rows=[]
    for path in paths:
        if not NAME.fullmatch(path.parent.name):continue
        with path.open('rb') as handle:raw=handle.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('skill entry exceeds 512 KiB; inspect it separately')
        text=raw.decode('utf-8')
        if not text.startswith('---\n') or '\n---' not in text[4:]:continue
        metadata=text.split('\n---',1)[0].lower()
        matched=sorted(t for t in terms if t in metadata or t in path.parent.name.lower())
        rows.append({'name':path.parent.name,'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),
                     'lines':len(text.splitlines()),'matched_terms':matched,'state':'INDEXED_NOT_READ'})
    return rows


def plan(roots: list[Path], query: str, selected: list[str], limit: int = 10) -> dict:
    if not 1<=limit<=30:raise ValueError('limit must be 1-30')
    if not isinstance(query,str) or len(query)>500:raise ValueError('query must be at most 500 characters')
    if any(not NAME.fullmatch(n) for n in selected):raise ValueError('invalid selected skill name')
    terms=set(re.findall(r'[a-z0-9-]{3,}',query.lower()))
    rows=[]
    for root in roots:rows.extend(inspect(root,terms))
    # Multiple installations remain visible; different editions must not be
    # silently collapsed into whichever directory happened to be searched first.
    present={r['name'] for r in rows}
    if set(selected)-present:raise ValueError('selected skills not in the supplied library: '+', '.join(sorted(set(selected)-present)))
    candidates=sorted(rows,key=lambda r:(r['name'] not in selected,-len(r['matched_terms']),r['name'],r['path']))
    candidates=[r for r in candidates if r['name'] in selected or r['matched_terms']][:limit]
    return {'schema':'g-skills.study-plan.v1','state':'INDEXED_NOT_APPLIED','network_requests':0,
            'roots':[str(p.expanduser().resolve()) for p in roots],'entries_indexed':len(rows),
            'query':query,'candidates':candidates,'private':True,
            'next_steps':['Read the selected instructions and relevant references locally.',
                          'Record applicability, rejected assumptions and one concrete code/test decision.',
                          'Reproduce the baseline, implement, then verify the actual user path.',
                          'Publish only original changes and non-sensitive verification; never the source library.'],
            'claims_not_made':['all skills read','independent reviewers ran','skill applied','design approved'],
            'apply_automatically':False,'can_publish':False}


def write_private(path: Path, value: dict) -> None:
    path=path.expanduser().absolute()
    parent=path.parent.resolve(strict=True)
    # A skill library inventory reveals local paths and installed subscriptions.
    # Keep it out of any source repository, not only this package.
    if any((part/'.git').exists() for part in (parent,*parent.parents)) or ROOT==parent or ROOT in parent.parents:
        raise ValueError('choose an existing private output directory outside Git repositories')
    if path.is_symlink():raise ValueError('output cannot be a symbolic link')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(parent/path.name,flags,0o600)
    with os.fdopen(fd,'w') as handle:json.dump(value,handle,indent=2);handle.write('\n')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,action='append',required=True,help='Approved local parent of skill folders; repeat for multiple libraries')
    parser.add_argument('--query',default='usability verification')
    parser.add_argument('--select',action='append',default=[],help='Explicit skill name to prioritize, not a claim it was read')
    parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--out',required=True,type=Path,help='New JSON file in an existing private directory outside Git')
    args=parser.parse_args(argv)
    try:
        if args.out.exists():raise ValueError('output already exists; preserve it and choose a new study plan')
        value=plan(args.root,args.query,args.select,args.limit);write_private(args.out,value)
        print(json.dumps({'state':value['state'],'entries_indexed':value['entries_indexed'],'selected_candidates':len(value['candidates']),'private_plan':str(args.out)}))
        return 0
    except (OSError,ValueError,UnicodeError) as exc:
        print('ERROR: '+str(exc)[:300],file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
