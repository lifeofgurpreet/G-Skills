"""Actual viewer interactions for the design-sprint implementation.

Uses the same temporary server as the existing browser suite. Only synthetic
response fixtures; the OS clipboard boundary is simulated, not email or a sender.
"""
from pathlib import Path
import copy
import json
from playwright.sync_api import expect
import vps_workspace as workspace
import vps_ops as ops


def run(page,context,root,base,out,passed):
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto(base,wait_until='networkidle')
    page.keyboard.press('Tab');expect(page.locator('.skip')).to_be_focused()
    page.keyboard.press('Enter');expect(page.locator('#main')).to_be_focused()
    expected=next(i for i in workspace.status(root)['operator']['items'] if i['node']=='example-offline')
    page.get_by_label('Inspect node',exact=True).select_option('example-offline')
    expect(page.locator('#action-title')).to_have_text(expected['title'])
    expect(page.locator('#action-copy')).to_have_text(expected['next_action'])
    expect(page.locator('#action-reason')).to_have_text(expected['reason'])
    passed('overview and inbox use the same canonical finding and next action')

    page.get_by_role('link',name='Providers',exact=True).click()
    details=page.locator('[data-provider="contabo"] details');details.locator('summary').click()
    with page.expect_response(lambda r:r.url==base+'/api/status'):
        page.get_by_role('button',name='Refresh live readings').click()
    expect(details).to_have_attribute('open','')
    page.get_by_label('Provider reference').select_option('aws')
    page.get_by_label('Provider reference').select_option('all')
    expect(page.locator('[data-provider="contabo"] details')).to_have_attribute('open','')
    passed('open provider context survives refresh and provider filtering')
    page.get_by_role('link',name='Overview',exact=True).click()

    page.get_by_role('button',name='Open command menu').click()
    expect(page.get_by_label('Search this workspace')).to_be_focused()
    page.get_by_label('Search this workspace').fill('offline')
    expect(page.locator('#command-results [role=option]')).to_have_count(1)
    page.keyboard.press('Enter')
    expect(page.locator('#command-dialog')).not_to_be_visible()
    expect(page.locator('#node-selector')).to_have_value('example-offline')
    expect(page.locator('#node-selector')).to_be_focused()
    page.keyboard.press('Control+k')
    page.get_by_label('Search this workspace').fill('NoMatchingPhrase')
    expect(page.locator('#command-empty')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('#command-dialog')).not_to_be_visible()
    expect(page.locator('#node-selector')).to_be_focused()
    passed('command menu searches actual nodes, handles empty results and restores focus on one Escape')

    page.get_by_label('Inspect node',exact=True).select_option('example-contended')
    original=page.locator('#selected-mean').inner_text()
    fresh=workspace.status(root);subject=next(n for n in fresh['assets'] if n['id']=='example-contended');subject['mean']=.62;fresh['operator']=ops.brief(fresh)
    page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(fresh)))
    page.get_by_role('button',name='Pause updates',exact=True).click()
    expect(page.locator('#pause-view')).to_have_attribute('aria-pressed','true')
    requests=[]
    listener=lambda request:requests.append(request.url) if request.url==base+'/api/status' else None
    page.on('request',listener)
    page.wait_for_timeout(5300)
    assert requests==[],requests
    expect(page.locator('#selected-mean')).to_have_text(original)
    expect(page.locator('#operator-feedback')).to_contain_text('Collection continues independently')
    page.get_by_role('button',name='Refresh live readings').click()
    expect(page.locator('#selected-mean')).to_have_text('62.0%')
    expect(page.locator('#pause-view')).to_have_attribute('aria-pressed','true')
    page.remove_listener('request',listener)
    page.unroute('**/api/status')
    page.get_by_role('button',name='Resume updates',exact=True).click()
    expect(page.locator('#selected-mean')).to_have_text(original)
    passed('pausing the view stops polling only; explicit refresh updates once without resuming')

    pending=[]
    page.route('**/api/status',lambda route:pending.append(route))
    page.get_by_role('button',name='Refresh live readings').click()
    expect(page.get_by_role('button',name='Refresh live readings')).to_be_disabled()
    page.get_by_role('button',name='Pause updates',exact=True).click()
    assert pending
    pending[0].fulfill(status=200,content_type='application/json',body=json.dumps(fresh))
    expect(page.get_by_role('button',name='Refresh live readings')).to_be_enabled()
    expect(page.locator('#selected-mean')).to_have_text(original)
    page.unroute('**/api/status');page.get_by_role('button',name='Resume updates',exact=True).click()
    expect(page.locator('#connection')).to_have_text('SYNTHETIC DEMO')
    passed('pausing during an in-flight request cannot replace the pinned readings')

    page.get_by_role('button',name='24h',exact=True).click()
    page.get_by_role('button',name='Review next step',exact=True).click()
    expect(page.locator('#review-dialog')).to_be_visible()
    expect(page.locator('#review-title')).to_be_focused()
    page.keyboard.press('Tab');expect(page.locator('#close-review')).to_be_focused()
    page.keyboard.press('Shift+Tab');expect(page.locator('#copy-review-task')).to_be_focused()
    pin=page.locator('#review-task').input_value();mean=page.locator('#review-mean').inner_text()
    assert 'Full assessment window:' in pin and 'not a new assessment window' in pin and 'SYNTHETIC DEMO' in pin
    page.route('**/api/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(fresh)))
    with page.expect_response(lambda response:response.url==base+'/api/status',timeout=9000):
        page.wait_for_timeout(5400)
    expect(page.locator('#selected-mean')).to_have_text('62.0%')
    expect(page.locator('#review-mean')).to_have_text(mean)
    expect(page.locator('#review-task')).to_have_value(pin)
    page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__copiedTask=text;}}})")
    page.get_by_role('button',name='Copy task for my agent',exact=True).click()
    expect(page.locator('#review-feedback')).to_contain_text('Copied locally')
    assert page.evaluate('window.__copiedTask')==pin
    assert 'Do not infer provider responsibility' in pin
    if out:page.screenshot(path=str(out/'pinned-review.png'))
    page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('synthetic denied clipboard')}}})")
    page.get_by_role('button',name='Copy task for my agent',exact=True).click()
    expect(page.locator('#review-task')).to_be_visible();expect(page.locator('#review-task')).to_be_focused()
    expect(page.locator('#review-feedback')).to_contain_text('Clipboard unavailable')
    page.keyboard.press('Escape');expect(page.locator('#review-dialog')).not_to_be_visible()
    expect(page.get_by_role('button',name='Review next step',exact=True)).to_be_focused()
    page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
    expect(page.locator('#selected-mean')).to_have_text(original)
    page.get_by_role('button',name='All history',exact=True).click()
    passed('review pins the full-window evidence and exact task across refresh, with local clipboard fallback')

    page.set_viewport_size({'width':390,'height':844})
    expect(page.locator('#primary-navigation')).not_to_be_visible()
    page.get_by_role('button',name='Menu',exact=True).click()
    expect(page.locator('#primary-navigation')).to_be_visible()
    expect(page.locator('#menu-toggle')).to_have_attribute('aria-expanded','true')
    assert page.locator('body').get_attribute('aria-current') is None
    page.get_by_role('link',name='Evidence',exact=True).click()
    expect(page.locator('#view-evidence')).to_be_visible()
    expect(page.locator('#primary-navigation [aria-current=page]')).to_have_count(1)
    expect(page.locator('#primary-navigation [aria-current=page]')).to_have_attribute('data-view','evidence')
    expect(page.locator('#primary-navigation')).not_to_be_visible()
    expect(page.locator('#main')).to_be_focused()
    page.get_by_role('button',name='Open command menu').click()
    page.get_by_label('Search this workspace').fill('Open Overview');page.keyboard.press('Enter')
    expect(page.locator('#view-overview')).to_be_visible()
    page.get_by_role('button',name='Review next step',exact=True).click()
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    if out:page.screenshot(path=str(out/'mobile-review.png'))
    page.get_by_role('button',name='Close evidence review').click()
    if out:
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(out/'workbench-mobile.png'))
        page.screenshot(path=str(out/'workbench-mobile-full.png'),full_page=True)
    passed('mobile navigation, local search and review dialogs remain reachable without horizontal overflow')

    page.set_viewport_size({'width':1440,'height':1000});page.goto(base,wait_until='networkidle')
    page.get_by_role('button',name='Open command menu').click()
    page.get_by_label('Search this workspace').fill('evidence')
    if out:page.screenshot(path=str(out/'command-menu.png'))
    page.keyboard.press('Escape')
    if out:
        page.locator('#page-title').click()
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(out/'workbench-desktop.png'))
        page.screenshot(path=str(out/'workbench-desktop-full.png'),full_page=True)
        (out/'demo.html').write_bytes(workspace.page(workspace.status(root)))
        offline=context.new_page();offline.goto((out/'demo.html').as_uri(),wait_until='networkidle')
        expect(offline.locator('#pause-view')).not_to_be_visible()
        offline.get_by_role('button',name='Open command menu').click()
        offline.get_by_label('Search this workspace').fill('Pause')
        expect(offline.locator('#command-empty')).to_be_visible()
        offline.keyboard.press('Escape');offline.get_by_role('button',name='Review next step').click()
        expect(offline.locator('#review-dialog')).to_be_visible();offline.close()
    passed('standalone offline workbench keeps review and navigation without offering live-only controls')
