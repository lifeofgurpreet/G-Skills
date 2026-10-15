#!/usr/bin/env python3
"""Provider context must be usable end-to-end, dated per source, and never consent."""
from pathlib import Path
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
import vps_ops as ops
sys.path.insert(0,str(Path(__file__).parent))
from test_workspace import args

NOW=core.stamp('2026-10-15T12:00:00Z')
NEW=('vultr','ovhcloud','netcup')
class ProviderCoverageTest(unittest.TestCase):
    def test_missing_suppliers_are_supported_by_the_same_offline_route(self):
        for name in NEW:
            with self.subTest(name=name),mock.patch.object(core,'get_json') as network:
                result=ops.providers(name,now=NOW)
                self.assertEqual(result['providers'][0]['id'],name)
                self.assertFalse(result['establishes_contract']);network.assert_not_called()
    def test_each_new_provider_remains_valid_in_a_private_inventory(self):
        for name in NEW:
            asset={'id':'example','instance':'example.invalid:9100','provider':name,'plan':'Owner-confirmed example'}
            core.plan_metadata(asset)
            self.assertEqual(asset['provider'],name)
    def test_new_names_are_accepted_by_bootstrap_and_managed_plan_cli(self):
        entry=Path(core.__file__)
        with tempfile.TemporaryDirectory() as temp:
            for name in NEW:
                root=Path(temp)/name
                p=subprocess.run([sys.executable,str(entry),'agent-plan','--workspace',str(root),'--mode','local','--node','example','--provider',name,'--plan','Owner-provided'],capture_output=True,text=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stderr);d=json.loads(p.stdout)
                self.assertEqual(d['intent']['configuration']['assets'][0]['provider'],name)
                self.assertFalse(root.exists())
    def test_vultr_high_frequency_is_not_relabelled_dedicated(self):
        p=ops.providers('vultr',now=NOW)['providers'][0]
        shared=next(f for f in p['facts'] if 'High Frequency' in f['scope'])
        self.assertIn('shared',shared['text'].lower())
        self.assertTrue(any('Optimized' in f['scope'] and 'dedicated' in f['text'].lower() for f in p['facts']))
    def test_netcup_root_server_does_not_mean_bare_metal(self):
        p=ops.providers('netcup',now=NOW)['providers'][0]
        fact=next(f for f in p['facts'] if 'Root' in f['scope'])
        self.assertIn('virtual',fact['text'].lower());self.assertIn('dedicated',fact['text'].lower())
    def test_ovh_scope_does_not_borrow_discovery_cpu_claim_for_vps(self):
        p=ops.providers('ovhcloud',now=NOW)['providers'][0]
        self.assertTrue(any('Discovery' in f['scope'] and 'shared' in f['text'].lower() for f in p['facts']))
        self.assertIn('not a CPU',p['not_a_promise'])
        self.assertTrue(any('availability' in f['text'].lower() for f in p['facts']))
    def test_no_reference_grants_a_numeric_delivery_floor_or_downtime_permission(self):
        for p in ops.providers(now=NOW)['providers']:
            self.assertNotIn('guaranteed_ratio',p)
            self.assertTrue(p['not_a_promise'])
            self.assertNotIn('I approve downtime',json.dumps(p))
            self.assertNotIn('send_authorized',p)

class ReferenceAgeTest(unittest.TestCase):
    def data(self):return core.read_json(core.ROOT/'assets/provider-catalog.json')
    def test_a_new_catalog_edit_does_not_refresh_an_old_fact(self):
        d=self.data();d['reviewed_on']='2026-10-15';p=d['providers'][0]
        p['facts'][0]['reviewed_on']='2025-01-01'
        with mock.patch.object(core,'read_json',return_value=d):result=ops.providers('contabo',now=NOW)
        self.assertEqual(result['providers'][0]['review_state'],'RECHECK_REQUIRED')
        self.assertEqual(result['providers'][0]['facts'][0]['reviewed_on'],'2025-01-01')
    def test_filtering_is_not_affected_by_an_unrelated_stale_provider(self):
        d=self.data();d['providers'][0]['facts'][0]['reviewed_on']='2025-01-01'
        with mock.patch.object(core,'read_json',return_value=d):result=ops.providers('vultr',now=NOW)
        self.assertEqual(result['review_state'],'DATED_REFERENCE')
    def test_fresh_diagnostics_does_not_refresh_old_allocation_fact(self):
        d=self.data();p=d['providers'][0];p['facts'][0]['reviewed_on']='2025-01-01';p['diagnostics'][0]['reviewed_on']='2026-10-15'
        with mock.patch.object(core,'read_json',return_value=d):r=ops.providers('contabo',now=NOW)['providers'][0]
        self.assertEqual(r['review_state'],'RECHECK_REQUIRED');self.assertEqual(r['diagnostics'][0]['review_state'],'DATED_REFERENCE')
    def test_missing_source_review_date_is_not_a_current_reference(self):
        d=self.data();d['providers'][0]['facts'][0].pop('reviewed_on',None)
        with mock.patch.object(core,'read_json',return_value=d):r=ops.providers('contabo',now=NOW)
        self.assertEqual(r['review_state'],'RECHECK_REQUIRED')
        self.assertIsNone(r['providers'][0]['facts'][0]['reviewed_on'])
    def test_future_and_malformed_source_dates_are_explicit_recheck_states(self):
        for date in ('2027-01-01','invalid','2026-02-30'):
            d=self.data();d['providers'][0]['facts'][0]['reviewed_on']=date
            with self.subTest(date=date),mock.patch.object(core,'read_json',return_value=d):r=ops.providers('contabo',now=NOW)
            self.assertEqual(r['review_state'],'RECHECK_REQUIRED')
    def test_provider_output_does_not_mutate_the_reference(self):
        d=self.data();before=copy.deepcopy(d)
        with mock.patch.object(core,'read_json',return_value=d):ops.providers('contabo',now=NOW)
        self.assertEqual(d,before)
    def test_unknown_provider_does_not_inherit_a_reviewed_contract(self):
        r=ops.providers('unknown',now=NOW)
        self.assertEqual(r['providers'][0]['id'],'other')
        self.assertEqual(r['providers'][0]['review_state'],'NO_PROVIDER_REFERENCE')
        self.assertEqual(r['providers'][0]['facts'],[])
    def test_each_returned_fact_has_its_own_review_state(self):
        r=ops.providers(now=NOW)
        for p in r['providers']:
            for f in p['facts']+p.get('diagnostics',[]):
                self.assertIn(f['review_state'],('DATED_REFERENCE','RECHECK_REQUIRED'))
                self.assertRegex(f['reviewed_on'],r'^\d{4}-\d{2}-\d{2}$')
    def test_provider_source_must_belong_to_that_provider(self):
        d=self.data();d['providers'][0]['facts'][0]['source']='https://www.netcup.com/en/helpcenter/documentation/server'
        with mock.patch.object(core,'read_json',return_value=d),self.assertRaises(core.InvalidEvidence):ops.providers()
    def test_bad_source_locations_are_not_accepted_as_reference_links(self):
        for url in ('http://docs.contabo.com/page','https://name:password@docs.contabo.com/page','https://docs.contabo.com:8765/page','https://docs.contabo.com.example.invalid/page'):
            d=self.data();d['providers'][0]['facts'][0]['source']=url
            with self.subTest(url=url),mock.patch.object(core,'read_json',return_value=d),self.assertRaises(core.InvalidEvidence):ops.providers()

if __name__=='__main__':unittest.main()
