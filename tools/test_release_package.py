#!/usr/bin/env python3
"""Artifact-shape regressions: the download must actually be an installable skill."""
from pathlib import Path
import copy
import hashlib
import io
import json
import sys
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).parent))
import package_release as package

class PackageTest(unittest.TestCase):
    def fixture(self):
        root=package.ROOT/'skills/vps-health'
        result={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        result['LICENSE']=(package.ROOT/'LICENSE').read_bytes()
        return result

    def test_zip_root_is_installable_and_not_the_repository(self):
        files=self.fixture();package.validate_skill(files)
        raw=package.zip_payload(files,'vps-health/')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn('vps-health/SKILL.md',archive.namelist())
            self.assertNotIn('vps-health/skills/vps-health/SKILL.md',archive.namelist())
            self.assertNotIn('vps-health/.github/workflows/verify.yml',archive.namelist())
            self.assertIn('vps-health/assets/vendor/uplot/LICENSE',archive.namelist())

    def test_actual_zip_can_bootstrap_and_export_without_the_repo(self):
        files=self.fixture()
        self.assertEqual(package.verify_zip(package.zip_payload(files,'vps-health/')),len(files))

    def test_archive_bytes_are_deterministic_across_input_order(self):
        files=self.fixture()
        self.assertEqual(package.zip_payload(files,'vps-health/'),package.zip_payload(dict(reversed(list(files.items()))),'vps-health/'))

    def test_wrong_root_missing_license_and_tampered_library_fail(self):
        for mode in ('root','license','vendor'):
            files=self.fixture()
            if mode=='root':files['skills/vps-health/SKILL.md']=files.pop('SKILL.md')
            elif mode=='license':files.pop('LICENSE')
            else:files['assets/vendor/uplot/uPlot.iife.min.js']+=b'changed'
            with self.subTest(mode=mode),self.assertRaises(ValueError):package.validate_skill(files)

    def test_paths_cannot_escape_the_export(self):
        with self.assertRaises(ValueError):package.zip_payload({'../../escape':b'x'},'vps-health/')
        with self.assertRaises(ValueError):package.zip_payload({'/absolute':b'x'},'vps-health/')

if __name__=='__main__':unittest.main()
