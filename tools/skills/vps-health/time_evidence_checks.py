"""Existing workbench acceptance against real synthetic sparse-context history.

No new frontend renderer is implied. The source-generated finding and exported
snapshot are checked with the actual server; inline coverage widgets are pending.
"""
from pathlib import Path
import json
import tempfile
import threading
import time
from types import SimpleNamespace
from playwright.sync_api import expect
import vps_workspace as ws
import vps_health as core
import vps_evidence as evidence


def run(context,out,passed):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)/'observations'
        ws.bootstrap(SimpleNamespace(workspace=root,mode='demo',node='example',interval=300,profile=None,
            url=None,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,acceptable=.9,investigate_below=.8))
        cfg=ws.config_load(root)[1];end=int(time.time()//300)*300;start=end-3*86400
        def seed(pressure):
            cap=core.new_capture('example-stable','synthetic',start,end,300)
            cap['source']['tool_sha256']='synthetic-time-context-'+str(pressure)
            cap['samples']=[{'timestamp':stamp,'duration_seconds':300,'quality':[],
                'cpu_accounted_ratio':.96,'executing_ratio':.2,'cpu_pressure_ratio':None,
                'cfs_throttled_periods_ratio':None} for stamp in range(start+300,end+1,300)]
            cap['samples'][-1].update(cpu_pressure_ratio=pressure,cfs_throttled_periods_ratio=0.)
            ws.ingest(root,cfg,[cap],end)
        seed(0.)
        server=ws.make_server(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        page=context.new_page();requests=[];page.on('request',lambda request:requests.append(request.url))
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            page.goto(base,wait_until='networkidle')
            page.get_by_label('Inspect node',exact=True).select_option('example-stable')
            expect(page.locator('#selected-mean')).to_have_text('96.0%')
            expect(page.locator('#action-title')).to_have_text('Check how much workload context was observed')
            expect(page.locator('#action-reason')).to_contain_text('A quiet average cannot fill unmeasured time')
            expect(page.locator('#action-copy')).to_contain_text('coverage and last observations')
            with page.expect_download() as download:page.get_by_role('button',name='Save summary JSON').click()
            payload=json.loads(Path(download.value.path()).read_text())
            selected=next(n for n in payload['assets'] if n['id']=='example-stable')
            assert selected['decision']=='WITHIN_TOLERANCE' and selected['context']=='CONTEXT_INCOMPLETE'
            cfs=selected['evidence_profile']['channels']['cfs']
            assert cfs['mean']==0 and 0<cfs['coverage']<.002 and not cfs['qualified']
            assert cfs['observed_seconds']==300
            assert all(url.startswith(base) or url.startswith('blob:') for url in requests)
            if out:page.screenshot(path=str(out/'sparse-context-corrected.png'),full_page=True)
            passed('real sparse-context source changes the existing workbench finding and private snapshot, not the accounting policy')
            seed(.4)
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#action-title')).to_have_text('Good accounting can still hide a busy service')
            d=ws.status(root)['assets'][0]
            assert d['context']=='CONTENTION_PRESENT' and 'workload_context_sparse' in d['holds']
            before=(root/'history.sqlite3').read_bytes()
            report=evidence.report(root,'example-stable',start,end)
            assert report['profile']['channels']['pressure']['mean']==.4
            assert report['profile']['channels']['pressure']['observed_seconds']==300
            assert not report['provider_cause_proven'] and (root/'history.sqlite3').read_bytes()==before
            passed('short observed pressure remains visible without becoming complete context or changing retained evidence')
        finally:
            page.close();server.shutdown();server.server_close();thread.join(3)
