#!/usr/bin/env python3
"""Real failure recovery and private-state boundaries, not permission theater."""
from pathlib import Path
import concurrent.futures
import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
import vps_agent as agent
import vps_ops as ops


def args(path,mode='demo'):
    return SimpleNamespace(workspace=path,mode=mode,node='example-node',profile=None,url=None,loki_url=None,
        token_env=None,loki_token_env=None,allow_http=False,interval=60,acceptable=.9,investigate_below=.8,
        provider='unknown',plan=None,duration_seconds=20,port=0,client='generic',approve_plan=None)


def tree(path):
    return {p.relative_to(path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_symlink()}

class WorkspaceBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'workspace'

    def test_resolved_parent_cannot_hide_a_workspace_inside_installed_skill(self):
        skill=self.base/'installed';skill.mkdir();alias=self.base/'alias';alias.symlink_to(skill,target_is_directory=True)
        with mock.patch.object(core,'ROOT',skill):
            with self.assertRaises(core.InvalidEvidence):ws.bootstrap(args(alias/'private'))
        self.assertFalse((skill/'private').exists())

    def test_parent_traversal_is_checked_after_resolution(self):
        skill=self.base/'installed';skill.mkdir()
        with mock.patch.object(core,'ROOT',skill):
            with self.assertRaises(core.InvalidEvidence):ws.public_path(self.base/'other/../installed/private')

    def test_regular_parent_alias_outside_skill_resolves_without_retargeting(self):
        actual=self.base/'actual';actual.mkdir();alias=self.base/'alias';alias.symlink_to(actual,target_is_directory=True)
        self.assertEqual(ws.public_path(alias/'workspace'),actual/'workspace')

    def test_public_workspace_is_refused_without_chmod_or_reads(self):
        ws.bootstrap(args(self.root));self.root.chmod(0o755);before=tree(self.root)
        with self.assertRaises(core.InvalidEvidence):ws.config_load(self.root)
        self.assertEqual(tree(self.root),before);self.assertEqual(self.root.stat().st_mode&0o777,0o755)
        self.assertEqual(ops.doctor(self.root)['verdict'],'UNAVAILABLE')

    def test_public_config_is_refused_without_repair(self):
        ws.bootstrap(args(self.root));p=self.root/'workspace.json';p.chmod(0o644)
        with self.assertRaises(core.InvalidEvidence):ws.config_load(self.root)
        self.assertEqual(p.stat().st_mode&0o777,0o644)

    def test_hardlinked_config_cannot_be_a_managed_private_state_file(self):
        ws.bootstrap(args(self.root));os.link(self.root/'workspace.json',self.base/'linked-config')
        with self.assertRaises(core.InvalidEvidence):ws.config_load(self.root)

    def test_hardlinked_database_is_refused_and_external_link_is_unchanged(self):
        ws.bootstrap(args(self.root));target=self.base/'linked-db';os.link(self.root/'history.sqlite3',target)
        before=hashlib.sha256(target.read_bytes()).hexdigest()
        with self.assertRaises(core.InvalidEvidence):
            with ws.database(self.root):pass
        self.assertEqual(before,hashlib.sha256(target.read_bytes()).hexdigest())

    def test_database_sidecar_symlinks_are_never_followed_or_deleted(self):
        ws.bootstrap(args(self.root));target=self.base/'other';target.write_bytes(b'preserve me')
        for suffix in ('-journal','-wal','-shm'):
            p=self.root/('history.sqlite3'+suffix);p.symlink_to(target)
            with self.subTest(suffix=suffix),self.assertRaises(core.InvalidEvidence):
                with ws.database(self.root):pass
            self.assertTrue(p.is_symlink());self.assertEqual(target.read_bytes(),b'preserve me');p.unlink()

    def test_fifo_config_returns_instead_of_waiting_for_an_unrelated_writer(self):
        if not hasattr(os,'mkfifo'):self.skipTest('POSIX pipe fixture')
        ws.bootstrap(args(self.root));p=self.root/'workspace.json';p.unlink();os.mkfifo(p,0o600)
        cli=Path(core.__file__)
        result=subprocess.run([sys.executable,str(cli),'doctor','--workspace',str(self.root)],capture_output=True,text=True,timeout=3)
        self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stdout)['verdict'],'UNAVAILABLE')

    def test_real_proc_regular_file_with_zero_reported_size_is_still_read(self):
        if sys.platform!='linux':self.skipTest('actual procfs')
        self.assertEqual(Path('/proc/stat').stat().st_size,0)
        self.assertTrue(core.read_bytes('/proc/stat').startswith(b'cpu '))

    def test_core_fifo_input_refuses_without_blocking(self):
        if not hasattr(os,'mkfifo'):self.skipTest('POSIX pipe fixture')
        pipe=self.base/'input';os.mkfifo(pipe,0o600)
        command='import sys;sys.path.insert(0,sys.argv[1]);import vps_health as c;c.read_json(sys.argv[2])'
        r=subprocess.run([sys.executable,'-c',command,str(Path(core.__file__).parent),str(pipe)],capture_output=True,text=True,timeout=3)
        self.assertNotEqual(r.returncode,0);self.assertIn('regular',r.stderr.lower())

    def test_private_capture_file_ignores_a_permissive_umask(self):
        p=self.base/'capture.json';old=os.umask(0)
        try:core.save_json(p,{'private':'synthetic'})
        finally:os.umask(old)
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):core.save_json(p,{})

    def test_atomic_derived_write_does_not_replace_a_fifo(self):
        if not hasattr(os,'mkfifo'):self.skipTest('POSIX pipe fixture')
        p=self.base/'derived';os.mkfifo(p,0o600)
        with self.assertRaises(core.InvalidEvidence):ws.atomic(p,b'new')
        import stat
        self.assertTrue(stat.S_ISFIFO(p.lstat().st_mode))

class InitializationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'workspace'

    def test_failed_render_never_publishes_half_a_workspace(self):
        with mock.patch.object(ws,'render',side_effect=OSError('synthetic render failure')):
            with self.assertRaises((OSError,core.InvalidEvidence)):ws.bootstrap(args(self.root))
        self.assertFalse(self.root.exists())
        stages=list(self.base.glob('.workspace.initializing-*'));self.assertEqual(len(stages),1)
        self.assertTrue((stages[0]/'history.sqlite3').is_file());self.assertEqual(stages[0].stat().st_mode&0o777,0o700)
        preserved=tree(stages[0]);ws.bootstrap(args(self.root))
        self.assertEqual(tree(stages[0]),preserved);self.assertEqual(ws.status(self.root)['expected_assets'],3)

    def test_process_death_mid_initialization_allows_safe_new_attempt(self):
        code='import os,sys;from types import SimpleNamespace;sys.path.insert(0,sys.argv[1]);import vps_workspace as w;w.bootstrap_checkpoint=lambda phase,stage,target:os._exit(93) if phase=="initialized" else None;w.bootstrap(SimpleNamespace(workspace=sys.argv[2],mode="demo",node="example",profile=None,url=None,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,interval=60,acceptable=.9,investigate_below=.8))'
        r=subprocess.run([sys.executable,'-c',code,str(Path(ws.__file__).parent),str(self.root)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,93);self.assertFalse(self.root.exists())
        stages=list(self.base.glob('.workspace.initializing-*'));self.assertEqual(len(stages),1);before=tree(stages[0])
        ws.bootstrap(args(self.root));self.assertEqual(tree(stages[0]),before)
        self.assertTrue((self.root/'dashboard.html').is_file())

    def test_publish_is_all_or_nothing_and_never_overwrites_a_new_destination(self):
        def checkpoint(phase,stage,target):
            if phase=='prepared':
                target.mkdir();(target/'user.txt').write_text('user data')
        with mock.patch.object(ws,'bootstrap_checkpoint',checkpoint):
            with self.assertRaises(core.InvalidEvidence):ws.bootstrap(args(self.root))
        self.assertEqual((self.root/'user.txt').read_text(),'user data')
        self.assertFalse((self.root/'workspace.json').exists())

    def test_two_concurrent_initializations_publish_only_one(self):
        def attempt():
            try:return ws.bootstrap(args(self.root))
            except (ValueError,OSError):return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(ws.status(self.root)['stored_captures'],1)

    def test_success_contains_no_live_staging_path_and_no_temp_rename_debris(self):
        result=ws.bootstrap(args(self.root))
        self.assertEqual(Path(result['workspace']),self.root)
        self.assertFalse(list(self.base.glob('.workspace.initializing-*')))
        self.assertNotIn('.initializing-',(self.root/'dashboard.html').read_text())

    def test_demo_first_window_is_retained_once_when_retried_after_failure(self):
        with mock.patch.object(ws,'render',side_effect=OSError('fail')):
            with self.assertRaises((OSError,core.InvalidEvidence)):ws.bootstrap(args(self.root))
        ws.bootstrap(args(self.root));d=ws.status(self.root)
        self.assertEqual(d['stored_captures'],1);self.assertEqual(len(d['assets']),3)

    def test_retained_failed_stage_budget_requires_inspection_not_deletion(self):
        for _ in range(4):
            with mock.patch.object(ws,'render',side_effect=OSError('synthetic interruption')):
                with self.assertRaises(core.InvalidEvidence):ws.bootstrap(args(self.root))
        before={p.name:tree(p) for p in self.base.glob('.workspace.initializing-*')}
        with self.assertRaises(core.InvalidEvidence):ws.bootstrap(args(self.root))
        self.assertEqual(before,{p.name:tree(p) for p in self.base.glob('.workspace.initializing-*')})
        self.assertFalse(self.root.exists())

    def test_empty_preexisting_directory_is_never_adopted(self):
        self.root.mkdir()
        with self.assertRaises(core.InvalidEvidence):ws.bootstrap(args(self.root))
        self.assertEqual(list(self.root.iterdir()),[])

    def test_interrupted_transaction_keeps_the_original_database_and_journal_together(self):
        ws.bootstrap(args(self.root))
        with ws.database(self.root,True) as db:
            before=(db.execute('SELECT COUNT(*) FROM points').fetchone()[0],db.execute('SELECT hash FROM captures').fetchone()[0])
        code='import os,sqlite3,sys;d=sqlite3.connect(sys.argv[1]);d.execute("PRAGMA cache_size=2");d.execute("BEGIN IMMEDIATE");d.execute("DELETE FROM points");os._exit(91)'
        r=subprocess.run([sys.executable,'-c',code,str(self.root/'history.sqlite3')],capture_output=True,timeout=15)
        self.assertEqual(r.returncode,91);self.assertTrue((self.root/'history.sqlite3-journal').is_file())
        # SQLite, not a hand-written cleanup script, owns rollback recovery.
        with ws.database(self.root) as db:
            after=(db.execute('SELECT COUNT(*) FROM points').fetchone()[0],db.execute('SELECT hash FROM captures').fetchone()[0])
        self.assertEqual(before,after)

    def test_after_publish_sync_failure_names_the_existing_complete_workspace(self):
        real=ws.sync_directory
        def sync(path):
            if path==self.root.parent and self.root.is_dir():raise OSError('synthetic parent sync failure')
            return real(path)
        with mock.patch.object(ws,'sync_directory',sync):
            with self.assertRaises(core.InvalidEvidence) as error:ws.bootstrap(args(self.root))
        self.assertIn(str(self.root),str(error.exception))
        self.assertTrue((self.root/'history.sqlite3').is_file());self.assertTrue((self.root/'dashboard.html').is_file())
        self.assertEqual(ws.status(self.root)['stored_captures'],1)

    def test_initialization_failure_never_starts_a_network_read_or_worker(self):
        with mock.patch.object(core,'get_json') as net,mock.patch.object(subprocess,'Popen') as process:
            with mock.patch.object(ws,'render',side_effect=OSError('fail')):
                with self.assertRaises((OSError,core.InvalidEvidence)):ws.bootstrap(args(self.root))
        net.assert_not_called();process.assert_not_called()

class RuntimeBoundaryTest(unittest.TestCase):
    def setUp(self):
        if sys.platform!='linux':self.skipTest('managed Linux runtime')
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name).resolve();self.root=self.base/'workspace';self.runs=[]
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for run in self.runs:
            try:agent.stop(self.root,run,wait=8)
            except (ValueError,OSError):pass
        self.temp.cleanup()

    def start(self):
        a=args(self.root);a.approve_plan=agent.plan(a)['plan_sha256'];d=agent.start(a);self.runs.append(d['run_id']);return d

    def test_stop_needs_owned_run_identity_not_a_working_configuration(self):
        d=self.start();(self.root/'workspace.json').write_text('{invalid json')
        stopped=agent.stop(self.root,d['run_id'],wait=8)
        self.assertFalse(stopped['process_verified']);self.assertIn(stopped['state'],('STOPPED','FAILED','NEEDS_REVIEW'))
        self.assertEqual((self.root/'workspace.json').read_text(),'{invalid json')

    def test_agent_retries_the_original_approved_setup_after_interrupted_render(self):
        a=args(self.root);original=agent.plan(a)['plan_sha256'];a.approve_plan=original
        with mock.patch.object(ws,'render',side_effect=OSError('interrupted first render')):
            with self.assertRaises(core.InvalidEvidence):agent.start(a)
        self.assertFalse(self.root.exists());self.assertEqual(agent.plan(a)['plan_sha256'],original)
        run=agent.start(a);self.runs.append(run['run_id'])
        self.assertEqual(run['state'],'RUNNING');self.assertTrue(agent.verify_runtime(self.root)['http_verified'])
        self.assertEqual(ws.status(self.root)['stored_captures'],1)

    def test_source_update_stops_the_old_worker_before_more_collection(self):
        skill=self.base/'copy';shutil.copytree(core.ROOT,skill,ignore=shutil.ignore_patterns('__pycache__'))
        cli=skill/'scripts/vps_health.py'
        def command(*extra):
            return json.loads(subprocess.check_output([sys.executable,str(cli),*extra],text=True,timeout=15))
        opt=['--workspace',str(self.root),'--mode','demo','--duration-seconds','15']
        p=command('agent-plan',*opt);d=command('agent-start',*opt,'--approve-plan',p['plan_sha256']);self.runs.append(d['run_id'])
        before=ws.status(self.root)['stored_captures'];file=skill/'scripts/vps_ops.py';file.write_text(file.read_text()+'\n# synthetic source upgrade\n')
        limit=time.monotonic()+6
        while time.monotonic()<limit:
            current=agent.runtime_status(self.root)
            if not current['process_verified']:break
            time.sleep(.1)
        self.assertFalse(current['process_verified']);self.assertEqual(current['state'],'NEEDS_REVIEW')
        self.assertEqual(current['last_event'],'installed_source_changed');self.assertEqual(ws.status(self.root)['stored_captures'],before)

    def test_request_file_hardlink_is_not_silently_replaced(self):
        ws.bootstrap(args(self.root));agent.connection_request(self.root,'mail.read','Synthetic approved purpose')
        path=self.root/'.agent/requests.json';external=self.base/'linked';os.link(path,external);before=external.read_bytes()
        with self.assertRaises(core.InvalidEvidence):agent.connection_request(self.root,'mail.draft','Another synthetic purpose')
        self.assertEqual(external.read_bytes(),before)

class SnapshotReadTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.path=self.base/'status.json'
        core.save_json(self.path,{'version':1})

    def replacement(self,value=2):
        next_path=self.base/'next.json';core.save_json(next_path,{'version':value});os.replace(next_path,self.path)

    def test_replaced_path_metadata_retries_instead_of_rejecting_normal_atomic_writer(self):
        real=Path.lstat;observations=[]
        def lstat(path,*a,**k):
            if path==self.path and not observations:
                fd=os.open(path,os.O_RDONLY)
                try:
                    self.replacement();info=os.fstat(fd);observations.append(info.st_nlink);return info
                finally:os.close(fd)
            return real(path,*a,**k)
        with mock.patch.object(Path,'lstat',lstat):info=ws.private_file(self.path)
        self.assertEqual(observations,[0]);self.assertEqual(info.st_nlink,1)

    def test_descriptor_replaced_before_validation_reads_one_complete_new_record(self):
        real=os.fstat;seen=[]
        def fstat(fd):
            if not seen:
                self.replacement();seen.append(True)
            return real(fd)
        with mock.patch.object(os,'fstat',fstat):value=ws.read_private_json(self.path)
        self.assertEqual(value,{'version':2})

    def test_continuous_replacement_is_bounded_and_never_weakens_checks(self):
        real=os.fstat;count=[]
        def fstat(fd):
            count.append(1);self.replacement(len(count)+1);return real(fd)
        with mock.patch.object(os,'fstat',fstat):
            with self.assertRaises(core.InvalidEvidence):ws.read_private_json(self.path)
        self.assertEqual(len(count),3)

    def test_hardlinked_record_stays_refused(self):
        os.link(self.path,self.base/'alias.json');before=self.path.read_bytes()
        with self.assertRaises(core.InvalidEvidence):ws.read_private_json(self.path)
        self.assertEqual(self.path.read_bytes(),before)

    def test_missing_record_keeps_the_callers_default(self):
        self.path.unlink();sentinel={'not_managed':True}
        self.assertIs(agent._read(self.path,sentinel),sentinel)

    def test_oversized_runtime_record_is_refused_before_reading_it(self):
        self.path.write_bytes(b' '*(256*1024+1))
        with self.assertRaises(core.InvalidEvidence):agent._read(self.path)

    def test_exposed_record_is_not_repaired(self):
        self.path.chmod(0o644)
        with self.assertRaises(core.InvalidEvidence):ws.read_private_json(self.path)
        self.assertEqual(self.path.stat().st_mode&0o777,0o644)

    def test_invalid_json_stays_invalid_not_a_missing_runtime(self):
        self.path.write_text('{bad')
        with self.assertRaises(core.InvalidEvidence):agent._read(self.path,{'not_managed':True})

if __name__=='__main__':unittest.main()
