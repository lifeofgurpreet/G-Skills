"""Real browser path through an approved-port TCP relay, using synthetic data.

Native cross-device SSH authentication is a separate proof. This fixture does not
rewrite headers, disable browser security or start measurement on a real host.
"""
from pathlib import Path
import http.server
import json
import socketserver
import sys
import tempfile
import threading
from types import SimpleNamespace
from playwright.sync_api import expect
import vps_agent as agent
import vps_workspace as workspace
import vps_viewer as viewer


def run(context,out,passed):
    tests=Path(workspace.core.ROOT)/'tests';sys.path.insert(0,str(tests))
    from test_viewer_access import Forward
    class Relay(Forward):
        allow_reuse_address=True
        def __init__(self,port=0):
            self.target=0
            socketserver.ThreadingTCPServer.__init__(self,('127.0.0.1',port),self.Handler)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'observations';handoff=Path(temp)/'handoff.json'
        relay=Relay();relay_port=relay.server_address[1];run_id=None;thread=None;page=None;entry=None;entry_thread=None
        def start_relay(target):
            nonlocal relay,thread
            relay.target=target;thread=threading.Thread(target=relay.serve_forever,daemon=True);thread.start()
        def close_relay():
            nonlocal relay,thread
            if relay is not None:
                if thread:relay.shutdown()
                relay.server_close();relay=None
            if thread:thread.join(3);thread=None
        try:
            args=SimpleNamespace(workspace=root,mode='demo',node='example',profile=None,url=None,loki_url=None,
                token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,investigate_below=.8,
                provider='unknown',plan=None,duration_seconds=120,port=0,viewer_port=relay_port,client='generic',approve_plan=None)
            args.approve_plan=agent.plan(args)['plan_sha256'];state=agent.start(args);run_id=state['run_id']
            target=int(state['dashboard_url'].split(':')[-1].rstrip('/'));assert target!=relay_port
            viewer.handoff(root,handoff,valid_seconds=120);before=(root/'history.sqlite3').read_bytes()
            url=f'http://127.0.0.1:{relay_port}/';start_relay(target)
            assert viewer.verify(handoff)['state']=='VIEWER_MATCHED'
            class Entry(http.server.BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    body=f'<a id="dashboard" href="{url}">Open private investigation</a><a id="api" href="{url}api/status">API</a>'.encode()
                    self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            entry=http.server.ThreadingHTTPServer(('127.0.0.1',0),Entry)
            entry_thread=threading.Thread(target=entry.serve_forever,daemon=True);entry_thread.start()
            outside=f'http://localhost:{entry.server_port}/'
            page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(outside,wait_until='networkidle')
            with page.expect_response(lambda r:r.url==url) as opened:page.locator('#dashboard').click()
            response=opened.value;assert response.status==200
            emitted=response.request.all_headers()
            assert emitted.get('sec-fetch-site')=='cross-site' and emitted.get('sec-fetch-mode')=='navigate'
            assert emitted.get('sec-fetch-dest')=='document' and emitted.get('sec-fetch-user')=='?1'
            expect(page.locator('#node-rows tr')).to_have_count(3);expect(page.locator('#connection')).to_have_text('SYNTHETIC DEMO')
            expect(page.locator('#history-chart canvas')).to_have_count(1)
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            assert response.headers['cross-origin-resource-policy']=='same-origin'
            passed('real cross-site user link opens the forwarded dashboard with native Fetch Metadata and unchanged CSP')
            page.get_by_role('button',name='Review next step',exact=True).click()
            expect(page.locator('#review-dialog')).to_be_visible();page.keyboard.press('Escape')
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            with page.expect_download() as download:page.get_by_role('button',name='Save minimal support report').click()
            report=json.loads(Path(download.value.path()).read_text());assert report['sent'] is False
            assert (root/'history.sqlite3').read_bytes()==before
            if out:page.screenshot(path=str(out/'remote-workbench.png'))
            passed('forwarded workbench review, refresh and private support download preserve retained evidence')
            # A direct user click to a data endpoint is not a dashboard navigation allowance.
            page.goto(outside,wait_until='networkidle')
            with page.expect_response(lambda r:r.url==url+'api/status') as blocked:page.locator('#api').click()
            assert blocked.value.status==403
            page.goto(outside,wait_until='networkidle')
            with page.expect_response(lambda r:r.url==url) as embedded:
                page.evaluate('(url)=>{const frame=document.createElement("iframe");frame.src=url;document.body.append(frame)}',url)
            assert embedded.value.status==403
            unreadable=page.evaluate('async url=>{try{const r=await fetch(url+"api/support");return await r.text()}catch{return "BROWSER_READ_BLOCKED"}}',url)
            assert unreadable=='BROWSER_READ_BLOCKED'
            passed('browser-initiated data navigation, embedding and cross-site subresource reads stay refused')
            page.goto(outside,wait_until='networkidle');page.locator('#dashboard').click()
            expect(page.locator('#node-rows tr')).to_have_count(3)
            close_relay();assert viewer.verify(handoff)['state']=='NOT_VERIFIED'
            page.get_by_role('button',name='Refresh live readings').click();expect(page.locator('#transport-error')).to_be_visible()
            assert agent.runtime_status(root)['process_verified']
            relay=Relay(relay_port);start_relay(target)
            assert viewer.verify(handoff)['state']=='VIEWER_MATCHED'
            page.get_by_role('button',name='Refresh live readings').click();expect(page.locator('#transport-error')).to_be_hidden()
            assert agent.runtime_status(root)['run_id']==run_id and (root/'history.sqlite3').read_bytes()==before
            passed('disconnect and reconnect restore the same browser investigation without a second collector')
            stopped=agent.stop(root,run_id,wait=8);assert stopped['state']=='STOPPED' and not stopped['process_verified']
            assert viewer.verify(handoff)['state']=='NOT_VERIFIED';assert not errors,errors
            passed('stopped source cannot pass viewing-machine verification and no owned worker survives the test')
        finally:
            if page:page.close()
            close_relay()
            if entry:entry.shutdown();entry.server_close()
            if entry_thread:entry_thread.join(3)
            if run_id:agent.stop(root,run_id,wait=8)
