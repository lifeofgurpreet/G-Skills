#!/usr/bin/env python3
"""VPS Health package acceptance; never imposed on unrelated skills."""
from pathlib import Path
import argparse,hashlib,json,posixpath,re,subprocess,sys,tempfile
from urllib.parse import unquote,urlsplit

def validate_files(files):
    required={'SKILL.md','scripts/vps_health.py','scripts/vps_workspace.py','assets/chart-adapter.js',
              'assets/workspace-dashboard.html','assets/view-model.js','assets/workbench.js','references/dashboard.md','references/providers.md','tests/test_provider_reference.py','assets/vendor/uplot/manifest.json','assets/vendor/uplot/LICENSE','LICENSE',
              'tests/test_workspace_export.py','references/exports.md','scripts/vps_support.py','tests/test_support_draft.py','assets/support-request.example.json','references/local-support-draft.md','references/support-scope.md','evals/evals.json','evals/trigger-evals.json','references/agent-actions.md','tests/test_prometheus_windows.py','references/prometheus-windows.md','scripts/vps_evidence.py','references/time-evidence.md','scripts/vps_ops.py','assets/operator.js','assets/operator.css','assets/provider-catalog.json',
              'references/first-hour.md','references/operator-playbook.md','references/support.md','references/workspace-recovery.md','tests/test_private_workspace.py',
              'scripts/vps_viewer.py','tests/test_viewer_access.py','references/remote-viewer.md','scripts/vps_agent.py','scripts/vps_forensics.py','references/forensics.md','references/agent-workflow.md','references/agent-connectors.md'}
    if not required<=set(files):raise ValueError('installable skill is missing required runtime/license files')
    if any(name.startswith(('skills/','.github/','tools/')) for name in files):
        raise ValueError('repository content incorrectly nested inside the skill ZIP')
    # Check authored inline Markdown references in the actual selected archive.
    # This is not a full Markdown parser or an external URL/anchor availability check.
    for name,raw in files.items():
        if not name.endswith('.md'):continue
        guide=raw.decode()
        # Installed runtime recipes cannot depend on the collection's parent
        # directories. Check command text before removing fences for link checks.
        if re.search(r"(?m)^\s*python3\s+['\"]?skills/vps-health/scripts/",guide):
            raise ValueError('repository-relative runtime command in installed guide: '+name)
        text=re.sub(r'^```[^\n]*\n.*?^```\s*$','',guide,flags=re.S|re.M)
        for link in re.findall(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)',text):
            parts=urlsplit(link)
            if parts.scheme or parts.netloc or not parts.path:continue
            target=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(parts.path)))
            if target not in files:raise ValueError('unshipped local documentation target: '+name+' -> '+link)
    import yaml
    header=yaml.safe_load(files['SKILL.md'].decode().split('---',2)[1])
    if not isinstance(header,dict) or header.get('name')!='vps-health' or not isinstance(header.get('description'),str):
        raise ValueError('actual exported skill discovery metadata is invalid')
    meta=json.loads(files['skill.json'])
    if header.get('metadata',{}).get('version')!=meta['version']:raise ValueError('exported discovery version differs')
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
        # Disable site-packages: the new YAML parser is a maintainer check,
        # never a dependency needed by an installed user's CLI or workbench.
        capability=json.loads(subprocess.check_output([sys.executable,'-S',entry,'capabilities'],text=True,timeout=20))
        if capability['version']!=json.loads((target/'skill.json').read_text())['version']:
            raise ValueError('standalone no-site-packages version mismatch')
        subprocess.run([sys.executable,'-S',entry,'bootstrap','--mode','demo','--workspace',str(workspace)],check=True,stdout=subprocess.DEVNULL,timeout=60)
        html=(workspace/'dashboard.html').read_text()
        if 'VpsCharts.mount' not in html or 'var uPlot=' not in html or '/*UPLOT_JS*/' in html:raise ValueError('exported chart runtime missing')
        for control in ('review-dialog','command-dialog','pause-view','VpsView.review','VpsView.commands','context-cfs-coverage','time-channel-rows','review-context'):
            if control not in html:raise ValueError('exported workbench control/module missing: '+control)
        if any(marker in html for marker in ('/*WORKBENCH_JS*/','/*VIEW_MODEL*/')):
            raise ValueError('unresolved workbench script in actual archive')
        subprocess.run([sys.executable,entry,'export','--workspace',str(workspace),'--out',str(Path(temp)/'report')],check=True,stdout=subprocess.DEVNULL,timeout=60)
        verified_summary=json.loads(subprocess.check_output([sys.executable,'-S',entry,'verify',str(Path(temp)/'report')],text=True,timeout=30))
        if (verified_summary.get('artifact_kind')!='workspace-summary' or verified_summary.get('integrity')!='PASS'
                or verified_summary.get('replay')!='NOT_AVAILABLE' or verified_summary.get('raw_data_included') is not False):
            raise ValueError('the actual exported summary did not verify with honest replay scope')

        doctor=subprocess.run([sys.executable,entry,'doctor','--workspace',str(workspace)],capture_output=True,text=True,timeout=30)
        if doctor.returncode!=1 or not json.loads(doctor.stdout)['read_only']:raise ValueError('exported doctor did not preserve diagnosis semantics')
        brief=json.loads(subprocess.check_output([sys.executable,entry,'brief','--workspace',str(workspace)],text=True,timeout=30))
        if len(brief['items'])!=2 or brief['automatic_actions']:raise ValueError('exported brief contract failed')
        subprocess.run([sys.executable,entry,'providers','--provider','aws'],check=True,stdout=subprocess.DEVNULL,timeout=30)
        status=json.loads(subprocess.check_output([sys.executable,entry,'dashboard','--workspace',str(workspace)],text=True,timeout=30))
        node=status['assets'][1]
        report=json.loads(subprocess.check_output([sys.executable,entry,'evidence-report','--workspace',str(workspace),
            '--node',node['id'],'--start',node['window_start'],'--end',node['window_end']],text=True,timeout=30))
        if report['profile']['schema']!='g-skills.time-evidence.v1' or not report['read_only'] or report['new_measurements']:
            raise ValueError('exported time-qualified report contract failed')
        if report['profile']['episodes']['count']<1 or not report['observation_hashes']:
            raise ValueError('exported report lost shortfall intervals or sample provenance')

        for provider in ('vultr','ovhcloud','netcup'):
            result=json.loads(subprocess.check_output([sys.executable,entry,'providers','--provider',provider],text=True,timeout=15))
            if result['providers'][0]['id']!=provider or result['establishes_contract'] or result['sources_fetched']:
                raise ValueError('standalone provider route or authority changed')
            if not all(f.get('reviewed_on') for f in result['providers'][0]['facts']):
                raise ValueError('standalone reference lacks individual review dates')
            profile=Path(temp)/(provider+'-profile.json')
            profile.write_text(json.dumps({'schema':'g-skills.vps-profile.v1','assets':[{'id':'example-'+provider,'instance':'example.invalid:9100','provider':provider,'plan':'Owner-provided example'}]}))
            location=Path(temp)/(provider+'-workspace')
            subprocess.run([sys.executable,entry,'bootstrap','--mode','prometheus','--profile',str(profile),
                '--url','https://metrics.example.invalid','--workspace',str(location)],check=True,stdout=subprocess.DEVNULL,timeout=20)
            retained=json.loads(subprocess.check_output([sys.executable,entry,'dashboard','--workspace',str(location)],text=True,timeout=20))
            if retained['assets'][0]['provider']!=provider or retained['assets'][0]['decision']!='HOLD' or retained['stored_captures']:
                raise ValueError('provider-labelled bootstrap invented observed evidence')

        support=json.loads(subprocess.check_output([sys.executable,entry,'support-report','--workspace',str(workspace)],text=True,timeout=30))
        if support['workspace']['retained_points']!=2288 or support['sent'] or not support['review_before_sharing']:
            raise ValueError('exported minimal support summary contract failed')
        if any(v in json.dumps(support) for v in ('example-stable','example-contended',str(workspace))):
            raise ValueError('private context entered exported support summary')
        issue=Path(temp)/'support-request.json';issue.write_bytes((target/'assets/support-request.example.json').read_bytes());issue.chmod(0o600)
        output=Path(temp)/'support-draft.txt'
        draft=json.loads(subprocess.check_output([sys.executable,'-B','-S',entry,'support-draft','--issue',str(issue),
             '--workspace',str(workspace),'--out',str(output),'--approve-draft'],text=True,cwd=temp,timeout=30))
        text=output.read_text()
        if (draft['sent'] or draft['connector_needed_for_local_draft'] or draft['attachments'] or not draft['draft_created']
                or not text.startswith('LOCAL SOFTWARE SUPPORT DRAFT') or '2288' not in text
                or any(private in text for private in (str(workspace),'example-stable','example-contended'))
                or hashlib.sha256(output.read_bytes()).hexdigest()!=draft['sha256']):
            raise ValueError('actual extracted support draft violated the local/private artifact contract')


        if sys.platform=='linux':
            options=['--workspace',str(workspace),'--mode','auto','--duration-seconds','30']
            plan=json.loads(subprocess.check_output([sys.executable,entry,'agent-plan',*options],text=True,timeout=20))
            runtime=json.loads(subprocess.check_output([sys.executable,entry,'agent-start',*options,'--approve-plan',plan['plan_sha256']],text=True,timeout=15))
            try:
                if runtime['state']!='RUNNING' or not runtime['process_verified']:raise ValueError('exported agent runtime not verified')
                current=json.loads(subprocess.check_output([sys.executable,entry,'agent-status','--workspace',str(workspace)],text=True,timeout=15))
                if current['run_id']!=runtime['run_id']:raise ValueError('exported handoff lost owned identity')
                verified=json.loads(subprocess.check_output([sys.executable,entry,'agent-verify','--workspace',str(workspace)],text=True,timeout=15))
                if verified['state']!='VERIFIED' or not verified['http_verified']:raise ValueError('exported viewer readback not verified')
                handoff=Path(temp)/'viewer-handoff.json'
                subprocess.run([sys.executable,'-B','-S',entry,'viewer-handoff','--workspace',str(workspace),'--out',str(handoff)],check=True,stdout=subprocess.DEVNULL,timeout=15)
                access=json.loads(subprocess.check_output([sys.executable,'-B','-S',entry,'viewer-plan','--handoff',str(handoff),'--ssh-target','example-host'],text=True,timeout=15))
                if access['state']!='PLAN_ONLY' or access['ssh_connection_verified']:raise ValueError('packaged viewer plan invented a connection')
                matched=json.loads(subprocess.check_output([sys.executable,'-B','-S',entry,'viewer-verify','--handoff',str(handoff)],text=True,timeout=15))
                if matched['state']!='VIEWER_MATCHED' or not matched['http_identity_matched']:raise ValueError('packaged handoff readback failed')

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

    result=subprocess.run([sys.executable,str(target/'tests/test_prometheus_windows.py'),'RetainedWindowTest','RealHTTPTest'],capture_output=True,text=True,timeout=45)
    if result.returncode:raise ValueError('exported Prometheus window/gap checks failed: '+result.stderr[-2500:])

def main():
    p=argparse.ArgumentParser();p.add_argument('--skill-dir',required=True,type=Path);a=p.parse_args()
    files={f.relative_to(a.skill_dir).as_posix():f.read_bytes() for f in a.skill_dir.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    validate_files(files);cold_check(a.skill_dir)
    print('PASS: isolated VPS Health package including owned stop and interrupted initialization recovery')
if __name__=='__main__':main()
