#!/usr/bin/env python3
"""Collection-wide checks plus explicitly owned per-skill acceptance."""
from pathlib import Path
import argparse
import ipaddress
import json
import re
import subprocess
import sys
import collection

ROOT=Path(__file__).resolve().parents[1]


def privacy(root=ROOT):
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if any(p in ('.git','__pycache__') for p in relative.parts) or not path.is_file():continue
        if path.is_symlink():raise ValueError('symlink is not portable: '+str(relative))
        if path.suffix in ('.db','.sqlite3','.gz','.zip','.pyc'):raise ValueError('generated/private artifact in source: '+str(relative))
        if path.suffix in ('.png','.jpg','.webp','.ico'):continue
        text=path.read_text()
        if path.name!='validate.py' and '-----BEGIN PRIVATE KEY-----' in text:raise ValueError('private key material in source')
        if path.suffix=='.json':json.loads(text)
        for raw in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',text):
            try:ip=ipaddress.ip_address(raw)
            except ValueError:continue
            if not ip.is_loopback and not any(ip in ipaddress.ip_network(n) for n in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24')):
                raise ValueError('non-example network address in public source: '+str(relative))


def selected(rows,name):
    if name is None:return rows
    result=[row for row in rows if row['name']==name]
    if not result:raise ValueError('unknown skill: '+name)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skill');p.add_argument('--structure-only',action='store_true');p.add_argument('--browser',action='store_true');p.add_argument('--javascript',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args(argv)
    try:
        rows=selected(collection.discover(),a.skill)
        if a.browser or a.javascript:
            kind='browser' if a.browser else 'javascript'
            if len(rows)!=1 or kind not in rows[0]['checks']:raise ValueError('select exactly one skill that owns this check')
            path=collection.owned_path(ROOT,rows[0]['checks'][kind],rows[0]['name'])
            if a.browser and 'javascript' in rows[0]['checks']:
                subprocess.run(['node','--test',str(collection.owned_path(ROOT,rows[0]['checks']['javascript'],rows[0]['name']))],check=True)
            command=[sys.executable,str(path)] if a.browser else ['node','--test',str(path)]
            if a.out and a.browser:command+=['--out',str(a.out)]
            subprocess.run(command,check=True);return 0
        privacy()
        subprocess.run([sys.executable,str(ROOT/'tools/collection.py'),'--check'],check=True)
        subprocess.run([sys.executable,str(ROOT/'tools/roadmap.py'),'--check'],check=True)
        for name in ('test_skill_study.py','test_collection.py','test_package_release.py','test_roadmap.py','test_install_skill.py'):
            subprocess.run([sys.executable,str(ROOT/'tools'/name)],check=True)
        if not a.structure_only:
            for row in rows:
                path=collection.owned_path(ROOT,row['checks']['python'],row['name'])
                subprocess.run([sys.executable,str(path)],check=True)
        print('PASS: collection boundaries and '+(', '.join(row['name'] for row in rows))+' selected acceptance');return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
