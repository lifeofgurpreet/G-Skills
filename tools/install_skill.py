#!/usr/bin/env python3
"""Plan and manage one explicitly selected skill; preserve rather than overwrite.

Offline collection tooling, not a daemon or client authentication service. It
executes no packaged scripts. A plan hash binds intent, not human consent.
Install/update/restore/removal require an authorized agent and stopped consumers.
Retired installations live outside discovery, with interrupted moves recoverable.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid
import zipfile
import collection
import package_release as package

RECEIPT='.gskills-install.json'
MAX_BYTES=package.MAX_BYTES
MAX_REVISIONS=20
SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def digest(value):
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()


def path_checked(value):
    path=Path(value).expanduser().absolute()
    if '..' in path.parts:raise ValueError('use an explicit canonical path without parent traversal')
    for current in (path,*path.parents):
        if current.is_symlink():raise ValueError('symbolic-link installation paths are not managed')
    return path


def read_bytes(path,limit=MAX_BYTES):
    path=path_checked(path);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>limit:raise ValueError('input must be a bounded regular file')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as f:data=f.read(limit+1)
    if len(data)>limit:raise ValueError('input grew beyond its bound')
    return data


def read_json(path):return json.loads(read_bytes(path,2*1024*1024))


def write_new(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def layout(directory,store,skill):
    collection.safe_name(skill);directory=path_checked(directory);store=path_checked(store)
    if directory==store or directory in store.parents or store in directory.parents:
        raise ValueError('recovery storage must be separate from every discoverable skill directory')
    for p in (directory,store):
        if p.exists() and not p.is_dir():raise ValueError('installation paths must be directories')
    target=directory/skill;key=digest(str(target))[:24]
    return directory,store,target,store/key


def source(archive,manifest,skill):
    raw=read_bytes(archive);release=read_json(manifest)
    if not isinstance(release,dict) or release.get('schema')!='g-skills.skill-release.v1' or release.get('skill')!=skill:
        raise ValueError('selected skill and release identity differ')
    if not isinstance(release.get('files'),dict):raise ValueError('release file map is invalid')
    meta=release['files'].get(Path(archive).name,{})
    if not isinstance(meta,dict):raise ValueError('release artifact record is invalid')
    if meta.get('bytes')!=len(raw) or meta.get('sha256')!=digest(raw):raise ValueError('archive does not match reviewed manifest')
    files=package.archive_files(raw,skill);description=json.loads(files['skill.json'])
    if description['version']!=release.get('version') or release.get('tag')!=skill+'/v'+description['version']:
        raise ValueError('release and packaged versions differ')
    if not re.fullmatch('[a-f0-9]{40}',str(release.get('commit',''))):raise ValueError('release must bind an exact commit')
    return {'skill':skill,'version':release['version'],'commit':release['commit'],'archive_sha256':digest(raw),
            'files':{k:digest(v) for k,v in files.items()}},files


def tree_files(directory):
    files={};count=0;size=0
    for path in directory.rglob('*'):
        count+=1
        if count>5000:raise ValueError('installed-tree inspection budget exceeded')
        if path.is_symlink():raise ValueError('symbolic link found in managed installation')
        if path.is_dir():continue
        if not path.is_file():raise ValueError('special file found in managed installation')
        relative=path.relative_to(directory).as_posix()
        if relative==RECEIPT:continue
        # Ordinary Python caches are disposable, not user edits. Any other added
        # data, even inside a cache directory, prevents update/removal.
        if path.parent.name=='__pycache__' and path.suffix=='.pyc':continue
        data=read_bytes(path);size+=len(data)
        if size>MAX_BYTES:raise ValueError('installed-tree byte budget exceeded')
        files[relative]=digest(data)
    return files


def installed(target,skill,identity_target=None):
    if target.is_symlink():raise ValueError('symbolic-link destination must not be overwritten')
    if not target.exists():return None
    if target.is_symlink() or not target.is_dir() or not (target/RECEIPT).is_file():
        raise ValueError('existing destination is unowned; never adopt or overwrite it implicitly')
    receipt=read_json(target/RECEIPT)
    identity=str(identity_target or target)
    if (not isinstance(receipt,dict) or receipt.get('schema')!='g-skills.install.v1' or receipt.get('target')!=identity
            or receipt.get('skill')!=skill or not re.fullmatch('[a-f0-9]{32}',str(receipt.get('generation','')))
            or not isinstance(receipt.get('files'),dict)):
        raise ValueError('installation receipt identity is invalid')
    if tree_files(target)!=receipt['files']:raise ValueError('installation contains modified, missing or unrecorded files; preserve and reconcile them')
    return receipt


def state_key(receipt):return digest(receipt) if receipt else None


def store_check(folder,target,create=False):
    if create:
        folder.mkdir(parents=True,mode=0o700,exist_ok=True)
    if folder.exists():
        if folder.is_symlink() or not folder.is_dir() or folder.stat().st_uid!=os.getuid() or folder.stat().st_mode&0o077:
            raise ValueError('recovery directory must be private and owned by the current user')
        binding=folder/'binding.json'
        if binding.exists():
            if read_json(binding)!={'target':str(target)}:raise ValueError('recovery store belongs to a different destination')
        elif create:write_new(binding,json.dumps({'target':str(target)}).encode())
        elif any(folder.iterdir()):raise ValueError('unbound recovery state needs inspection')


def status(directory,store,skill):
    _,_,target,folder=layout(directory,store,skill);store_check(folder,target)
    current=installed(target,skill)
    revisions=[]
    if folder.exists():
        for path in sorted(folder.glob('retired-*')):
            if not re.fullmatch('retired-[a-f0-9]{32}',path.name):raise ValueError('invalid recovery revision')
            old=installed(path,skill,target)
            if old:revisions.append({'revision':path.name,'version':old['version'],'generation':old['generation']})
    return {'schema':'g-skills.install-status.v1','state':'RECOVERY_REQUIRED' if (folder/'pending.json').exists() else 'INSTALLED' if current else 'NOT_INSTALLED',
            'target':str(target),'current':current,'revisions':revisions,
            'native_client_verified':False,'runtime_started':False,'evidence_removed':False,
            'agent_entry':({'file':str(target/'SKILL.md'),'search_machine':False,
                'instruction':'Read this installed entry directly: '+str(target/'SKILL.md')+'. Do not search the whole host to locate it. Use only the scoped tools authorized for the requested task; a denied broad scan does not establish whether a different, explicitly allowed operation is available.'} if current else None),
            'retained_staging':len(list(folder.glob('stage-*'))) if folder.exists() else 0}


def plan(operation,directory,store,skill,archive=None,manifest=None,revision=None):
    if operation not in ('install','remove','restore','recover'):raise ValueError('unknown operation')
    directory,store,target,folder=layout(directory,store,skill);store_check(folder,target)
    journal=read_json(folder/'pending.json') if (folder/'pending.json').exists() else None
    completed=sorted(p.name for p in folder.glob('done-*.json')) if folder.exists() else []
    if len(completed)>MAX_REVISIONS:raise ValueError('recovery history requires explicit archival')
    generation=digest(completed)
    current=installed(target,skill);desired=None
    if operation=='recover':
        if not journal:raise ValueError('no interrupted managed operation to recover')
        return _plan(operation,target,store,state_key(current),None,digest(journal),generation)
    if journal:raise ValueError('interrupted operation requires explicit recovery first')
    if operation=='install':desired,_=source(archive,manifest,skill)
    if operation=='restore':
        if not re.fullmatch('retired-[a-f0-9]{32}',str(revision)):raise ValueError('select an exact retained revision')
        desired=installed(folder/revision,skill,target)
        if not desired:raise ValueError('retained revision is absent')
        desired={k:desired[k] for k in ('skill','version','commit','archive_sha256','files')}
    return _plan(operation,target,store,state_key(current),desired,revision,generation)


def _plan(operation,target,store,before,desired,revision,generation):
    intent={'operation':operation,'target':str(target),'store':str(store),'before':before,
            'desired':desired,'revision':revision,'recovery_generation':generation,'tool_sha256':SOURCE_SHA256}
    return {'schema':'g-skills.install-plan.v1','intent':intent,'plan_sha256':digest(intent),
            'effect':'Publish only the selected reviewed files; retain any replaced installation outside discovery.',
            'needs_quiescence':True,
            'instructions_executed':False,'native_client_verified':False,'approval_is_authentication':False}


@contextlib.contextmanager
def locked(folder):
    if os.name!='posix':raise ValueError('managed installation currently requires a qualified POSIX filesystem')
    import fcntl
    fd=os.open(folder/'lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('another installer owns this destination; inspect its result before retrying') from None
        yield
    finally:os.close(fd)


def checkpoint(name):
    """Fault-injection seam; production has no user-controlled hooks."""


def make_stage(folder,files,receipt,token):
    stage=folder/('stage-'+token);stage.mkdir(mode=0o700)
    for name,data in files.items():
        relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or name==RECEIPT:raise ValueError('invalid staged path')
        path=stage/name;path.parent.mkdir(parents=True,mode=0o700,exist_ok=True);write_new(path,data)
    write_new(stage/RECEIPT,json.dumps(receipt,sort_keys=True).encode())
    for path in sorted((p for p in stage.rglob('*') if p.is_dir()),reverse=True):sync_dir(path)
    sync_dir(stage);sync_dir(folder)
    return stage


def finish(folder,journal):
    os.rename(folder/'pending.json',folder/('done-'+journal['id']+'.json'));sync_dir(folder)


def recover_locked(target,folder,skill,journal):
    # Journal names are generated identifiers, never arbitrary recovery paths.
    if (not isinstance(journal,dict) or journal.get('schema')!='g-skills.install-transaction.v1'
            or journal.get('target')!=str(target) or journal.get('skill')!=skill
            or not re.fullmatch('[a-f0-9]{32}',str(journal.get('id','')))):
        raise ValueError('invalid recovery journal; preserve for inspection')
    token=journal['id'];old_path=folder/('retired-'+token)
    current=installed(target,skill);old=installed(old_path,skill,target)
    before=journal.get('before');after=journal.get('after')
    if current is not None and state_key(current)==after:
        # Publication completed; the old snapshot is retained, never deleted.
        finish(folder,journal);return 'PUBLISHED_OPERATION_CONFIRMED'
    if current is not None and state_key(current)==before and old is None:
        finish(folder,journal);return 'PRIOR_INSTALLATION_PRESERVED'
    if current is None and old is not None and state_key(old)==before:
        os.rename(old_path,target);sync_dir(target.parent);sync_dir(folder)
        finish(folder,journal);return 'PRIOR_INSTALLATION_RESTORED'
    if current is None and before is None and old is None:
        finish(folder,journal);return 'UNPUBLISHED_INSTALLATION_ABANDONED'
    raise ValueError('recovery encountered changed or incomplete evidence; do not overwrite anything')


def apply(operation,directory,store,skill,approval,archive=None,manifest=None,revision=None,consumers_stopped=False):
    if os.name!='posix':raise ValueError('managed installation currently requires a qualified POSIX filesystem')
    if not consumers_stopped:raise ValueError('the agent must stop skill consumers first; pass --consumers-stopped only after doing so')
    expected=plan(operation,directory,store,skill,archive,manifest,revision)
    if approval!=expected['plan_sha256']:
        # Retry a committed install receipt, not another update or budget.
        current=status(directory,store,skill)['current']
        desired=expected['intent']['desired']
        if not (operation=='install' and current and current.get('applied_plan')==approval and desired
                and all(current.get(k)==v for k,v in desired.items())):
            raise ValueError('approval differs from the current source/destination plan; no changes made')
        return {'state':'UNCHANGED','target':str(Path(directory)/skill),'native_client_verified':False}
    directory,store,target,folder=layout(directory,store,skill)
    directory.mkdir(parents=True,mode=0o700,exist_ok=True)
    store.mkdir(parents=True,mode=0o700,exist_ok=True)
    if store.stat().st_mode&0o077 or store.stat().st_uid!=os.getuid():raise ValueError('recovery store must be private; no permissions were changed')
    store_check(folder,target,True)
    if directory.stat().st_dev!=folder.stat().st_dev:raise ValueError('installation and recovery need the same filesystem for rename recovery')
    with locked(folder):
        now=plan(operation,directory,store,skill,archive,manifest,revision)
        if now['plan_sha256']!=approval:raise ValueError('installation changed while acquiring ownership; review again')
        if operation=='recover':
            message=recover_locked(target,folder,skill,read_json(folder/'pending.json'))
            return {'state':message,'status':status(directory,store,skill),'native_client_verified':False}
        old=installed(target,skill);desired=now['intent']['desired']
        if operation=='remove' and old is None:return {'state':'UNCHANGED','native_client_verified':False}
        if old and desired and all(old.get(k)==v for k,v in desired.items()):return {'state':'UNCHANGED','native_client_verified':False}
        if len(list(folder.glob('done-*')))+len(list(folder.glob('stage-*')))>=MAX_REVISIONS:
            raise ValueError('retained-history budget reached; explicitly archive old recovery state before continuing')
        token=uuid.uuid4().hex;new=None;stage=None
        if desired is not None:
            if operation=='install':check,files=source(archive,manifest,skill)
            else:
                snapshot=folder/revision
                saved=installed(snapshot,skill,target)
                check={k:saved[k] for k in ('skill','version','commit','archive_sha256','files')}
                files={name:read_bytes(snapshot/name) for name in saved['files']}
            if check!=desired:raise ValueError('source changed after planning')
            new={**desired,'schema':'g-skills.install.v1','target':str(target),'generation':token,'applied_plan':approval}
            stage=make_stage(folder,files,new,token)
            installed(stage,skill,target)
        # Recheck the observed installation after staging; do not overwrite edits.
        if state_key(installed(target,skill))!=state_key(old):raise ValueError('installation changed during staging; original is untouched')
        journal={'schema':'g-skills.install-transaction.v1','id':token,'operation':operation,'skill':skill,'target':str(target),
                 'before':state_key(old),'after':state_key(new),'plan_sha256':approval}
        write_new(folder/'pending.json',json.dumps(journal,sort_keys=True).encode());sync_dir(folder)
        checkpoint('prepared')
        if old:
            os.rename(target,folder/('retired-'+token));sync_dir(directory);sync_dir(folder)
        checkpoint('retired')
        if stage:
            if target.exists():raise ValueError('destination unexpectedly reappeared; explicit recovery required')
            os.rename(stage,target);sync_dir(directory);sync_dir(folder)
        checkpoint('published')
        finish(folder,journal)
        return {'state':'REMOVED_RETAINED' if new is None else 'INSTALLED','status':status(directory,store,skill),
                'native_client_verified':False,'instructions_executed':False,'consumers_stopped':'agent_asserted_not_independently_proven',
                'note':'Restart or refresh the actual client and verify discovery separately. No account was connected and no monitor started.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','apply','status'))
    parser.add_argument('--operation',choices=('install','remove','restore','recover'),default='install')
    parser.add_argument('--skill',required=True);parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--store',required=True,type=Path);parser.add_argument('--archive',type=Path);parser.add_argument('--manifest',type=Path)
    parser.add_argument('--revision');parser.add_argument('--approve-plan');parser.add_argument('--consumers-stopped',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='status':result=status(args.directory,args.store,args.skill)
        elif args.command=='plan':result=plan(args.operation,args.directory,args.store,args.skill,args.archive,args.manifest,args.revision)
        else:result=apply(args.operation,args.directory,args.store,args.skill,args.approve_plan,args.archive,args.manifest,args.revision,args.consumers_stopped)
        print(json.dumps(result,sort_keys=True,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
        print(json.dumps({'state':'BLOCKED','reason':str(exc),'no_force_override':True,'native_client_verified':False}));return 1

if __name__=='__main__':raise SystemExit(main())
