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

    def test_repeat_start_attaches_without_duplicate_or_new_budget(self):
        a=self.begin();b=self.begin(mode='auto')
        self.assertEqual(a['run_id'],b['run_id']);self.assertEqual(a['pid'],b['pid'])
        self.assertEqual(a['deadline_utc'],b['deadline_utc'])

    def test_changed_request_does_not_replace_active_run(self):
        original=self.begin()
        a=args(self.root,mode='auto',duration_seconds=30);a.approve_plan=agent.plan(a)['plan_sha256']
        with self.assertRaises(core.InvalidEvidence):agent.start(a)
        self.assertEqual(agent.runtime_status(self.root)['run_id'],original['run_id'])

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
