#!/usr/bin/env python3
"""Failure-first reproductions for the public export/verify workflow.

No runtime fix is present in this branch. Run this file explicitly; failures are
pending acceptance, not a claim that the existing full suite includes these cases.
All files/workspaces here are temporary and synthetic. No collector is started.
"""
from pathlib import Path
import hashlib
import json
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


def files(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}

class SummaryExportTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'observations';self.out=self.base/'summary'
        ws.bootstrap(SimpleNamespace(workspace=self.root,mode='demo',node='example',profile=None,url=None,
            loki_url=None,token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,investigate_below=.8))

    def test_existing_cli_can_verify_its_own_workspace_export_without_claiming_raw_replay(self):
        ws.export(self.root,self.out)
        result=subprocess.run([sys.executable,'-B','-S',core.__file__,'verify',str(self.out)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertEqual(value['integrity'],'PASS');self.assertNotEqual(value.get('replay'),'PASS')

    def test_summary_and_capture_index_use_one_read_transaction(self):
        original=ws.status;used=[]
        def checked(*args,**kwargs):
            db=kwargs.get('_read_db');self.assertIsNotNone(db);self.assertTrue(db.in_transaction);used.append(db)
            return original(*args,**kwargs)
        with mock.patch.object(ws,'status',side_effect=checked):ws.export(self.root,self.out)
        self.assertEqual(len(used),1)

    def test_capture_arriving_during_export_does_not_disagree_with_saved_summary(self):
        # WAL is confined to the disposable fixture. It permits the next writer
        # while a future coherent read transaction retains its original snapshot.
        with ws.database(self.root) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0],'wal')
        original=ws.status;cfg=ws.config_load(self.root)[1];called=[]
        def arrival(*args,**kwargs):
            value=original(*args,**kwargs)
            if not called:
                called.append(True);observed=time.time()+301
                ws.ingest(self.root,cfg,ws.demo_seed(cfg,observed),observed)
            return value
        with mock.patch.object(ws,'status',side_effect=arrival):ws.export(self.root,self.out)
        summary=core.read_json(self.out/'status.json');index=core.read_json(self.out/'capture-index.json')
        self.assertEqual(len(index),summary['stored_captures'])
        self.assertEqual(sum(row['bytes'] for row in index),summary['stored_bytes'])

    def test_changed_configuration_is_not_mixed_into_an_export(self):
        original=ws.status
        def changed(*args,**kwargs):
            result=original(*args,**kwargs);result['configuration_sha256']='f'*64;return result
        with mock.patch.object(ws,'status',side_effect=changed):
            with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        self.assertFalse(self.out.exists())

    def test_render_failure_does_not_publish_a_success_shaped_partial_destination(self):
        with mock.patch.object(ws,'page',side_effect=core.InvalidEvidence('synthetic render interruption')):
            with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        self.assertFalse(self.out.exists())

    def test_export_cannot_add_derived_files_inside_its_observation_workspace(self):
        before=files(self.root)
        with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.root/'nested-export')
        self.assertEqual(files(self.root),before)

    def test_existing_destination_is_rejected_before_a_status_read(self):
        self.out.mkdir()
        with mock.patch.object(ws,'status') as status:
            with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        status.assert_not_called()

    def test_existing_export_file_checksums_are_real_and_reads_do_not_collect(self):
        before=files(self.root)
        with mock.patch.object(core,'get_json') as network,mock.patch.object(core,'cpu_snapshot') as sample:
            ws.export(self.root,self.out)
        network.assert_not_called();sample.assert_not_called();self.assertEqual(files(self.root),before)
        manifest=core.read_json(self.out/'manifest.json')
        for name,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((self.out/name).read_bytes()).hexdigest(),digest)

    def test_original_raw_capture_bundle_replay_still_works(self):
        out=self.base/'raw';core.report(core.read_json(core.ROOT/'assets/demo-capture.json'),out)
        result=subprocess.run([sys.executable,'-B','-S',core.__file__,'verify',str(out)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['replay'],'PASS')

if __name__=='__main__':unittest.main()
