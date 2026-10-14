#!/usr/bin/env python3
"""Real process/HTTP contracts for agent-owned observation, not a model eval."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
import vps_agent as agent


def args(path,**changes):
    base=dict(workspace=path,mode='demo',node='example-node',profile=None,url=None,loki_url=None,
              token_env=None,loki_token_env=None,allow_http=False,interval=60,acceptable=.9,
              investigate_below=.8,provider='unknown',plan=None,duration_seconds=15,port=0,
              approve_plan=None,client='generic')
    return SimpleNamespace(**{**base,**changes})

class PlanTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'private'

    def test_plan_reads_only_and_binds_source_scope(self):
        result=agent.plan(args(self.root))
        self.assertTrue(result['ready']);self.assertFalse(self.root.exists())
        self.assertFalse(result['external_actions_authorized'])
        self.assertEqual(result['plan_sha256'],core.digest(result['intent']))
        self.assertIn('source',result['intent'])

    def test_new_auto_mode_requires_target_not_a_guess(self):
        p=agent.plan(args(self.root,mode='auto'))
        self.assertFalse(p['ready']);self.assertEqual(p['needs'][0]['code'],'target_scope')
        self.assertFalse(self.root.exists())

    def test_wrong_approval_does_not_create_workspace(self):
        with self.assertRaises(core.InvalidEvidence):agent.start(args(self.root,approve_plan='a'*64))
        self.assertFalse(self.root.exists())

    def test_plan_change_requires_new_scope_hash(self):
        p=agent.plan(args(self.root))
        with self.assertRaises(core.InvalidEvidence):agent.start(args(self.root,duration_seconds=30,approve_plan=p['plan_sha256']))
        self.assertFalse(self.root.exists())

    def test_existing_workspace_is_reused_without_modification(self):
        ws.bootstrap(args(self.root))
        before=(self.root/'workspace.json').read_bytes()
        p=agent.plan(args(self.root,mode='auto'))
        self.assertTrue(p['ready']);self.assertEqual(p['operation'],'reuse_workspace')
        self.assertEqual(before,(self.root/'workspace.json').read_bytes())

    def test_existing_different_mode_refused(self):
        ws.bootstrap(args(self.root))
        with self.assertRaises(core.InvalidEvidence):agent.plan(args(self.root,mode='local'))

    def test_missing_named_credentials_block_before_state_changes(self):
        profile=Path(self.temp.name)/'profile.json'
        profile.write_text(json.dumps({'schema':'g-skills.vps-profile.v1','assets':[{'id':'example','instance':'example.invalid:9100'}]}))
        with mock.patch.dict(os.environ,{},clear=True):
            p=agent.plan(args(self.root,mode='prometheus',profile=profile,url='https://metrics.example.invalid',token_env='EXAMPLE_TOKEN'))
        self.assertFalse(p['ready']);self.assertEqual(p['needs'][0]['code'],'credential_variable')
        self.assertFalse(self.root.exists())

    def test_plan_never_includes_secret_value(self):
        with mock.patch.dict(os.environ,{'EXAMPLE_TOKEN':'do-not-copy-secret'}):
            p=agent.plan(args(self.root))
        self.assertNotIn('do-not-copy-secret',json.dumps(p))

    def test_plan_duration_port_and_platform_bounds(self):
        for values in ({'duration_seconds':0},{'duration_seconds':7*86400+1},{'port':-1}):
            with self.subTest(values=values),self.assertRaises(core.InvalidEvidence):agent.plan(args(self.root,**values))
        with mock.patch.object(agent.sys,'platform','win32'):
            p=agent.plan(args(self.root))
            self.assertFalse(p['ready']);self.assertEqual(p['needs'][0]['code'],'runtime_platform')

    def test_state_read_does_not_create_missing_directory(self):
        d=agent.runtime_status(self.root)
        self.assertEqual(d['state'],'NOT_MANAGED');self.assertFalse(self.root.exists())

class ExistingMetricsRouteTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'private'
        self.profile=Path(self.temp.name)/'profile.json'
        self.profile.write_text(json.dumps({'schema':'g-skills.vps-profile.v1','assets':[
            {'id':'example-node','instance':'example.invalid:9100','provider':'other','epoch':'initial'}]}))
        self.a=args(self.root,mode='prometheus',profile=self.profile,url='https://metrics.example.invalid',
                    loki_url='https://logs.example.invalid')

    def test_identical_profile_and_endpoints_preserve_retry_plan(self):
        first=agent.plan(self.a)
        ws.bootstrap(self.a)
        before=(self.root/'workspace.json').read_bytes()
        again=agent.plan(self.a)
        self.assertEqual(first['plan_sha256'],again['plan_sha256'])
        self.assertEqual(before,(self.root/'workspace.json').read_bytes())

    def test_auto_resume_accepts_matching_explicit_route(self):
        ws.bootstrap(self.a)
        self.a.mode='auto'
        self.assertTrue(agent.plan(self.a)['ready'])

    def test_changed_endpoint_refuses_without_altering_workspace(self):
        ws.bootstrap(self.a);before=(self.root/'workspace.json').read_bytes()
        self.a.url='https://different.example.invalid'
        with self.assertRaises(core.InvalidEvidence):agent.plan(self.a)
        self.assertEqual(before,(self.root/'workspace.json').read_bytes())

    def test_changed_inventory_refuses_without_altering_workspace(self):
        ws.bootstrap(self.a);before=(self.root/'workspace.json').read_bytes()
        self.profile.write_text(json.dumps({'schema':'g-skills.vps-profile.v1','assets':[
            {'id':'other-node','instance':'other.invalid:9100'}]}))
        with self.assertRaises(core.InvalidEvidence):agent.plan(self.a)
        self.assertEqual(before,(self.root/'workspace.json').read_bytes())

    def test_omitted_route_uses_retained_config_without_original_profile_file(self):
        ws.bootstrap(self.a);self.profile.unlink()
        self.assertTrue(agent.plan(args(self.root,mode='auto'))['ready'])

    def test_different_credential_variable_does_not_silently_use_original(self):
        ws.bootstrap(self.a);self.a.token_env='DIFFERENT_VPS_TOKEN'
        with mock.patch.dict(os.environ,{'DIFFERENT_VPS_TOKEN':'not-a-real-token'}):
            with self.assertRaises(core.InvalidEvidence):agent.plan(self.a)

class RuntimeTest(unittest.TestCase):
    def setUp(self):
        if sys.platform!='linux':self.skipTest('managed worker currently qualifies Linux only')
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'private';self.runs=[]
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for run in self.runs:
            try:agent.stop(self.root,run,wait=8)
            except (ValueError,OSError):pass
        self.temp.cleanup()

    def begin(self,**changes):
        a=args(self.root,**changes);p=agent.plan(a);self.assertTrue(p['ready'],p)
        a.approve_plan=p['plan_sha256'];d=agent.start(a);self.runs.append(d['run_id'])
        return d

    def test_real_detached_viewer_has_verified_identity_and_handoff(self):
        d=self.begin()
        self.assertTrue(d['process_verified']);self.assertEqual(d['state'],'RUNNING')
        with urllib.request.urlopen(d['dashboard_url']+'api/status',timeout=5) as res:value=json.load(res)
        self.assertTrue(value['synthetic']);self.assertEqual(value['agent_runtime']['run_id'],d['run_id'])
        self.assertTrue(value['agent_runtime']['process_verified'])
        self.assertTrue((self.root/'HANDOFF.md').is_file())
        self.assertNotIn('NOT_MANAGED',(self.root/'HANDOFF.md').read_text())

    def test_concurrent_same_plan_starts_attach_to_one_worker(self):
        import concurrent.futures
        ws.bootstrap(args(self.root))
        a=args(self.root,mode='auto');a.approve_plan=agent.plan(a)['plan_sha256']
        results=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(agent.start,copy.copy(a)) for _ in range(2)]
            for future in futures:
                try:
                    item=future.result(timeout=15);self.runs.append(item['run_id']);results.append(item)
                except Exception as exc:results.append(exc)
        self.assertTrue(all(isinstance(item,dict) for item in results),repr(results))
        self.assertEqual(results[0]['run_id'],results[1]['run_id'])
        self.assertEqual(results[0]['pid'],results[1]['pid'])

    def test_repeat_start_attaches_without_duplicate_or_new_budget(self):
        a=self.begin();b=self.begin(mode='auto')
        self.assertEqual(a['run_id'],b['run_id']);self.assertEqual(a['pid'],b['pid'])
        self.assertEqual(a['deadline_utc'],b['deadline_utc'])

    def test_changed_request_does_not_replace_active_run(self):
        original=self.begin()
        a=args(self.root,mode='auto',duration_seconds=30);a.approve_plan=agent.plan(a)['plan_sha256']
        with self.assertRaises(core.InvalidEvidence):agent.start(a)
        self.assertEqual(agent.runtime_status(self.root)['run_id'],original['run_id'])

    def test_stopped_run_cannot_silently_renew_the_old_approval(self):
        original_args=args(self.root);old=agent.plan(original_args)['plan_sha256']
        d=self.begin();agent.stop(self.root,d['run_id'],wait=8)
        original_args.approve_plan=old
        with self.assertRaises(core.InvalidEvidence):
            again=agent.start(original_args);self.runs.append(again['run_id'])
        new=agent.plan(args(self.root,mode='auto'))
        self.assertNotEqual(new['plan_sha256'],old)
        self.assertEqual(new['intent']['predecessor_run'],d['run_id'])

    def test_stop_is_scoped_and_preserves_observations(self):
        d=self.begin();before=ws.status(self.root)['stored_captures']
        with self.assertRaises(core.InvalidEvidence):agent.stop(self.root,'0'*32,wait=0)
        self.assertTrue(agent.runtime_status(self.root)['process_verified'])
        stopped=agent.stop(self.root,d['run_id'],wait=8)
        self.assertEqual(stopped['state'],'STOPPED');self.assertFalse(stopped['process_verified'])
        self.assertEqual(ws.status(self.root)['stored_captures'],before)
        self.assertEqual(agent.stop(self.root,d['run_id'],wait=0)['state'],'STOPPED')

    def test_natural_budget_completion_is_not_a_three_day_verdict(self):
        d=self.begin(duration_seconds=2)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            d=agent.runtime_status(self.root)
            if d['state']=='COMPLETED' and not d['process_verified']:break
            time.sleep(.1)
        self.assertEqual(d['state'],'COMPLETED');self.assertFalse(d['process_verified'])
        self.assertFalse(d['evidence_ready'])

    def test_abrupt_owned_worker_exit_is_detected_and_recovery_preserves_history(self):
        import signal
        d=self.begin();saved=core.read_json(self.root/'.agent/status.json')
        self.assertEqual(agent.process_identity(d['pid']),saved['process_identity'])
        before=ws.status(self.root)['stored_captures']
        # Test fixture fault only: this PID was just spawned by this test and
        # its kernel identity was verified. Product stop never sends a signal.
        os.kill(d['pid'],signal.SIGKILL)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            state=agent.runtime_status(self.root)
            if state['state']=='ORPHANED':break
            time.sleep(.05)
        self.assertEqual(state['state'],'ORPHANED');self.assertFalse(state['process_verified'])
        resumed=self.begin(mode='auto')
        self.assertNotEqual(resumed['run_id'],d['run_id'])
        self.assertEqual(ws.status(self.root)['stored_captures'],before)

    def test_occupied_requested_port_fails_without_claiming_a_running_viewer(self):
        import socket
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0));occupied.listen()
            d=self.begin(port=occupied.getsockname()[1])
            self.assertEqual(d['state'],'FAILED')
            self.assertIsNone(d['dashboard_url'])
            self.assertEqual(d['last_event'],'runtime_failed')

    def test_foreign_pid_is_never_signalled(self):
        d=self.begin();agent.stop(self.root,d['run_id'],wait=8)
        path=self.root/'.agent/status.json';doc=core.read_json(path)
        doc.update(state='RUNNING',pid=os.getpid(),process_identity={'boot':'fake','start':'fake'})
        ws.atomic(path,core.canonical(doc))
        with mock.patch.object(os,'kill') as signal:
            state=agent.runtime_status(self.root)
            self.assertEqual(state['state'],'ORPHANED')
            agent.stop(self.root,d['run_id'],wait=0)
        signal.assert_not_called()

    def test_symlink_state_is_refused(self):
        ws.bootstrap(args(self.root));folder=self.root/'.agent';folder.mkdir()
        target=Path(self.temp.name)/'outside';target.write_text('{}');(folder/'status.json').symlink_to(target)
        with self.assertRaises(core.InvalidEvidence):agent.runtime_status(self.root)
        self.assertEqual(target.read_text(),'{}')

    def test_credential_values_are_not_in_run_files(self):
        with mock.patch.dict(os.environ,{'NOT_NEEDED_SECRET':'do-not-store-actual-value'}):self.begin()
        for p in (self.root/'.agent').glob('*'):
            if p.is_file():self.assertNotIn('do-not-store-actual-value',p.read_text(errors='replace'))

    def test_an_existing_collector_lock_cannot_be_bypassed_by_an_expired_lease(self):
        ws.bootstrap(args(self.root,mode='local'))
        with agent.collection_lock(self.root):
            a=args(self.root,mode='auto');a.approve_plan=agent.plan(a)['plan_sha256']
            with self.assertRaises(core.InvalidEvidence):agent.start(a)
        self.assertFalse(agent.runtime_status(self.root)['process_verified'])

    def test_actual_launching_cli_exits_while_its_worker_remains_owned(self):
        cli=[sys.executable,str(Path(agent.__file__).with_name('vps_health.py'))]
        options=['--workspace',str(self.root),'--mode','demo','--duration-seconds','15']
        p=json.loads(subprocess.check_output([*cli,'agent-plan',*options],text=True,timeout=10))
        d=json.loads(subprocess.check_output([*cli,'agent-start',*options,'--approve-plan',p['plan_sha256']],text=True,timeout=12))
        self.runs.append(d['run_id'])
        self.assertEqual(d['state'],'RUNNING')
        self.assertTrue(agent.runtime_status(self.root)['process_verified'])
        with urllib.request.urlopen(d['dashboard_url'],timeout=5) as response:
            self.assertIn('Agent',response.read().decode())
        self.assertEqual(agent.stop(self.root,d['run_id'],wait=8)['state'],'STOPPED')

    def test_new_agent_can_resume_using_cli_without_restarting_the_worker(self):
        d=self.begin()
        command=[sys.executable,str(Path(agent.__file__).with_name('vps_health.py')),'agent-status','--workspace',str(self.root)]
        new=json.loads(subprocess.check_output(command,text=True,timeout=10))
        self.assertEqual(new['run_id'],d['run_id']);self.assertTrue(new['process_verified'])
        self.assertEqual(new['cycles'],0)  # demo viewer is not a collector

    def test_real_local_first_tick_and_manual_overlap_guard(self):
        d=self.begin(mode='local')
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if ws.status(self.root)['stored_captures']:break
            time.sleep(.1)
        self.assertGreaterEqual(ws.status(self.root)['stored_captures'],1)
        with self.assertRaises(core.InvalidEvidence):ws.collect(self.root)
        self.assertEqual(agent.runtime_status(self.root)['run_id'],d['run_id'])

    def test_current_config_change_stops_instead_of_collecting_unapproved_target(self):
        d=self.begin();cfg=core.read_json(self.root/'workspace.json');cfg['policy']['acceptable_ratio']=.92
        ws.atomic(self.root/'workspace.json',core.canonical(cfg))
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            current=agent.runtime_status(self.root)
            if current['state']=='NEEDS_REVIEW' and not current['process_verified']:break
            time.sleep(.1)
        self.assertEqual(current['state'],'NEEDS_REVIEW');self.assertFalse(current['process_verified'])

class ConnectorRequestTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'private';ws.bootstrap(args(self.root))

    def test_request_records_need_not_access_or_permission(self):
        d=agent.connection_request(self.root,'mail.draft','Create the explicitly requested review draft','claude-code')
        self.assertEqual(d['state'],'NEEDS_CONNECTION')
        self.assertFalse(d['connected']);self.assertFalse(d['send_authorized'])
        self.assertEqual(d['required_capability'],'mail.draft')
        self.assertIn('tool',d['agent_next_step'].lower())
        self.assertTrue((self.root/'HANDOFF.md').is_file())

    def test_pending_request_is_visible_without_a_worker(self):
        request=agent.connection_request(self.root,'mail.read','Find only the approved ticket','generic')
        state=agent.runtime_status(self.root)
        self.assertEqual(state['state'],'NOT_MANAGED')
        self.assertEqual(state['requests'][0]['id'],request['id'])
        self.assertEqual(state['agent_next_action'],'resolve_host_capability')

    def test_host_capability_receipt_is_not_send_approval(self):
        request=agent.connection_request(self.root,'mail.send','User asks to inspect a send operation','codex')
        d=agent.resolve_request(self.root,request['id'],'available','gmail.send_email','tool-result-42')
        self.assertEqual(d['state'],'HOST_REPORTED_AVAILABLE')
        self.assertFalse(d['send_authorized']);self.assertTrue(d['recheck_in_current_session'])
        self.assertEqual(agent.runtime_status(self.root)['requests'][0]['state'],d['state'])

    def test_connection_decline_is_recorded_not_retried_as_approval(self):
        r=agent.connection_request(self.root,'mail.read','Approved thread investigation','claude-code')
        d=agent.resolve_request(self.root,r['id'],'declined',None,None)
        self.assertEqual(d['state'],'DECLINED');self.assertFalse(d['connected'])
        self.assertEqual(agent.connection_request(self.root,'mail.read','Approved thread investigation','claude-code')['state'],'DECLINED')

    def test_connector_receipt_rejects_secret_bearing_urls(self):
        r=agent.connection_request(self.root,'mail.draft','Approved local draft','generic')
        with self.assertRaises(core.InvalidEvidence):agent.resolve_request(self.root,r['id'],'available','gmail.draft','https://example.invalid/?token=secret')

    def test_repeated_request_is_idempotent_and_distinct_from_send(self):
        a=agent.connection_request(self.root,'mail.draft','User approved a draft','codex')
        b=agent.connection_request(self.root,'mail.draft','User approved a draft','codex')
        c=agent.connection_request(self.root,'mail.send','User asks to review a send','codex')
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['id'],c['id'])
        self.assertFalse(c['send_authorized'])

    def test_request_does_not_install_fetch_or_export_credentials(self):
        with mock.patch.object(subprocess,'Popen') as proc,mock.patch.object(core,'get_json') as net:
            agent.connection_request(self.root,'mail.read','Find the authorized support thread','generic')
        proc.assert_not_called();net.assert_not_called()

    def test_unsupported_capability_is_not_a_shell_escape(self):
        with self.assertRaises(core.InvalidEvidence):agent.connection_request(self.root,'sh -c whoami','test','generic')

if __name__=='__main__':unittest.main()
