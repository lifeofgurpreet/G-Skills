#!/usr/bin/env python3
"""Validate portable skill structure, examples, privacy boundaries and tests."""
from pathlib import Path
import ipaddress
import json
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/vps-health'


def main():
    text=(SKILL/'SKILL.md').read_text()
    assert text.startswith('---\n') and text.count('\n---\n')>=1,'missing frontmatter'
    front=text.split('\n---\n',1)[0]
    assert re.search(r'^name: vps-health$',front,re.M),'skill name/path mismatch'
    description=re.search(r'^description: (.+)$',front,re.M).group(1)
    assert 1<=len(description)<=1024,'description length'
    assert len(text.splitlines())<500,'move long references out of the skill entry point'
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if '://' not in target:
            assert (SKILL/target).is_file(),'missing skill reference: '+target
    forbidden=('-----BEGIN PRIVATE KEY-----',)
    for p in ROOT.rglob('*'):
        if not p.is_file() or '.git' in p.parts or '__pycache__' in p.parts:continue
        assert not p.is_symlink(),'symlink not allowed in public package: '+str(p)
        if p.suffix in ('.pyc','.gz','.zip'):raise AssertionError('unexpected generated binary: '+str(p))
        content=p.read_text()
        if p.name!='validate.py':
            for value in forbidden:assert value not in content,'private key material: '+str(p)
        if p.suffix=='.json':json.loads(content)
        for address in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',content):
            try:ip=ipaddress.ip_address(address)
            except ValueError:continue
            safe=ip.is_loopback or any(ip in ipaddress.ip_network(n) for n in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24'))
            assert safe,'non-example IP address in public source: '+str(p)
    assert 'PROPOSED_NOT_APPLIED' in (SKILL/'scripts/vps_health.py').read_text()
    assert 'human-decision-only' in (SKILL/'scripts/vps_health.py').read_text()
    subprocess.run([sys.executable,str(ROOT/'tools/test_skill_study.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_vps_health.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_workspace.py')],check=True)
    with tempfile.TemporaryDirectory() as directory:
        # Test the actual exported folder, not only imports from this repository.
        dest=Path(directory)/'standalone'
        import shutil
        shutil.copytree(SKILL,dest,ignore=shutil.ignore_patterns('__pycache__'))
        subprocess.run([sys.executable,str(dest/'scripts/vps_health.py'),'demo','--out',str(Path(directory)/'demo')],stdout=subprocess.DEVNULL,check=True)
        subprocess.run([sys.executable,str(dest/'scripts/vps_health.py'),'verify',str(Path(directory)/'demo')],check=True)
        entry=str(dest/'scripts/vps_health.py');workspace=Path(directory)/'workspace'
        subprocess.run([sys.executable,entry,'bootstrap','--workspace',str(workspace),'--mode','demo'],stdout=subprocess.DEVNULL,check=True)
        status=json.loads(subprocess.check_output([sys.executable,entry,'dashboard','--workspace',str(workspace)],text=True))
        assert status['synthetic'] and status['expected_assets']==3
        assert status['assets'][2]['stale'], 'offline subject must not look fresh'
        subprocess.run([sys.executable,entry,'export','--workspace',str(workspace),'--out',str(Path(directory)/'export')],stdout=subprocess.DEVNULL,check=True)
        subprocess.run([sys.executable,entry,'learn',str(workspace),'--out',str(Path(directory)/'proposal.json')],stdout=subprocess.DEVNULL,check=True)
        proposal=json.loads((Path(directory)/'proposal.json').read_text())
        assert proposal['state']=='PROPOSED_NOT_APPLIED' and proposal['can_publish'] is False
        subprocess.run([sys.executable,entry,'draft-email','--workspace',str(workspace),'--node','example-contended','--impact','synthetic build slowdown','--approve-draft','--example','--out',str(Path(directory)/'example.txt')],stdout=subprocess.DEVNULL,check=True)
        assert (Path(directory)/'example.txt').read_text().startswith('EXAMPLE ONLY')

    print('PASS: skill structure, local references, privacy examples, offline tests, bounded loopback contracts and standalone CLI bootstrap/replay')
    return 0


if __name__=='__main__':raise SystemExit(main())
