#!/usr/bin/env python3
"""The evaluator checks observable artifacts, not a self-reported agent success."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).parent))
import package_release as package
import client_journey as journey

ROOT=Path(__file__).resolve().parents[3]

class JourneyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        skill=ROOT/'skills/vps-health'
        files={p.relative_to(skill).as_posix():p.read_bytes() for p in skill.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        files['LICENSE']=(ROOT/'LICENSE').read_bytes()
        cls.raw=package.zip_payload(files,'vps-health/')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'trial';self.run=None
        self.archive=self.base/'vps-health-v0.7.1.zip';self.archive.write_bytes(self.raw)
        self.manifest=self.base/'manifest.json'
        self.manifest.write_text(json.dumps({'schema':'g-skills.skill-release.v1','skill':'vps-health','commit':'0'*40,
            'files':{self.archive.name:{'bytes':len(self.raw),'sha256':journey.digest(self.raw)}}}))
        journey.prepare(self.archive,self.manifest,self.root)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.run:
            try:self.cli('agent-stop','--run-id',self.run)
            except (subprocess.SubprocessError,ValueError):pass
        self.temp.cleanup()

    def cli(self,command,*options):
        return json.loads(subprocess.check_output([sys.executable,str(self.root/'vps-health/scripts/vps_health.py'),
            command,'--workspace',str(self.root/'workspace'),*options],text=True,timeout=20))

    def start(self):
        if sys.platform!='linux':self.skipTest('actual owned runtime qualifies Linux')
        params=['--mode','demo','--duration-seconds','30']
        p=self.cli('agent-plan',*params);r=self.cli('agent-start',*params,'--approve-plan',p['plan_sha256']);self.run=r['run_id'];return r

    def test_preparation_does_not_start_or_claim_a_client(self):
        self.assertFalse((self.root/'workspace').exists())
        self.assertFalse(journey.load(self.root/'trial.json')['native_client_verified'])
        self.assertIn('routine steps yourself',(self.root/'PROMPT.md').read_text())
        self.assertIn(str(self.root/'vps-health/SKILL.md'),(self.root/'PROMPT.md').read_text())
        self.assertIn('do not search the whole host',(self.root/'PROMPT.md').read_text())

    def test_success_message_without_runtime_cannot_pass(self):
        (self.root/'agent-result.json').write_text(json.dumps({'success':True,'client':'codex'}))
        with self.assertRaises((ValueError,OSError)):journey.check(self.root,'running')

    def test_changed_installed_source_is_rejected_before_execution(self):
        p=self.root/'vps-health/scripts/vps_agent.py';p.write_text(p.read_text()+'\n# changed\n')
        with self.assertRaises(ValueError):journey.inspect_contract(self.root)

    def test_extra_installed_script_is_not_ignored(self):
        (self.root/'vps-health/scripts/unreviewed.py').write_text('print("not part of release")')
        with self.assertRaises(ValueError):journey.inspect_contract(self.root)

    def test_archive_hash_mismatch_never_creates_trial(self):
        self.archive.write_bytes(self.raw+b'tampered')
        with self.assertRaises(ValueError):journey.prepare(self.archive,self.manifest,self.base/'other')
        self.assertFalse((self.base/'other').exists())

    def test_existing_destination_is_not_overwritten(self):
        before=(self.root/'trial.json').read_bytes()
        with self.assertRaises(ValueError):journey.prepare(self.archive,self.manifest,self.root)
        self.assertEqual(before,(self.root/'trial.json').read_bytes())

    def test_real_running_and_stopped_proof_requires_same_retained_evidence(self):
        self.start();first=journey.check(self.root,'running');self.assertEqual(first['state'],'ARTIFACT_VERIFIED')
        self.assertFalse(first['native_client_verified']);self.assertTrue(first['semantic_review_required'])
        receipt=self.base/'running.json';journey.private_write(receipt,first)
        self.cli('agent-stop','--run-id',self.run)
        last=journey.check(self.root,'stopped',receipt)
        self.assertEqual(first['evidence'],last['evidence']);self.assertEqual(first['run_id'],last['run_id'])
        self.assertFalse(last['publication_authorized'])

    def test_stop_without_prior_observation_does_not_pass(self):
        self.start();self.cli('agent-stop','--run-id',self.run)
        with self.assertRaises(ValueError):journey.check(self.root,'stopped')

    def test_a_new_run_cannot_replace_the_original_continuation(self):
        self.start();proof=journey.check(self.root,'running');receipt=self.base/'running.json';journey.private_write(receipt,proof)
        self.cli('agent-stop','--run-id',self.run);self.start();self.cli('agent-stop','--run-id',self.run)
        with self.assertRaises(ValueError):journey.check(self.root,'stopped',receipt)

    def test_readback_cannot_redirect_to_another_service(self):
        with self.assertRaises(ValueError):
            journey.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://example.invalid/private')

    def test_symbolic_workspace_is_not_followed(self):
        outside=self.base/'outside';outside.mkdir();(self.root/'workspace').symlink_to(outside)
        with self.assertRaises(ValueError):journey.inspect_contract(self.root)

    def test_archive_limit_is_checked_before_reading_whole_file(self):
        with mock.patch.object(journey,'MAX_BYTES',1):
            with self.assertRaises(ValueError):journey.prepare(self.archive,self.manifest,self.base/'too-large')
        self.assertFalse((self.base/'too-large').exists())

    def test_receipt_is_private_and_does_not_overwrite(self):
        p=self.base/'result.json';journey.private_write(p,{'state':'example'})
        if os.name=='posix':self.assertEqual(p.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):journey.private_write(p,{})

if __name__=='__main__':unittest.main()
