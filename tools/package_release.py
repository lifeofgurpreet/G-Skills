#!/usr/bin/env python3
"""Build and cold-test the actual archives from one committed, immutable tree.

No upload, tag, git mutation or network. Files absent from Git never enter a ZIP.
Run after the release commit is reviewed; this command does not authorize release.
"""
from pathlib import Path,PurePosixPath
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PREFIX='skills/vps-health/'
MAX_BYTES=16*1024*1024


def read_tree(ref):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,180}',ref):raise ValueError('invalid source ref')
    sha=subprocess.check_output(['git','rev-parse','--verify','--end-of-options',ref+'^{commit}'],cwd=ROOT,text=True).strip()
    if not re.fullmatch('[a-f0-9]{40}',sha):raise ValueError('expected exact source commit')
    raw=subprocess.check_output(['git','archive','--format=tar',sha],cwd=ROOT)
    if len(raw)>MAX_BYTES:raise ValueError('source archive exceeds reviewed size budget')
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            if member.isdir():continue
            path=PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or '.git' in path.parts:
                raise ValueError('unsafe source archive member')
            if member.name in files:raise ValueError('duplicate source member')
            files[member.name]=archive.extractfile(member).read()
    return sha,files


def zip_payload(files,prefix):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw in sorted(files.items()):
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:raise ValueError('unsafe ZIP path')
            info=zipfile.ZipInfo(prefix+name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,raw)
    return stream.getvalue()


def validate_skill(files):
    required={'SKILL.md','scripts/vps_health.py','scripts/vps_workspace.py','assets/chart-adapter.js',
              'assets/workspace-dashboard.html','assets/vendor/uplot/manifest.json','assets/vendor/uplot/LICENSE','LICENSE',
              'scripts/vps_ops.py','assets/operator.js','assets/operator.css','assets/provider-catalog.json',
              'references/first-hour.md','references/operator-playbook.md'}
    if not required<=set(files):raise ValueError('installable skill is missing required runtime/license files')
    if any(name.startswith(('skills/','.github/','tools/')) for name in files):
        raise ValueError('repository content incorrectly nested inside the skill ZIP')
    manifest=json.loads(files['assets/vendor/uplot/manifest.json'])
    for name,data in manifest['files'].items():
        raw=files['assets/vendor/uplot/'+name]
        if hashlib.sha256(raw).hexdigest()!=data['sha256'] or len(raw)!=data['bytes']:
            raise ValueError('vendored artifact does not match reviewed manifest')


def verify_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or sum(m.file_size for m in archive.infolist())>MAX_BYTES:
            raise ValueError('invalid or oversized installable archive')
        if any(not name.startswith('vps-health/') for name in names):raise ValueError('wrong skill root')
        files={name[len('vps-health/'):]:archive.read(name) for name in names}
        validate_skill(files)
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'exported';target.mkdir()
            for name,value in files.items():
                path=PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts:raise ValueError('unsafe exported member')
                dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(value)
            entry=str(target/'scripts/vps_health.py');workspace=Path(temp)/'workspace'
            subprocess.run([sys.executable,entry,'bootstrap','--mode','demo','--workspace',str(workspace)],check=True,stdout=subprocess.DEVNULL,timeout=60)
            html=(workspace/'dashboard.html').read_text()
            if 'VpsCharts.mount' not in html or 'var uPlot=' not in html or '/*UPLOT_JS*/' in html:raise ValueError('exported chart runtime missing')
            subprocess.run([sys.executable,entry,'export','--workspace',str(workspace),'--out',str(Path(temp)/'report')],check=True,stdout=subprocess.DEVNULL,timeout=60)
            doctor=subprocess.run([sys.executable,entry,'doctor','--workspace',str(workspace)],capture_output=True,text=True,timeout=30)
            if doctor.returncode!=1 or not json.loads(doctor.stdout)['read_only']:raise ValueError('exported doctor did not preserve diagnosis semantics')
            brief=json.loads(subprocess.check_output([sys.executable,entry,'brief','--workspace',str(workspace)],text=True,timeout=30))
            if len(brief['items'])!=2 or brief['automatic_actions']:raise ValueError('exported brief contract failed')
            subprocess.run([sys.executable,entry,'providers','--provider','aws'],check=True,stdout=subprocess.DEVNULL,timeout=30)
    return len(files)


def build(ref,out):
    sha,files=read_tree(ref)
    skill={name[len(PREFIX):]:raw for name,raw in files.items() if name.startswith(PREFIX)}
    skill['LICENSE']=files['LICENSE']
    validate_skill(skill)
    text=skill['scripts/vps_workspace.py'].decode()
    version=re.search(r"^VERSION\s*=\s*['\"]([0-9]+\.[0-9]+\.[0-9]+)['\"]",text,re.M).group(1)
    core_version=re.search(r"^VERSION\s*=\s*['\"]([0-9]+\.[0-9]+\.[0-9]+)['\"]",skill['scripts/vps_health.py'].decode(),re.M).group(1)
    if version!=core_version:raise ValueError('CLI and workspace versions disagree')
    artifacts={f'G-Skills-v{version}.zip':zip_payload(files,f'G-Skills-v{version}/'),
               f'vps-health-v{version}.zip':zip_payload(skill,'vps-health/')}
    count=verify_zip(artifacts[f'vps-health-v{version}.zip'])
    out=Path(out);out.mkdir(parents=False,exist_ok=False)
    for name,raw in artifacts.items():(out/name).write_bytes(raw)
    manifest={'schema':'g-skills.release-artifacts.v1','version':version,'commit':sha,'skill_files':count,
              'verification':'actual ZIP extraction -> standalone synthetic bootstrap -> HTML -> export',
              'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in artifacts.items()}}
    (out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ref',default='HEAD');p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    try:print(json.dumps(build(args.ref,args.out),indent=2));return 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc:print(str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
