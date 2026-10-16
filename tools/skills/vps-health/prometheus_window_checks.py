"""Real workbench and export checks over a synthetic coarse Prometheus history.

The temporary endpoint returns shaped range-query data; it is not a PromQL engine.
An independent installed-promtool check qualifies the actual query semantics.
"""
from pathlib import Path
import hashlib,http.server,json,tempfile,threading,time,urllib.parse
from types import SimpleNamespace
from playwright.sync_api import expect
import vps_health as core
import vps_workspace as ws
import vps_evidence as evidence


def run(context,out,passed):
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);root=base/'observations';end=int(time.time()//300)*300;start=end-3*86400
        requests=[]
        class Metrics(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);requests.append(q)
                query=q['query'][0]
                value='.96' if 'mode=~"user|nice|system|idle' in query else '.2' if 'mode=~' in query else '.01'
                a=int(float(q['start'][0]));b=int(float(q['end'][0]));step=int(q['step'][0])
                body={'status':'success','data':{'resultType':'matrix','result':[{'metric':{},'values':[[t,value] for t in range(a,b+1,step)]}]}}
                raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        metrics=http.server.ThreadingHTTPServer(('127.0.0.1',0),Metrics);mt=threading.Thread(target=metrics.serve_forever,daemon=True);mt.start()
        endpoint='http://127.0.0.1:'+str(metrics.server_port)
        profile={'schema':'g-skills.vps-profile.v1','assets':[{'id':'example-hourly','instance':'example.invalid:9100'}]}
        core.save_json(base/'profile.json',profile)
        ws.bootstrap(SimpleNamespace(workspace=root,mode='prometheus',profile=base/'profile.json',url=endpoint,node='example',interval=3600,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,acceptable=.9,investigate_below=.8))
        try:captures=core.collect_prometheus(profile,endpoint,start,end,3600)
        finally:metrics.shutdown();metrics.server_close();mt.join(3)
        self_cfg=ws.config_load(root)[1];ws.ingest(root,self_cfg,captures,end)
        before=(root/'history.sqlite3').read_bytes()
        server=ws.make_server(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        page=context.new_page();page_errors=[];page.on('pageerror',lambda error:page_errors.append(str(error)))
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            page.goto(url,wait_until='networkidle')
            expect(page.locator('#selected-mean')).to_have_text('96.0%')
            expect(page.locator('#selected-status')).to_contain_text('On hold')
            expect(page.locator('#count-held')).to_have_text('01')
            expect(page.locator('#count-tolerance')).to_have_text('00')
            expect(page.locator('#action-title')).to_have_text('Review the monitoring interval')
            expect(page.locator('#action-copy')).to_contain_text('existing approved Prometheus plan')
            page.get_by_role('link',name='Evidence',exact=True).click()
            expect(page.locator('#time-channel-rows [data-channel=accounted]')).to_contain_text('6.0 h')
            row=page.locator('#time-channel-rows [data-channel=accounted]').inner_text()
            assert '8.' in row and 'Sparse' in row,row
            page.get_by_role('link',name='Overview',exact=True).click()
            page.get_by_role('button',name='Review next step',exact=True).click()
            task=page.locator('#review-task').input_value()
            assert 'Measured time: 6.0 h' in task and 'insufficient_coverage' in task and 'at most 300 seconds' in task,task
            page.keyboard.press('Escape')
            with page.expect_download() as dl:page.get_by_role('button',name='Save summary JSON').click()
            value=json.loads(Path(dl.value.path()).read_text());node=value['assets'][0]
            assert node['decision']=='HOLD' and node['observed_hours']==6
            assert all(p['break_before'] for p in node['history'][1:])
            assert all(p['mean'] is None or p['coverage']<.75 for p in node['timeline'])
            assert len(requests)==7 and all(q['step']==['3600'] for q in requests)
            assert not page_errors,page_errors
            if out:page.screenshot(path=str(out/'coarse-query-workbench.png'),full_page=True)
            passed('coarse five-minute query windows stay six observed hours, HOLD and visible gaps in real workbench and pinned handoff')
            exported=base/'export';ws.export(root,exported);verified=ws.verify_export(exported)
            assert verified['integrity']=='PASS' and verified['replay']=='NOT_AVAILABLE'
            report=evidence.report(root,'example-hourly',start,end)
            assert report['profile']['observed_seconds']==21600 and report['profile']['unobserved_seconds']==237600
            offline=context.new_page()
            offline.goto((exported/'dashboard.html').as_uri(),wait_until='networkidle')
            expect(offline.locator('#count-held')).to_have_text('01')
            offline.close();assert (root/'history.sqlite3').read_bytes()==before
            passed('time report, verified summary and offline dashboard preserve the same coarse gaps without changing source observations')
        finally:page.close();server.shutdown();server.server_close();thread.join(3)
