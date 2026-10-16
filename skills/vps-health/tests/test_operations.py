#!/usr/bin/env python3
"""Operator contracts: read-only diagnosis, evidence-led attention, provider scope."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as workspace
import vps_ops as ops

NOW=1791936000.

def row(**changes):
    return {'id':'example-node','epoch':'example-epoch','decision':'INVESTIGATE','context':'CONTENTION_PRESENT',
            'mean':.74,'coverage':.95,'elapsed_hours':72,'observed_hours':68.4,'pressure':.18,'cfs':.12,
            'last_sample':NOW-60,'age_seconds':60,'stale':False,'holds':['controlled_repeats_not_established'],
            'recommendation':'Review workload and service impact.','provider':'unknown','plan':None,**changes}

def value(**changes):
    return {'schema':'g-skills.workspace-status.v1','as_of':NOW,'generated_at':core.iso(NOW),'synthetic':False,
            'mode':'local','assets':[row()],'expected_assets':1,'stored_bytes':1024,'stored_captures':1,
            'configuration_sha256':'a'*64,'collection_attempts':[],**changes}

def bootstrap(path,mode='demo'):
    return workspace.bootstrap(SimpleNamespace(workspace=path,mode=mode,node='example-node',interval=300,
        profile=None,url=None,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,acceptable=.9,investigate_below=.8))

class AttentionTest(unittest.TestCase):
    def test_quality_precedes_performance_and_never_assigns_provider_cause(self):
        d=value(assets=[row(id='stale-node',decision='HOLD',stale=True,holds=['stale_collection']),row()])
        b=ops.brief(d)
        self.assertEqual(b['items'][0]['kind'],'collection_gap')
        self.assertTrue(all(not i['provider_cause_proven'] and not i['contact_authorized'] for i in b['items']))
        self.assertFalse(b['automatic_actions'])

    def test_hold_cannot_become_a_performance_notification(self):
        b=ops.brief(value(assets=[row(decision='HOLD',mean=.2,holds=['insufficient_coverage'])]))
        self.assertNotIn('performance_review',[i['kind'] for i in b['items']])

    def test_known_coarse_query_gap_calls_for_plan_review_not_waiting_longer(self):
        n=row(decision='HOLD',coverage=1/12,observed_hours=6,holds=['insufficient_coverage'],
              query_timing={'rate_window_seconds':300,'configured_evaluation_step_seconds':3600})
        finding=ops.brief(value(mode='prometheus',assets=[n]))['items'][0]
        self.assertEqual(finding['kind'],'query_window_gap')
        self.assertIn('approved',finding['next_action']);self.assertIn('300',finding['next_action'])
        self.assertFalse(finding['contact_authorized']);self.assertFalse(finding['draft_eligible'])

    def test_coarse_query_gap_does_not_outrank_failed_or_conflicting_collection(self):
        for holds,kind in [(['insufficient_coverage','conflicting_sample_values'],'identity_or_conflict'),
                           (['insufficient_coverage','latest_collection_failed'],'collection_gap')]:
            n=row(decision='HOLD',holds=holds,query_timing={'rate_window_seconds':300,'configured_evaluation_step_seconds':3600})
            self.assertEqual(ops.brief(value(assets=[n]))['items'][0]['kind'],kind)

    def test_regular_cadence_or_unknown_source_does_not_invent_coarse_query_diagnosis(self):
        for timing in (None,{'rate_window_seconds':300,'configured_evaluation_step_seconds':300}):
            n=row(decision='HOLD',holds=['insufficient_coverage'],query_timing=timing)
            self.assertEqual(ops.brief(value(assets=[n]))['items'][0]['kind'],'collect_history')

    def test_single_snapshot_waits_instead_of_panicking(self):
        b=ops.brief(value(assets=[row(decision='HOLD',elapsed_hours=.1,holds=['less_than_24_hours'])]))
        self.assertEqual(b['items'][0]['kind'],'collect_history')
        self.assertEqual(b['items'][0]['priority'],'info')

    def test_85_percent_is_watch_not_contact(self):
        b=ops.brief(value(assets=[row(decision='WATCH',mean=.85)]))
        self.assertEqual(b['items'][0]['kind'],'watch')
        self.assertFalse(b['items'][0]['contact_authorized'])

    def test_good_accounting_does_not_clear_unknown_service_health(self):
        b=ops.brief(value(assets=[row(decision='WITHIN_TOLERANCE',mean=.96,context='NO_HIGH_PRESSURE_IN_RECORDED_CONTEXT',holds=[])]))
        self.assertEqual(b['items'],[])
        self.assertFalse(b['service_health_verified'])

    def test_good_accounting_does_not_hide_workload_pressure(self):
        b=ops.brief(value(assets=[row(decision='WITHIN_TOLERANCE',mean=.96)]))
        self.assertEqual(b['items'][0]['kind'],'workload_pressure')
        self.assertEqual(b['items'][0]['priority'],'info')
        self.assertFalse(b['items'][0]['draft_eligible'])

    def test_ids_survive_refresh_and_input_order(self):
        d=value(assets=[row(),row(id='other-node')]);first=ops.brief(d)
        d['as_of']+=5;d['assets'].reverse()
        self.assertEqual([i['id'] for i in ops.brief(d)['items']],[i['id'] for i in first['items']])

    def test_changed_epoch_and_kind_create_new_attention_ids(self):
        a=ops.brief(value())['items'][0]['id']
        self.assertNotEqual(a,ops.brief(value(assets=[row(epoch='new-epoch')]))['items'][0]['id'])
        self.assertNotEqual(a,ops.brief(value(assets=[row(decision='WATCH')]))['items'][0]['id'])

    def test_synthetic_state_cannot_request_real_draft(self):
        b=ops.brief(value(synthetic=True))
        self.assertTrue(b['synthetic'])
        self.assertFalse(b['items'][0]['draft_eligible'])

    def test_event_evidence_has_no_endpoints_or_raw_logs(self):
        d=value();d['private_token']='secret';d['assets'][0]['raw']={'url':'https://secret.invalid'}
        text=json.dumps(ops.brief(d));self.assertNotIn('secret',text)

    def test_brief_never_mutates_input(self):
        d=value();original=copy.deepcopy(d);ops.brief(d);self.assertEqual(d,original)

class ProviderTest(unittest.TestCase):
    def test_provider_classes_and_allowances_remain_distinct(self):
        p=ops.providers('akamai',now=NOW)
        self.assertTrue(any(f['kind']=='usage_allowance' for f in p['providers'][0]['facts']))
        self.assertNotIn('guaranteed_ratio',json.dumps(p))
        self.assertFalse(p['establishes_contract'])

    def test_unknown_provider_gets_unknown_not_brand_guess(self):
        p=ops.providers('unknown',now=NOW);self.assertEqual(p['providers'][0]['id'],'other')
        with self.assertRaises(core.InvalidEvidence):ops.providers('contabo; rm',now=NOW)

    def test_stale_reference_is_visible_not_silently_current(self):
        p=ops.providers(now=NOW+400*86400)
        self.assertEqual(p['review_state'],'RECHECK_REQUIRED')
        self.assertFalse(p['automatically_refreshed'])

    def test_no_provider_link_is_a_runtime_fetch(self):
        with mock.patch.object(core,'get_json') as net:ops.providers()
        net.assert_not_called()

    def test_catalog_uses_https_sources_and_is_complete(self):
        p=ops.providers();self.assertEqual(set(r['id'] for r in p['providers']),set(ops.PROVIDER_SOURCES))
        for provider in p['providers']:
            self.assertTrue(provider['check_next']);self.assertTrue(provider['not_a_promise'])
            for fact in provider['facts']:
                self.assertTrue(fact['source'].startswith('https://'))
                self.assertIn(fact['kind'],('allocation','usage_allowance','credit_model','billing_behavior','product_scope'))

    def test_contabo_diagnostics_guidance_is_dated_primary_and_never_a_run(self):
        entry=ops.providers('contabo')['providers'][0]
        self.assertEqual(len(entry['diagnostics']),1)
        for item in entry['diagnostics']:
            self.assertEqual(item['kind'],'support_request')
            self.assertEqual(item['reviewed_on'],'2026-10-15')
            self.assertTrue(item['source'].startswith('https://help.contabo.com/'))
            self.assertIn('not run implicitly',item['text'])
        with mock.patch.object(core,'get_json') as net:ops.providers('contabo')
        net.assert_not_called()

    def test_diagnostics_source_origin_is_checked(self):
        data=core.read_json(core.ROOT/'assets/provider-catalog.json')
        data['providers'][0]['diagnostics'][0]['source']='https://example.invalid/mtr'
        with mock.patch.object(core,'read_json',return_value=data):
            with self.assertRaises(core.InvalidEvidence):ops.providers('contabo')


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'workspace'

    def hashes(self):
        return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}

    def test_missing_workspace_returns_recovery_without_creation(self):
        result=ops.doctor(self.root)
        self.assertEqual(result['verdict'],'UNAVAILABLE');self.assertFalse(self.root.exists())
        self.assertEqual(result['checks'][0]['code'],'workspace_missing')

    def test_real_demo_diagnosis_makes_no_network_or_writes(self):
        bootstrap(self.root);before=self.hashes()
        with mock.patch.object(core,'get_json') as net,mock.patch.object(core,'cpu_snapshot') as read:
            result=ops.doctor(self.root)
        self.assertEqual(before,self.hashes());net.assert_not_called();read.assert_not_called()
        self.assertTrue(result['read_only']);self.assertIn('synthetic_demo',[c['code'] for c in result['checks']])

    def test_local_diagnostics_do_not_claim_daemon_is_running(self):
        bootstrap(self.root,'local');d=ops.doctor(self.root)
        self.assertIsNone(d['collector_process_running'])
        self.assertFalse(d['can_install_services'])

    def test_malformed_asset_is_a_diagnostic_not_a_traceback(self):
        bootstrap(self.root,'local');cfg=core.read_json(self.root/'workspace.json');cfg['assets']=[None]
        workspace.atomic(self.root/'workspace.json',core.canonical(cfg));before=self.hashes()
        self.assertEqual(ops.doctor(self.root)['verdict'],'UNAVAILABLE')
        self.assertEqual(self.hashes(),before)

    def test_malformed_policy_is_a_diagnostic_not_a_traceback(self):
        bootstrap(self.root,'local');cfg=core.read_json(self.root/'workspace.json');cfg['policy']=[]
        workspace.atomic(self.root/'workspace.json',core.canonical(cfg));before=self.hashes()
        self.assertEqual(ops.doctor(self.root)['verdict'],'UNAVAILABLE')
        self.assertEqual(self.hashes(),before)

    def test_missing_database_is_not_created(self):
        bootstrap(self.root);(self.root/'history.sqlite3').unlink();before=self.hashes()
        result=ops.doctor(self.root)
        self.assertEqual(before,self.hashes());self.assertEqual(result['verdict'],'UNAVAILABLE')

    def test_corrupt_database_reports_category_not_secret_error_text(self):
        bootstrap(self.root);(self.root/'history.sqlite3').write_bytes(b'private-secret-not-a-database')
        result=ops.doctor(self.root)
        self.assertEqual(result['verdict'],'UNAVAILABLE');self.assertNotIn('private-secret',json.dumps(result))

    def test_missing_named_credential_is_reported_without_its_value(self):
        bootstrap(self.root);cfg=core.read_json(self.root/'workspace.json');cfg['token_env']='TEST_VPS_SECRET'
        workspace.atomic(self.root/'workspace.json',core.canonical(cfg))
        with mock.patch.dict(os.environ,{'TEST_VPS_SECRET':'TOP_SECRET_VALUE'}):
            result=ops.doctor(self.root)
        self.assertNotIn('TOP_SECRET_VALUE',json.dumps(result))

    def test_doctor_read_plan_does_not_execute_next_command(self):
        bootstrap(self.root,'local');d=ops.doctor(self.root)
        self.assertTrue(d['next_steps']);self.assertTrue(all('effect' in s for s in d['next_steps']))
        self.assertTrue(any(s['approval_required'] for s in d['next_steps']))

    def test_symlink_database_is_refused_not_followed(self):
        bootstrap(self.root);db=self.root/'history.sqlite3';copy_path=Path(self.temp.name)/'db-copy';db.rename(copy_path);db.symlink_to(copy_path)
        self.assertEqual(ops.doctor(self.root)['verdict'],'UNAVAILABLE')

class DemonstrationTest(unittest.TestCase):
    def test_activity_is_variable_bounded_and_not_a_causal_experiment(self):
        cfg={'assets':[{'id':'example-stable'},{'id':'example-contended'},{'id':'example-offline'}]}
        first=workspace.demo_seed(cfg,NOW);second=workspace.demo_seed(cfg,NOW)
        self.assertEqual(first,second)
        for capture in first:
            self.assertEqual(capture['source']['kind'],'synthetic')
            self.assertTrue(all(0<=s['executing_ratio']<=s['cpu_accounted_ratio'] for s in capture['samples']))
        for key in ('executing_ratio','cpu_pressure_ratio','cfs_throttled_periods_ratio'):
            self.assertGreater(len({s[key] for s in first[1]['samples']}),1)


class TimelineTest(unittest.TestCase):
    policy={'acceptable_ratio':.9,'investigate_below':.8}
    def point(self,ts,value=.95,duration=60,**extra):
        return {'timestamp':ts,'duration_seconds':duration,'cpu_accounted_ratio':value,'quality':[],**extra}

    def test_gap_does_not_become_a_healthy_cell(self):
        cells=ops.timeline([self.point(60),self.point(180)],0,180,self.policy,3)
        self.assertEqual([c['state'] for c in cells],['within','unknown','within'])
        self.assertIsNone(cells[1]['mean'])

    def test_narrow_dip_is_visible_despite_a_good_average(self):
        points=[self.point(55,duration=55),self.point(60,.4,duration=5)]
        cell=ops.timeline(points,0,60,self.policy,1)[0]
        self.assertGreater(cell['mean'],.9);self.assertEqual(cell['minimum'],.4)
        self.assertEqual(cell['state'],'investigate')

    def test_intervals_split_exactly_across_cells(self):
        cells=ops.timeline([self.point(90,duration=90)],0,120,self.policy,2)
        self.assertEqual([c['valid_seconds'] for c in cells],[60,30])
        self.assertEqual(cells[1]['state'],'partial')

    def test_duplicate_intervals_do_not_add_observed_time(self):
        point=self.point(60)
        cell=ops.timeline([point,copy.deepcopy(point)],0,60,self.policy,1)[0]
        self.assertEqual(cell['valid_seconds'],60);self.assertEqual(cell['coverage'],1)

    def test_invalid_interval_remains_unknown(self):
        cells=ops.timeline([self.point(60,quality=['counter_reset'])],0,60,self.policy,1)
        self.assertEqual(cells[0]['state'],'unknown')

    def test_fractional_cell_boundaries_do_not_drop_time(self):
        points=[self.point(101.37,duration=101.37)]
        cells=ops.timeline(points,0,101.37,self.policy,48)
        self.assertAlmostEqual(sum(c['valid_seconds'] for c in cells),101.37,places=8)
        self.assertTrue(all(abs(c['coverage']-1)<1e-8 for c in cells))

    def test_projection_has_no_mutation(self):
        points=[self.point(60)];before=copy.deepcopy(points)
        ops.timeline(points,0,60,self.policy);self.assertEqual(points,before)

class CorrespondenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'workspace';bootstrap(self.root,'local')

    def args(self,**changes):
        data=dict(workspace=self.root,node='example-node',purpose='plan-question',plan='Example shared plan',impact=None,
                  approve_draft=True,example=False,out=Path(self.temp.name)/'question.txt')
        return SimpleNamespace(**{**data,**changes})

    def test_plan_question_needs_permission_but_not_fake_performance_evidence(self):
        args=self.args();result=workspace.draft_email(args);text=args.out.read_text()
        self.assertFalse(result['sent']);self.assertFalse(result['approved_to_send'])
        self.assertIn('Example shared plan',text);self.assertIn('allocation',text)
        self.assertNotIn('averaged',text);self.assertLess(result['words'],150)

    def test_plan_question_cannot_infer_the_purchased_plan(self):
        with self.assertRaises(core.InvalidEvidence):workspace.draft_email(self.args(plan=None))

    def test_plan_question_has_no_automatic_permission(self):
        with self.assertRaises(core.InvalidEvidence):workspace.draft_email(self.args(approve_draft=False))
        self.assertFalse(self.args().out.exists())

    def test_performance_purpose_keeps_original_evidence_gate(self):
        with self.assertRaises(core.InvalidEvidence):workspace.draft_email(self.args(purpose='performance-review',impact='Example service latency'))

    def test_plan_controls_or_overwriting_are_refused(self):
        with self.assertRaises(core.InvalidEvidence):workspace.draft_email(self.args(plan='Plan\nInjected line'))
        args=self.args();workspace.draft_email(args);old=args.out.read_bytes()
        with self.assertRaises(core.InvalidEvidence):workspace.draft_email(args)
        self.assertEqual(args.out.read_bytes(),old)

if __name__=='__main__':unittest.main()
