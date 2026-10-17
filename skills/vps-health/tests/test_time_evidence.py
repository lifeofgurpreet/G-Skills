#!/usr/bin/env python3
"""Observation duration, not a reassuring average or a sample count, is evidence."""
from pathlib import Path
import copy
import json
import math
import hashlib
import subprocess
from types import SimpleNamespace
import random
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
sys.path.insert(0,str(Path(__file__).parent))
from test_workspace import args,capture,NOW

POLICY={'acceptable_ratio':.9,'investigate_below':.8}
def point(end,value=.95,duration=300,execution=.2,pressure=.01,cfs=0.,**more):
    return {'timestamp':float(end),'duration_seconds':duration,'cpu_accounted_ratio':value,
            'executing_ratio':execution,'cpu_pressure_ratio':pressure,'cfs_throttled_periods_ratio':cfs,
            'quality':[],**more}

class ContextCoverageTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'private';ws.bootstrap(args(self.root,'local'));self.cfg=ws.config_load(self.root)[1]
    def test_one_quiet_sample_cannot_clear_three_days_of_unknown_workload_context(self):
        cap=capture(start=NOW-3*86400,ratio=.96)
        for p in cap['samples']:p.update(executing_ratio=.2,cpu_pressure_ratio=None,cfs_throttled_periods_ratio=None)
        cap['samples'][-1].update(cpu_pressure_ratio=0.,cfs_throttled_periods_ratio=0.)
        ws.ingest(self.root,self.cfg,[cap],NOW);value=ws.status(self.root,NOW);n=value['assets'][0]
        self.assertEqual(n['context'],'CONTEXT_INCOMPLETE')
        self.assertEqual(n['decision'],'WITHIN_TOLERANCE')  # CPU policy is not rewritten.
        self.assertIn('workload_context_sparse',n['holds'])
        self.assertAlmostEqual(n['evidence_profile']['channels']['cfs']['coverage'],300/(3*86400))
        self.assertEqual(value['operator']['items'][0]['kind'],'workload_context_gap')
    def test_old_context_does_not_become_current_because_cpu_counters_are_fresh(self):
        cap=capture(start=NOW-3*86400,ratio=.96)
        for p in cap['samples']:
            p['executing_ratio']=.2
            if p['timestamp']>NOW-3600:p.update(cpu_pressure_ratio=None,cfs_throttled_periods_ratio=None)
        ws.ingest(self.root,self.cfg,[cap],NOW);n=ws.status(self.root,NOW)['assets'][0]
        self.assertFalse(n['stale']);self.assertEqual(n['context'],'CONTEXT_INCOMPLETE')
    def test_elevated_partial_pressure_is_not_erased_by_incomplete_coverage(self):
        cap=capture(start=NOW-3*86400,ratio=.96)
        for p in cap['samples']:p.update(cpu_pressure_ratio=None,cfs_throttled_periods_ratio=None)
        cap['samples'][-1]['cpu_pressure_ratio']=.4
        ws.ingest(self.root,self.cfg,[cap],NOW);n=ws.status(self.root,NOW)['assets'][0]
        self.assertEqual(n['context'],'CONTENTION_PRESENT');self.assertIn('workload_context_sparse',n['holds'])
        self.assertFalse(n['provider_cause_proven'])
    def test_fully_observed_quiet_context_preserves_existing_classification(self):
        cap=capture(start=NOW-3*86400,ratio=.96)
        for p in cap['samples']:p['executing_ratio']=.2
        ws.ingest(self.root,self.cfg,[cap],NOW);n=ws.status(self.root,NOW)['assets'][0]
        self.assertEqual(n['context'],'NO_HIGH_PRESSURE_IN_RECORDED_CONTEXT')
        self.assertNotIn('workload_context_sparse',n['holds'])

class TemporalProfileTest(unittest.TestCase):
    def setUp(self):
        import vps_evidence
        self.e=vps_evidence
    def profile(self,points,start=0,end=3600):return self.e.summarize(points,start,end,POLICY,300)
    def test_time_weighted_bands_not_sample_count_or_peak(self):
        d=self.profile([point(300,.5),point(3600,1.,3300)])
        self.assertAlmostEqual(d['bands']['investigate_seconds'],300)
        self.assertAlmostEqual(d['bands']['within_seconds'],3300)
        self.assertAlmostEqual(d['channels']['accounted']['mean'],3450/3600)
        self.assertEqual(d['episodes']['longest_seconds'],300)
    def test_chosen_policy_boundaries_are_exact_and_not_new_thresholds(self):
        d=self.profile([point(300,.9),point(600,.8),point(900,.799)],end=900)
        self.assertEqual(d['bands'],{'within_seconds':300.,'watch_seconds':300.,'investigate_seconds':300.})
    def test_outages_split_shortfall_runs_and_stay_unobserved(self):
        d=self.profile([point(300,.5),point(600,.6),point(1500,.5),point(1800,.5)],end=1800)
        self.assertEqual(d['episodes']['count'],2);self.assertEqual(d['episodes']['longest_seconds'],600)
        self.assertEqual(d['unobserved_seconds'],600);self.assertEqual(d['observed_seconds'],1200)
    def test_quality_failure_splits_runs_and_is_not_interpolated(self):
        d=self.profile([point(300,.5),point(600,.1,quality=['counter_reset']),point(900,.5)],end=900)
        self.assertEqual(d['episodes']['count'],2);self.assertEqual(d['invalid_seconds'],300)
        self.assertEqual(d['unobserved_seconds'],0);self.assertEqual(d['missing_seconds'],300)
    def test_overlapping_or_repeated_intervals_never_add_extra_time(self):
        data=[point(300,.7),point(300,.7),point(450,.7,300),point(600,.7)]
        d=self.profile(data,end=600);self.assertEqual(d['observed_seconds'],600)
        self.assertEqual(d['episodes']['longest_seconds'],600)
    def test_missing_context_is_a_separate_channel_not_zero(self):
        d=self.profile([point(300,.9,pressure=None,cfs=None),point(600,.9,pressure=0,cfs=0)],end=600)
        self.assertEqual(d['channels']['accounted']['coverage'],1)
        self.assertEqual(d['channels']['pressure']['coverage'],.5)
        self.assertEqual(d['channels']['pressure']['mean'],0)
        self.assertFalse(d['channels']['pressure']['qualified'])
    def test_low_execution_is_not_low_demand_or_provider_guilt(self):
        d=self.profile([point(300,.4,execution=.15,pressure=.8)],end=300)
        row=next(r for r in d['execution_bands'] if r['id']=='low')
        self.assertEqual(row['seconds'],300);self.assertEqual(row['pressure_mean'],.8)
        self.assertFalse(d['provider_cause_proven']);self.assertIn('not demand',d['method'])
    def test_missing_execution_has_its_own_retained_bucket(self):
        d=self.profile([point(300,.5,execution=None)],end=600)
        row=next(r for r in d['execution_bands'] if r['id']=='unknown')
        self.assertEqual(row['seconds'],300);self.assertEqual(d['unobserved_seconds'],300)
    def test_recent_window_delta_requires_two_complete_observed_windows(self):
        d=self.profile([point(t,.6 if t>3600 else .98) for t in range(300,7201,300)],end=7200)
        self.assertEqual(d['recent_change']['state'],'OBSERVED_WINDOWS')
        self.assertAlmostEqual(d['recent_change']['mean_delta'],-.38)
        early=self.profile([point(300,.6)],end=300)
        self.assertEqual(early['recent_change']['state'],'INSUFFICIENT_EVIDENCE');self.assertIsNone(early['recent_change']['mean_delta'])
    def test_source_mean_does_not_change_when_only_the_display_is_decimated(self):
        data=[point(i*300,.95 if i%7 else .5) for i in range(1,4001)]
        before=self.profile(data,end=1200000);ws.chart_history(data,300)
        self.assertEqual(before,self.profile(data,end=1200000));self.assertLessEqual(len(before['episodes']['longest']),5)
    def test_duration_partitions_and_input_are_preserved(self):
        rng=random.Random(87);data=[point(t,rng.uniform(.2,1.)) for t in range(300,7201,300)]
        for p in data[::7]:p['quality']=['unknown']
        del data[10:12];saved=copy.deepcopy(data);d=self.profile(data,end=7200)
        self.assertAlmostEqual(d['observed_seconds']+d['invalid_seconds']+d['unobserved_seconds'],7200)
        self.assertAlmostEqual(sum(d['bands'].values()),d['observed_seconds'])
        self.assertAlmostEqual(sum(r['seconds'] for r in d['execution_bands']),d['observed_seconds'])
        self.assertEqual(data,saved)
    def test_translation_changes_only_time_not_durations_or_values(self):
        data=[point(300,.5),point(900,.5)];a=self.profile(data,end=900)
        moved=[{**p,'timestamp':p['timestamp']+10000} for p in data];b=self.profile(moved,start=10000,end=10900)
        self.assertEqual(a['bands'],b['bands']);self.assertEqual(a['episodes']['count'],b['episodes']['count'])
        self.assertEqual(a['episodes']['longest_seconds'],b['episodes']['longest_seconds'])
    def test_empty_and_zero_span_never_fabricate_measurements(self):
        for end in (0,3600):
            d=self.profile([],end=end);self.assertIsNone(d['channels']['accounted']['mean']);self.assertEqual(d['observed_seconds'],0)
            self.assertEqual(d['unobserved_seconds'],end);self.assertEqual(d['episodes']['count'],0)
    def test_bad_order_and_nonfinite_inputs_fail(self):
        for data in ([point(600),point(300)],[point(float('nan'))],[point(300,duration=-1)]):
            with self.subTest(data=data),self.assertRaises(core.InvalidEvidence):self.profile(data)

class ReportTest(unittest.TestCase):
    setUp=ContextCoverageTest.setUp
    def fixture(self):
        cap=capture(start=NOW-3*86400,ratio=.96)
        for row in cap['samples']:row.update(executing_ratio=.2,cpu_pressure_ratio=None,cfs_throttled_periods_ratio=None)
        cap['samples'][-1].update(cpu_pressure_ratio=0.,cfs_throttled_periods_ratio=0.)
        ws.ingest(self.root,self.cfg,[cap],NOW)

    def hashes(self):
        return {p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_report_uses_one_read_transaction_for_summary_and_provenance(self):
        import vps_evidence as e
        self.fixture();original=ws.status;connections=[]
        def checked(*args,**kwargs):
            db=kwargs.get('_read_db');self.assertIsNotNone(db);self.assertTrue(db.in_transaction)
            connections.append(db)
            return original(*args,**kwargs)
        with mock.patch.object(ws,'status',side_effect=checked):r=e.report(self.root,'example-node',NOW-86400,NOW)
        self.assertEqual(len(connections),1);self.assertTrue(r['observation_hashes'])

    def test_configuration_change_is_not_silently_accepted_during_report(self):
        import vps_evidence as e
        self.fixture();old=ws.status
        def changed(*args,**kwargs):
            result=old(*args,**kwargs);result['configuration_sha256']='0'*64;return result
        with mock.patch.object(ws,'status',side_effect=changed):
            with self.assertRaises(core.InvalidEvidence):e.report(self.root,'example-node',NOW-86400,NOW)

    def test_requested_range_does_not_shrink_to_first_sample(self):
        import vps_evidence as e
        self.fixture();r=e.report(self.root,'example-node',NOW-4*86400,NOW)
        self.assertEqual(r['profile']['window_seconds'],4*86400)
        self.assertEqual(r['profile']['observed_seconds'],3*86400)
        self.assertEqual(r['profile']['unobserved_seconds'],86400)
        self.assertEqual(r['workload_context'],'CONTEXT_INCOMPLETE')

    def test_read_only_replay_makes_no_collection_or_runtime_change(self):
        import vps_evidence as e
        self.fixture();before=self.hashes()
        with mock.patch.object(core,'get_json') as network,mock.patch.object(core,'cpu_snapshot') as sample:
            r=e.report(self.root,'example-node',NOW-3*86400,NOW)
        network.assert_not_called();sample.assert_not_called();self.assertEqual(before,self.hashes())
        self.assertTrue(r['read_only']);self.assertFalse(r['new_measurements']);self.assertTrue(r['observation_hashes'])
        self.assertFalse(r['provider_cause_proven']);self.assertFalse(r['contact_authorized'])

    def test_new_private_cli_report_reuses_the_installed_command_entry(self):
        self.fixture();out=Path(self.temp.name)/'report.json'
        subprocess.run([sys.executable,str(Path(core.__file__)),'evidence-report','--workspace',str(self.root),
            '--node','example-node','--start',core.iso(NOW-3*86400),'--end',core.iso(NOW),'--out',str(out)],
            check=True,capture_output=True,timeout=20)
        r=core.read_json(out);self.assertEqual(r['profile']['channels']['cfs']['coverage'],300/(3*86400))
        self.assertEqual(out.stat().st_mode&0o777,0o600)

    def test_unsupported_subject_and_unbounded_or_empty_range_refuse(self):
        import vps_evidence as e
        for node,start,end in [('different',NOW-60,NOW),('example-node',NOW,NOW),('example-node',NOW-15*86400,NOW)]:
            with self.subTest(node=node,start=start),self.assertRaises(core.InvalidEvidence):e.report(self.root,node,start,end)

    def test_report_cannot_overwrite_or_land_inside_retained_workspace(self):
        import vps_evidence as e
        self.fixture();out=Path(self.temp.name)/'existing.json';out.write_text('keep')
        for target in (out,self.root/'report.json'):
            a=SimpleNamespace(workspace=self.root,node='example-node',start=core.iso(NOW-86400),end=core.iso(NOW),out=target)
            with self.subTest(target=target),self.assertRaises((ValueError,FileExistsError)):e.dispatch(a)
        self.assertEqual(out.read_text(),'keep');self.assertFalse((self.root/'report.json').exists())

    def test_epoch_change_does_not_pull_old_context_into_a_new_host(self):
        import vps_evidence as e
        self.fixture();cfg=copy.deepcopy(self.cfg);cfg['assets'][0]['epoch']='after-migration'
        ws.atomic(self.root/'workspace.json',core.canonical(cfg));r=e.report(self.root,'example-node',NOW-3*86400,NOW)
        self.assertEqual(r['profile']['observed_seconds'],0);self.assertEqual(r['observation_hashes'],[])
        self.assertIn('epoch_changed_collect_new_evidence',r['limitations'])

    def test_shared_weighting_matches_legacy_reference_with_gaps_and_duplicates(self):
        import vps_evidence as e
        def legacy(rows,start,end):
            cursor=start;total=0.;weight=0.
            for p in rows:
                right=min(p['timestamp'],end);left=max(start,p['timestamp']-p['duration_seconds'],cursor)
                delta=max(0,right-left);cursor=max(cursor,right)
                if p.get('quality') or p.get('conflict') or p.get('cpu_accounted_ratio') is None:continue
                total+=p['cpu_accounted_ratio']*delta;weight+=delta
            return total/weight if weight else None,weight
        rng=random.Random(519)
        for _ in range(30):
            rows=[point(i*60,rng.random(),duration=rng.choice([30,60,90,120])) for i in range(1,100)]
            for row in rows[::9]:row['quality']=['counter_reset']
            rows.insert(30,copy.deepcopy(rows[30]));mean,weight=legacy(rows,0,6000)
            d=e.summarize(rows,0,6000,POLICY,60)
            self.assertAlmostEqual(d['channels']['accounted']['mean'],mean)
            self.assertAlmostEqual(d['observed_seconds'],weight)
            self.assertEqual(ws.weighted(rows,0,6000)['means']['cpu_accounted_ratio'],mean)


class ReportBoundaryTest(unittest.TestCase):
    setUp=ContextCoverageTest.setUp
    hashes=ReportTest.hashes

    def retain(self,rows,start=NOW-600,end=NOW):
        cap=capture(start=start,end=end,ratio=.5);cap['samples']=rows
        ws.ingest(self.root,self.cfg,[cap],end)
        return cap

    def report(self,start,end):
        import vps_evidence as e
        return e.report(self.root,'example-node',start,end)

    def test_cli_window_inside_retained_interval_keeps_measured_time_and_provenance(self):
        row=point(NOW,.5);self.retain([row]);before=self.hashes()
        command=[sys.executable,str(Path(core.__file__)),'evidence-report','--workspace',str(self.root),
                 '--node','example-node','--start',core.iso(NOW-200),'--end',core.iso(NOW-100)]
        result=subprocess.run(command,cwd=self.temp.name,capture_output=True,text=True,check=True,timeout=20)
        value=json.loads(result.stdout);profile=value['profile']
        self.assertEqual(profile['window_seconds'],100)
        self.assertEqual(profile['observed_seconds'],100)
        self.assertEqual(profile['missing_seconds'],0)
        self.assertEqual(profile['channels']['accounted']['mean'],.5)
        self.assertEqual(value['observation_hashes'],[core.digest(row)])
        self.assertEqual(self.hashes(),before)

    def test_end_overlap_is_clipped_once_without_future_chart_or_freshness(self):
        self.retain([point(NOW-300,.95),point(NOW,.5),point(NOW+100,.9)],end=NOW+100)
        value=ws.status(self.root,now=NOW-50,window_start=NOW-300)['assets'][0]
        profile=value['evidence_profile']
        self.assertEqual(profile['observed_seconds'],250)
        self.assertEqual(profile['bands']['investigate_seconds'],250)
        self.assertEqual(profile['episodes']['longest_seconds'],250)
        self.assertEqual(profile['channels']['accounted']['mean'],.5)
        self.assertEqual(value['last_sample'],NOW-50)
        self.assertEqual(value['age_seconds'],0)
        self.assertTrue(all(NOW-300<=row['t']<=NOW-50 for row in value['history']))

    def test_future_interval_that_does_not_overlap_stays_unobserved(self):
        self.retain([point(NOW,.5)])
        value=self.report(NOW-600,NOW-301)
        self.assertEqual(value['profile']['observed_seconds'],0)
        self.assertEqual(value['profile']['unobserved_seconds'],299)
        self.assertEqual(value['observation_hashes'],[])

    def test_nonoverlapping_future_row_keeps_its_existing_interval_ownership(self):
        rows=[point(NOW+50,.95,duration=10),point(NOW+100,.5)]
        self.retain(rows,end=NOW+100)
        import vps_evidence as e
        direct=e.summarize(rows,NOW-150,NOW,self.cfg['policy'],300)
        value=self.report(NOW-150,NOW)
        self.assertEqual(direct['observed_seconds'],0)
        self.assertEqual(value['profile']['observed_seconds'],direct['observed_seconds'])
        self.assertEqual(value['profile']['unobserved_seconds'],150)
        self.assertEqual(value['observation_hashes'],[])
        containing=self.report(NOW-150,NOW+100)
        self.assertEqual(containing['profile']['observed_seconds'],60)

    def test_legacy_prometheus_duration_cannot_reach_back_past_five_minutes(self):
        self.retain([point(NOW,.5)])
        with ws.database(self.root) as db,db:db.execute('UPDATE points SET duration=3600')
        before=self.hashes();value=self.report(NOW-800,NOW-400)
        self.assertEqual(value['profile']['observed_seconds'],0)
        self.assertEqual(value['observation_hashes'],[])
        inside=self.report(NOW-200,NOW-100)
        self.assertEqual(inside['profile']['observed_seconds'],100)
        self.assertEqual(self.hashes(),before)

    def test_invalid_crossing_interval_remains_invalid_instead_of_a_gap(self):
        row=point(NOW,.5,quality=['counter_reset']);self.retain([row])
        value=self.report(NOW-200,NOW-100)
        self.assertEqual(value['profile']['observed_seconds'],0)
        self.assertEqual(value['profile']['invalid_seconds'],100)
        self.assertEqual(value['profile']['unobserved_seconds'],0)
        self.assertEqual(value['observation_hashes'],[core.digest(row)])

    def test_conflicting_crossing_interval_cannot_supply_measurement(self):
        original=self.retain([point(NOW,.5)])
        other=copy.deepcopy(original);other['samples'][0]['cpu_accounted_ratio']=.95
        ws.ingest(self.root,self.cfg,[other],NOW)
        value=self.report(NOW-200,NOW-100)
        self.assertEqual(value['profile']['observed_seconds'],0)
        self.assertEqual(value['profile']['invalid_seconds'],100)
        self.assertIn('conflicting_sample_values',value['limitations'])

    def test_live_status_does_not_read_observations_after_its_cutoff(self):
        self.retain([point(NOW,.5)])
        value=ws.status(self.root,now=NOW-100)['assets'][0]
        self.assertEqual(value['points'],0)
        self.assertIsNone(value['last_sample'])
        self.assertEqual(value['evidence_profile']['observed_seconds'],0)

if __name__=='__main__':unittest.main()
