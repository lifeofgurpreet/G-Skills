"""Temporal workbench, pinned handoff and real summary export acceptance.

All source observations are synthetic. Most checks use the actual local server;
one explicitly malformed response and a legacy-profile response test refusal and
compatibility. No browser action can execute a CLI command or contact a provider.
"""
from pathlib import Path
import json
import copy
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
        page=context.new_page();requests=[];errors=[];page.on('request',lambda request:requests.append(request.url));page.on('pageerror',lambda error:errors.append(str(error)))
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
            expect(page.locator('#context-pressure-coverage')).to_contain_text('5.0 min · 0.12% coverage · sparse')
            expect(page.locator('#context-cfs-coverage')).to_contain_text('5.0 min · 0.12% coverage · sparse')
            page.get_by_role('link',name='Evidence',exact=True).click()
            expect(page.get_by_label('Evidence subject',exact=True)).to_have_value('example-stable')
            row=page.locator('#time-channel-rows [data-channel=cfs]')
            expect(row).to_contain_text('0.0%');expect(row).to_contain_text('5.0 min');expect(row).to_contain_text('0.12%');expect(row).to_contain_text('Sparse coverage')
            cli=evidence.report(root,'example-stable',core.stamp(selected['window_start']),core.stamp(selected['window_end']))
            assert cli['profile']['channels']['cfs']['observed_seconds']==300
            assert abs(cli['profile']['channels']['cfs']['coverage']-cfs['coverage'])<1e-8
            full=page.locator('#time-summary').inner_text()
            page.locator('#time-details summary').click()
            expect(page.locator('#time-details')).to_have_attribute('open','')
            with page.expect_response(lambda response:response.url==base+'/api/status'):
                page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#time-details')).to_have_attribute('open','')
            page.get_by_role('link',name='Overview',exact=True).click()
            page.get_by_role('button',name='6h',exact=True).click()
            page.get_by_role('link',name='Evidence',exact=True).click()
            expect(page.locator('#time-summary')).to_have_text(full)
            if out:page.screenshot(path=str(out/'context-evidence.png'),full_page=True)
            passed('channel denominators agree with the CLI and full assessment survives chart zoom and detail refresh')
            page.get_by_label('Evidence subject',exact=True).select_option('example-contended')
            expect(page.locator('#time-subject')).to_contain_text('example-contended')
            expect(page.locator('#time-episodes')).not_to_contain_text('0 uninterrupted')
            expect(page.locator('#time-run-list .check-item')).not_to_have_count(0)
            expect(page.locator('#time-execution-rows tr')).to_have_count(4)
            page.get_by_label('Evidence subject',exact=True).select_option('example-stable')
            passed('evidence selection exposes source shortfall runs and execution bands without a new verdict')
            page.get_by_role('link',name='Overview',exact=True).click()
            page.get_by_role('button',name='Review next step',exact=True).click()
            expect(page.locator('#review-context')).to_contain_text('0.12% of the full window')
            pinned=page.locator('#review-context p').all_text_contents();task=page.locator('#review-task').input_value()
            assert '5.0 min measured (0.12%' in task and 'Do not infer provider responsibility' in task
            if out:page.screenshot(path=str(out/'context-review.png'))
            seed(.4)
            with page.expect_response(lambda response:response.url==base+'/api/status',timeout=10000):
                page.wait_for_timeout(5600)
            expect(page.locator('#review-context p')).to_have_text(pinned)
            expect(page.locator('#review-task')).to_have_value(task)
            page.keyboard.press('Escape')
            expect(page.locator('#context-pressure')).to_have_text('40.0%')
            expect(page.locator('#context-pressure-coverage')).to_contain_text('0.12% coverage · sparse')
            passed('pinned review and copied agent task retain contextual denominators while newer source observations arrive')
            expect(page.locator('#action-title')).to_have_text('Good accounting can still hide a busy service')
            d=ws.status(root)['assets'][0]
            assert d['context']=='CONTENTION_PRESENT' and 'workload_context_sparse' in d['holds']
            before=(root/'history.sqlite3').read_bytes()
            report=evidence.report(root,'example-stable',start,end)
            assert report['profile']['channels']['pressure']['mean']==.4
            assert report['profile']['channels']['pressure']['observed_seconds']==300
            assert not report['provider_cause_proven'] and (root/'history.sqlite3').read_bytes()==before
            passed('short observed pressure remains visible without becoming complete context or changing retained evidence')
            invalid=ws.status(root);invalid['assets'][0]['evidence_profile']['bands']['within_seconds']+=60
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(invalid)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#context-pressure')).to_have_text('40.0%')
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).not_to_be_visible()
            legacy=ws.status(root)
            for item in legacy['assets']:item.pop('evidence_profile',None)
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(legacy)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#context-cfs-coverage')).to_have_text('Coverage not recorded')
            page.get_by_role('link',name='Evidence',exact=True).click()
            expect(page.locator('#time-window')).to_contain_text('Time qualification is missing')
            expect(page.locator('#time-channel-rows tr')).to_have_count(0)
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#time-channel-rows tr')).to_have_count(4)
            passed('malformed temporal payload freezes prior evidence; legacy absence remains visibly unqualified')
            page.set_viewport_size({'width':320,'height':800})
            page.get_by_label('Evidence subject',exact=True).select_option('example-offline')
            expect(page.locator('#time-channel-rows')).to_contain_text('Stale')
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.get_by_label('Evidence subject',exact=True).select_option('example-stable')
            if out:page.screenshot(path=str(out/'context-mobile.png'),full_page=True)
            passed('320-pixel evidence view preserves node selection, missingness and readable bounded tables')
            archive=Path(folder)/'private-export';before=(root/'history.sqlite3').read_bytes()
            ws.export(root,archive);checked=ws.verify_export(archive)
            assert checked['integrity']=='PASS' and checked['replay']=='NOT_AVAILABLE'
            assert before==(root/'history.sqlite3').read_bytes()
            offline=context.new_page();offline.goto((archive/'dashboard.html').as_uri(),wait_until='networkidle')
            offline.get_by_role('link',name='Evidence',exact=True).click()
            offline.get_by_label('Evidence subject',exact=True).select_option('example-stable')
            expect(offline.locator('#time-channel-rows [data-channel=cfs]')).to_contain_text('0.12%')
            expect(offline.locator('#pause-view')).not_to_be_visible()
            if out:
                (out/'context-demo.html').write_bytes((archive/'dashboard.html').read_bytes())
                offline.screenshot(path=str(out/'context-offline.png'),full_page=True)
            offline.close();assert not errors,errors
            assert all(url.startswith(base) or url.startswith('blob:') for url in requests)
            passed('actual verified summary opens the same time-qualified workbench offline with no new collection')

        finally:
            page.close();server.shutdown();server.server_close();thread.join(3)
