#!/usr/bin/env python3
"""Reversible selected-skill installation without accounts, hooks or user edits."""
from pathlib import Path
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import collection
import package_release as package
import install_skill as install

class InstallTest(unittest.TestCase):
    def setUp(self):
        if os.name!='posix':self.skipTest('managed filesystem operations qualify POSIX only')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.directory=self.root/'client/skills';self.store=self.root/'private-recovery'
        self.skill='meeting-notes';self.archive,self.manifest=self.release('1.0.0')

    def release(self,version,name='meeting-notes',extra=None):
        meta={'schema':'g-skills.skill.v1','name':name,'title':'Meeting Notes','summary':'Synthetic lifecycle fixture.',
              'version':version,'category':'writing','status':'ready','entry':'SKILL.md',
              'checks':{'python':f'tools/skills/{name}/validate.py','package':f'tools/skills/{name}/package_check.py'}}
        files={'SKILL.md':f'---\nname: {name}\ndescription: Synthetic fixture.\n---\n# version {version}\n'.encode(),
               'skill.json':json.dumps(meta).encode(),'LICENSE':b'MIT synthetic fixture\n',
               'scripts/example.py':b'raise RuntimeError("installer must never execute me")'}
        if extra:files.update(extra)
        raw=package.zip_payload(files,name+'/');archive=self.root/f'{name}-v{version}.zip';archive.write_bytes(raw)
        manifest=self.root/f'{name}-{version}-manifest.json'
        manifest.write_text(json.dumps({'schema':'g-skills.skill-release.v1','skill':name,'version':version,'tag':name+'/v'+version,
            'commit':'a'*40,'files':{archive.name:{'bytes':len(raw),'sha256':install.digest(raw)}}}))
        return archive,manifest

    def plan(self,op='install',**changes):
        data=dict(operation=op,directory=self.directory,store=self.store,skill=self.skill,archive=self.archive,manifest=self.manifest)
        return install.plan(**{**data,**changes})

    def apply(self,op='install',approval=None,**changes):
        data=dict(operation=op,directory=self.directory,store=self.store,skill=self.skill,archive=self.archive,manifest=self.manifest)
        data.update(changes)
        if approval is None:approval=install.plan(**data)['plan_sha256']
        return install.apply(**data,approval=approval,consumers_stopped=True)

    def target(self):return self.directory/self.skill

    def test_plan_is_read_only_and_binds_destination_and_source(self):
        p=self.plan();self.assertFalse(self.directory.exists());self.assertFalse(self.store.exists())
        self.assertEqual(p['plan_sha256'],install.digest(p['intent']))
        self.assertFalse(p['approval_is_authentication']);self.assertFalse(p['native_client_verified'])

    def test_bad_approval_does_not_create_directories(self):
        with self.assertRaises(ValueError):self.apply(approval='0'*64)
        self.assertFalse(self.directory.exists());self.assertFalse(self.store.exists())

    def test_missing_quiescence_confirmation_refuses(self):
        p=self.plan()
        with self.assertRaises(ValueError):install.apply('install',self.directory,self.store,self.skill,p['plan_sha256'],self.archive,self.manifest)
        self.assertFalse(self.directory.exists())

    def test_install_writes_only_selected_skill_and_no_scripts_run(self):
        with mock.patch.object(subprocess,'run') as execute:
            result=self.apply()
        execute.assert_not_called();self.assertEqual(result['state'],'INSTALLED')
        self.assertEqual([p.name for p in self.directory.iterdir()],[self.skill])
        self.assertTrue((self.target()/'SKILL.md').is_file());self.assertFalse(result['native_client_verified'])

    def test_retry_same_plan_is_noop_with_same_generation(self):
        p=self.plan();a=self.apply(approval=p['plan_sha256']);b=self.apply(approval=p['plan_sha256'])
        self.assertEqual(b['state'],'UNCHANGED')
        self.assertEqual(install.status(self.directory,self.store,self.skill)['current']['generation'],a['status']['current']['generation'])

    def test_removed_installation_cannot_be_recreated_with_its_old_approval(self):
        first=self.plan()['plan_sha256'];self.apply(approval=first);self.apply('remove')
        with self.assertRaises(ValueError):self.apply(approval=first)
        self.assertFalse(self.target().exists())
        self.assertNotEqual(self.plan()['plan_sha256'],first)

    def test_real_process_interruption_releases_lock_and_restores_prior_files(self):
        self.apply();before=(self.target()/'SKILL.md').read_bytes()
        self.archive,self.manifest=self.release('2.0.0');approval=self.plan()['plan_sha256']
        code="import os,sys; sys.path.insert(0,sys.argv[1]); import install_skill as i; i.checkpoint=lambda name: os._exit(93) if name=='retired' else None; i.apply('install',sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],consumers_stopped=True)"
        result=subprocess.run([sys.executable,'-c',code,str(Path(install.__file__).parent),str(self.directory),str(self.store),self.skill,approval,str(self.archive),str(self.manifest)],timeout=15)
        self.assertEqual(result.returncode,93);self.assertFalse(self.target().exists())
        self.apply('recover');self.assertEqual((self.target()/'SKILL.md').read_bytes(),before)

    def test_same_archive_new_plan_is_noop(self):
        self.apply();self.assertEqual(self.apply()['state'],'UNCHANGED')

    def test_upgrade_and_restore_preserve_exact_old_skill_bytes(self):
        self.apply();original=(self.target()/'SKILL.md').read_bytes()
        self.archive,self.manifest=self.release('2.0.0');d=self.apply()
        self.assertEqual(d['status']['current']['version'],'2.0.0');self.assertEqual(len(d['status']['revisions']),1)
        r=self.apply('restore',revision=d['status']['revisions'][0]['revision'])
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),original);self.assertEqual(r['status']['current']['version'],'1.0.0')

    def test_remove_is_retained_and_does_not_touch_private_workspace(self):
        evidence=self.root/'private-observations';evidence.mkdir();(evidence/'user.json').write_text('private-data')
        self.apply();d=self.apply('remove');self.assertFalse(self.target().exists())
        self.assertEqual(d['state'],'REMOVED_RETAINED');self.assertEqual((evidence/'user.json').read_text(),'private-data')
        self.assertEqual(len(d['status']['revisions']),1)
        self.apply('restore',revision=d['status']['revisions'][0]['revision']);self.assertTrue(self.target().exists())

    def test_two_unrelated_skills_keep_independent_installations(self):
        self.apply();original=(self.target()/'SKILL.md').read_bytes()
        archive,manifest=self.release('3.1.0','writing-review')
        self.apply(skill='writing-review',archive=archive,manifest=manifest)
        self.archive,self.manifest=self.release('2.0.0');self.apply()
        other=install.status(self.directory,self.store,'writing-review')
        self.assertEqual(other['current']['version'],'3.1.0');self.assertEqual(len(other['revisions']),0)

    def test_existing_unowned_directory_is_never_adopted(self):
        self.target().mkdir(parents=True);(self.target()/'SKILL.md').write_text('my own work')
        with self.assertRaises(ValueError):self.plan()
        self.assertEqual((self.target()/'SKILL.md').read_text(),'my own work');self.assertFalse(self.store.exists())

    def test_modified_missing_and_added_files_refuse_all_mutations(self):
        for kind in ('modified','missing','added'):
            with self.subTest(kind=kind):
                self.apply();p=self.target()/'SKILL.md';old=p.read_bytes()
                if kind=='modified':p.write_text('user edits')
                elif kind=='missing':p.unlink()
                else:(self.target()/'customer.json').write_text('private')
                for op in ('install','remove'):
                    with self.assertRaises(ValueError):self.plan(op)
                if kind=='added':(self.target()/'customer.json').unlink()
                else:p.write_bytes(old)

    def test_normal_python_caches_are_not_treated_as_user_edits(self):
        self.apply();cache=self.target()/'scripts/__pycache__';cache.mkdir();(cache/'example.cpython-312.pyc').write_bytes(b'cache')
        self.assertEqual(self.apply()['state'],'UNCHANGED')
        (cache/'actual-notes.md').write_text('user text')
        with self.assertRaises(ValueError):self.plan('remove')

    def test_edit_after_plan_refuses_stale_approval(self):
        self.apply();p=self.plan('remove');(self.target()/'SKILL.md').write_text('do not destroy')
        with self.assertRaises(ValueError):self.apply('remove',approval=p['plan_sha256'])
        self.assertEqual((self.target()/'SKILL.md').read_text(),'do not destroy')

    def test_changed_archive_after_plan_refuses_before_mutation(self):
        p=self.plan();self.archive.write_bytes(self.archive.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.apply(approval=p['plan_sha256'])
        self.assertFalse(self.directory.exists())

    def test_symlink_parent_or_destination_is_refused(self):
        outside=self.root/'outside';outside.mkdir();link=self.root/'link';link.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.plan(directory=link/'skills')
        self.directory.mkdir(parents=True);self.target().symlink_to(outside)
        with self.assertRaises(ValueError):self.plan()

    def test_dangling_destination_symlink_is_not_treated_as_absent(self):
        self.directory.mkdir(parents=True);self.target().symlink_to(self.root/'missing')
        with self.assertRaises(ValueError):self.plan()

    def test_recovery_store_cannot_be_discovered_as_another_skill(self):
        with self.assertRaises(ValueError):self.plan(store=self.directory/'retired')
        with self.assertRaises(ValueError):self.plan(store=self.directory.parent)

    def test_wrong_skill_or_version_manifest_refuses(self):
        for change in ({'skill':'other-skill'},{'version':'9.9.9'}):
            original=json.loads(self.manifest.read_text());self.manifest.write_text(json.dumps({**original,**change}))
            with self.assertRaises(ValueError):self.plan()
            self.manifest.write_text(json.dumps(original))

    def test_malformed_manifest_and_receipt_are_controlled_refusals(self):
        original=self.manifest.read_bytes();self.manifest.write_text('[]')
        with self.assertRaises(ValueError):self.plan()
        self.manifest.write_bytes(original);self.apply()
        (self.target()/install.RECEIPT).write_text('[]')
        with self.assertRaises(ValueError):self.plan('remove')

    def test_corrupt_archive_cli_has_no_traceback_or_side_effect(self):
        self.archive.write_bytes(b'not-a-zip');release=json.loads(self.manifest.read_text())
        release['files'][self.archive.name]={'bytes':9,'sha256':install.digest(b'not-a-zip')};self.manifest.write_text(json.dumps(release))
        result=subprocess.run([sys.executable,str(Path(install.__file__)),'plan','--skill',self.skill,'--directory',str(self.directory),'--store',str(self.store),'--archive',str(self.archive),'--manifest',str(self.manifest)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stdout)['state'],'BLOCKED')
        self.assertNotIn('Traceback',result.stderr);self.assertFalse(self.directory.exists())

    def test_private_files_and_recovery_are_not_world_readable(self):
        self.apply()
        for p in self.target().rglob('*'):
            if p.is_file():self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(self.store.stat().st_mode&0o777,0o700)

    def test_other_recovery_binding_cannot_be_reused(self):
        self.apply();folder=install.layout(self.directory,self.store,self.skill)[3]
        (folder/'binding.json').write_text(json.dumps({'target':str(self.root/'someone-else')}))
        with self.assertRaises(ValueError):self.plan('remove')

    def test_retired_files_modified_before_restore_are_preserved(self):
        self.apply();self.archive,self.manifest=self.release('2.0.0');d=self.apply()
        folder=install.layout(self.directory,self.store,self.skill)[3];revision=d['status']['revisions'][0]['revision']
        (folder/revision/'SKILL.md').write_text('edited backup')
        with self.assertRaises(ValueError):self.plan('restore',revision=revision)
        self.assertEqual((folder/revision/'SKILL.md').read_text(),'edited backup')

    def test_same_destination_lock_rejects_concurrent_mutation(self):
        self.apply();folder=install.layout(self.directory,self.store,self.skill)[3]
        with install.locked(folder):
            with self.assertRaises(ValueError):self.apply('remove')
        self.assertTrue(self.target().exists())

    def test_interrupted_upgrade_recovers_without_losing_the_old_installation(self):
        for point in ('prepared','retired','published'):
            with self.subTest(point=point):
                self.directory=self.root/point/'skills';self.store=self.root/point/'recovery'
                self.archive,self.manifest=self.release('1.0.0');self.apply()
                original=(self.target()/'SKILL.md').read_bytes()
                self.archive,self.manifest=self.release('2.0.0')
                with mock.patch.object(install,'checkpoint',side_effect=lambda name:(_ for _ in ()).throw(OSError('injected interruption')) if name==point else None):
                    with self.assertRaises(OSError):self.apply()
                self.assertEqual(install.status(self.directory,self.store,self.skill)['state'],'RECOVERY_REQUIRED')
                with self.assertRaises(ValueError):self.plan()
                result=self.apply('recover')
                self.assertNotEqual(result['status']['state'],'RECOVERY_REQUIRED')
                if point!='published':self.assertEqual((self.target()/'SKILL.md').read_bytes(),original)
                else:self.assertEqual(result['status']['current']['version'],'2.0.0')

    def test_interrupted_initial_install_can_be_abandoned_safely(self):
        with mock.patch.object(install,'checkpoint',side_effect=OSError('test failure')):
            with self.assertRaises(OSError):self.apply()
        self.apply('recover');self.assertFalse(self.target().exists())

    def test_recovery_does_not_overwrite_a_user_created_replacement(self):
        self.apply();self.archive,self.manifest=self.release('2.0.0')
        with mock.patch.object(install,'checkpoint',side_effect=lambda name:(_ for _ in ()).throw(OSError('test failure')) if name=='retired' else None):
            with self.assertRaises(OSError):self.apply()
        self.target().mkdir();(self.target()/'SKILL.md').write_text('manual replacement')
        with self.assertRaises(ValueError):self.apply('recover')
        self.assertEqual((self.target()/'SKILL.md').read_text(),'manual replacement')

    def test_exact_cli_plan_apply_and_status(self):
        cli=[sys.executable,str(Path(install.__file__))];scope=['--skill',self.skill,'--directory',str(self.directory),'--store',str(self.store),'--archive',str(self.archive),'--manifest',str(self.manifest)]
        p=json.loads(subprocess.check_output([*cli,'plan',*scope],text=True))
        r=json.loads(subprocess.check_output([*cli,'apply',*scope,'--approve-plan',p['plan_sha256'],'--consumers-stopped'],text=True))
        self.assertEqual(r['state'],'INSTALLED');self.assertFalse(r['instructions_executed'])
        s=json.loads(subprocess.check_output([*cli,'status',*scope],text=True));self.assertEqual(s['state'],'INSTALLED')

class ArchiveBoundaryTest(unittest.TestCase):
    def valid(self):
        meta={'schema':'g-skills.skill.v1','name':'example','title':'Example','summary':'Synthetic fixture','version':'1.0.0','category':'testing','status':'ready','entry':'SKILL.md',
              'checks':{'python':'tools/skills/example/validate.py','package':'tools/skills/example/package_check.py'}}
        return {'example/SKILL.md':b'Example','example/LICENSE':b'MIT','example/skill.json':json.dumps(meta).encode()}

    def build(self,entries):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for name,data in self.valid().items():z.writestr(name,data)
            for entry in entries:z.writestr(entry,b'fixture')
        return stream.getvalue()

    def test_noncanonical_paths_do_not_alias_during_extraction(self):
        for name in ('example/./other','example/a/../other','example//other','example/a\\other','example/C:stream','example/a.'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'unsafe'):
                package.archive_files(self.build([name]),'example')

    def test_case_collisions_are_rejected_before_cross_platform_installation(self):
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            package.archive_files(self.build(['example/README.md','example/readme.md']),'example')

    def test_directory_and_special_file_members_are_rejected(self):
        for filename,mode in [('example/data/',0o40755),('example/link',0o120777),('example/fifo',0o010600)]:
            entry=zipfile.ZipInfo(filename);entry.external_attr=mode<<16
            with self.subTest(filename=filename),self.assertRaisesRegex(ValueError,'unsafe'):
                package.archive_files(self.build([entry]),'example')

    def test_archive_cannot_replace_its_own_management_receipt(self):
        for name in ('.gskills-install.json','.GSKILLS-INSTALL.JSON'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'reserved'):
                package.archive_files(self.build(['example/'+name]),'example')

if __name__=='__main__':unittest.main()
