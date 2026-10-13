#!/usr/bin/env python3
"""Synthetic and loopback contracts for workspace bootstrap, history and safety."""
import argparse
import copy
import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_workspace as w
import vps_health as c

NOW=1800000000.


def args(path,mode='demo',**changes):
    d=dict(workspace=Path(path),mode=mode,node='example-node',interval=300,profile=None,url=None,loki_url=None,
           token_env=None,loki_token_env=None,allow_http=False,acceptable=.9,investigate_below=.8)
    return argparse.Namespace(**{**d,**changes})


def capture(start=NOW-86400,end=NOW,ratio=.78,kind='prometheus',node='example-node'):
    cap=c.new_capture(node,kind,start,end,300)
    cap['samples']=[{'timestamp':i,'duration_seconds':300,'quality':[],'cpu_accounted_ratio':ratio,
                     'cpu_pressure_ratio':.01,'cfs_throttled_periods_ratio':0.} for i in range(int(start)+300,int(end)+1,300)]
    return cap


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'workspace'

    def setup_real(self,mode='local'):
        w.bootstrap(args(self.root,mode))
        return w.config_load(self.root)[1]

    def test_bootstrap_defaults_to_demo_without_network(self):
        with mock.patch.object(c,'get_json') as net,mock.patch.object(c,'cpu_snapshot') as cpu:
            w.bootstrap(args(self.root))
        net.assert_not_called();cpu.assert_not_called()
        self.assertTrue(w.status(self.root)['synthetic'])
        self.assertEqual(w.status(self.root)['expected_assets'],3)
        self.assertTrue((self.root/'dashboard.html').is_file())

    def test_existing_workspace_never_overwritten(self):
        w.bootstrap(args(self.root));old=(self.root/'workspace.json').read_bytes()
        with self.assertRaises(c.InvalidEvidence):w.bootstrap(args(self.root))
        self.assertEqual(old,(self.root/'workspace.json').read_bytes())

    def test_bootstrap_rejects_bad_policy_before_writes(self):
        with self.assertRaises(c.InvalidEvidence):w.bootstrap(args(self.root,acceptable=.75,investigate_below=.8))
        self.assertFalse(self.root.exists())

    def test_local_bootstrap_does_not_collect(self):
        with mock.patch.object(c,'cpu_snapshot') as snapshot:w.bootstrap(args(self.root,'local'))
        snapshot.assert_not_called();self.assertEqual(w.status(self.root)['assets'][0]['decision'],'HOLD')

    def test_overlap_and_duplicate_capture_add_no_time(self):
        cfg=self.setup_real();cap=capture()
        w.ingest(self.root,cfg,[cap],NOW);one=w.status(self.root,NOW)
        result=w.ingest(self.root,cfg,[cap],NOW+1);two=w.status(self.root,NOW)
        self.assertFalse(result['imported']);self.assertEqual(one,two)
        cap2=capture(start=NOW-3600,end=NOW)
        w.ingest(self.root,cfg,[cap2],NOW)
        three=w.status(self.root,NOW)['assets'][0]
        self.assertEqual(three['points'],288);self.assertEqual(three['observed_hours'],24)

    def test_conflicting_point_is_not_last_writer_wins(self):
        cfg=self.setup_real();w.ingest(self.root,cfg,[capture()],NOW)
        cap=capture();cap['samples'][0]['cpu_accounted_ratio']=.99
        w.ingest(self.root,cfg,[cap],NOW)
        row=w.status(self.root,NOW)['assets'][0]
        self.assertIn('conflicting_sample_values',row['holds']);self.assertEqual(row['decision'],'HOLD')
        self.assertLess(row['coverage'],1)

    def test_stale_is_not_last_good_value_forever(self):
        cfg=self.setup_real();w.ingest(self.root,cfg,[capture(ratio=.99)],NOW)
        row=w.status(self.root,NOW+3600)['assets'][0]
        self.assertEqual(row['observed'],'WITHIN_TOLERANCE');self.assertTrue(row['stale']);self.assertEqual(row['decision'],'HOLD')

    def test_sparse_snapshots_are_not_a_full_day(self):
        cfg=self.setup_real();cap=capture()
        for p in cap['samples']:p['duration_seconds']=10
        w.ingest(self.root,cfg,[cap],NOW);row=w.status(self.root,NOW)['assets'][0]
        self.assertLess(row['coverage'],.04);self.assertEqual(row['decision'],'HOLD')

    def test_85_percent_is_watch_not_provider_contact(self):
        cfg=self.setup_real();w.ingest(self.root,cfg,[capture(ratio=.85)],NOW)
        row=w.status(self.root,NOW)['assets'][0]
        self.assertEqual(row['decision'],'WATCH');self.assertFalse(row['send_authorized'])
        self.assertIn('not a support escalation',row['recommendation'])

    def test_78_percent_is_investigation_not_proven_provider(self):
        cfg=self.setup_real();w.ingest(self.root,cfg,[capture(ratio=.78)],NOW)
        row=w.status(self.root,NOW)['assets'][0]
        self.assertEqual(row['decision'],'INVESTIGATE');self.assertFalse(row['provider_cause_proven'])

    def test_new_method_epoch_is_not_pooled(self):
        cfg=self.setup_real();w.ingest(self.root,cfg,[capture()],NOW)
        cap=capture(start=NOW-3600,end=NOW,ratio=.99);cap['source']['tool_sha256']='new-method'
        w.ingest(self.root,cfg,[cap],NOW)
        row=w.status(self.root,NOW)['assets'][0]
        self.assertEqual(row['observed_hours'],1);self.assertEqual(row['decision'],'HOLD')

    def test_missing_asset_stays_visible(self):
        cfg=self.setup_real();cfg['mode']='prometheus';cfg['prometheus_url']='https://metrics.example.invalid'
        cfg['assets']=[{'id':'example-node','instance':'first'},{'id':'missing-node','instance':'second'}]
        w.atomic(self.root/'workspace.json',c.canonical(cfg))
        w.ingest(self.root,cfg,[capture()],NOW)
        rows=w.status(self.root,NOW)['assets'];self.assertEqual(len(rows),2)
        self.assertEqual(rows[1]['observed'],'NOT_MEASURED')

    def test_ingestion_is_atomic_on_bad_second_subject(self):
        cfg=self.setup_real()
        with self.assertRaises(c.InvalidEvidence):w.ingest(self.root,cfg,[capture(),capture(node='wrong-node')],NOW)
        self.assertEqual(w.status(self.root,NOW)['stored_captures'],0)

    def test_demo_cannot_mix_with_real_capture(self):
        w.bootstrap(args(self.root));cfg=w.config_load(self.root)[1]
        with self.assertRaises(c.InvalidEvidence):w.ingest(self.root,cfg,[capture(node='example-stable')],NOW)

    def test_future_capture_rejected(self):
        cfg=self.setup_real()
        with self.assertRaises(c.InvalidEvidence):w.ingest(self.root,cfg,[capture(end=NOW+3600)],NOW)

    def test_failed_latest_collection_is_not_clean(self):
        cfg=self.setup_real();cap=capture();cap['errors']=['api-error']
        w.ingest(self.root,cfg,[cap],NOW)
        self.assertIn('latest_collection_errors',w.status(self.root,NOW)['assets'][0]['holds'])

    def test_no_state_read_executes_log_or_config_commands(self):
        cfg=self.setup_real();cfg['assets'][0]['plan']='$(touch /tmp/not-executed)'
        w.atomic(self.root/'workspace.json',c.canonical(cfg))
        self.assertEqual(w.status(self.root)['expected_assets'],1)

    def test_history_deterministic_for_explicit_asof(self):
        cfg=self.setup_real();w.ingest(self.root,cfg,[capture()],NOW)
        self.assertEqual(c.canonical(w.status(self.root,NOW)),c.canonical(w.status(self.root,NOW)))

    def test_token_values_not_accepted_as_env_names(self):
        with self.assertRaises(c.InvalidEvidence):w.bootstrap(args(self.root,'local',token_env='secret string with spaces'))

    def test_store_budget_stops_without_deleting_history(self):
        cfg=self.setup_real()
        with mock.patch.object(w,'MAX_STORE_BYTES',1),self.assertRaises(c.InvalidEvidence):w.ingest(self.root,cfg,[capture()],NOW)
        self.assertEqual(w.status(self.root,NOW)['stored_captures'],0)

    def test_symbolic_history_refused(self):
        self.setup_real();db=self.root/'history.sqlite3';old=self.root/'saved.sqlite';db.rename(old);db.symlink_to(old)
        with self.assertRaises(c.InvalidEvidence):w.status(self.root)

    def test_write_lease_prevents_concurrent_collection(self):
        self.setup_real()
        with w.database(self.root) as db,db:w.set_state(db,'collector_lease',{'until':time.time()+300,'id':'other'})
        with mock.patch.object(c,'cpu_snapshot') as snapshot,self.assertRaises(c.InvalidEvidence):w.collect(self.root)
        snapshot.assert_not_called()

    def test_passive_ticks_cover_intervening_time_without_stress(self):
        self.setup_real()
        def snap(t,ticks):
            n=int(t*1e9);return {'start_ns':n,'end_ns':n,'wall_start_ns':n,'wall_end_ns':n,'boot_fingerprint':'same',
                'cpus':{'cpu0':[ticks,0,0,0,0,0,0,0]},'pressure':{'cpu':0,'io':0,'memory':0}}
        with mock.patch.object(c,'cpu_snapshot',return_value=snap(NOW-300,0)),mock.patch.object(w.time,'time',return_value=NOW-300):w.collect(self.root)
        self.assertEqual(w.status(self.root,NOW-300)['assets'][0]['points'],0)
        with mock.patch.object(c,'cpu_snapshot',return_value=snap(NOW,30000)),mock.patch.object(w.time,'time',return_value=NOW),mock.patch.object(w.os,'sysconf',return_value=100):w.collect(self.root)
        row=w.status(self.root,NOW)['assets'][0];self.assertEqual(row['observed_hours'],300/3600);self.assertEqual(row['mean'],1)

    def test_watch_requires_explicit_optin(self):
        self.setup_real()
        with self.assertRaises(c.InvalidEvidence):w.watch(argparse.Namespace(workspace=self.root,approve_collection=False))

    def test_generated_scheduler_is_not_installed(self):
        self.setup_real();out=Path(self.tmp.name)/'units';value=w.schedule(self.root,out)
        self.assertFalse(value['installed']);self.assertEqual(len(list(out.iterdir())),2)
        content='\n'.join(p.read_text() for p in out.iterdir());self.assertIn('collect --workspace',content)
        self.assertNotIn('curl',content);self.assertNotIn('sudo',content)

    def test_local_draft_needs_explicit_permission(self):
        w.bootstrap(args(self.root))
        with self.assertRaises(c.InvalidEvidence):w.draft_email(argparse.Namespace(approve_draft=False))

    def test_demo_draft_is_always_labelled_example(self):
        w.bootstrap(args(self.root));out=Path(self.tmp.name)/'example.txt'
        a=argparse.Namespace(workspace=self.root,approve_draft=True,example=False,node='example-contended',impact='slow example builds',out=out)
        with self.assertRaises(c.InvalidEvidence):w.draft_email(a)
        a.example=True;value=w.draft_email(a)
        self.assertFalse(value['sent']);self.assertTrue(out.read_text().startswith('EXAMPLE ONLY'))
        self.assertLess(value['words'],180)

    def test_85_percent_draft_is_refused_even_after_two_days(self):
        cfg=self.setup_real();cap=capture(start=NOW-3*86400,end=NOW,ratio=.85);w.ingest(self.root,cfg,[cap],NOW)
        a=argparse.Namespace(workspace=self.root,approve_draft=True,example=False,node='example-node',impact='example issue',out=Path(self.tmp.name)/'draft')
        with mock.patch.object(w.time,'time',return_value=NOW),self.assertRaises(c.InvalidEvidence):w.draft_email(a)

    def test_export_new_directory_and_hashes(self):
        w.bootstrap(args(self.root));out=Path(self.tmp.name)/'export';w.export(self.root,out)
        m=c.read_json(out/'manifest.json')
        for name,digest in m['files'].items():self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)
        with self.assertRaises(c.InvalidEvidence):w.export(self.root,out)

    def test_html_escapes_payload_end_script(self):
        page=w.page({'arbitrary':'</script><script>alert(1)</script>'}).decode()
        self.assertNotIn('"</script>',page);self.assertIn('\\u003c/script',page)

    def test_http_only_fixed_read_routes_loopback_and_no_foreign_origins(self):
        w.bootstrap(args(self.root));server=w.make_server(self.root,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            host='127.0.0.1:'+str(server.server_port)
            def get(path,headers=None):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                conn.request('GET',path,headers=headers or {});r=conn.getresponse();body=r.read();result=(r.status,dict(r.getheaders()),body);conn.close();return result
            self.assertEqual(server.server_address[0],'127.0.0.1')
            code,headers,body=get('/api/status');self.assertEqual(code,200);self.assertNotIn(b'prometheus_url',body)
            self.assertEqual(headers['Cache-Control'],'no-store');self.assertNotIn('Access-Control-Allow-Origin',headers)
            for path in ('/workspace.json','/history.sqlite3','/../workspace.json','/api/status?raw=true'):
                self.assertEqual(get(path)[0],404)
            self.assertEqual(get('/',{'Host':'attacker.example'})[0],403)
            self.assertEqual(get('/',{'Origin':'https://attacker.example'})[0],403)
            self.assertEqual(get('/',{'Origin':'http://'+host})[0],200)
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);conn.request('POST','/api/status');r=conn.getresponse();self.assertEqual(r.status,501);r.read();conn.close()
        finally:server.shutdown();server.server_close();thread.join(5)

    def test_daily_report_outputs_are_derived_not_raw_log_exports(self):
        w.bootstrap(args(self.root));files=list((self.root/'daily').glob('*.json'));self.assertGreaterEqual(len(files),3)
        for p in files:
            d=c.read_json(p);self.assertTrue(d['synthetic']);self.assertNotIn('raw',d)


if __name__=='__main__':unittest.main()
