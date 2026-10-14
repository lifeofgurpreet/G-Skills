#!/usr/bin/env python3
"""Render separate collection and skill roadmaps from one scoped native graph."""
from pathlib import Path
import argparse
import json
import re
import sys
import collection

ROOT=Path(__file__).resolve().parents[1]


def scope(row):
    labels=[value for value in row.get('labels',[]) if value=='scope:collection' or value.startswith('skill:')]
    if len(labels)!=1:raise ValueError('each task needs exactly one collection/skill scope: '+row['id'])
    return labels[0]


def load(root=ROOT):
    rows=[json.loads(line) for line in (root/'.beads/issues.jsonl').read_text().splitlines() if line.strip()]
    ids={row['id']:row for row in rows};names={r['name'] for r in collection.discover(root)}
    if len(ids)!=len(rows):raise ValueError('duplicate task IDs')
    for row in rows:
        if not re.fullmatch(r'gs-[a-z0-9]+(?:\.\d+)?',row['id']):raise ValueError('invalid task ID')
        owner=scope(row)
        if owner!='scope:collection' and owner[6:] not in names:raise ValueError('unknown skill scope')
        if row['status'] not in ('open','in_progress','blocked','deferred','closed'):raise ValueError('invalid task state')
        if not row.get('description') or not row.get('acceptance_criteria'):raise ValueError('task needs description and acceptance')
        if row['status']=='closed' and not row.get('close_reason'):raise ValueError('closed task needs evidence')
        for dep in row.get('dependencies',[]):
            if dep['depends_on_id'] not in ids:raise ValueError('dangling dependency')
            if dep['type']=='parent-child' and scope(ids[dep['depends_on_id']])!=owner:raise ValueError('parent scope differs from child')
            if row['status']=='closed' and dep['type']=='blocks' and ids[dep['depends_on_id']]['status']!='closed':raise ValueError('closed task has unfinished prerequisite')
    def visit(key,active,done):
        if key in active:raise ValueError('cyclic dependency graph')
        if key in done:return
        active.add(key)
        for dep in ids[key].get('dependencies',[]):
            if dep['type'] in ('blocks','parent-child'):visit(dep['depends_on_id'],active,done)
        active.remove(key);done.add(key)
    done=set()
    for key in ids:visit(key,set(),done)
    return sorted(rows,key=lambda r:(r['issue_type']!='epic',r['priority'],r['id']))


def table(rows):
    lines=['| Task | State | Priority | Owner role | Target | Blocking prerequisites |','|---|---|---:|---|---|---|']
    for r in rows:
        deps=[d['depends_on_id'] for d in r.get('dependencies',[]) if d['type']=='blocks']
        owner=str(r.get('assignee') or 'Unassigned').replace('|','/').replace('\n',' ')
        due=str(r.get('due_at') or '')[:10] or '—'
        lines.append(f"| `{r['id']}` {r['title'].replace('|','/')} | {r['status']} | {r['priority']} | {owner} | {due} | {', '.join('`'+d+'`' for d in deps) or '—'} |")
    return lines


def details(rows):
    lines=[]
    for r in rows:
        lines += [f"### {r['id']} — {r['title']}",'',r['description'],'','**Acceptance:** '+r['acceptance_criteria'],'']
        if r.get('close_reason'):lines+=['**Receipt:** '+r['close_reason'],'']
    return lines


def render(root=ROOT):
    rows=load(root);skills=collection.discover(root)
    shared=[r for r in rows if scope(r)=='scope:collection']
    lines=['# G-Skills collection roadmap','','This repository hosts independent public skills. Root work is catalog/distribution/quality infrastructure, not the roadmap of the first skill. Canonical task state is `.beads/issues.jsonl`; regenerate with `python3 tools/roadmap.py --write`.','','[Three-month execution plan and sharing gates](docs/plans/2026-10-14-quarter.md). Owners and targets below come from Beads; a target date is not a scheduled job or release authorization.','','## Collection infrastructure','']+table(shared)+['','## Skill programmes','']
    for skill in skills:
        own=[r for r in rows if scope(r)=='skill:'+skill['name']]
        opened=sum(r['status']!='closed' for r in own if r['issue_type']!='epic')
        lines.append(f"- [{skill['title']}](docs/skills/{skill['name']}/ROADMAP.md): {opened} open implementation/acceptance tasks; independent version {skill['version']}.")
    lines+=['','## Collection acceptance','']+details(shared)+['A second unrelated skill must be discoverable, independently validated and packaged without inheriting another skill\'s browser, runtime or safety policy. Draft scaffolds are not completed products.','','Beads is a development tool. Users of an installed skill need only that skill\'s declared requirements. No private user workspace becomes part of this graph.','']
    outputs={root/'ROADMAP.md':'\n'.join(lines)}
    for skill in skills:
        name=skill['name'];own=[r for r in rows if scope(r)=='skill:'+name]
        body=[f'# {skill["title"]} roadmap','','This is one skill within G-Skills. Its work does not define the whole collection. State is generated from the shared native graph using the `skill:'+name+'` label.','','[Quarter plan and preview gates](../../plans/2026-10-14-quarter.md). This skill does not need every optional feature finished before a supported, evidence-backed preview.','','## Task graph','']+table(own)+['','```mermaid','flowchart LR']
        for r in own:
            ident=r['id'].replace('-','_').replace('.','_');body.append(f'  {ident}["{r["id"]}: {r["status"]}"]')
            for d in r.get('dependencies',[]):
                if d['type']=='blocks':body.append('  '+d['depends_on_id'].replace('-','_').replace('.','_')+' --> '+ident)
        body+=['```','','## Acceptance and evidence','']+details(own)+['Read the owning skill and current task before acting. Source tests, a running process, client integration and sustained real-world evidence are separate gates. Do not close the programme merely because the source exists.','']
        outputs[root/'docs/skills'/name/'ROADMAP.md']='\n'.join(body)
    return outputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
    try:
        outputs=render()
        for path,text in outputs.items():
            if a.write:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            elif not path.exists() or path.read_text()!=text:raise ValueError('roadmap drift: '+str(path.relative_to(ROOT)))
        print(f'PASS: scoped native graph and {len(outputs)} roadmaps match');return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:print('FAIL: roadmap: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
