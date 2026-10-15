#!/usr/bin/env python3
"""Portable attachment checks plus a real byte-preserving loopback port forward.

TCP fixtures prove the HTTP origin boundary, not an SSH authentication handshake.
Actual native SSH between authorized devices is qualified separately.
"""
from pathlib import Path
import contextlib
import copy
import http.client
import json
import os
import select
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_agent as agent
import vps_health as core
import vps_workspace as ws


def args(root,**changes):
    options=dict(workspace=root,mode='demo',node='example',profile=None,url=None,loki_url=None,
        token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,
        investigate_below=.8,provider='unknown',plan=None,duration_seconds=30,port=0,
        viewer_port=None,client='generic',approve_plan=None)
    return SimpleNamespace(**{**options,**changes})


class Forward(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=False
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            with socket.create_connection(('127.0.0.1',self.server.target),timeout=2) as remote:
                self.request.settimeout(3);remote.settimeout(3)
                until=time.monotonic()+5
                while time.monotonic()<until:
                    ready,_,_=select.select([self.request,remote],[],[],.2)
                    for source in ready:
                        data=source.recv(32768)
                        if not data:return
                        (remote if source is self.request else self.request).sendall(data)
    def __init__(self):
        self.target=0
        super().__init__(('127.0.0.1',0),self.Handler)


def response(port,path='/api/status',headers=None):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    try:
        conn.request('GET',path,headers=headers or {});res=conn.getresponse()
        return res.status,dict(res.getheaders()),res.read()
    finally:conn.close()


class OriginTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'demo';ws.bootstrap(args(self.root))

    def test_no_viewer_port_keeps_exact_original_origin(self):
        server=ws.make_server(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            port=server.server_port;other=port-1
            self.assertEqual(response(port)[0],200)
            self.assertEqual(response(port,headers={'Host':f'127.0.0.1:{other}'})[0],403)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_explicit_different_local_port_works_through_byte_preserving_forward(self):
        forward=Forward();server=ws.make_server(self.root,0,viewer_port=forward.server_address[1]);forward.target=server.server_port
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (server,forward)]
        for thread in threads:thread.start()
        try:
            code,headers,body=response(forward.server_address[1])
            self.assertEqual(code,200);self.assertTrue(json.loads(body)['synthetic'])
            self.assertNotIn('Access-Control-Allow-Origin',headers)
            self.assertEqual(headers['Cross-Origin-Resource-Policy'],'same-origin')
            self.assertEqual(server.server_address[0],'127.0.0.1')
            self.assertEqual(response(forward.server_address[1],'/')[0],200)
            self.assertEqual(response(forward.server_address[1],'/api/support')[0],200)
        finally:
            for s in (server,forward):s.shutdown();s.server_close()
            for thread in threads:thread.join(2)

    def test_foreign_origin_other_port_and_authority_headers_remain_refused(self):
        server=ws.make_server(self.root,0,viewer_port=19843);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            accepted='127.0.0.1:19843'
            for headers in ({'Host':accepted,'Origin':'http://'+accepted}, {'Host':accepted}):
                self.assertEqual(response(server.server_port,headers=headers)[0],200)
            for headers in ({'Host':'attacker.invalid'},{'Host':'127.0.0.1:19844'},
                            {'Host':accepted,'Origin':'https://attacker.invalid'},
                            {'Host':accepted,'Origin':f'http://127.0.0.1:{server.server_port}'},
                            {'Host':accepted,'Origin':'null'},
                            {'Host':'attacker.invalid','X-Forwarded-Host':accepted}):
                with self.subTest(headers=headers):self.assertEqual(response(server.server_port,headers=headers)[0],403)
            self.assertEqual(response(server.server_port,'/api/status?private=true',{'Host':accepted})[0],404)
            self.assertEqual(response(server.server_port,'/workspace.json',{'Host':accepted})[0],404)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_duplicate_host_origin_and_cross_site_reads_are_refused(self):
        server=ws.make_server(self.root,0,viewer_port=19843);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            for extra in ('Host: 127.0.0.1:19843','Origin: http://127.0.0.1:19843\r\nOrigin: http://127.0.0.1:19843','Sec-Fetch-Site: cross-site','Sec-Fetch-Site: same-site'):
                with self.subTest(extra=extra),socket.create_connection(('127.0.0.1',server.server_port),timeout=3) as sock:
                    request='GET /api/status HTTP/1.1\r\nHost: 127.0.0.1:19843\r\n'+extra+'\r\nConnection: close\r\n\r\n'
                    sock.sendall(request.encode());self.assertIn(b'403',sock.recv(1024).split(b'\r\n')[0])
        finally:server.shutdown();server.server_close();t.join(2)

    def test_invalid_viewer_port_does_not_bind_any_socket(self):
        for value in (0,-1,65536,True,'19843'):
            with self.subTest(value=value),mock.patch.object(ws.http.server,'ThreadingHTTPServer') as listener:
                with self.assertRaises(core.InvalidEvidence):ws.make_server(self.root,0,viewer_port=value)
                listener.assert_not_called()

    def test_viewer_port_changes_the_approved_plan_but_not_workspace_config(self):
        before=(self.root/'workspace.json').read_bytes()
        a=agent.plan(args(self.root,mode='auto'));b=agent.plan(args(self.root,mode='auto',viewer_port=19843))
        self.assertNotEqual(a['plan_sha256'],b['plan_sha256'])
        self.assertEqual(b['intent']['viewer_port'],19843)
        self.assertEqual(before,(self.root/'workspace.json').read_bytes())


def example_handoff():
    now=time.time()
    return {'schema':'g-skills.viewer-handoff.v1','issued_at':now,'expires_at':now+300,
        'run_id':'1'*32,'plan_sha256':'2'*64,'configuration_sha256':'3'*64,
        'subjects_sha256':core.digest(['example-node']),'expected_subjects':1,'mode':'demo',
        'server_port':18763,'viewer_port':19843,'source_version':'0.9.1'}


class PortableContractTest(unittest.TestCase):
    def setUp(self):
        import vps_viewer
        self.viewer=vps_viewer
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'handoff.json'
        core.save_json(self.path,example_handoff())

    def test_plan_uses_existing_ssh_without_network_or_process_actions(self):
        with mock.patch.object(socket,'create_connection') as connect,mock.patch.object(subprocess,'Popen') as start:
            result=self.viewer.plan(self.path,'known-host')
        self.assertEqual(result['state'],'PLAN_ONLY');self.assertFalse(result['ssh_connection_verified'])
        self.assertFalse(result['external_actions_authorized']);self.assertTrue(result['existing_ssh_configuration_applies'])
        self.assertIn('127.0.0.1:19843:127.0.0.1:18763',result['ssh_argv'])
        self.assertEqual(result['ssh_argv'][-1],'known-host');self.assertIn('StrictHostKeyChecking=yes',result['ssh_argv'])
        self.assertIn('ForwardAgent=no',result['ssh_argv']);self.assertNotIn('-f',result['ssh_argv'])
        self.assertNotIn('ClearAllForwardings=yes',result['ssh_argv'])
        connect.assert_not_called();start.assert_not_called()

    def test_target_must_be_explicit_not_taken_from_untrusted_handoff(self):
        for target in ('','-oProxyCommand=bad','user@host;whoami','$(whoami)','*','host\nother','ssh://host/path'):
            with self.subTest(target=target),self.assertRaises(core.InvalidEvidence):self.viewer.plan(self.path,target)

    def test_stale_future_or_malformed_handoff_refuses_before_http(self):
        original=example_handoff()
        changes=({'expires_at':time.time()-1},{'issued_at':time.time()+100},
                 {'viewer_port':True},{'run_id':'unknown'},{'expected_subjects':0},
                 {'expires_at':time.time()+8000},{'configuration_sha256':'not-hash'})
        for change in changes:
            ws.atomic(self.path,core.canonical({**original,**change}))
            with self.subTest(change=change),mock.patch.object(agent,'read_viewer') as read:
                with self.assertRaises(core.InvalidEvidence):self.viewer.verify(self.path)
                read.assert_not_called()

    def test_unexpected_fields_cannot_smuggle_a_command_or_endpoint(self):
        ws.atomic(self.path,core.canonical({**example_handoff(),'remote_command':'whoami'}))
        with self.assertRaises(core.InvalidEvidence):self.viewer.plan(self.path,'known-host')

    def test_read_only_preflight_preserves_receipt_and_private_config(self):
        before=self.path.read_bytes();a=self.viewer.plan(self.path,'known-host');b=self.viewer.plan(self.path,'known-host')
        self.assertEqual(a,b);self.assertEqual(before,self.path.read_bytes())

    def test_mismatched_run_config_inventory_or_mode_is_never_verified(self):
        h=core.read_json(self.path)
        base={'schema':'g-skills.workspace-status.v1','as_of':time.time(),'configuration_sha256':h['configuration_sha256'],
              'mode':'demo','synthetic':True,'version':h['source_version'],'expected_assets':1,'assets':[{'id':'example-node'}],
              'agent_runtime':{'run_id':h['run_id'],'plan_sha256':h['plan_sha256'],'state':'RUNNING','process_verified':True}}
        variants=[{**base,'configuration_sha256':'a'*64},{**base,'assets':[{'id':'other'}]},
                  {**base,'mode':'local','synthetic':False},{**base,'as_of':time.time()-600},
                  {**base,'agent_runtime':{**base['agent_runtime'],'run_id':'a'*32}},
                  {**base,'agent_runtime':{**base['agent_runtime'],'process_verified':False}},
                  {**base,'agent_runtime':{**base['agent_runtime'],'state':'STOPPED'}}]
        for value in variants:
            with self.subTest(value=value),mock.patch.object(agent,'read_viewer',return_value=value):
                result=self.viewer.verify(self.path)
                self.assertEqual(result['state'],'NOT_VERIFIED');self.assertFalse(result['http_identity_matched'])

    def test_success_matches_identity_but_is_not_remote_kernel_or_ssh_attestation(self):
        h=core.read_json(self.path);payload={'schema':'g-skills.workspace-status.v1','as_of':time.time(),
           'configuration_sha256':h['configuration_sha256'],'mode':'demo','synthetic':True,'version':h['source_version'],'expected_assets':1,
           'assets':[{'id':'example-node'}],'agent_runtime':{'run_id':h['run_id'],'plan_sha256':h['plan_sha256'],
             'state':'RUNNING','process_verified':True}}
        with mock.patch.object(agent,'read_viewer',return_value=payload):result=self.viewer.verify(self.path)
        self.assertEqual(result['state'],'VIEWER_MATCHED');self.assertTrue(result['http_identity_matched'])
        self.assertFalse(result['ssh_connection_verified']);self.assertFalse(result['remote_kernel_independently_verified'])
        self.assertFalse(result['service_health_verified']);self.assertFalse(result['provider_cause_proven'])

    def test_handoff_expiring_during_response_never_passes(self):
        h=core.read_json(self.path);now=time.time();h['issued_at']=now-10;h['expires_at']=now+2
        ws.atomic(self.path,core.canonical(h))
        payload={'schema':'g-skills.workspace-status.v1','as_of':now,'version':h['source_version'],
            'configuration_sha256':h['configuration_sha256'],'mode':'demo','synthetic':True,'expected_assets':1,
            'assets':[{'id':'example-node'}],'agent_runtime':{'run_id':h['run_id'],'plan_sha256':h['plan_sha256'],'state':'RUNNING','process_verified':True}}
        with mock.patch.object(agent,'read_viewer',return_value=payload),mock.patch.object(self.viewer.time,'time',side_effect=[now,now+3]):
            result=self.viewer.verify(self.path)
        self.assertEqual(result['state'],'NOT_VERIFIED');self.assertEqual(result['reason'],'handoff_expired_during_readback')

    def test_handoff_is_not_a_script_and_code_version_drift_is_refused(self):
        with mock.patch.object(agent,'read_viewer',return_value={'schema':'g-skills.workspace-status.v1','version':'different'}):
            self.assertEqual(self.viewer.verify(self.path)['state'],'NOT_VERIFIED')
        self.assertFalse(self.viewer.plan(self.path,'person@known-host')['external_actions_authorized'])

    def test_linux_kernel_checks_are_not_required_on_the_viewing_machine(self):
        with mock.patch.object(sys,'platform','darwin'),mock.patch.object(agent,'runtime_status') as status:
            self.assertEqual(self.viewer.plan(self.path,'known-host')['state'],'PLAN_ONLY')
        status.assert_not_called()


class OwnedHandoffTest(unittest.TestCase):
    def setUp(self):
        if sys.platform!='linux':self.skipTest('managed worker is Linux-qualified')
        import vps_viewer
        self.viewer=vps_viewer;self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'demo'
        self.runs=[];self.addCleanup(self.cleanup)
    def cleanup(self):
        for run in self.runs:
            try:agent.stop(self.root,run,wait=8)
            except (OSError,ValueError):pass
        self.temp.cleanup()
    def start(self,**changes):
        a=args(self.root,**changes);a.approve_plan=agent.plan(a)['plan_sha256'];r=agent.start(a);self.runs.append(r['run_id']);return r
    def test_handoff_requires_actual_owned_worker_and_omits_raw_identity(self):
        self.start();out=Path(self.temp.name)/'handoff.json';result=self.viewer.handoff(self.root,out)
        raw=out.read_text();h=json.loads(raw)
        self.assertEqual(h['expected_subjects'],3)
        self.assertNotIn(str(self.root),raw);self.assertNotIn('example-',raw);self.assertNotIn('process_identity',raw)
        self.assertFalse(result['connection_opened']);self.assertEqual(out.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):self.viewer.handoff(self.root,out)
    def test_stopped_worker_does_not_export_a_fresh_connection_handoff(self):
        r=self.start();agent.stop(self.root,r['run_id'],wait=8);out=Path(self.temp.name)/'bad.json'
        with self.assertRaises(core.InvalidEvidence):self.viewer.handoff(self.root,out)
        self.assertFalse(out.exists())
    def test_auto_resume_preserves_the_explicit_viewer_port(self):
        first=self.start(viewer_port=19843)
        a=args(self.root,mode='auto');plan=agent.plan(a);self.assertEqual(plan['intent']['viewer_port'],19843)
        a.approve_plan=plan['plan_sha256'];second=agent.start(a)
        self.assertEqual(first['run_id'],second['run_id']);self.assertEqual(first['deadline_utc'],second['deadline_utc'])

    def test_changed_viewer_port_cannot_replace_an_active_run(self):
        first=self.start(viewer_port=19843);a=args(self.root,viewer_port=19844)
        a.approve_plan=agent.plan(a)['plan_sha256']
        with self.assertRaises(core.InvalidEvidence):agent.start(a)
        self.assertEqual(agent.runtime_status(self.root)['run_id'],first['run_id'])

    def test_original_same_port_route_still_verifies(self):
        self.start();out=Path(self.temp.name)/'handoff.json';self.viewer.handoff(self.root,out)
        h=core.read_json(out);self.assertEqual(h['server_port'],h['viewer_port'])
        self.assertEqual(self.viewer.verify(out)['state'],'VIEWER_MATCHED')
    def test_forwarded_route_verifies_then_closure_or_wrong_service_cannot_pass(self):
        forward=Forward();r=self.start(viewer_port=forward.server_address[1]);forward.target=int(r['dashboard_url'].split(':')[-1].rstrip('/'))
        thread=threading.Thread(target=forward.serve_forever,daemon=True);thread.start()
        out=Path(self.temp.name)/'handoff.json';self.viewer.handoff(self.root,out)
        before=ws.status(self.root)['stored_captures']
        try:self.assertEqual(self.viewer.verify(out)['state'],'VIEWER_MATCHED')
        finally:forward.shutdown();forward.server_close();thread.join(2)
        self.assertEqual(self.viewer.verify(out)['state'],'NOT_VERIFIED')
        self.assertEqual(ws.status(self.root)['stored_captures'],before)
        self.assertTrue(agent.runtime_status(self.root)['process_verified'])

if __name__=='__main__':unittest.main()
