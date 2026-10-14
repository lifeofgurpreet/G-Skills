import copy
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

P=Path(__file__).resolve().parents[1]/'scripts/vps_health.py'
spec=importlib.util.spec_from_file_location('health',P);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
START=1760000000


def fixture(mean=.93,pressure=.02):
    c=h.new_capture('example-a','synthetic',START,START+86400,300)
    c['samples']=[{'timestamp':START+i*300,'duration_seconds':300,'quality':[],
                  'cpu_accounted_ratio':mean,'executing_ratio':.2,'steal_ratio':0,
                  'cpu_pressure_ratio':pressure,'cfs_throttled_periods_ratio':0} for i in range(289)]
    return c


def snap(t,ticks,boot='same'):
    return {'start_ns':int((100+t)*1e9),'end_ns':int((100+t)*1e9),'wall_start_ns':int((START+t)*1e9),
            'wall_end_ns':int((START+t)*1e9),'boot_fingerprint':boot,
            'cpus':{'cpu0':[1000+ticks,0,0,0,0,0,0,0]},'pressure':{'cpu':0,'io':0,'memory':0}}


class PolicyTests(unittest.TestCase):
    def test_ninety_three_percent_is_tolerable_not_certification(self):
        r=h.assess(fixture());self.assertEqual(r['state'],'WITHIN_WORKING_TOLERANCE')
        self.assertAlmostEqual(r['accounted_mean'],.93);self.assertFalse(r['provider_cause_proven'])
        self.assertFalse(r['contact_provider']);self.assertFalse(r['service_health_verified'])

    def test_below_tolerance_with_pressure_is_mixed_not_provider_blame(self):
        r=h.assess(fixture(.85,.3));self.assertEqual(r['state'],'LOW_ACCOUNTING_WITH_CONTENTION');self.assertFalse(r['contact_provider'])

    def test_low_ratio_without_context_does_not_exclude_our_work(self):
        r=h.assess(fixture(.85,None));self.assertEqual(r['state'],'LOW_ACCOUNTING_NEEDS_CONTEXT');self.assertIn('cpu_pressure_context_missing',r['holds'])

    def test_no_samples_is_not_healthy(self):
        c=fixture();c['samples']=[];r=h.assess(c);self.assertEqual(r['state'],'NOT_MEASURED');self.assertEqual(r['coverage'],0)

    def test_missing_cfs_is_not_zero(self):
        c=fixture()
        for r in c['samples']:r.pop('cfs_throttled_periods_ratio')
        self.assertIn('workload_cfs_context_missing',h.assess(c)['holds'])

    def test_sparse_evidence_retains_gap(self):
        c=fixture();c['samples']=c['samples'][::10];r=h.assess(c)
        self.assertLess(r['coverage'],.11);self.assertIn('insufficient_coverage',r['holds'])

    def test_dense_burst_cannot_fake_day_of_coverage(self):
        c=fixture()
        for i,r in enumerate(c['samples']):r['timestamp']=START+i
        self.assertLess(h.assess(c)['coverage'],.01)

    def test_unequal_durations_weight_by_represented_time(self):
        c=h.new_capture('example-a','synthetic',START,START+400,300)
        c['samples']=[{'timestamp':START+100,'duration_seconds':100,'quality':[],'cpu_accounted_ratio':.5},
                      {'timestamp':START+400,'duration_seconds':300,'quality':[],'cpu_accounted_ratio':1}]
        self.assertEqual(h.assess(c)['accounted_mean'],.875)

    def test_duplicate_or_reversed_timestamps_refused(self):
        for mutate in (lambda c:c['samples'].reverse(),lambda c:c['samples'].__setitem__(1,copy.deepcopy(c['samples'][0]))):
            c=fixture();mutate(c)
            with self.assertRaises(h.InvalidEvidence):h.assess(c)

    def test_nonfinite_bool_and_string_ratios_refused(self):
        for v in (float('nan'),float('inf'),True,'0.9',-1):
            c=fixture();c['samples'][0]['cpu_accounted_ratio']=v
            with self.subTest(value=v),self.assertRaises(h.InvalidEvidence):h.assess(c)

    def test_caller_cannot_grant_authority(self):
        c=fixture();c.update(provider_cause_proven=True,contact_provider=True)
        r=h.assess(c);self.assertFalse(r['contact_provider']);self.assertFalse(r['provider_cause_proven'])

    def test_unknown_schema_and_source_rejected(self):
        for field,value in (('schema','v99'),('source',{'kind':'guess'})):
            c=fixture();c[field]=value
            with self.assertRaises(h.InvalidEvidence):h.assess(c)

    def test_known_quality_failures_reduce_evidence(self):
        c=fixture()
        for r in c['samples']:r['quality']=['clock_discontinuity']
        self.assertEqual(h.assess(c)['state'],'NOT_MEASURED');self.assertIn('clock_discontinuity',h.assess(c)['holds'])

    def test_unqualified_out_of_domain_ratio_cannot_pass(self):
        c=fixture();c['samples'][0]['cpu_accounted_ratio']=1.5
        with self.assertRaises(h.InvalidEvidence):h.assess(c)

    def test_dates_require_timezone(self):
        for value in ('now-24h','2026-10-01T00:00:00',123):
            with self.assertRaises(h.InvalidEvidence):h.stamp(value)


class ProbeTests(unittest.TestCase):
    def test_stable_local_sample_reports_counter_fraction(self):
        r=h.local_interval(snap(0,0),snap(2,196),100,2)
        self.assertAlmostEqual(r['cpu_accounted_ratio'],.98);self.assertEqual(r['quality'],[])

    def test_clock_steps_flag_but_do_not_clamp(self):
        b=snap(2,196);b['wall_start_ns']+=60_000_000_000;b['wall_end_ns']+=60_000_000_000
        r=h.local_interval(snap(0,0),b,100,2);self.assertIn('clock_discontinuity',r['quality'])

    def test_cpu_hotplug_invalidates(self):
        b=snap(2,196);b['cpus']['cpu1']=[0]*8
        self.assertIn('cpu_set_changed',h.local_interval(snap(0,0),b,100,2)['quality'])

    def test_counter_decrease_is_not_lost_cpu(self):
        b=snap(2,-5);r=h.local_interval(snap(0,0),b,100,2)
        self.assertIn('counter_decreased',r['quality']);self.assertIsNone(r['cpu_accounted_ratio'])

    def test_unknown_or_changed_boot_is_not_bridged(self):
        r=h.local_interval(snap(0,0),snap(2,196,'other'),100,2);self.assertIsNone(r['cpu_accounted_ratio'])

    def test_gap_and_overhead_visible(self):
        r=h.local_interval(snap(0,0),snap(20,196),100,2);self.assertIn('sampling_gap',r['quality'])
        b=snap(2,196);b['end_ns']+=400_000_000
        self.assertIn('measurement_overhead',h.local_interval(snap(0,0),b,100,2)['quality'])

    def test_bounded_observation_before_any_read(self):
        with mock.patch.object(h,'cpu_snapshot') as capture:
            for interval,n in ((0,2),(10,2),(5,31),(2,100),(float('nan'),3)):
                with self.assertRaises(h.InvalidEvidence):h.collect_local('example',interval,n)
            capture.assert_not_called()

    def test_non_linux_refuses_without_installing(self):
        with mock.patch.object(h.sys,'platform','darwin'),self.assertRaises(h.InvalidEvidence):h.collect_local('example')

    def test_proc_files_read_in_small_bounded_chunks(self):
        real_fdopen=h.os.fdopen
        class Reader:
            def __init__(self,handle):self.handle=handle
            def __enter__(self):return self
            def __exit__(self,*args):self.handle.close()
            def fileno(self):return self.handle.fileno()
            def read(self,n=-1):
                if not 0<=n<=4096:raise AssertionError('oversized proc read')
                return self.handle.read(n)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'regular';p.write_bytes(b'x'*8200)
            with mock.patch.object(h.os,'fdopen',side_effect=lambda fd,mode:Reader(real_fdopen(fd,mode))):
                self.assertEqual(h.read_bytes(p),b'x'*8200)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def bundle(self,name='report',c=None):
        p=self.root/name;h.report([c or fixture()],p);return p

    def test_report_and_replay_verify(self):
        p=self.bundle();self.assertEqual(h.verify_bundle(p)['replay'],'PASS')
        self.assertIn('WITHIN_WORKING_TOLERANCE',(p/'report.html').read_text())

    def test_rehashed_report_cannot_grant_contact_authority(self):
        p=self.bundle();r=h.read_json(p/'report.json');r['contact_provider']=True
        (p/'report.json').write_text(json.dumps(r))
        m=h.read_json(p/'manifest.json');m['files']['report.json']=hashlib.sha256((p/'report.json').read_bytes()).hexdigest()
        (p/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(h.InvalidEvidence):h.verify_bundle(p)

    def test_tampering_is_detected(self):
        p=self.bundle();(p/'report.html').write_text('wrong')
        with self.assertRaises(h.InvalidEvidence):h.verify_bundle(p)

    def test_outputs_never_overwrite(self):
        p=self.bundle()
        with self.assertRaises(FileExistsError):h.report([fixture()],p)

    def test_path_injection_and_private_names_not_accepted_as_aliases(self):
        for name in ('../../secrets','<script>alert(1)</script>','x\ny','a'*81):
            with self.assertRaises(h.InvalidEvidence):h.alias(name)

    def test_manifest_traversal_refused(self):
        p=self.bundle();m=h.read_json(p/'manifest.json');m['files']['../secret']='0'*64
        (p/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(h.InvalidEvidence):h.verify_bundle(p)

    def test_lessons_whitelist_no_identifiers_or_logs(self):
        c=fixture();c['subject']['id']='private-host-name';c['raw']={'logs':'private email@example.org and 198.51.100.42'}
        p=self.bundle(c=c);target=self.root/'lesson.json';h.lesson_proposal(p,target);s=target.read_text()
        for forbidden in ('private-host-name','email@example.org','198.51.100.42','"logs"'):self.assertNotIn(forbidden,s)
        self.assertFalse(h.read_json(target)['can_change_policy']);self.assertFalse(h.read_json(target)['can_publish'])

    def test_learning_never_modifies_skill_or_report(self):
        p=self.bundle();before=P.read_bytes();manifest=(p/'manifest.json').read_bytes()
        h.lesson_proposal(p,self.root/'lesson.json')
        self.assertEqual(P.read_bytes(),before);self.assertEqual((p/'manifest.json').read_bytes(),manifest)

    def test_comparison_does_not_claim_causality(self):
        a=self.bundle('a');b=self.bundle('b',fixture(.85,.3));r=h.compare(a,b)
        self.assertFalse(r['causal_claim']);self.assertAlmostEqual(r['changes'][0]['accounted_delta'],-.08)

    def test_compare_rejects_changed_subjects(self):
        a=self.bundle('a');c=fixture();c['subject']['id']='other';b=self.bundle('b',c)
        with self.assertRaises(h.InvalidEvidence):h.compare(a,b)

    def test_cli_end_to_end_demo_report_and_learn(self):
        out=self.root/'demo'
        p=subprocess.run([sys.executable,str(P),'demo','--out',str(out)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run([sys.executable,str(P),'verify',str(out)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run([sys.executable,str(P),'learn',str(out),'--out',str(self.root/'proposal.json')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_no_source_input_can_send_provider_message(self):
        self.assertFalse(h.POLICY['automatic_changes']);self.assertEqual(h.POLICY['provider_contact'],'human-decision-only')


class ApiTests(unittest.TestCase):
    def test_endpoints_reject_embedded_secrets_and_non_http(self):
        for url in ('file:///tmp/x','https://u:p@example.org','https://example.org?q=token','https://example.org#token','http://example.org'):
            with self.assertRaises(h.InvalidEvidence):h.endpoint(url)
        self.assertEqual(h.endpoint('http://127.0.0.1:123/'),'http://127.0.0.1:123')

    def test_no_credentials_over_plaintext(self):
        with self.assertRaises(h.InvalidEvidence):h.get_json('http://127.0.0.1','/api/v1/query',{},'secret')

    def test_redirects_do_not_forward_credentials(self):
        with self.assertRaises(h.InvalidEvidence):h.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')

    def test_json_duplicates_and_nonfinite_refused(self):
        for text in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
            with self.assertRaises(h.InvalidEvidence):h.decode(text)

    def test_metric_selector_escapes_labels(self):
        q=h.metrics_queries('x"} or vector(1) #')['cpu_accounted_ratio']
        self.assertIn('x\\"',q)

    def test_collection_bounds(self):
        with self.assertRaises(h.InvalidEvidence):h.collect_prometheus({'assets':[]},'https://example.org',START,START+99999999)

    def test_http_transport_and_failure_retention(self):
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                calls.append(self.path)
                data={'status':'success','data':{'resultType':'matrix','result':[{'metric':{},'values':[[START+i*300,'0.93'] for i in range(13)]}]}}
                body=json.dumps(data).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            rows=h.collect_prometheus({'assets':[{'id':'example-a','instance':'192.0.2.1:9100'}]},f'http://127.0.0.1:{server.server_port}',START,START+3600)
            self.assertEqual(len(calls),7);self.assertEqual(len(rows[0]['samples']),13);self.assertEqual(rows[0]['errors'],[])
        finally:server.shutdown();server.server_close();thread.join()

    def test_prometheus_warning_is_not_valid_evidence(self):
        response=io.BytesIO(json.dumps({'status':'success','warnings':['partial'],'data':{'result':[]}}).encode())
        with mock.patch.object(h.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=response
            with self.assertRaises(h.InvalidEvidence):h.get_json('https://example.org','/api/v1/query',{})

    def test_token_not_reused_for_loki(self):
        calls=[]
        def get(base,path,params,token=None,**kw):
            calls.append((base,token));return {'status':'success','data':{'resultType':'matrix','result':[]}}
        p={'assets':[{'id':'example','instance':'example:9100','loki_selector':'{app="example"}'}]}
        with mock.patch.object(h,'get_json',side_effect=get):h.collect_prometheus(p,'https://prom.example',START,START+3600,token='prom-token',loki='https://logs.example')
        self.assertIn(('https://logs.example',None),calls)

    def test_time_budget_stops_requests_without_losing_expected_assets(self):
        p={'assets':[{'id':'example','instance':'example:9100'}]}
        with mock.patch.object(h.time,'monotonic',side_effect=[0]+[999]*20),mock.patch.object(h,'get_json') as get:
            result=h.collect_prometheus(p,'https://example.org',START,START+3600)
            get.assert_not_called();self.assertEqual(len(result),1);self.assertTrue(result[0]['errors'])


if __name__=='__main__':unittest.main()
