#!/usr/bin/env python3
"""VPS Health package acceptance; never imposed on unrelated skills."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tempfile

def validate_files(files):
    required={'SKILL.md','scripts/vps_health.py','scripts/vps_workspace.py','assets/chart-adapter.js',
              'assets/workspace-dashboard.html','assets/view-model.js','assets/workbench.js','references/dashboard.md','assets/vendor/uplot/manifest.json','assets/vendor/uplot/LICENSE','LICENSE',
              'scripts/vps_ops.py','assets/operator.js','assets/operator.css','assets/provider-catalog.json',
              'references/first-hour.md','references/operator-playbook.md','references/support.md','references/workspace-recovery.md','tests/test_private_workspace.py',
              'scripts/vps_agent.py','scripts/vps_forensics.py','references/forensics.md','references/agent-workflow.md','references/agent-connectors.md'}
    if not required<=set(files):raise ValueError('installable skill is missing required runtime/license files')
    if any(name.startswith(('skills/','.github/','tools/')) for name in files):
        raise ValueError('repository content incorrectly nested inside the skill ZIP')
    meta=json.loads(files['skill.json'])
    for code in ('scripts/vps_health.py','scripts/vps_workspace.py'):
        if ("VERSION = '"+meta['version']+"'") not in files[code].decode():raise ValueError('skill manifest/runtime versions differ')
    manifest=json.loads(files['assets/vendor/uplot/manifest.json'])
    for name,data in manifest['files'].items():
        raw=files['assets/vendor/uplot/'+name]
        if hashlib.sha256(raw).hexdigest()!=data['sha256'] or len(raw)!=data['bytes']:
            raise ValueError('vendored artifact does not match reviewed manifest')



def cold_check(target):
    with tempfile.TemporaryDirectory() as temp:
        entry=str(target/'scripts/vps_health.py');workspace=Path(temp)/'workspace'
        subprocess.run([sys.executable,entry,'bootstrap','--mode','demo','--workspace',str(workspace)],check=True,stdout=subprocess.DEVNULL,timeout=60)
        html=(workspace/'dashboard.html').read_text()
        if 'VpsCharts.mount' not in html or 'var uPlot=' not in html or '/*UPLOT_JS*/' in html:raise ValueError('exported chart runtime missing')
        for control in ('review-dialog','command-dialog','pause-view','VpsView.review','VpsView.commands'):
            if control not in html:raise ValueError('exported workbench control/module missing: '+control)
        if any(marker in html for marker in ('/*WORKBENCH_JS*/','/*VIEW_MODEL*/')):
            raise ValueError('unresolved workbench script in actual archive')
        subprocess.run([sys.executable,entry,'export','--workspace',str(workspace),'--out',str(Path(temp)/'report')],check=True,stdout=subprocess.DEVNULL,timeout=60)
        doctor=subprocess.run([sys.executable,entry,'doctor','--workspace',str(workspace)],capture_output=True,text=True,timeout=30)
        if doctor.returncode!=1 or not json.loads(doctor.stdout)['read_only']:raise ValueError('exported doctor did not preserve diagnosis semantics')
        brief=json.loads(subprocess.check_output([sys.executable,entry,'brief','--workspace',str(workspace)],text=True,timeout=30))
        if len(brief['items'])!=2 or brief['automatic_actions']:raise ValueError('exported brief contract failed')
        subprocess.run([sys.executable,entry,'providers','--provider','aws'],check=True,stdout=subprocess.DEVNULL,timeout=30)
        support=json.loads(subprocess.check_output([sys.executable,entry,'support-report','--workspace',str(workspace)],text=True,timeout=30))
        if support['workspace']['retained_points']!=2288 or support['sent'] or not support['review_before_sharing']:
            raise ValueError('exported minimal support summary contract failed')
        if any(v in json.dumps(support) for v in ('example-stable','example-contended',str(workspace))):
            raise ValueError('private context entered exported support summary')

        if sys.platform=='linux':
            options=['--workspace',str(workspace),'--mode','auto','--duration-seconds','10']
            plan=json.loads(subprocess.check_output([sys.executable,entry,'agent-plan',*options],text=True,timeout=20))
            runtime=json.loads(subprocess.check_output([sys.executable,entry,'agent-start',*options,'--approve-plan',plan['plan_sha256']],text=True,timeout=15))
            try:
                if runtime['state']!='RUNNING' or not runtime['process_verified']:raise ValueError('exported agent runtime not verified')
                current=json.loads(subprocess.check_output([sys.executable,entry,'agent-status','--workspace',str(workspace)],text=True,timeout=15))
                if current['run_id']!=runtime['run_id']:raise ValueError('exported handoff lost owned identity')
                verified=json.loads(subprocess.check_output([sys.executable,entry,'agent-verify','--workspace',str(workspace)],text=True,timeout=15))
                if verified['state']!='VERIFIED' or not verified['http_verified']:raise ValueError('exported viewer readback not verified')
            finally:
                stop=subprocess.run([sys.executable,entry,'agent-stop','--workspace',str(workspace),'--run-id',runtime['run_id']],capture_output=True,text=True,timeout=20)
                if stop.returncode or json.loads(stop.stdout)['state']!='STOPPED':raise ValueError('exported runtime stop not verified')

    if sys.platform=='linux':
        result=subprocess.run([sys.executable,str(target/'tests/test_private_workspace.py'),
            'InitializationTest.test_process_death_mid_initialization_allows_safe_new_attempt',
            'RuntimeBoundaryTest.test_agent_retries_the_original_approved_setup_after_interrupted_render'],
            capture_output=True,text=True,timeout=90)
        if result.returncode:
            raise ValueError('extracted initialization/agent recovery check failed: '+result.stderr[-3000:])

def main():
    p=argparse.ArgumentParser();p.add_argument('--skill-dir',required=True,type=Path);a=p.parse_args()
    files={f.relative_to(a.skill_dir).as_posix():f.read_bytes() for f in a.skill_dir.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    validate_files(files);cold_check(a.skill_dir)
    print('PASS: isolated VPS Health package including owned stop and interrupted initialization recovery')
if __name__=='__main__':main()
