#!/usr/bin/env python3
"""Pinned, offline chart dependency contracts; no fetch or update permissions."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'skills/vps-health/scripts'))
import vps_workspace as w

class VendorTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'skill'
        shutil.copytree(ROOT/'skills/vps-health/assets',self.root/'assets')
        self.vendor=self.root/'assets/vendor/uplot'
        patch=mock.patch.object(w.core,'ROOT',self.root);patch.start();self.addCleanup(patch.stop)

    def test_exact_upstream_artifacts_and_license(self):
        payload=w.chart_assets();self.assertEqual(set(payload),{'uPlot.iife.min.js','uPlot.min.css','LICENSE'})
        self.assertIn('Permission is hereby granted',payload['LICENSE'])
        self.assertLess(sum(len(s.encode()) for s in payload.values()),60000)

    def test_script_modification_fails_closed(self):
        p=self.vendor/'uPlot.iife.min.js';p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):w.chart_assets()

    def test_css_modification_fails_closed(self):
        p=self.vendor/'uPlot.min.css';p.write_text('body{display:none}')
        with self.assertRaises(ValueError):w.chart_assets()

    def test_manifest_cannot_add_an_arbitrary_path(self):
        p=self.vendor/'manifest.json';d=json.loads(p.read_text());d['files']['../../unrelated']={}
        p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):w.chart_assets()

    def test_symlink_is_not_vendor_provenance(self):
        p=self.vendor/'LICENSE';p.unlink();p.symlink_to(self.vendor/'uPlot.min.css')
        with self.assertRaises(ValueError):w.chart_assets()

    def test_page_bundles_library_without_external_asset_requests(self):
        raw=w.page({'test':'</script><script>not executed</script>'}).decode()
        self.assertTrue('var uPlot=' in raw)
        self.assertNotIn('/*UPLOT_JS*/',raw);self.assertNotIn('/*CHART_ADAPTER*/',raw)
        self.assertNotIn('<script src=',raw)
        self.assertIn('\\u003c/script',raw)
        self.assertTrue('dataset.chartVersion' in raw)

if __name__=='__main__':unittest.main()
