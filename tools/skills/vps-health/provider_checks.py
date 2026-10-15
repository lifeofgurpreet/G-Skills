"""Provider references rendered by the actual local viewer, not live API claims."""
import copy
import json
from playwright.sync_api import expect
import vps_workspace as workspace


def run(page,root,out,passed):
    selector=page.get_by_label('Provider reference')
    for name,needle in (('vultr','High Frequency'),('ovhcloud','Discovery'),('netcup','Root Servers')):
        selector.select_option(name)
        card=page.locator('[data-provider="'+name+'"]')
        expect(card).to_be_visible();card.locator('summary').click()
        expect(card).to_contain_text(needle)
        expect(card.locator('.source-review-date').first).to_contain_text('2026-10-15')
        expect(card).to_contain_text('not')
    passed('new provider choices render their dated purchased-product distinctions without fetching services')

    selector.select_option('contabo');card=page.locator('[data-provider="contabo"]')
    card.locator('summary').click()
    diagnostic=card.locator('[data-kind="support_request"]')
    expect(diagnostic).to_contain_text('not run implicitly')
    expect(diagnostic.locator('a')).to_have_attribute('href','https://help.contabo.com/en/support/solutions/articles/103000271266-how-can-i-run-diagnostics-on-my-server-')
    expect(diagnostic.locator('.source-review-date')).to_contain_text('2026-10-15')
    passed('existing provider diagnostics are visible with their date and separate active-probe permission boundary')

    payload=workspace.status(root)
    old=next(p for p in payload['provider_reference']['providers'] if p['id']=='contabo')
    old.update(review_state='RECHECK_REQUIRED',reviewed_on='2025-01-01')
    old['facts'][0].update(reviewed_on='2025-01-01',review_state='RECHECK_REQUIRED')
    payload['provider_reference']['review_state']='RECHECK_REQUIRED'
    page.route('**/api/status',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(payload)))
    page.get_by_role('button',name='Refresh live readings').click()
    expect(card.locator('details')).to_have_attribute('open','')
    expect(card.locator('.provider-review-state')).to_contain_text('Source recheck required')
    expect(card.locator('.source-review-date').first).to_contain_text('2025-01-01')
    expect(card.locator('[data-kind="support_request"] .source-review-date')).to_contain_text('2026-10-15')
    selector.select_option('vultr');expect(page.locator('#provider-review')).to_contain_text('0 need rechecking')
    selector.select_option('contabo');expect(page.locator('#provider-review')).to_contain_text('1 need rechecking')
    if out:page.screenshot(path=str(out/'provider-stale-source.png'),full_page=True)
    page.unroute('**/api/status')
    passed('old source dates stay visible, current diagnostics do not refresh them, and selected-provider age is independent')

    malformed=copy.deepcopy(payload)
    p=next(p for p in malformed['provider_reference']['providers'] if p['id']=='contabo')
    p['diagnostics'][0]['source']='https://www.netcup.com/en/helpcenter/documentation/server'
    page.route('**/api/status',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(malformed)))
    page.get_by_role('button',name='Refresh live readings').click()
    expect(page.locator('#transport-error')).to_be_visible()
    expect(card.locator('[data-kind="support_request"] a')).to_have_attribute('href','https://help.contabo.com/en/support/solutions/articles/103000271266-how-can-i-run-diagnostics-on-my-server-')
    page.unroute('**/api/status');page.get_by_role('button',name='Refresh live readings').click()
    expect(page.locator('#transport-error')).to_be_hidden()
    expect(card.locator('.provider-review-state')).to_contain_text('Dated sources')
    selector.select_option('other')
    expect(page.locator('.provider-card')).to_contain_text('Provider not identified')
    expect(page.locator('.provider-card .policy-fact')).to_have_count(0)
    selector.select_option('all')
    if out:page.screenshot(path=str(out/'provider-reference-expanded.png'),full_page=True)
    passed('mismatched provider diagnostics cannot replace valid references; unidentified products stay unknown')
