#!/usr/bin/env python3
"""Collection boundaries proved with unrelated disposable skills, not VPS mocks."""
from pathlib import Path
import copy
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from unittest import mock
import collection
import validate


class CollectionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def new(self,name='meeting-notes'):
        collection.scaffold(self.root,name,'Meeting notes' if name=='meeting-notes' else 'A separate skill')
        return self.root/'skills'/name

    def test_scaffold_stays_draft_and_never_invents_monitoring(self):
        p=self.new();doc=collection.discover(self.root)[0]
        self.assertEqual(doc['status'],'draft');self.assertNotIn('vps',json.dumps(doc).lower())
        self.assertFalse((p/'scripts/vps_health.py').exists())

    def test_two_unrelated_skills_have_independent_versions_and_checks(self):
        self.new();p=self.new('writing-review');d=json.loads((p/'skill.json').read_text());d['version']='2.3.4';(p/'skill.json').write_text(json.dumps(d))
        rows=collection.discover(self.root);self.assertEqual([r['name'] for r in rows],['meeting-notes','writing-review'])
        self.assertEqual([r['version'] for r in rows],['0.1.0','2.3.4'])
        self.assertTrue(all('browser' not in r['checks'] for r in rows))
        c=collection.catalog(rows);self.assertNotIn('version',c);self.assertEqual(c['skills'][1]['release_tag'],'writing-review/v2.3.4')

    def test_adding_skill_does_not_change_existing_files(self):
        self.new();before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.new('other-skill')
        for p,data in before.items():self.assertEqual((self.root/p).read_bytes(),data)

    def test_no_overwrite_or_path_escape(self):
        self.new()
        with self.assertRaises(ValueError):self.new()
        for name in ('../outside','Upper','a/b','a b',''):
            with self.subTest(name=name),self.assertRaises(ValueError):self.new(name)

    def test_design_kit_copies_must_match_and_pages_use_tokens(self):
        p=self.new();self.assertEqual(collection.design_kit(self.root),0)
        (p/'assets').mkdir();(p/'assets/operator-ui.css').write_text(':root{--ui-ink:#fff}\n')
        with self.assertRaises(ValueError):collection.design_kit(self.root)
        (self.root/'docs/design').mkdir(parents=True);(self.root/'docs/design/operator-ui.css').write_text(':root{--ui-ink:#fff}\n')
        self.assertEqual(collection.design_kit(self.root),1)
        (p/'assets/operator-ui.css').write_text(':root{--ui-ink:#eee}\n')
        with self.assertRaises(ValueError):collection.design_kit(self.root)
        (p/'assets/operator-ui.css').write_text(':root{--ui-ink:#fff}\n')
        page=p/'assets/page.html';page.write_text('<link rel="stylesheet" href="/operator-ui.css"><style>.a{color:var(--ui-ink)}</style><svg fill="#000"></svg>')
        self.assertEqual(collection.design_kit(self.root),1)
        for raw in ('.a{color:#123456}','.a{background:rgba(0,0,0,.2)}','.a{color:HSL(1,2%,3%)}'):
            with self.subTest(raw=raw):
                page.write_text('<link rel="stylesheet" href="/operator-ui.css"><style>'+raw+'</style>')
                with self.assertRaises(ValueError):collection.design_kit(self.root)
        page.write_text('<style>.own-design{color:#123456}</style>')  # pages not using the kit keep their own look
        self.assertEqual(collection.design_kit(self.root),1)

    def test_missing_declared_check_fails(self):
        self.new();(self.root/'tools/skills/meeting-notes/validate.py').unlink()
        with self.assertRaises(ValueError):collection.discover(self.root)

    def test_check_cannot_point_into_another_skill(self):
        p=self.new();self.new('other-skill');d=json.loads((p/'skill.json').read_text());d['checks']['python']='tools/skills/other-skill/validate.py';(p/'skill.json').write_text(json.dumps(d))
        with self.assertRaises(ValueError):collection.discover(self.root)

    def test_metadata_identity_and_version_are_validated(self):
        p=self.new();original=json.loads((p/'skill.json').read_text())
        for changes in ({'name':'wrong'},{'version':'latest'},{'entry':'other.md'},{'status':'published-ish'}):
            (p/'skill.json').write_text(json.dumps({**original,**changes}))
            with self.subTest(changes=changes),self.assertRaises(ValueError):collection.discover(self.root)

    def test_mismatched_entry_fails(self):
        p=self.new();(p/'SKILL.md').write_text((p/'SKILL.md').read_text().replace('name: meeting-notes','name: different'))
        with self.assertRaises(ValueError):collection.discover(self.root)

    def test_symlinked_entry_is_not_a_portable_package(self):
        p=self.new();(p/'SKILL.md').rename(p/'real.md');(p/'SKILL.md').symlink_to(p/'real.md')
        with self.assertRaises(ValueError):collection.discover(self.root)

    def test_javascript_skill_does_not_require_a_browser_to_enter_its_ci_matrix(self):
        path=self.new();manifest=json.loads((path/'skill.json').read_text())
        manifest['checks']['javascript']='tools/skills/meeting-notes/test.cjs'
        (self.root/manifest['checks']['javascript']).write_text('// synthetic optional check')
        (path/'skill.json').write_text(json.dumps(manifest))
        outputs={}
        for kind in ('javascript','browser'):
            stream=io.StringIO()
            with mock.patch.object(collection,'ROOT',self.root),mock.patch.object(collection,'discover',return_value=collection.discover(self.root)),contextlib.redirect_stdout(stream):
                self.assertEqual(collection.main(['--matrix',kind]),0)
            outputs[kind]=json.loads(stream.getvalue())['skill']
        self.assertEqual(outputs,{'javascript':['meeting-notes'],'browser':[]})

    def test_catalog_is_deterministic(self):
        self.new();self.assertEqual(collection.catalog(collection.discover(self.root)),collection.catalog(collection.discover(self.root)))

class SourcePrivacyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'.gitignore').write_text('.beads/runtime.db*\n.beads/.br_recovery/\noutside.db\n.ruff_cache/\n')
        (self.root/'.beads').mkdir()
        self.runtime=self.root/'.beads/runtime.db'
        self.runtime.write_bytes(b'\xff\x00private SQLite runtime')

    def test_ignored_untracked_beads_database_is_not_published_source(self):
        (self.root/'.beads/runtime.db-fsqlite-ns-use').write_bytes(b'\xff\x00private sidecar')
        validate.privacy(self.root)

    def test_forced_tracked_database_still_fails(self):
        subprocess.run(['git','-C',str(self.root),'add','-f','.beads/runtime.db'],check=True)
        with self.assertRaisesRegex(ValueError,'generated/private artifact'):validate.privacy(self.root)

    def test_unignored_beads_database_still_fails(self):
        self.runtime.rename(self.root/'.beads/private.db')
        with self.assertRaisesRegex(ValueError,'generated/private artifact'):validate.privacy(self.root)

    def test_ignored_linter_cache_is_not_published_source(self):
        cache=self.root/'.ruff_cache';cache.mkdir();(cache/'index').write_bytes(b'\xff\x00private cache')
        validate.privacy(self.root)

    def test_ignored_database_outside_beads_is_checked_when_force_added(self):
        self.runtime.unlink();(self.root/'outside.db').write_bytes(b'\xff\x00private runtime')
        subprocess.run(['git','-C',str(self.root),'add','-f','outside.db'],check=True)
        with self.assertRaisesRegex(ValueError,'generated/private artifact'):validate.privacy(self.root)

    def test_unignored_private_database_outside_beads_is_checked(self):
        self.runtime.unlink();(self.root/'public.db').write_bytes(b'\xff\x00private runtime')
        with self.assertRaisesRegex(ValueError,'generated/private artifact'):validate.privacy(self.root)

    def test_no_git_archive_cannot_hide_private_files_with_gitignore(self):
        archive=self.root/'archive';archive.mkdir();(archive/'.beads').mkdir()
        (archive/'.gitignore').write_text('.beads/runtime.db\n')
        (archive/'.beads/runtime.db').write_bytes(b'\xff\x00private runtime')
        with self.assertRaisesRegex(ValueError,'generated/private artifact'):validate.privacy(archive)


if __name__=='__main__':unittest.main()
