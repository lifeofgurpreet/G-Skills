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

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'skills/vps-health/scripts'))
import vps_workspace as workspace
import vps_ops as ops
import vps_agent as agent
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
        page=context.new_page();errors=[];requests=[];owned_run=None
        # The OS permission boundary is simulated; DOM/server behavior is real.
        page.add_init_script("""window.__notificationRequests=0;window.__notifications=[];
        window.Notification=function(title,opts){window.__notifications.push({title,opts});this.close=()=>{};};
        Notification.permission='default';Notification.requestPermission=async()=>{window.__notificationRequests++;Notification.permission='granted';return 'granted';};""")
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
            expect(page.locator('#history-chart canvas')).to_have_count(1)
            expect(page.locator('#context-chart canvas')).to_have_count(1)
            expect(page.locator('#history-chart .uplot')).to_have_attribute('data-chart-engine','uPlot')
            passed('actual server, three subjects, derived counts and selected history')
            page.locator('#guest-context-details summary').click()
            expect(page.locator('#guest-context-status')).to_contain_text('Not collected')
            expect(page.locator('#guest-context-readings')).to_have_text('')
            diagnostic=workspace.status(root)
            subject=next(n for n in diagnostic['assets'] if n['id']=='example-contended')
            subject['guest_context_current']=True
            subject['guest_context']={'schema':'g-skills.guest-context-interval.v1','quality':[],'seconds':10,
                'storage':[{'device_id':'259:0','name':'nvme0n1','state':'observed','read_await_ms':None,'write_await_ms':30,'iops':.3}],
                'pressure':{'io':{'state':'observed','some':.2,'full':.1}},'network':{},'provider_cause_proven':False}
            mean=page.locator('#selected-mean').inner_text()
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(diagnostic)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#guest-context-readings')).to_contain_text('read mean unmeasured')
            expect(page.locator('#guest-context-readings')).to_contain_text('write mean 30.00 ms')
            expect(page.locator('#selected-mean')).to_have_text(mean)
            page.unroute('**/api/status')
            broken=copy.deepcopy(diagnostic);next(n for n in broken['assets'] if n['id']=='example-contended')['guest_context']['storage']=[None]
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(broken)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#guest-context-readings')).to_contain_text('write mean 30.00 ms')
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            page.locator('#guest-context-details summary').click()
            passed('guest diagnostics retain missing latency and reject malformed data without changing the CPU decision')
            expect(page.locator('#attention-banner')).to_be_visible()
            expect(page.locator('#evidence-ribbon button')).to_have_count(48)
            assert page.evaluate('window.__notificationRequests')==0
            passed('operator briefing and interval ribbon render without requesting notification permission')
            if args.out:
                page.screenshot(path=str(args.out/'desktop.png'))
                (args.out/'demo.html').write_bytes(workspace.page(workspace.status(root)))
                (args.out/'status.json').write_text(json.dumps(workspace.status(root),indent=2)+'\n')

            page.get_by_role('button',name='Inspect example-stable',exact=True).click()
            expect(page.locator('#node-selector')).to_have_value('example-stable')
            expect(page.locator('#action-title')).to_have_text('Keep an eye on service impact')
            page.get_by_label('Inspect node',exact=True).select_option('example-offline')
            expect(page.locator('#action-title')).to_have_text('Restore trustworthy collection')
            expect(page.locator('#chart-message')).to_contain_text('No observations')
            page.get_by_label('Inspect sample',exact=True).focus();page.keyboard.press('Home')
            first=page.locator('#sample-value').inner_text();page.keyboard.press('End')
            assert page.locator('#sample-value').inner_text()!=first
            latest=page.locator('#sample-value').inner_text()
            page.locator('#history-chart .u-over').hover(position={'x':55,'y':85})
            expect(page.locator('#sample-value')).not_to_have_text(latest)
            if args.out:page.screenshot(path=str(args.out/'missing-data.png'))
            passed('row/dropdown selection and keyboard sample inspection')

            # Exercise a real chart-library integration, not a decorative canvas.
            page.get_by_label('Inspect node',exact=True).select_option('example-contended')
            mean=page.locator('#selected-mean').inner_text()
            page.get_by_role('button',name='24h',exact=True).click()
            expect(page.get_by_role('button',name='24h',exact=True)).to_have_attribute('aria-pressed','true')
            limits=page.evaluate('chartEngine.getWindow()')
            assert abs(limits[1]-limits[0]-86400)<1
            expect(page.locator('#selected-mean')).to_have_text(mean)
            expect(page.locator('#view-boundary')).to_contain_text('view only')
            page.get_by_label('Inspect sample',exact=True).focus();page.keyboard.press('Home')
            sample_values=[page.locator('#'+name).inner_text() for name in ('sample-accounted','sample-execution','sample-pressure','sample-cfs')]
            assert all(value not in ('—','Unmeasured') for value in sample_values),sample_values
            page.get_by_role('button',name='Execution',exact=True).click()
            expect(page.get_by_role('button',name='Execution',exact=True)).to_have_attribute('aria-pressed','false')
            page.get_by_role('button',name='Execution',exact=True).click()
            with page.expect_response(lambda response:response.url==base+'/api/status'):
                page.get_by_role('button',name='Refresh live readings').click()
            expect(page.get_by_role('button',name='24h',exact=True)).to_have_attribute('aria-pressed','true')
            assert abs(page.evaluate('chartEngine.getWindow()[1]-chartEngine.getWindow()[0]')-86400)<1
            passed('linked library charts, exact context readout, channel toggle and persistent range without policy changes')

            # Drag the real plot overlay. Both panes must adopt the same range.
            overlay=page.locator('#history-chart .u-over').bounding_box()
            page.mouse.move(overlay['x']+overlay['width']*.25,overlay['y']+40)
            page.mouse.down();page.mouse.move(overlay['x']+overlay['width']*.70,overlay['y']+45,steps=8);page.mouse.up()
            assert page.evaluate('chartEngine.getWindow()[1]-chartEngine.getWindow()[0]')<86400*.75
            page.get_by_role('button',name='All history',exact=True).click()
            assert page.evaluate('chartEngine.getWindow()[1]-chartEngine.getWindow()[0]')>86400*2
            assert page.evaluate('JSON.stringify(chartEngine.getScales()[0])===JSON.stringify(chartEngine.getScales()[1])')
            passed('drag zoom and reset inspect history without altering assessment')

            with page.expect_download() as event:page.get_by_role('button',name='Save chart image').click()
            image=Path(event.value.path()).read_bytes();assert image[:8]==b'\x89PNG\r\n\x1a\n' and len(image)>1000
            page.get_by_role('button',name='6h',exact=True).click()
            with page.expect_download() as event:page.get_by_role('button',name='Save displayed samples CSV').click()
            csv=Path(event.value.path()).read_text();assert csv.startswith('observed_utc,accounted_ratio')
            assert len(csv.strip().splitlines())==page.locator('#sample-rows tr').count()+1
            page.get_by_text('Inspect displayed data as a table',exact=True).click()
            expect(page.locator('.sample-table')).to_be_visible()
            page.get_by_text('Inspect displayed data as a table',exact=True).click()
            page.get_by_role('button',name='All history',exact=True).click()
            passed('real PNG and bounded CSV downloads plus keyboard-accessible observation table')

            # New workflows exercise actual controls, not injected DOM calls.
            baseline_mean=page.locator('#selected-mean').inner_text()
            page.get_by_role('link',name='Attention',exact=False).click()
            expect(page.locator('#view-attention')).to_be_visible()
            expect(page.locator('.finding')).to_have_count(2)
            page.locator('.finding').first.get_by_role('button',name='Acknowledge',exact=True).click()
            expect(page.locator('.finding.acknowledged')).to_have_count(1)
            expect(page.locator('#operator-feedback')).to_contain_text('unchanged')
            page.get_by_role('link',name='Overview',exact=True).click()
            expect(page.locator('#selected-mean')).to_have_text(baseline_mean)
            passed('acknowledgment changes unread state without clearing HOLD or altering measurements')
            # Resolved incidents must not keep their old acknowledgment when
            # they recur in the same host epoch.
            page.get_by_role('link',name='Attention',exact=False).click()
            recovered=workspace.status(root)
            old=recovered['assets'][2]
            old.update(decision='WITHIN_TOLERANCE',context='NO_HIGH_PRESSURE_IN_RECORDED_CONTEXT',stale=False,holds=[])
            recovered['operator']=ops.brief(recovered)
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(recovered)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('.finding')).to_have_count(1)
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('.finding')).to_have_count(2)
            expect(page.locator('.finding.acknowledged')).to_have_count(0)
            page.get_by_role('link',name='Overview',exact=True).click()
            passed('resolved findings reappear unread instead of inheriting an old acknowledgment')
            if args.out:
                page.get_by_role('link',name='Attention',exact=False).click();page.screenshot(path=str(args.out/'attention.png'),full_page=True);page.get_by_role('link',name='Overview',exact=True).click()

            page.get_by_role('link',name='Setup',exact=True).click()
            expect(page.locator('#setup-command')).to_contain_text('doctor')
            page.get_by_role('button',name='Existing Prometheus',exact=True).click()
            expect(page.locator('#setup-command')).to_contain_text('--token-env')
            expect(page.locator('#setup-checks')).to_contain_text('not an independent account census')
            page.get_by_role('button',name='Explore the demo',exact=True).click()
            expect(page.locator('#setup-command')).to_contain_text('--mode demo')
            passed('single-host, existing-monitoring and demo setup routes expose commands with their boundaries')

            page.get_by_role('link',name='Providers',exact=True).click()
            expect(page.locator('.provider-card')).to_have_count(6)
            page.get_by_label('Provider reference').select_option('akamai')
            expect(page.locator('.provider-card')).to_have_count(1)
            page.locator('.provider-card summary').click()
            expect(page.locator('.provider-card')).to_contain_text('80%')
            expect(page.locator('.provider-card')).to_contain_text('usage allowance')
            links=page.locator('.provider-card a').evaluate_all('(links)=>links.map(a=>({url:a.href,rel:a.rel}))')
            assert all(link['url'].startswith('https://techdocs.akamai.com/') and 'noreferrer' in link['rel'] for link in links)
            page.get_by_label('Provider reference').select_option('all')
            passed('provider references preserve allocation/allowance distinction without fetching external policies')
            if args.out:page.screenshot(path=str(args.out/'providers.png'),full_page=True)

            page.get_by_role('link',name='Attention',exact=False).click()
            page.get_by_role('button',name='Enable desktop alerts',exact=True).click()
            expect(page.locator('#notification-status')).to_contain_text('while this viewer is open')
            assert page.evaluate('window.__notificationRequests')==1
            assert page.evaluate('window.__notifications.length')==0
            payload=workspace.status(root)
            payload['assets'][0]['epoch']='new-synthetic-epoch'
            payload['operator']=ops.brief(payload)
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(payload)))
            page.get_by_role('button',name='Refresh live readings').click()
            # The stable subject has no finding; changing it cannot generate an alert.
            assert page.evaluate('window.__notifications.length')==0
            payload['assets'][1]['epoch']='new-synthetic-epoch'
            payload['operator']=ops.brief(payload)
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            page.wait_for_timeout(100)
            assert page.evaluate('window.__notifications.length')==1
            page.get_by_role('button',name='Refresh live readings').click();page.wait_for_timeout(100)
            assert page.evaluate('window.__notifications.length')==1
            page.unroute('**/api/status')
            page.get_by_role('button',name='Refresh live readings').click()
            page.get_by_role('link',name='Overview',exact=True).click()
            passed('desktop permission is explicit and simulated notifications deduplicate repeated findings')

            page.get_by_label('Inspect node',exact=True).select_option('example-contended')
            before=page.locator('#selected-mean').inner_text()
            page.locator('#evidence-ribbon button').nth(35).click()
            expect(page.locator('#view-boundary')).to_contain_text('assessment uses the full retained window')
            expect(page.locator('#selected-mean')).to_have_text(before)
            page.get_by_role('button',name='All history',exact=True).click()
            passed('evidence ribbon changes only the displayed interval, not the decision')

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
            with page.expect_download() as event:page.get_by_role('button',name='Save minimal support report').click()
            support=json.loads(Path(event.value.path()).read_text())
            assert support['schema']=='g-skills.support-report.v1' and support['sent'] is False
            assert support['workspace']['expected_subjects']==3 and support['workspace']['retained_points']==2288
            assert all(value not in json.dumps(support) for value in ('example-stable','example-offline',str(root),'prometheus_url'))
            expect(page.locator('#operator-feedback')).to_contain_text('Review it before sharing')
            page.route('**/api/support',lambda route:route.fulfill(status=503,body='unavailable'))
            page.get_by_role('button',name='Save minimal support report').click()
            expect(page.locator('#operator-feedback')).to_contain_text('Nothing was uploaded')
            page.unroute('**/api/support')
            passed('real minimal-support download omits identities and handles unavailable service without an upload')

            # A slow request exposes an honest busy state instead of silently
            # swallowing a manual refresh during an automatic poll.
            pending=[]
            page.route('**/api/status',lambda route:pending.append(route))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.get_by_role('button',name='Refresh live readings')).to_be_disabled()
            assert pending
            pending[0].fulfill(status=200,content_type='application/json',body=json.dumps(workspace.status(root)))
            expect(page.get_by_role('button',name='Refresh live readings')).to_be_enabled()
            page.unroute('**/api/status')
            passed('in-flight refresh is visibly busy and cannot silently swallow another click')

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

            empty=workspace.status(root);empty['assets']=[];empty['expected_assets']=0;empty['operator']=ops.brief(empty)
            page.route('**/api/status',lambda route:route.fulfill(json=empty))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#action-title')).to_have_text('Configure your first node')
            expect(page.locator('.chart-wrap canvas')).to_have_count(0)
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('.chart-wrap canvas')).to_have_count(2)
            passed('zero-subject refresh removes prior charts and clean recovery rebuilds only two')

            payload=workspace.status(root)
            payload['assets'][0]['history']=[{'t':None,'value':.98,'quality':False}]
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(payload)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#selected-mean')).to_have_text(previous)
            page.unroute('**/api/status')
            payload=workspace.status(root);payload['as_of']=1e200
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(payload)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#selected-mean')).to_have_text(previous)
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            passed('malformed history does not partially replace the last valid view')
            broken=workspace.status(root);broken['operator']['items'][0].pop('evidence')
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(broken)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_visible()
            expect(page.locator('#selected-mean')).to_have_text(previous)
            page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#transport-error')).to_be_hidden()
            passed('malformed operator context cannot partially replace a valid screen')

            for width in (1440,768,390,320):
                page.set_viewport_size({'width':width,'height':900 if width>400 else 844})
                expect(page.locator('#history-chart canvas')).to_be_visible()
                # Canvas sizes settle on a rendering cycle. Verify the actual
                # stable view, not an observation made before resize delivery.
                # Do not weaken CSP or evaluate a polling string inside the page.
                try:page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                except Exception:
                    print('OVERFLOW',page.evaluate("[...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,cls:e.className,id:e.id,r:e.getBoundingClientRect()})).filter(e=>e.r.height>0&&e.r.right>innerWidth+.5).map(e=>({tag:e.tag,cls:typeof e.cls==='string'?e.cls:'svg',id:e.id,left:e.r.left,width:e.r.width,right:e.r.right})).slice(0,20)"))
                    raise
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'),str(width)
                assert page.locator('#node-selector').bounding_box()['width']>80
                if width<=390:
                    for selector in ('#save-summary','#node-selector','#node-search','#state-filter','#sample-inspector','#save-chart','#save-samples'):
                        assert page.locator(selector).bounding_box()['height']>=44,(width,selector)
                if args.out and width==390:
                    page.screenshot(path=str(args.out/'mobile.png'))
                    page.screenshot(path=str(args.out/'mobile-full.png'),full_page=True)
            passed('desktop/tablet/phone/minimum-width layout and touch target dimensions')
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_label('Search nodes').focus()
            page.keyboard.press('Tab');expect(page.get_by_label('Filter by evidence state')).to_be_focused()
            assert page.get_by_label('Filter by evidence state').evaluate('e=>getComputedStyle(e).outlineStyle')!='none'
            assert page.locator('#history-chart .u-cursor-x').evaluate("e => getComputedStyle(e).borderLeftWidth")=='0px'
            assert page.locator('#history-chart .u-cursor-x').evaluate("e => getComputedStyle(e).borderRightWidth")=='1px'
            passed('keyboard order and visible focus')
            colors=page.evaluate("Object.fromEntries(['--ink','--muted','--paper','--canvas','--soft','--strong'].map(k=>[k,getComputedStyle(document.documentElement).getPropertyValue(k).trim()]))")
            def luminance(value):
                if len(value)==4:value='#'+''.join(char*2 for char in value[1:])
                channels=[int(value[i:i+2],16)/255 for i in (1,3,5)]
                linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in channels]
                return sum(x*y for x,y in zip(linear,(.2126,.7152,.0722)))
            for foreground,background in [(colors[a],colors[b]) for a in ('--ink','--muted') for b in ('--paper','--canvas','--soft')]+[('#ffffff',colors['--strong'])]:
                low,high=sorted((luminance(foreground),luminance(background)))
                assert (high+.05)/(low+.05)>=4.5,(foreground,background)
            passed('main text and status text contrast at least 4.5 to 1')

            # Stage edge fixtures through the read endpoint. Signoff still uses
            # real inputs, not DOM mutations or calls into renderer internals.
            dense=workspace.status(root);seed=copy.deepcopy(dense['assets'][0]);dense['assets']=[]
            for index in range(100):
                node=copy.deepcopy(seed);node['id']='example-long-node-name-'+str(index).zfill(3);dense['assets'].append(node)
            dense['expected_assets']=100;dense['operator']=ops.brief(dense)
            page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(dense)))
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#node-rows tr')).to_have_count(100)
            page.get_by_label('Search nodes').fill('099');expect(page.locator('#node-rows tr')).to_have_count(1)
            page.get_by_role('button',name='Inspect example-long-node-name-099',exact=True).click()
            expect(page.locator('#node-selector')).to_have_value('example-long-node-name-099')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.unroute('**/api/status');page.get_by_label('Search nodes').fill('')
            passed('100-subject fixture keeps search and selection usable')
            touch=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='reduce')
            touch_page=touch.new_page();touch_page.goto(base,wait_until='networkidle')
            touch_page.get_by_role('button',name='24h',exact=True).tap()
            expect(touch_page.get_by_role('button',name='24h',exact=True)).to_have_attribute('aria-pressed','true')
            touch_page.get_by_role('button',name='Execution',exact=True).tap()
            expect(touch_page.get_by_role('button',name='Execution',exact=True)).to_have_attribute('aria-pressed','false')
            touch_page.get_by_role('button',name='Execution',exact=True).tap()
            touch_page.get_by_role('button',name='All history',exact=True).tap()
            if args.out:touch_page.screenshot(path=str(args.out/'touch-mobile.png'),full_page=True)
            touch.close();passed('touch-context time controls and channel toggles against the actual viewer')
            # The existing viewer stays up while a separately owned synthetic
            # worker is started and stopped. This is not a mocked runtime record.
            a=SimpleNamespace(workspace=root,mode='auto',node='example-node',profile=None,url=None,loki_url=None,
                token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,investigate_below=.8,
                provider='unknown',plan=None,duration_seconds=30,port=0,client='generic',approve_plan=None)
            a.approve_plan=agent.plan(a)['plan_sha256'];managed=agent.start(a);owned_run=managed['run_id']
            assert managed['process_verified'] and managed['state']=='RUNNING'
            page.get_by_role('button',name='Refresh live readings').click()
            page.get_by_role('link',name='Agent',exact=True).click()
            expect(page.locator('#agent-state')).to_have_text('RUNNING')
            expect(page.locator('#agent-title')).to_contain_text('owned worker is present')
            expect(page.locator('#agent-events')).to_contain_text('viewer verified')
            req=agent.connection_request(root,'mail.draft','Synthetic explicit draft task','generic')
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#agent-requests')).to_contain_text('NEEDS CONNECTION')
            assert 'mail.draft' in page.locator('#agent-requests').inner_text()
            agent.resolve_request(root,req['id'],'available','synthetic.mail_draft','synthetic-result')
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#agent-requests')).to_contain_text('HOST REPORTED AVAILABLE')
            expect(page.locator('#agent-requests')).to_contain_text('Recheck')
            if args.out:page.screenshot(path=str(args.out/'agent.png'),full_page=True)
            stopped=agent.stop(root,owned_run,wait=10)
            assert stopped['state']=='STOPPED' and not stopped['process_verified']
            page.get_by_role('button',name='Refresh live readings').click()
            expect(page.locator('#agent-state')).to_have_text('STOPPED')
            page.get_by_role('link',name='Overview',exact=True).click()
            passed('actual managed worker, connector handoff distinction and cooperative stop shown in the viewer')
            expect(page.locator('.chart-wrap .uplot')).to_have_count(2)
            assert not errors,errors
            assert all(url.startswith(base) or url.startswith('blob:') for url in requests),requests
            import workbench_checks
            workbench_checks.run(page,context,root,base,args.out,passed)
            assert not errors,errors
            passed('no JavaScript errors or external asset requests')
            receipt={'schema':'g-skills.browser-proof.v1','template_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/workspace-dashboard.html').read_bytes()).hexdigest(),
                     'chart_vendor_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/vendor/uplot/uPlot.iife.min.js').read_bytes()).hexdigest(),
                     'chart_adapter_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/chart-adapter.js').read_bytes()).hexdigest(),
                     'operator_js_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/operator.js').read_bytes()).hexdigest(),
                     'operator_css_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/operator.css').read_bytes()).hexdigest(),
                     'view_model_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/view-model.js').read_bytes()).hexdigest(),
                     'workbench_sha256':hashlib.sha256((ROOT/'skills/vps-health/assets/workbench.js').read_bytes()).hexdigest(),
                     'checks':checks,'result':'PASS','synthetic_only':True,'route':'actual loopback workspace HTTP handler',
                     'not_claimed':['physical phone validation','independent model review','production fleet qualification']}
            if args.out:(args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(json.dumps(receipt,indent=2))
        except Exception:
            if args.out:page.screenshot(path=str(args.out/'failure.png'),full_page=True)
            raise
        finally:
            if owned_run:
                agent.stop(root,owned_run,wait=10)
            context.close();browser.close();server.shutdown();server.server_close();thread.join(5)
    return 0


if __name__=='__main__':raise SystemExit(main())
