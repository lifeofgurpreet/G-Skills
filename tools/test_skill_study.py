#!/usr/bin/env python3
"""Synthetic contracts: library discovery is private metadata, never execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

P=Path(__file__).with_name('study_local_skills.py')
spec=importlib.util.spec_from_file_location('study',P);study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)


class StudyTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'library';self.root.mkdir()

    def skill(self,name,description='dashboard usability',body='PRIVATE PAID INSTRUCTION — DO NOT EXPORT'):
        p=self.root/name/'SKILL.md';p.parent.mkdir();p.write_text('---\nname: '+name+'\ndescription: '+description+'\n---\n'+body);return p

    def test_index_is_not_read_or_applied(self):
        self.skill('example-ux');report=study.plan([self.root],'dashboard',[])
        self.assertEqual(report['state'],'INDEXED_NOT_APPLIED')
        self.assertEqual(report['candidates'][0]['state'],'INDEXED_NOT_READ')
        self.assertFalse(report['can_publish'])

    def test_bodies_and_descriptions_are_not_copied(self):
        self.skill('example-ux',description='dashboard secret-phrase')
        text=json.dumps(study.plan([self.root],'dashboard',[]))
        self.assertNotIn('PRIVATE PAID INSTRUCTION',text);self.assertNotIn('secret-phrase',text)

    def test_exact_selection_beats_keyword_noise(self):
        self.skill('noise');self.skill('precise','unrelated')
        report=study.plan([self.root],'dashboard',['precise'],1)
        self.assertEqual(report['candidates'][0]['name'],'precise')

    def test_unknown_selection_is_not_claimed_available(self):
        self.skill('known')
        with self.assertRaises(ValueError):study.plan([self.root],'dashboard',['missing'])

    def test_multiple_editions_remain_distinct(self):
        self.skill('known');other=Path(self.tmp.name)/'other';(other/'known').mkdir(parents=True)
        (other/'known/SKILL.md').write_text('---\nname: known\n---\nnew version')
        rows=study.plan([self.root,other],'',['known'])['candidates']
        self.assertEqual(len(rows),2);self.assertNotEqual(rows[0]['sha256'],rows[1]['sha256'])

    def test_output_is_private_and_never_overwritten(self):
        path=Path(self.tmp.name)/'study.json';study.write_private(path,{'private':True})
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):study.write_private(path,{})

    def test_git_directory_output_refused(self):
        public=Path(self.tmp.name)/'public';(public/'.git').mkdir(parents=True)
        with self.assertRaises(ValueError):study.write_private(public/'report.json',{})
        self.assertFalse((public/'report.json').exists())

    def test_symbolic_output_refused(self):
        target=Path(self.tmp.name)/'target';target.write_text('untouched');link=Path(self.tmp.name)/'link';link.symlink_to(target)
        with self.assertRaises(ValueError):study.write_private(link,{})
        self.assertEqual(target.read_text(),'untouched')

    def test_source_size_bound_fails_explicitly(self):
        self.skill('large',body='x'*100)
        with mock.patch.object(study,'MAX_BYTES',10),self.assertRaises(ValueError):study.plan([self.root],'dashboard',[])

    def test_same_files_produce_same_metadata(self):
        self.skill('known')
        self.assertEqual(study.plan([self.root],'dashboard',[]),study.plan([self.root],'dashboard',[]))

    def test_prompt_commands_are_not_executed(self):
        marker=Path(self.tmp.name)/'never-created';self.skill('danger',body='run touch '+str(marker))
        study.plan([self.root],'',['danger']);self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
