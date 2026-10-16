#!/usr/bin/env python3
"""Query evaluation spacing must not enlarge the source's five-minute window."""
from pathlib import Path
import copy,hashlib,http.server,json,math,subprocess,sys,tempfile,threading,unittest
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
import vps_evidence as evidence

START=1780000000
PROFILE={'assets':[{'id':'example-metrics','instance':'example.invalid:9100'}]}


def matrix(start=START,end=START+3600,step=300,value='.96'):
    return {'status':'success','data':{'resultType':'matrix','result':[{'metric':{},'values':[[t,value] for t in range(start,end+1,step)]}]}}


def collect(step=3600,hours=72,reply=None):
    with mock.patch.object(core,'get_json',return_value=reply or matrix(START,START+hours*3600,step)):
        return core.collect_prometheus(PROFILE,'https://example.invalid',START,START+hours*3600,step)[0]


def old_capture(step=3600,hours=72):
    c=core.new_capture('example-metrics','prometheus',START,START+hours*3600,step)
    c['source']['tool_sha256']='retained-legacy-five-minute-adapter'
    c['samples']=[{'timestamp':t,'duration_seconds':step,'quality':[],'cpu_accounted_ratio':.96,
                   'executing_ratio':.2,'cpu_pressure_ratio':.01,'cfs_throttled_periods_ratio':None}
                  for t in range(START,START+hours*3600+1,step)]
    return c

class SourceWindowTest(unittest.TestCase):
    def test_hourly_evaluation_does_not_turn_a_five_minute_rate_into_an_hour(self):
        c=collect();self.assertEqual(len(c['samples']),73)
        self.assertTrue(all(p['duration_seconds']==300 for p in c['samples']))
        self.assertAlmostEqual(core.assess(c)['coverage'],1/12)

    def test_standard_cadence_still_covers_the_recorded_window(self):
        for step in (60,120,300):
            with self.subTest(step=step):
                c=collect(step=step,hours=1)
                self.assertTrue(all(p['duration_seconds']==step for p in c['samples']))
                self.assertAlmostEqual(core.assess(c)['coverage'],1.)

    def test_intermediate_coarse_cadence_preserves_its_gaps(self):
        c=collect(step=600,hours=4)
        self.assertAlmostEqual(core.assess(c)['coverage'],.5)

    def test_query_window_and_eval_step_are_explicit_source_metadata(self):
        c=collect();m=c['source']['range_query']
        self.assertEqual(m['rate_window_seconds'],300);self.assertEqual(m['evaluation_step_seconds'],3600)
        self.assertFalse(m['raw_scrape_coverage_verified'])
        self.assertIn('five-minute', ' '.join(c['notes']))

    def test_old_capture_assessment_is_conservative_without_mutating_its_bytes(self):
        c=old_capture();before=core.canonical(c);report=core.assess(c)
        self.assertAlmostEqual(report['coverage'],1/12);self.assertEqual(core.canonical(c),before)
        self.assertIn('insufficient_coverage',report['holds'])

    def test_passive_linux_duration_is_not_capped_by_prometheus_query_rules(self):
        c=old_capture();c['source']['kind']='passive-linux'
        self.assertAlmostEqual(core.assess(c)['coverage'],1.)

    def test_queries_keep_fixed_five_minute_windows_and_no_new_remote_calls(self):
        qs=core.metrics_queries('example.invalid:9100');self.assertEqual(len(qs),7)
        self.assertTrue(all('[5m]' in q for q in qs.values()))
        self.assertTrue(all('[1h]' not in q for q in qs.values()))

class ResponseBoundaryTest(unittest.TestCase):
    def bad(self,body):
        c=collect(hours=1,step=300,reply=body)
        self.assertEqual(c['samples'],[])
        self.assertEqual(len(c['errors']),7)
        self.assertEqual(c['subject']['id'],'example-metrics')

    def test_wrong_result_type_with_empty_result_is_not_silent_success(self):
        self.bad({'status':'success','data':{'resultType':'vector','result':[]}})

    def test_duplicate_or_descending_timestamps_fail_the_entire_channel(self):
        for values in ([[START,'.96'],[START,'.96']],[[START+300,'.96'],[START,'.96']]):
            d=matrix();d['data']['result'][0]['values']=values
            with self.subTest(values=values):self.bad(d)

    def test_off_grid_timestamp_does_not_invent_an_extra_observation(self):
        d=matrix();d['data']['result'][0]['values'].append([START+301,'.96']);self.bad(d)

    def test_bad_pairs_and_special_sample_shapes_remain_per_asset_errors(self):
        for values in ([['not-a-time','.96']],[[START]],[None],{'not':'a sequence'},[[START,True]]):
            d=matrix();d['data']['result'][0]['values']=values
            with self.subTest(values=values):self.bad(d)

    def test_duplicate_series_and_histogram_only_shape_are_not_chosen(self):
        d=matrix();d['data']['result']*=2;self.bad(d)
        d=matrix();d['data']['result'][0]={'metric':{},'histograms':[[START,{}]]};self.bad(d)

    def test_non_finite_values_stay_missing_not_zero(self):
        d=matrix();d['data']['result'][0]['values'][1][1]='NaN';c=collect(hours=1,step=300,reply=d)
        self.assertNotIn(START+300,[p['timestamp'] for p in c['samples']]);self.assertEqual(c['errors'],[])
        self.assertLess(core.assess(c)['coverage'],1)

    def test_bad_optional_channel_does_not_erase_valid_accounting_or_skip_subject(self):
        good=matrix();bad=copy.deepcopy(good);bad['data']['result'][0]['values']=[[START]]
        def get(base,path,params,*args,**kwargs):
            return bad if 'node_pressure_cpu_waiting' in params['query'] else good
        with mock.patch.object(core,'get_json',side_effect=get):c=core.collect_prometheus(PROFILE,'https://example.invalid',START,START+3600)[0]
        self.assertEqual(len(c['samples']),13);self.assertEqual(len(c['errors']),1)
        self.assertTrue(all('cpu_pressure_ratio' not in p for p in c['samples']))
        self.assertTrue(all(p['cpu_accounted_ratio']==.96 for p in c['samples']))

    def test_finite_out_of_domain_values_fail_the_channel_not_other_targets(self):
        for value in ('-0.1','1.5'):
            d=matrix();d['data']['result'][0]['values'][1][1]=value
            with self.subTest(value=value):self.bad(d)

    def test_empty_matrix_is_valid_unmeasured_not_an_api_exception(self):
        d=matrix();d['data']['result']=[];c=collect(hours=1,reply=d)
        self.assertEqual(c['samples'],[]);self.assertEqual(c['errors'],[])

    def test_time_budget_keeps_all_hundred_expected_nodes_visible(self):
        profile={'assets':[{'id':f'example-{i}','instance':f'example-{i}.invalid:9100'} for i in range(100)]}
        with mock.patch.object(core.time,'monotonic',side_effect=[0]+[999]*1000),mock.patch.object(core,'get_json') as get:
            values=core.collect_prometheus(profile,'https://example.invalid',START,START+3600,3600)
        get.assert_not_called();self.assertEqual(len(values),100)
        self.assertTrue(all(not c['samples'] and c['errors'] for c in values))

class RetainedWindowTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve();self.root=self.base/'workspace'
        profile=self.base/'profile.json';core.save_json(profile,{'schema':'g-skills.vps-profile.v1',**PROFILE})
        ws.bootstrap(SimpleNamespace(workspace=self.root,mode='prometheus',profile=profile,url='https://example.invalid',node='example',
           interval=3600,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,acceptable=.9,investigate_below=.8))
        self.cfg=ws.config_load(self.root)[1];self.end=START+72*3600
        ws.ingest(self.root,self.cfg,[old_capture()],self.end)
        # Reproduce rows as actually stored by the old importer, not the fixed one.
        with ws.database(self.root) as db,db:db.execute('UPDATE points SET duration=3600 WHERE ts>?',(START,))

    def unchanged(self):
        return {p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}

    def test_legacy_workspace_reanalysis_preserves_raw_data_but_reports_six_hours_not_seventy_two(self):
        before=self.unchanged();d=ws.status(self.root,now=self.end)['assets'][0]
        self.assertEqual(d['observed_hours'],6);self.assertAlmostEqual(d['coverage'],1/12)
        self.assertEqual(d['decision'],'HOLD');self.assertAlmostEqual(d['mean'],.96)
        self.assertEqual(before,self.unchanged())

    def test_full_range_report_shows_unmeasured_time_and_no_cause_or_contact(self):
        r=evidence.report(self.root,'example-metrics',START,self.end);p=r['profile']
        self.assertEqual(p['observed_seconds'],6*3600);self.assertEqual(p['unobserved_seconds'],66*3600)
        self.assertFalse(r['provider_cause_proven']);self.assertFalse(r['contact_authorized'])

    def test_old_hourly_shortfalls_are_not_stitched_into_a_seventy_two_hour_episode(self):
        root=self.base/'shortfalls';args=SimpleNamespace(workspace=root,mode='prometheus',profile=self.base/'profile.json',url='https://example.invalid',node='example',interval=3600,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,acceptable=.9,investigate_below=.8)
        ws.bootstrap(args);cfg=ws.config_load(root)[1];c=old_capture()
        for p in c['samples']:p['cpu_accounted_ratio']=.7
        ws.ingest(root,cfg,[c],self.end);d=ws.status(root,now=self.end)['assets'][0]
        self.assertEqual(d['evidence_profile']['episodes']['count'],72)
        self.assertEqual(d['evidence_profile']['episodes']['longest_seconds'],300)
        self.assertTrue(all(p['break_before'] for p in d['history'][1:]))

    def test_daily_rollups_use_same_supported_windows(self):
        d=ws.status(self.root,now=self.end)['assets'][0]
        complete=[r for r in d['daily'] if r['complete_utc_day']]
        self.assertTrue(complete);self.assertTrue(all(abs(r['coverage']-1/12)<1e-9 for r in complete))

    def test_repeat_capture_import_adds_no_coverage_and_stored_duration_stays_immutable(self):
        with ws.database(self.root,True) as db:before=[tuple(r) for r in db.execute('SELECT ts,duration,hash FROM points ORDER BY ts')]
        value=ws.ingest(self.root,self.cfg,[old_capture()],self.end);self.assertFalse(value['imported'])
        ws.status(self.root,now=self.end)
        with ws.database(self.root,True) as db:after=[tuple(r) for r in db.execute('SELECT ts,duration,hash FROM points ORDER BY ts')]
        self.assertEqual(before,after);self.assertEqual(after[-1][1],3600)

class RealHTTPTest(unittest.TestCase):
    def test_real_range_api_cannot_expand_estimates_between_coarse_evaluations(self):
        requests=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                requests.append(self.path);raw=json.dumps(matrix(START,START+72*3600,3600)).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            values=core.collect_prometheus(PROFILE,'http://127.0.0.1:'+str(server.server_port),START,START+72*3600,3600)
            self.assertEqual(len(requests),7);self.assertTrue(all('step=3600' in url for url in requests))
            self.assertAlmostEqual(core.assess(values[0])['coverage'],1/12)
        finally:server.shutdown();server.server_close();thread.join(3)

if __name__=='__main__':unittest.main()
