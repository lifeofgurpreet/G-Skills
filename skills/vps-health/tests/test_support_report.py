#!/usr/bin/env python3
"""Public-support summaries are constructed from allowed fields, not redacted logs."""
from pathlib import Path
import hashlib,json,os,sqlite3,subprocess,sys,tempfile,unittest
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
import vps_ops as ops


def setup(root,mode='demo'):
    return ws.bootstrap(SimpleNamespace(workspace=root,mode=mode,node='private-node-name',profile=None,url=None,loki_url=None,
        token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,investigate_below=.8))


def files(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

class SupportReportTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve();self.root=self.base/'private-workspace'

    def test_no_workspace_reports_only_installed_software_without_host_discovery(self):
        with mock.patch.object(core,'cpu_snapshot') as cpu,mock.patch.object(core,'get_json') as net:
            d=ops.support_report()
        cpu.assert_not_called();net.assert_not_called()
        self.assertEqual(d['workspace']['state'],'NOT_REQUESTED');self.assertFalse(d['sent'])
        self.assertTrue(d['review_before_sharing']);self.assertFalse(d['provider_fault_established'])

    def test_demo_counts_are_not_a_live_host_or_health_verdict(self):
        setup(self.root);d=ops.support_report(self.root)
        self.assertEqual(d['workspace']['mode'],'demo')
        self.assertEqual(d['workspace']['expected_subjects'],3)
        self.assertEqual(d['workspace']['retained_points'],2288)
        self.assertEqual(d['workspace']['capture_batches'],1)
        self.assertEqual(d['state'],'SUMMARY_AVAILABLE');self.assertFalse(d['real_host_qualification'])

    def test_private_paths_aliases_environment_and_raw_errors_never_enter_summary(self):
        setup(self.root,'local');cfg=core.read_json(self.root/'workspace.json');cfg['assets'][0]['plan']='secret purchased plan';cfg['token_env']='SECRET_VARIABLE_NAME'
        ws.atomic(self.root/'workspace.json',core.canonical(cfg))
        with ws.database(self.root) as db,db:
            db.execute('INSERT INTO attempts VALUES (?,?,?,?)',('private-id',123.,'ERROR','token-value hostname@example.invalid /private/path'))
        with mock.patch.dict(os.environ,{'SECRET_VARIABLE_NAME':'do-not-leak-token-value'}):d=ops.support_report(self.root)
        text=json.dumps(d)
        for forbidden in ('private-node-name','secret purchased plan','SECRET_VARIABLE_NAME','do-not-leak-token-value',str(self.root),'hostname@example.invalid','/private/path','private-id'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(d['workspace']['attempt_states'],{'ERROR':1})

    def test_summary_does_not_change_workspace_or_trigger_collection(self):
        setup(self.root);before=files(self.root)
        with mock.patch.object(ws,'collect') as collect,mock.patch.object(core,'get_json') as network:
            ops.support_report(self.root)
        collect.assert_not_called();network.assert_not_called();self.assertEqual(files(self.root),before)

    def test_missing_workspace_is_explicit_without_creating_files(self):
        d=ops.support_report(self.root)
        self.assertEqual(d['workspace']['state'],'UNAVAILABLE');self.assertFalse(self.root.exists())
        self.assertNotIn(str(self.root),json.dumps(d))

    def test_malformed_configuration_returns_category_not_contents(self):
        setup(self.root);(self.root/'workspace.json').write_text('private-api-secret malformed')
        d=ops.support_report(self.root)
        self.assertEqual(d['workspace']['state'],'UNAVAILABLE');self.assertNotIn('private-api-secret',json.dumps(d))

    def test_missing_database_does_not_create_one_or_claim_empty_healthy_history(self):
        setup(self.root);(self.root/'history.sqlite3').unlink();d=ops.support_report(self.root)
        self.assertEqual(d['workspace']['database'],'UNAVAILABLE');self.assertIsNone(d['workspace']['retained_points'])
        self.assertFalse((self.root/'history.sqlite3').exists())

    def test_unknown_attempt_outcomes_are_counted_not_echoed(self):
        setup(self.root)
        with ws.database(self.root) as db,db:db.execute('INSERT INTO attempts VALUES (?,?,?,?)',('id',100.,'private-new-outcome','secret'))
        d=ops.support_report(self.root)
        self.assertEqual(d['workspace']['attempt_states'].get('OTHER'),1);self.assertNotIn('private-new-outcome',json.dumps(d))

    def test_runtime_corruption_does_not_leak_raw_exception(self):
        setup(self.root);folder=self.root/'.agent';folder.mkdir(mode=0o700);ws.atomic(folder/'status.json',b'{private bearer token')
        d=ops.support_report(self.root)
        self.assertEqual(d['workspace']['runtime'],'UNAVAILABLE');self.assertNotIn('bearer',json.dumps(d))

    def test_fixed_schema_cannot_include_additional_fields_from_future_status(self):
        setup(self.root)
        import vps_agent as agent
        with mock.patch.object(agent,'runtime_status',return_value={'state':'RUNNING','process_verified':False,'private_extra':'do-not-include','run_id':'private-id'}):
            d=ops.support_report(self.root)
        self.assertNotIn('private_extra',json.dumps(d));self.assertNotIn('private-id',json.dumps(d));self.assertFalse(d['workspace']['process_verified'])

    def test_changing_only_private_identity_does_not_change_exported_summary(self):
        setup(self.root,'local');a=ops.support_report(self.root)
        cfg=core.read_json(self.root/'workspace.json');cfg['assets'][0]['id']='other-private-name';cfg['assets'][0]['plan']='different private purchase'
        ws.atomic(self.root/'workspace.json',core.canonical(cfg));b=ops.support_report(self.root)
        self.assertEqual(a,b)

    def test_cli_returns_summary_not_an_exception_with_a_private_path(self):
        r=subprocess.run([sys.executable,str(Path(core.__file__)),'support-report','--workspace',str(self.root)],capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['workspace']['state'],'UNAVAILABLE')
        self.assertNotIn(str(self.root),r.stdout+r.stderr)

    def test_private_output_never_overwrites_an_existing_file(self):
        p=self.base/'support.json'
        command=[sys.executable,str(Path(core.__file__)),'support-report','--out',str(p)]
        first=subprocess.run(command,capture_output=True,text=True,timeout=15);self.assertEqual(first.returncode,0)
        before=p.read_bytes();second=subprocess.run(command,capture_output=True,text=True,timeout=15)
        self.assertNotEqual(second.returncode,0);self.assertEqual(p.read_bytes(),before)
        self.assertEqual(p.stat().st_mode&0o777,0o600)

    def test_restoring_changed_private_config_does_not_expose_endpoint_values_or_hashes(self):
        setup(self.root,'local')
        cfg=core.read_json(self.root/'workspace.json')
        cfg.update(mode='prometheus',prometheus_url='https://private-metrics.example.invalid',token_env='PRIVATE_METRICS_TOKEN')
        cfg['assets'][0]['instance']='private-instance.example.invalid:9100'
        ws.atomic(self.root/'workspace.json',core.canonical(cfg))
        output=json.dumps(ops.support_report(self.root))
        for value in ('https://private-metrics.example.invalid','private-instance.example.invalid:9100','PRIVATE_METRICS_TOKEN'):
            self.assertNotIn(value,output);self.assertNotIn(hashlib.sha256(value.encode()).hexdigest(),output)

    def test_read_only_database_integrity_error_is_a_missing_evidence_state(self):
        setup(self.root);ws.atomic(self.root/'history.sqlite3',b'not a database with private-token')
        d=ops.support_report(self.root);self.assertEqual(d['workspace']['database'],'UNAVAILABLE')
        self.assertIsNone(d['workspace']['capture_batches']);self.assertNotIn('private-token',json.dumps(d))

class SupportHTTPTest(unittest.TestCase):
    def test_real_support_route_is_readonly_and_preserves_host_origin_guards(self):
        import threading,urllib.request,urllib.error
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';setup(root);before=files(root)
            server=ws.make_server(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/api/support'
                with urllib.request.urlopen(url,timeout=3) as response:
                    d=json.load(response);self.assertEqual(response.headers['Cache-Control'],'no-store')
                self.assertEqual(d['workspace']['retained_points'],2288)
                self.assertEqual(before,files(root))
                for extra in ({'Origin':'https://example.invalid'},{'Host':'example.invalid'}):
                    with self.subTest(headers=extra),self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(urllib.request.Request(url,headers=extra),timeout=3)
                    self.assertEqual(error.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url+'?include=raw',timeout=3)
            finally:server.shutdown();server.server_close();thread.join(3)

    def test_support_output_cannot_modify_the_observation_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';setup(root);before=files(root)
            r=subprocess.run([sys.executable,str(Path(core.__file__)),'support-report','--workspace',str(root),'--out',str(root/'new.json')],capture_output=True,text=True,timeout=15)
            self.assertNotEqual(r.returncode,0);self.assertEqual(before,files(root))

if __name__=='__main__':unittest.main()
