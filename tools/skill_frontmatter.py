#!/usr/bin/env python3
"""Validate actual YAML skill discovery metadata. Development-only dependency.

A script suite passing does not establish that a client can parse SKILL.md.
This check validates the shared artifact boundary without adding a user runtime.
"""
from pathlib import Path
import json
import re
import sys
import yaml


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def mapping(loader,node,deep=False):
    result={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        if not isinstance(key,str) or key in result:raise ValueError('frontmatter keys must be unique strings')
        result[key]=loader.construct_object(value_node,deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
ALLOWED={'name','description','license','compatibility','allowed-tools','metadata'}


def parse(text):
    if not isinstance(text,str) or len(text)>128000:raise ValueError('skill entry is missing or too large')
    match=re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)',text,re.S)
    if not match:raise ValueError('skill needs a YAML frontmatter block at the beginning')
    header=match.group(1)
    if len(header)>16384:raise ValueError('frontmatter is not a small discovery record')
    try:
        if any(isinstance(token,(yaml.tokens.AliasToken,yaml.tokens.AnchorToken,yaml.tokens.TagToken)) for token in yaml.scan(header)):
            raise ValueError('discovery metadata does not need aliases, anchors or custom tags')
        data=yaml.load(header,Loader=UniqueSafeLoader)
    except yaml.YAMLError as exc:raise ValueError('invalid skill frontmatter YAML: '+str(exc)) from exc
    if not isinstance(data,dict) or set(data)-ALLOWED:raise ValueError('unknown or invalid discovery metadata')
    name=data.get('name');description=data.get('description')
    if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64:
        raise ValueError('skill name must be a bounded kebab-case string')
    if not isinstance(description,str) or not description.strip() or len(description)>1024 or any(x in description for x in '<>'):
        raise ValueError('description must be a nonempty bounded discovery string')
    compatibility=data.get('compatibility','')
    if not isinstance(compatibility,str) or len(compatibility)>500:raise ValueError('compatibility must be a short string')
    if 'metadata' in data and not isinstance(data['metadata'],dict):raise ValueError('metadata must be a mapping')
    return data


def validate_tree(root):
    root=Path(root);results=[]
    for path in sorted((root/'skills').glob('*/skill.json')):
        meta=json.loads(path.read_text());header=parse(path.with_name('SKILL.md').read_text())
        if header['name']!=meta['name']:raise ValueError('skill folder and discovery name disagree: '+str(path.parent))
        if header.get('metadata',{}).get('version')!=meta['version']:raise ValueError('discovery and manifest versions differ: '+meta['name'])
        results.append(header['name'])
    if not results:raise ValueError('no installed skill manifests to validate')
    return results


if __name__=='__main__':
    try:print('PASS: real YAML discovery metadata for '+', '.join(validate_tree(Path(__file__).resolve().parents[1])))
    except (OSError,ValueError,KeyError) as exc:print('FAIL: '+str(exc),file=sys.stderr);raise SystemExit(1)
