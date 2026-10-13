#!/usr/bin/env python3
"""A second unrelated skill proves package/version/dependency isolation."""
from pathlib import Path
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
import collection
import package_release as package

class CollectionPackageTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        (self.root/'LICENSE').write_text('MIT\nSynthetic release fixture.\n')
        for name in ('meeting-notes','writing-review'):collection.scaffold(self.root,name,'Synthetic unrelated skill')
        for name,version in (('meeting-notes','1.2.3'),('writing-review','4.5.6')):
            path=self.root/'skills'/name/'skill.json';d=json.loads(path.read_text());d.update(status='ready',version=version);path.write_text(json.dumps(d))
        subprocess.run(['git','init','-q'],cwd=self.root,check=True)
        subprocess.run(['git','add','.'],cwd=self.root,check=True)
        subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Synthetic two-skill fixture'],cwd=self.root,check=True)

    def test_only_selected_skill_is_packaged_and_owns_version(self):
        out=Path(self.temp.name)/'release';d=package.build('HEAD',out,'writing-review',self.root)
        self.assertEqual(d['version'],'4.5.6');self.assertEqual(d['tag'],'writing-review/v4.5.6')
        self.assertEqual(set(d['files']),{'writing-review-v4.5.6.zip'})
        with zipfile.ZipFile(out/'writing-review-v4.5.6.zip') as archive:
            self.assertTrue(all(name.startswith('writing-review/') for name in archive.namelist()))
            self.assertFalse(any('meeting-notes' in name or 'vps' in name or 'tools/' in name for name in archive.namelist()))

    def test_uncommitted_mutations_do_not_enter_a_release(self):
        p=self.root/'skills/meeting-notes/SKILL.md';p.write_text('uncommitted change')
        out=Path(self.temp.name)/'release';package.build('HEAD',out,'meeting-notes',self.root)
        with zipfile.ZipFile(out/'meeting-notes-v1.2.3.zip') as z:self.assertNotIn(b'uncommitted',z.read('meeting-notes/SKILL.md'))

    def test_missing_selection_never_defaults_to_first_skill(self):
        with self.assertRaises(ValueError):package.build('HEAD',Path(self.temp.name)/'bad','absent',self.root)

    def test_draft_not_releasable(self):
        p=self.root/'skills/meeting-notes/skill.json';d=json.loads(p.read_text());d['status']='draft';p.write_text(json.dumps(d))
        subprocess.run(['git','add','.'],cwd=self.root,check=True)
        subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Mark draft'],cwd=self.root,check=True)
        with self.assertRaises(ValueError):package.build('HEAD',Path(self.temp.name)/'bad','meeting-notes',self.root)

    def test_wrong_archive_root_is_refused(self):
        with self.assertRaises(ValueError):package.verify_zip(package.zip_payload({'SKILL.md':b'text'},'wrong/'),'meeting-notes')

    def test_path_traversal_and_duplicate_members_are_refused(self):
        with self.assertRaises(ValueError):package.zip_payload({'../outside':b'x'},'meeting-notes/')
        with self.assertRaises(ValueError):package.zip_payload({'/outside':b'x'},'meeting-notes/')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('meeting-notes/../escape',b'no')
        with self.assertRaises(ValueError):package.verify_zip(stream.getvalue(),'meeting-notes')

    def test_packaging_does_not_overwrite_prior_evidence(self):
        out=Path(self.temp.name)/'release';package.build('HEAD',out,'meeting-notes',self.root)
        old=(out/'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):package.build('HEAD',out,'meeting-notes',self.root)
        self.assertEqual((out/'manifest.json').read_bytes(),old)

if __name__=='__main__':unittest.main()
