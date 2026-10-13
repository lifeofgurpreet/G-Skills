#!/usr/bin/env python3
"""Package one independently versioned skill from an immutable Git tree.

No upload, tag or network. The selected skill owns its cold acceptance. Another
skill cannot inherit its browser, runtime, versions or dependencies by accident.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import io
import json
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
import collection

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=16*1024*1024


def read_tree(ref,root=ROOT,skill=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,180}',ref):raise ValueError('invalid source ref')
    sha=subprocess.check_output(['git','rev-parse','--verify','--end-of-options',ref+'^{commit}'],cwd=root,text=True).strip()
    if not re.fullmatch('[a-f0-9]{40}',sha):raise ValueError('expected exact source commit')
    paths=[]
    if skill is not None:
        collection.safe_name(skill)
        exists=subprocess.run(['git','cat-file','-e',sha+':skills/'+skill+'/skill.json'],cwd=root,capture_output=True)
        if exists.returncode:raise ValueError('selected skill is absent from the chosen source tree')
        paths=['skills/'+skill,'tools/skills/'+skill,'LICENSE']
    raw=subprocess.check_output(['git','archive','--format=tar',sha,*paths],cwd=root)
    if len(raw)>MAX_BYTES:raise ValueError('source exceeds reviewed archive size bound')
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            if member.isdir():continue
            path=PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or '.git' in path.parts or member.name in files:
                raise ValueError('unsafe source archive member')
            files[member.name]=archive.extractfile(member).read()
    return sha,files


def zip_payload(files,prefix):
    if not prefix.endswith('/') or not collection.NAME.fullmatch(prefix[:-1]):raise ValueError('ZIP root must be one skill name')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw in sorted(files.items()):
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or not path.parts:raise ValueError('unsafe ZIP path')
            info=zipfile.ZipInfo(prefix+name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,raw)
    return stream.getvalue()


def verify_zip(raw,name,checker=None):
    collection.safe_name(name)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist();names=archive.namelist()
        if len(names)!=len(set(names)) or sum(i.file_size for i in infos)>MAX_BYTES or not infos:
            raise ValueError('duplicate, empty or oversized archive')
        if any(not n.startswith(name+'/') for n in names):raise ValueError('wrong skill root')
        for item in infos:
            path=PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(item.external_attr>>16):raise ValueError('unsafe ZIP member')
        files={n[len(name)+1:]:archive.read(n) for n in names}
        if not {'SKILL.md','skill.json','LICENSE'}<=set(files):raise ValueError('missing entry, metadata or license')
        meta=collection.validate_manifest(json.loads(files['skill.json']),name)
        if meta['status']!='ready':raise ValueError('draft skill is not releasable')
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/name;target.mkdir()
            for relative,data in files.items():
                dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            if checker is not None:
                subprocess.run([sys.executable,str(checker),'--skill-dir',str(target)],check=True,timeout=150)
    return len(files)


def build(ref,out,skill,root=ROOT):
    name=collection.safe_name(skill);sha,files=read_tree(ref,root,name)
    prefix=f'skills/{name}/'
    if prefix+'skill.json' not in files:raise ValueError('selected skill is absent from the chosen source tree')
    doc=collection.validate_manifest(json.loads(files[prefix+'skill.json']),name)
    if doc['status']!='ready':raise ValueError('draft skill cannot be released')
    selected={path[len(prefix):]:raw for path,raw in files.items() if path.startswith(prefix)}
    if 'LICENSE' not in selected:
        if 'LICENSE' not in files:raise ValueError('license missing')
        selected['LICENSE']=files['LICENSE']
    payload=zip_payload(selected,name+'/')
    # Run the checker from THAT committed tree, not uncommitted working code.
    checker=doc['checks']['package']
    if not checker.startswith(f'tools/skills/{name}/') or checker not in files or '..' in PurePosixPath(checker).parts:
        raise ValueError('missing or out-of-scope committed package check')
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)/'source';source.mkdir()
        for path,raw in files.items():
            dest=source/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        count=verify_zip(payload,name,source/checker)
    version=doc['version'];filename=f'{name}-v{version}.zip'
    manifest={'schema':'g-skills.skill-release.v1','skill':name,'version':version,'tag':f'{name}/v{version}',
              'commit':sha,'skill_files':count,'verification':'actual selected archive extraction and owning committed acceptance',
              'files':{filename:{'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}}}
    out=Path(out);out.mkdir(parents=False,exist_ok=False)
    (out/filename).write_bytes(payload);(out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skill',required=True);p.add_argument('--ref',default='HEAD');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(build(a.ref,a.out,a.skill),indent=2));return 0
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:print(str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
