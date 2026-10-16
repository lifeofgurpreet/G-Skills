#!/usr/bin/env python3
"""Validate portable skill structure, examples, privacy boundaries and tests."""
from pathlib import Path
import ipaddress
import json
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
SKILL=ROOT/'skills/vps-health'


def main():
    study=json.loads((ROOT/'docs/skills/vps-health/improvement-v0.4.0.json').read_text())
    entries=study['additional_jsm_sources']
    assert len(entries)==9 and len({entry['skill'] for entry in entries})==9
    for entry in entries:
        assert re.fullmatch('[0-9a-f]{64}',entry['source_sha256'])
        assert entry['read_scope'] and entry['applied_change']
        target=(ROOT/entry['check']).resolve()
        assert ROOT.resolve() in target.parents and target.is_file(),'unresolved study-to-check mapping'
    study=json.loads((ROOT/'docs/skills/vps-health/improvement-v0.5.0.json').read_text())
    for entry in study['additional_sources']:
        assert re.fullmatch('[0-9a-f]{64}',entry['source_sha256'])
        assert entry['read_scope'] and (ROOT/entry['check']).is_file()
    assert 'PROPOSED_NOT_APPLIED' in (SKILL/'scripts/vps_health.py').read_text()
    assert 'human-decision-only' in (SKILL/'scripts/vps_health.py').read_text()
    subprocess.run([sys.executable,str(SKILL/'tests/test_vps_health.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_workspace.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_workspace_export.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_chart_context.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_time_evidence.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_operations.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_provider_reference.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_support_report.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_support_draft.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_agent_runtime.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_viewer_access.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_private_workspace.py')],check=True)
    subprocess.run([sys.executable,str(SKILL/'tests/test_forensics.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/skills/vps-health/test_vendor.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/skills/vps-health/test_release_package.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/skills/vps-health/test_client_journey.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/skills/vps-health/test_agent_eval.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/skills/vps-health/test_launch_media.py')],check=True)
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
