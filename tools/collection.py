#!/usr/bin/env python3
"""Discover independent skills, check catalog drift, and scaffold draft entries.

Repository maintenance only. Installing one skill does not run this code or
install any other skill's tools. Tests and packages explicitly select their owner.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
NAME=re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
VERSION=re.compile(r'\d+\.\d+\.\d+')


def safe_name(name):
    if not isinstance(name,str) or not NAME.fullmatch(name) or len(name)>64:
        raise ValueError('skill name must be lower-case words separated by hyphens')
    return name


def owned_path(root,relative,owner=None):
    path=PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('repository path must be relative and contained')
    if owner and not path.as_posix().startswith(f'tools/skills/{owner}/'):
        raise ValueError('maintenance hook must belong to the selected skill')
    target=Path(root)/relative
    current=Path(root)
    for part in path.parts:
        current=current/part
        if current.is_symlink():raise ValueError('skill/maintenance symlinks are not accepted')
    if Path(root).resolve() not in target.resolve().parents:
        raise ValueError('path escaped the repository')
    return target


def validate_manifest(doc,name):
    safe_name(name)
    if not isinstance(doc,dict) or doc.get('schema')!='g-skills.skill.v1' or doc.get('name')!=name:
        raise ValueError('skill manifest identity/schema mismatch')
    if not VERSION.fullmatch(str(doc.get('version',''))):raise ValueError('skill version must be semantic x.y.z')
    for key in ('title','summary','category'):
        if not isinstance(doc.get(key),str) or not 1<=len(doc[key])<=1024 or any(ord(c)<32 for c in doc[key]):
            raise ValueError(f'invalid skill {key}')
    if doc.get('status') not in ('draft','ready'):raise ValueError('skill status must be draft or ready')
    if doc.get('entry')!='SKILL.md':raise ValueError('skill entry must be SKILL.md')
    checks=doc.get('checks',{})
    if not isinstance(checks,dict) or set(checks)-{'python','browser','javascript','package'}:
        raise ValueError('unsupported maintenance check contract')
    if 'python' not in checks or 'package' not in checks:raise ValueError('every skill needs its own Python verification and package check')
    for value in checks.values():
        if not isinstance(value,str):raise ValueError('check path must be a string')
    return doc


def discover(root=ROOT):
    root=Path(root);base=root/'skills'
    if not base.is_dir():raise ValueError('skills directory missing')
    rows=[]
    for directory in sorted(base.iterdir()):
        if not directory.is_dir() or directory.name.startswith('.'):continue
        name=safe_name(directory.name)
        manifest=owned_path(root,f'skills/{name}/skill.json')
        doc=validate_manifest(json.loads(manifest.read_text()),name)
        text=owned_path(root,f'skills/{name}/SKILL.md').read_text()
        if not text.startswith('---\n') or '\n---\n' not in text:raise ValueError('missing skill frontmatter')
        front=text.split('\n---\n',1)[0]
        if not re.search(r'^name:\s*'+re.escape(name)+r'\s*$',front,re.M):raise ValueError('entry name differs from directory')
        if len(text.splitlines())>=500:raise ValueError('move long instructions into references')
        for path in doc['checks'].values():
            if not owned_path(root,path,name).is_file():raise ValueError('declared check is missing: '+path)
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if '://' not in target and not target.startswith('#'):
                rel=(PurePosixPath('skills')/name/target.split('#',1)[0]).as_posix()
                if not owned_path(root,rel).is_file():raise ValueError('missing local skill reference: '+target)
        rows.append(doc)
    if not rows:raise ValueError('no skills discovered')
    return rows


def catalog(rows):
    return {'schema':'g-skills.catalog.v1','purpose':'Independent public skills curated by Gurpreet; no collection runtime or shared skill version.',
            'skills':[{**{key:row[key] for key in ('name','title','summary','version','category','status')},
                       'path':'skills/'+row['name'],'entry':'skills/'+row['name']+'/SKILL.md',
                       'release_tag':row['name']+'/v'+row['version']} for row in rows]}


def scaffold(root,name,title):
    """Create a deliberately draft skill. No discovery, installation or publish."""
    name=safe_name(name);root=Path(root)
    if not isinstance(title,str) or not title.strip() or len(title)>100 or '\n' in title:raise ValueError('a short title is required')
    dest=root/'skills'/name;maintenance=root/'tools/skills'/name
    if dest.exists() or maintenance.exists():raise ValueError('skill or maintenance destination already exists; nothing overwritten')
    for path in (root/'skills',root/'tools',root/'tools/skills'):
        if path.is_symlink():raise ValueError('scaffold destination must not be a symlink')
    manifest={'schema':'g-skills.skill.v1','name':name,'title':title,'summary':'Draft: define the useful outcome, authority and acceptance checks before release.',
              'version':'0.1.0','category':'uncategorized','status':'draft','entry':'SKILL.md',
              'checks':{kind:f'tools/skills/{name}/{file}' for kind,file in [('python','validate.py'),('package','package_check.py')]}}
    entry=f'''---
name: {name}
description: Draft skill. Define the trigger, useful output and limits before publishing.
license: MIT
metadata:
  version: "0.1.0"
---

# {title}

This is a draft scaffold, not an implemented capability.

## Agent responsibility

Define the user goal, inputs, authorized tools and work the agent performs. Ask
only for genuinely missing scope, authentication or consequential decisions.

## Workflow and verification

Replace this section with the smallest useful workflow, executable checks and
failure recovery. No side effects are authorized by an example or a placeholder.

## Acceptance

Record supported environments and a real cold-use test. Mark the manifest ready
only after implementation, privacy checks and reviewed release evidence exist.
'''
    test='''from pathlib import Path
import sys
root=Path(__file__).resolve().parents[3]
name=Path(__file__).parent.name
assert (root/'skills'/name/'SKILL.md').is_file()
print('Draft structure present; functional acceptance is not implemented.')
'''
    package='''from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--skill-dir',required=True,type=Path);a=p.parse_args()
assert (a.skill_dir/'SKILL.md').is_file()
print('Draft entry exists. Replace with actual exported-folder acceptance.')
'''
    dest.mkdir(parents=True);maintenance.mkdir(parents=True)
    (dest/'SKILL.md').write_text(entry);(dest/'skill.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (maintenance/'validate.py').write_text(test);(maintenance/'package_check.py').write_text(package)
    return {'name':name,'state':'draft','path':str(dest),'automatic_publish':False,
            'next':'Implement the skill-specific acceptance, then explicitly review status=ready. Draft packages are not releasable.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true')
    p.add_argument('--matrix',choices=('python','browser','javascript'))
    p.add_argument('--new');p.add_argument('--title')
    a=p.parse_args(argv)
    try:
        if a.new:print(json.dumps(scaffold(ROOT,a.new,a.title),indent=2));return 0
        rows=discover()
        if a.matrix:
            print(json.dumps({'skill':[r['name'] for r in rows if a.matrix in r['checks']]}));return 0
        text=json.dumps(catalog(rows),sort_keys=True,indent=2)+'\n';path=ROOT/'catalog.json'
        if a.write:path.write_text(text)
        elif not path.exists() or path.read_text()!=text:raise ValueError('catalog drift; run tools/collection.py --write')
        print(f'PASS: {len(rows)} independently versioned skills and catalog match');return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('FAIL: collection: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
