#!/usr/bin/env python3
"""Artifact-shape regressions: the download must actually be an installable skill."""
from pathlib import Path
import copy
import hashlib
import io
import json
import re
import shlex
import sys
import subprocess
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).parent))
import package_check as check
import package_release as package

class PackageTest(unittest.TestCase):
    def fixture(self):
        root=package.ROOT/'skills/vps-health'
        result={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        result['LICENSE']=(package.ROOT/'LICENSE').read_bytes()
        return result

    def test_zip_root_is_installable_and_not_the_repository(self):
        files=self.fixture();check.validate_files(files)
        raw=package.zip_payload(files,'vps-health/')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn('vps-health/SKILL.md',archive.namelist())
            self.assertNotIn('vps-health/skills/vps-health/SKILL.md',archive.namelist())
            self.assertNotIn('vps-health/.github/workflows/verify.yml',archive.namelist())
            self.assertIn('vps-health/assets/vendor/uplot/LICENSE',archive.namelist())

    def test_actual_zip_can_bootstrap_and_export_without_the_repo(self):
        files=self.fixture()
        self.assertEqual(package.verify_zip(package.zip_payload(files,'vps-health/'),'vps-health',checker=Path(__file__).with_name('package_check.py')),len(files))

    def test_archive_bytes_are_deterministic_across_input_order(self):
        files=self.fixture()
        self.assertEqual(package.zip_payload(files,'vps-health/'),package.zip_payload(dict(reversed(list(files.items()))),'vps-health/'))

    def test_wrong_root_missing_license_and_tampered_library_fail(self):
        for mode in ('root','license','vendor'):
            files=self.fixture()
            if mode=='root':files['skills/vps-health/SKILL.md']=files.pop('SKILL.md')
            elif mode=='license':files.pop('LICENSE')
            else:files['assets/vendor/uplot/uPlot.iife.min.js']+=b'changed'
            with self.subTest(mode=mode),self.assertRaises(ValueError):check.validate_files(files)

    def test_operator_files_are_required_in_the_actual_installable_archive(self):
        for name in ('scripts/vps_ops.py','assets/operator.js','assets/operator.css','assets/provider-catalog.json','scripts/vps_agent.py','references/agent-connectors.md'):
            files=self.fixture();files.pop(name)
            with self.subTest(name=name),self.assertRaises(ValueError):check.validate_files(files)

    def test_paths_cannot_escape_the_export(self):
        with self.assertRaises(ValueError):package.zip_payload({'../../escape':b'x'},'vps-health/')
        with self.assertRaises(ValueError):package.zip_payload({'/absolute':b'x'},'vps-health/')

    def test_agent_entry_identifies_the_bundled_cli(self):
        files=self.fixture();entry=files['SKILL.md'].decode()
        self.assertIn('[scripts/vps_health.py](scripts/vps_health.py)',entry)
        self.assertIn('references/support-scope.md',entry)

    def test_release_support_scope_is_bundled_not_only_an_online_page(self):
        files=self.fixture();self.assertIn('references/support-scope.md',files)
        self.assertIn('references/support-scope.md',files['README.md'].decode())
        files.pop('references/support-scope.md')
        with self.assertRaises(ValueError):check.validate_files(files)

    def test_a_missing_local_reference_cannot_pass_release_acceptance(self):
        files=self.fixture();files['SKILL.md']+=b'\nRead [a missing guide](references/not-shipped.md).\n'
        with self.assertRaises(ValueError):check.validate_files(files)

    def test_nested_guide_links_resolve_relative_to_the_guide(self):
        files=self.fixture();files['references/forensics.md']+=b'\nRead [the method](./method.md#context).\n'
        check.validate_files(files)

    def test_absolute_or_escaping_local_references_fail(self):
        for target in ('../private.txt','/private.txt','../../another-skill/SKILL.md'):
            files=self.fixture();files['SKILL.md']+=('\n[Invalid]('+target+')\n').encode()
            with self.subTest(target=target),self.assertRaises(ValueError):check.validate_files(files)

    def test_repository_relative_runtime_recipes_fail_package_acceptance(self):
        files=self.fixture()
        files['references/bootstrap.md']+=b'\n```bash\npython3 skills/vps-health/scripts/vps_health.py capabilities\n```\n'
        with self.assertRaisesRegex(ValueError,'repository-relative runtime command'):
            check.validate_files(files)

    def test_documented_demo_and_learning_work_outside_the_installed_folder(self):
        files=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);unrelated=base/'another working folder';unrelated.mkdir()
            installation=base/'installed skill with spaces'
            with zipfile.ZipFile(io.BytesIO(package.zip_payload(files,'vps-health/'))) as archive:
                archive.extractall(installation)
            entry=installation/'vps-health/scripts/vps_health.py'
            workspace=base/'synthetic workspace';proposal=base/'lesson.json'
            replacements={'$VPS_HEALTH_CLI':str(entry),'/tmp/vps-demo':str(workspace),
                          '$HOME/vps-health':str(workspace),'$HOME/vps-lesson-001.json':str(proposal)}

            def documented_command(guide,verb):
                # Select only the two authorized synthetic recipes; never execute
                # arbitrary shell text or the guides' real collection examples.
                blocks=re.findall(r'^```bash\n(.*?)^```',files[guide].decode(),re.S|re.M)
                commands=[]
                for block in blocks:
                    for line in block.replace('\\\n',' ').splitlines():
                        argv=shlex.split(line)
                        if len(argv)>2 and argv[0]=='python3' and argv[2]==verb:
                            if verb=='bootstrap' and argv[argv.index('--mode')+1]!='demo':continue
                            commands.append([replacements.get(arg,arg) for arg in argv[1:]])
                self.assertEqual(len(commands),1)
                return [sys.executable,'-B','-S',*commands[0]]

            demo=json.loads(subprocess.check_output(documented_command('references/bootstrap.md','bootstrap'),
                cwd=unrelated,text=True,timeout=30))
            self.assertEqual(demo['mode'],'demo');self.assertTrue((workspace/'dashboard.html').is_file())
            before={p.name:p.read_bytes() for p in workspace.iterdir() if p.is_file()}
            lesson=json.loads(subprocess.check_output(documented_command('references/improvement.md','learn'),
                cwd=unrelated,text=True,timeout=30))
            self.assertEqual(lesson['state'],'PROPOSED_NOT_APPLIED')
            self.assertEqual(json.loads(proposal.read_text()),lesson)
            self.assertEqual(before,{p.name:p.read_bytes() for p in workspace.iterdir() if p.is_file()})
            self.assertEqual(list(unrelated.iterdir()),[])

    def test_real_cli_entry_does_not_depend_on_working_directory_or_site_packages(self):
        files=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            installed=Path(temp)/'skill folder with spaces';unrelated=Path(temp)/'another working folder';unrelated.mkdir()
            for name,body in files.items():
                target=installed/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
            entry=installed/'scripts/vps_health.py'
            result=json.loads(subprocess.check_output([sys.executable,'-B','-S',str(entry),'capabilities'],cwd=unrelated,text=True,timeout=20))
            help_text=subprocess.check_output([sys.executable,'-B','-S',str(entry),'--help'],cwd=unrelated,text=True,timeout=20)
            self.assertEqual(result['version'],json.loads(files['skill.json'])['version'])
            self.assertIn('agent-plan',help_text);self.assertEqual(list(unrelated.iterdir()),[])
            self.assertFalse(list(installed.rglob('*.pyc')))

if __name__=='__main__':unittest.main()
