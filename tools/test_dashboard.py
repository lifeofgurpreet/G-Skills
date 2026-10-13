#!/usr/bin/env python3
"""Browser qualification against the ACTUAL read-only workspace server.

Developer-only Playwright dependency. Runtime users still need only Python.
No provider endpoints, host collection, credentials or external assets are used.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/vps-health/scripts'))
import vps_workspace as workspace
from playwright.sync_api import sync_playwright, expect


def bootstrap(path,mode='demo'):
    return workspace.bootstrap(SimpleNamespace(workspace=path,mode=mode,node='example-node',interval=300,
        profile=None,url=None,loki_url=None,token_env=None,loki_token_env=None,allow_http=False,
        acceptable=.9,investigate_below=.8))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,help='Optional NEW screenshot/receipt directory; synthetic evidence only')
    args=parser.parse_args()
    if args.out:args.out.mkdir(parents=True,exist_ok=False)
    checks=[]
    def passed(name):checks.append(name);print('PASS:',name,flush=True)
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as playwright:
        root=Path(tmp)/'workspace';bootstrap(root)
        server=workspace.make_server(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        launch={'headless':True}
        if os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'):launch['executable_path']=os.environ['PLAYWRIGHT_CHROMIUM_EXECUTABLE']
        browser=playwright.chromium.launch(**launch)
        context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce',accept_downloads=True)
        page=context.new_page();errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(request.url))
        try:
            page.goto(base,wait_until='networkidle')
            expect(page.locator('#node-rows tr')).to_have_count(3)
            expect(page.locator('#connection')).to_have_text('SYNTHETIC DEMO')
            expect(page.locator('#count-tolerance')).to_have_text('01')
            expect(page.locator('#count-attention')).to_have_text('01')
            expect(page.locator('#count-held')).to_have_text('01')
            expect(page.locator('#node-selector')).to_have_value('example-contended')
            assert page.locator('#history-chart polyline').count()>0
            passed('actual server, three subjects, derived counts and selected history')
            if args.out:page.screenshot(path=str(args.out/'desktop.png'))

            page.get_by_role('button',name='Inspect example-stable',exact=True).click()
            expect(page.locator('#node-selector')).to_have_value('example-stable')
            expect(page.locator('#action-title')).to_have_text('Keep an eye on service impact')
            page.get_by_label('Inspect node',exact=True).select_option('example-offline')
            expect(page.locator('#action-title')).to_have_text('Restore fresh observations')
            expect(page.locator('#history-chart')).to_contain_text('No observations')
            page.get_by_label('Inspect sample',exact=True).focus();page.keyboard.press('Home')
            first=page.locator('#sample-value').inner_text();page.keyboard.press('End')
            assert page.locator('#sample-value').inner_text()!=first
            passed('row/dropdown selection and keyboard sample inspection')

            page.get_by_label('Filter by evidence state').select_option('held')
            expect(page.locator('#node-rows tr')).to_have_count(1)
            page.get_by_label('Search nodes').fill('not-present')
            expect(page.locator('#empty-search')).to_be_visible()
            expect(page.locator('#node-rows tr')).to_have_count(0)
            page.get_by_label('Search nodes').fill('')
            expect(page.locator('#node-rows tr')).to_have_count(1)
            page.get_by_label('Filter by evidence state').select_option('all')
            expect(page.locator('#node-rows tr')).to_have_count(3)
            passed('search and filters round trip with explicit empty state')

            page.get_by_role('link',name='Evidence',exact=True).click()
            expect(page.locator('#view-evidence')).to_be_visible()
            expect(page.locator('#view-overview')).to_be_hidden()
            assert page.locator('#daily-rows tr').count()>=9
            page.get_by_role('link',name='Collection',exact=True).click()
            expect(page.locator('#view-activity')).to_be_visible()
            assert page.locator('#event-rows tr').count()>0
            page.get_by_role('link',name='Overview',exact=True).click()
            expect(page.locator('#view-overview')).to_be_visible()
            passed('navigation changes actual evidence/collection views and returns')

            page.get_by_label('Inspect node',exact=True).select_option('example-contended')
            page.locator('#limits-label').click()
            expect(page.locator('#evidence-limits')).to_have_attribute('open','')
            with page.expect_response(lambda response:response.url==base+'/api/status'):
                page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#node-selector')).to_have_value('example-contended')
            expect(page.locator('#evidence-limits')).to_have_attribute('open','')
            passed('live refresh preserves selected subject and expanded limitations')

            with page.expect_download() as event:page.get_by_role('button',name='Save summary JSON').click()
            downloaded=json.loads(Path(event.value.path()).read_text())
            assert downloaded['synthetic'] and len(downloaded['assets'])==3
            assert 'code_hashes' in downloaded and 'prometheus_url' not in downloaded
            passed('real download contains synthetic summary and provenance, not endpoints')

            previous=page.locator('#selected-mean').inner_text()
            page.route('**/api/status',lambda route:route.abort())
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#connection')).to_have_text('Disconnected')
            expect(page.locator('#selected-mean')).to_have_text(previous)
            page.unroute('**/api/status')
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            passed('disconnect freezes last known values and recovery clears the warning')

            payload=workspace.status(root)
            payload['assets'][0]['history']=[{'t':None,'value':.98,'quality':False}]
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(payload)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#selected-mean')).to_have_text(previous)
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            passed('malformed history does not partially replace the last valid view')

            for width in (1440,768,390,320):
                page.set_viewport_size({'width':width,'height':900 if width>400 else 844})
                expect(page.locator('#history-chart svg')).to_be_visible()
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'),str(width)
                assert page.locator('#node-selector').bounding_box()['width']>80
                if width<=390:
                    for selector in ('#save-summary','#node-selector','#node-search','#state-filter','#sample-inspector'):
                        assert page.locator(selector).bounding_box()['height']>=44,(width,selector)
                if args.out and width==390:page.screenshot(path=str(args.out/'mobile.png'))
            passed('desktop/tablet/phone/minimum-width layout and touch target dimensions')
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_label('Search nodes').focus()
            page.keyboard.press('Tab');expect(page.get_by_label('Filter by evidence state')).to_be_focused()
            assert page.get_by_label('Filter by evidence state').evaluate('e=>getComputedStyle(e).outlineStyle')!='none'
            passed('keyboard order and visible focus')

            # Stage edge fixtures through the read endpoint. Signoff still uses
            # real inputs, not DOM mutations or calls into renderer internals.
            dense=workspace.status(root);seed=copy.deepcopy(dense['assets'][0]);dense['assets']=[]
            for index in range(100):
                node=copy.deepcopy(seed);node['id']='example-long-node-name-'+str(index).zfill(3);dense['assets'].append(node)
            dense['expected_assets']=100
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(dense)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#node-rows tr')).to_have_count(100)
            page.get_by_label('Search nodes').fill('099');expect(page.locator('#node-rows tr')).to_have_count(1)
            page.get_by_role('button',name='Inspect example-long-node-name-099',exact=True).click()
            expect(page.locator('#node-selector')).to_have_value('example-long-node-name-099')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.unroute('**/api/status');page.get_by_label('Search nodes').fill('')
            passed('100-subject fixture keeps search and selection usable')
            assert not errors,errors
            assert all(url.startswith(base) or url.startswith('blob:') for url in requests),requests
            passed('no JavaScript errors or external asset requests')
            receipt={'schema':'g-skills.browser-proof.v1','template_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/workspace-dashboard.html').read_bytes()).hexdigest(),
                     'checks':checks,'result':'PASS','synthetic_only':True,'route':'actual loopback workspace HTTP handler',
                     'not_claimed':['physical phone validation','independent model review','production fleet qualification']}
            if args.out:(args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(json.dumps(receipt,indent=2))
        finally:
            context.close();browser.close();server.shutdown();server.server_close();thread.join(5)
    return 0


if __name__=='__main__':raise SystemExit(main())
