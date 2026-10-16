#!/usr/bin/env python3
"""The real workspace-summary round trip, coherent capture arrivals and recovery.

The original nine cases were retained from the failure-first branch. All test
workspaces are synthetic; verification neither replays absent raw captures nor
executes the exported HTML. Existing raw-capture replay remains a separate path.
"""
from pathlib import Path
import hashlib
import copy
import os
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

    def exported(self):
        ws.export(self.root,self.out)
        return self.out

    def rehash(self,name):
        manifest=core.read_json(self.out/'manifest.json')
        manifest['files'][name]=hashlib.sha256((self.out/name).read_bytes()).hexdigest()
        ws.atomic(self.out/'manifest.json',core.canonical(manifest))

    def test_summary_verdict_separates_integrity_replay_and_attestation(self):
        self.exported();result=ws.verify_export(self.out)
        self.assertEqual(result['artifact_kind'],'workspace-summary')
        self.assertEqual(result['integrity'],'PASS');self.assertEqual(result['snapshot_receipt'],'MATCHES_PAYLOAD')
        self.assertEqual(result['replay'],'NOT_AVAILABLE');self.assertEqual(result['subjects'],3)
        for key in ('raw_data_included','measurements_recomputed','independent_attestation','content_safety_certified',
                    'provider_cause_proven','service_health_verified','contact_authorized'):
            self.assertIs(result[key],False,key)

    def test_failed_stage_is_preserved_and_the_same_target_can_be_retried(self):
        with mock.patch.object(ws,'page',side_effect=ValueError('synthetic failed render')):
            with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        self.assertFalse(self.out.exists());stages=list(self.base.glob('.summary.exporting-*'))
        self.assertEqual(len(stages),1);before=files(stages[0])
        self.assertTrue((stages[0]/'status.json').is_file());self.assertEqual(stages[0].stat().st_mode&0o777,0o700)
        ws.export(self.root,self.out);self.assertEqual(files(stages[0]),before)
        self.assertEqual(ws.verify_export(self.out)['integrity'],'PASS')

    def test_failed_stages_remain_bounded_instead_of_being_deleted(self):
        for _ in range(4):
            with mock.patch.object(ws,'page',side_effect=ValueError('synthetic render failure')):
                with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        before={p.name:files(p) for p in self.base.glob('.summary.exporting-*')}
        with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        self.assertEqual(before,{p.name:files(p) for p in self.base.glob('.summary.exporting-*')})
        self.assertFalse(self.out.exists())

    def test_extra_files_are_not_silently_included_or_ignored(self):
        self.exported();p=self.out/'unrelated-private.txt';p.write_text('synthetic unrelated data')
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)
        self.assertEqual(p.read_text(),'synthetic unrelated data')

    def test_changed_and_missing_bytes_do_not_verify(self):
        self.exported();p=self.out/'report.md';original=p.read_bytes();ws.atomic(p,b'changed')
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)
        ws.atomic(p,original);self.assertEqual(ws.verify_export(self.out)['integrity'],'PASS')
        p.unlink()
        with self.assertRaises((OSError,core.InvalidEvidence)):ws.verify_export(self.out)

    def test_symbolic_and_hardlinked_payloads_are_refused_untouched(self):
        self.exported();p=self.out/'report.md';outside=self.base/'unchanged';outside.write_bytes(p.read_bytes());before=outside.read_bytes()
        p.unlink();p.symlink_to(outside)
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)
        self.assertTrue(p.is_symlink());p.unlink();os.link(outside,p)
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)
        self.assertEqual(outside.read_bytes(),before)

    def test_outside_manifest_paths_are_refused_before_reading_them(self):
        self.exported();manifest=core.read_json(self.out/'manifest.json');manifest['files']['../outside']='a'*64
        ws.atomic(self.out/'manifest.json',core.canonical(manifest))
        with mock.patch.object(core,'read_bytes') as reader:
            with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)
        reader.assert_not_called()

    def test_old_summary_manifests_have_no_invented_snapshot_receipt(self):
        self.exported();manifest=core.read_json(self.out/'manifest.json')
        ws.atomic(self.out/'manifest.json',core.canonical({key:manifest[key] for key in ('schema','files','note')}))
        result=ws.verify_export(self.out)
        self.assertEqual(result['integrity'],'PASS');self.assertEqual(result['snapshot_receipt'],'NOT_RECORDED')
        self.assertEqual(result['replay'],'NOT_AVAILABLE')

    def test_mismatching_recorded_snapshot_is_not_accepted(self):
        self.exported();m=core.read_json(self.out/'manifest.json');m['snapshot']['capture_batches']=42
        ws.atomic(self.out/'manifest.json',core.canonical(m))
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)

    def test_rehashed_index_must_match_the_saved_observation_counts(self):
        self.exported();p=self.out/'capture-index.json';rows=core.read_json(p);rows.append(copy.deepcopy(rows[0]))
        ws.atomic(p,core.canonical(rows));self.rehash(p.name)
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)

    def test_rehashed_payload_cannot_grant_provider_action(self):
        self.exported();p=self.out/'status.json';data=core.read_json(p);data['contact_provider']=True
        ws.atomic(p,core.canonical(data));self.rehash(p.name)
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)

    def test_manifest_cannot_relabel_absent_raw_measurements_as_present(self):
        self.exported();m=core.read_json(self.out/'manifest.json');m['raw_data_included']=True
        ws.atomic(self.out/'manifest.json',core.canonical(m))
        with self.assertRaises(core.InvalidEvidence):ws.verify_export(self.out)

    def test_verification_never_executes_html_or_rebuilds_a_different_version(self):
        self.exported();p=self.out/'dashboard.html';ws.atomic(p,b'<script>throw Error("never execute a verification input")</script>');self.rehash(p.name)
        before=files(self.out)
        with mock.patch.object(ws,'page') as page,mock.patch.object(ws,'status') as status,mock.patch.object(ws,'markdown_summary') as markdown:
            result=ws.verify_export(self.out)
        page.assert_not_called();status.assert_not_called();markdown.assert_not_called()
        self.assertEqual(files(self.out),before);self.assertEqual(result['integrity'],'PASS')
        self.assertFalse(result['content_safety_certified'])

    def test_export_permissions_do_not_inherit_a_permissive_umask(self):
        old=os.umask(0)
        try:self.exported()
        finally:os.umask(old)
        self.assertEqual(self.out.stat().st_mode&0o777,0o700)
        self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in self.out.iterdir()))

    def test_output_must_be_outside_a_resolved_installation(self):
        installed=self.base/'synthetic-installed';installed.mkdir()
        alias=self.base/'alias';alias.symlink_to(installed,target_is_directory=True)
        with mock.patch.object(core,'ROOT',installed):
            with self.assertRaises(core.InvalidEvidence):ws.export(self.root,alias/'export')
        self.assertEqual(list(installed.iterdir()),[])

    def test_oversized_index_aborts_before_publishing_output(self):
        with mock.patch.object(ws,'MAX_SUMMARY_BATCHES',0):
            with self.assertRaises(core.InvalidEvidence):ws.export(self.root,self.out)
        self.assertFalse(self.out.exists())

if __name__=='__main__':unittest.main()
