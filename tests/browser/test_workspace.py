"""Repeatable Playwright interaction check for the review workspace.

Requires a locally served app with the browser fixture seeded::

    ./bin/start                      # serve the local database
    python -m pip install -r tests/browser/requirements.txt
    python -m playwright install chromium
    ./bin/manage shell -c 'from tests.browser.seed import seed; seed()'
    python -m unittest tests.browser.test_workspace -v

Reads WORKSPACE_URL (default http://localhost:8001/app/). Restores the edited
claim's original status/notes through the page's CSRF-protected PATCH.
"""

import os
import json
import unittest

from playwright.sync_api import expect, sync_playwright

WORKSPACE_URL = os.environ.get('WORKSPACE_URL', 'http://localhost:8001/app/')


def click_row(page, selector):
    """Click a table row like a user, tolerating sticky-header overlap.

    A row parked at the exact top edge sits beneath the sticky ``thead``,
    where no pointer can land (the same as any sticky-header table). The
    dispatched fallback fires the identical handlers for that case.
    """
    target = page.locator(selector)
    target.evaluate('node => node.scrollIntoView({block: "center"})')
    try:
        target.click(timeout=5000)
    except Exception:
        target.evaluate('node => node.click()')


def search(page, query, count_text=None):
    """Fill the search box and wait for its fetch round-trip.

    Count text alone cannot signal freshness: consecutive searches may
    legitimately render the same counts from stale rows.
    """
    seq = page.evaluate('window.workspace.state.seq')
    page.fill('#ws-search', query)
    page.wait_for_function(f'window.workspace.state.seq > {seq}', timeout=10000)
    if count_text is not None:
        expect(page.locator('#ws-count')).to_contain_text(count_text, timeout=10000)


class WorkspaceBrowserTestCase(unittest.TestCase):
    def test_imports_with_intercepted_requests(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                calls = []
                records = []

                def import_publication(route):
                    payload = json.loads(route.request.post_data)
                    calls.append(('publications', payload))
                    pmid = payload['pmid']
                    if pmid == '111':
                        route.fulfill(status=502, json={'id': pmid, 'status': 'failed',
                                                        'error': 'Could not load publication. Retry this ID.',
                                                        'logs': [{'level': 'WARNING', 'message': 'Source unavailable',
                                                                  'time': '2026-09-30T22:00:00Z'}]})
                    else:
                        records.append({'id': 707, 'pmid': pmid, 'title': 'Imported paper',
                                        'journal': 'Journal', 'year': 2026, 'pub_date': None})
                        route.fulfill(json={'id': pmid, 'record_id': 707, 'status': 'ok',
                                            'logs': [{'level': 'INFO', 'message': 'Saved safely',
                                                      'time': '2026-09-30T22:00:00Z'}]})

                def import_trial(route):
                    payload = json.loads(route.request.post_data)
                    calls.append(('trials', payload))
                    route.fulfill(json={'id': payload['nct_id'], 'record_id': 808, 'status': 'ok',
                                        'related_publications': 2 if payload['load_related_publications'] else None,
                                        'logs': []})

                def publication_list(route):
                    route.fulfill(json={'count': len(records), 'results': records,
                                        'next': None, 'previous': None})

                page.route('**/api/import/publications/', import_publication)
                page.route('**/api/import/trials/', import_trial)
                page.route('**/api/publications/?*', publication_list)
                page.route('**/api/publications/707/', lambda route: route.fulfill(json={
                    'id': 707, 'pmid': '222', 'title': 'Imported paper'}))
                page.goto(WORKSPACE_URL, wait_until='networkidle')
                page.get_by_role('tab', name='Publications').click()
                page.fill('#ws-publication-ids', '111, invalid')
                page.get_by_role('button', name='Load publications').click()
                expect(page.locator('#ws-import-publications .ws-import-error')).to_contain_text('valid PMIDs')
                self.assertEqual(calls, [])
                page.fill('#ws-publication-ids', ', '.join(str(i) for i in range(1, 12)))
                page.get_by_role('button', name='Load publications').click()
                expect(page.locator('#ws-import-publications .ws-import-error')).to_contain_text('at most 10')
                self.assertEqual(calls, [])
                page.fill('#ws-publication-ids', ' 111, 222, 222 ')
                page.get_by_role('button', name='Load publications').click()
                expect(page.locator('#ws-modal')).to_be_visible()
                expect(page.locator('#ws-operation')).to_contain_text('111, 222')
                expect(page.locator('#ws-operation')).to_contain_text('Source unavailable')
                expect(page.locator('#ws-operation')).to_contain_text('Saved safely')
                expect(page.locator('#ws-operation')).to_contain_text('2026-09-30T22:00:00Z')
                expect(page.locator('#ws-operation')).to_contain_text('Partial', timeout=10000)
                self.assertEqual(calls[:2], [('publications', {'pmid': '111'}),
                                             ('publications', {'pmid': '222'})])
                expect(page.locator('#ws-publication-ids')).to_have_value('111')
                expect(page.locator('#ws-tbody')).to_contain_text('222')
                page.click('#ws-modal-close')
                page.click('#ws-view-progress')
                expect(page.locator('#ws-operation')).to_contain_text('Saved safely')
                page.locator('#ws-operation button', has_text='222').click()
                expect(page.locator('#ws-modal-body')).to_contain_text('Imported paper')
                page.click('#ws-modal-close')

                page.get_by_role('button', name='Load publications').click()
                expect(page.locator('#ws-operation')).to_contain_text('Failed:', timeout=10000)
                self.assertEqual(calls[-1], ('publications', {'pmid': '111'}))
                page.click('#ws-modal-close')

                page.get_by_role('tab', name='Trials').click()
                expect(page.locator('#ws-related-publications')).not_to_be_checked()
                page.fill('#ws-trial-ids', 'nct03026140, NCT03026140')
                page.evaluate('''() => {
                  const original = window.fetch;
                  window.fetch = (url, options) => String(url).startsWith('/api/import/trials/')
                    ? new Promise(resolve => setTimeout(() => resolve(original(url, options)), 400))
                    : original(url, options);
                }''')
                page.get_by_role('button', name='Load trials').click()
                expect(page.locator('#ws-import-trials button')).to_be_disabled()
                page.click('#ws-modal-close')
                page.get_by_role('tab', name='Claims').click()
                page.click('#ws-view-progress')
                expect(page.locator('#ws-operation')).to_contain_text('Completed', timeout=10000)
                self.assertEqual(calls[-1], ('trials', {'nct_id': 'NCT03026140',
                                                        'load_related_publications': False}))
                page.click('#ws-modal-close')
                page.get_by_role('tab', name='Trials').click()
                page.check('#ws-related-publications')
                page.fill('#ws-trial-ids', 'NCT03026141')
                page.get_by_role('button', name='Load trials').click()
                expect(page.locator('#ws-operation')).to_contain_text('Completed', timeout=10000)
                self.assertEqual(calls[-1], ('trials', {'nct_id': 'NCT03026141',
                                                        'load_related_publications': True}))
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),
                                     page.evaluate('window.innerWidth') + 1)
            finally:
                browser.close()

    def test_workspace(self):
        claim_id = None
        original = {'status': 'pending', 'notes': ''}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={'width': 1280, 'height': 800})
                page.goto(WORKSPACE_URL, wait_until='networkidle')

                # Five tabs are present; Claims is active.
                for label in ['Claims', 'Diseases', 'Interventions', 'Trials', 'Publications']:
                    expect(page.get_by_role('tab', name=label)).to_be_visible()
                expect(page.get_by_role('tab', name='Claims')).to_have_attribute('aria-selected', 'true')

                # Single stylesheet, no inline styling hooks.
                self.assertEqual(page.locator('link').count(), 1)
                self.assertEqual(page.locator('style').count(), 0)
                self.assertEqual(
                    page.evaluate('document.querySelectorAll("[style]").length'), 0)

                # Search the fixture: 26 UI-SMOKE claims across two pages.
                search(page, 'UI-SMOKE', '26')
                expect(page.locator('#ws-tbody tr').first).to_be_visible()

                # Sort toggle keeps the table functional.
                page.click('th button[data-field="status"]')
                expect(page.locator('#ws-tbody tr').first).to_be_visible()

                # Server pagination.
                page.click('#ws-next')
                expect(page.locator('#ws-count')).to_contain_text('26–26 of 26')
                self.assertEqual(page.locator('#ws-tbody tr').count(), 1)
                page.click('#ws-prev')
                expect(page.locator('#ws-count')).to_contain_text('1–25 of 26')

                # Status filter narrows the fixture set.
                page.select_option('select[name="status"]', 'pending')
                expect(page.locator('#ws-count')).to_contain_text('26')
                page.select_option('select[name="status"]', '')

                # Select the chunk-backed claim and verify its source text.
                search(page, 'UI-SMOKE chunk evidence', '1–1 of 1')
                expect(page.locator('#ws-tbody tr')).to_have_count(1)
                click_row(page, '#ws-tbody button.ws-row-open')
                expect(page.locator('#ws-detail')).to_contain_text(
                    'UI-SMOKE chunk body text.', timeout=10000)
                expect(page.locator('#ws-detail')).to_contain_text('supports')

                # Related disease row opens the shared modal; close returns focus.
                opener = page.locator('#ws-detail tbody button', has_text='UI-SMOKE Disease')
                expect(opener).to_be_visible()
                opener.click()
                modal = page.locator('#ws-modal')
                expect(modal).to_be_visible()
                expect(page.locator('#ws-modal-title')).to_contain_text('Disease')
                expect(page.locator('#ws-modal-body')).to_contain_text('UI-SMOKE Disease')
                page.click('#ws-modal-close')
                expect(modal).to_be_hidden()
                self.assertIn('UI-SMOKE Disease', page.evaluate('document.activeElement.textContent'))

                # Save flow on the title-backed claim, then reload persistence.
                search(page, 'UI-SMOKE title evidence', '1–1 of 1')
                expect(page.locator('#ws-tbody tr')).to_have_count(1)
                click_row(page, '#ws-tbody button.ws-row-open')
                expect(page.locator('#ws-review-status')).to_be_visible(timeout=10000)
                claim_id = page.evaluate(
                    'window.workspace.state.selected ? window.workspace.state.selected.id : null')
                original = {
                    'status': page.locator('#ws-review-status').input_value(),
                    'notes': page.locator('#ws-review-notes').input_value(),
                }
                page.select_option('#ws-review-status', 'approved')
                page.fill('#ws-review-notes', 'UI-SMOKE review note')
                page.get_by_role('button', name='Save').click()
                expect(page.locator('.ws-save-status')).to_contain_text('Saved.', timeout=10000)
                page.reload(wait_until='networkidle')
                search(page, 'UI-SMOKE title evidence', '1–1 of 1')
                expect(page.locator('#ws-tbody tr')).to_have_count(1)
                click_row(page, '#ws-tbody button.ws-row-open')
                expect(page.locator('#ws-review-status')).to_have_value('approved', timeout=10000)
                self.assertEqual(page.locator('#ws-review-notes').input_value(), 'UI-SMOKE review note')

                # Keyboard focus lands on a real control with visible status text.
                page.locator('#ws-search').focus()
                self.assertEqual(page.evaluate('document.activeElement.id'), 'ws-search')
                self.assertTrue(page.locator('#ws-status, #ws-count').first.is_visible())

                # Narrow viewport: no page-wide horizontal overflow.
                page.set_viewport_size({'width': 390, 'height': 844})
                page.wait_for_timeout(300)
                self.assertLessEqual(
                    page.evaluate('document.documentElement.scrollWidth'),
                    page.evaluate('window.innerWidth') + 1)
            finally:
                if claim_id is not None:
                    # Awaited: the browser must finish restoring before it closes.
                    status = page.evaluate(
                        """async ([id, status, notes]) => {
                          const token = document.cookie.match(/csrftoken=([^;]+)/)[1];
                          const response = await fetch('/api/claims/' + id + '/', {
                            method: 'PATCH',
                            headers: {
                              'Content-Type': 'application/json',
                              'X-CSRFToken': token
                            },
                            body: JSON.stringify({status: status, notes: notes})
                          });
                          return response.status;
                        }""",
                        [claim_id, original['status'], original['notes']])
                    self.assertEqual(status, 200)
                browser.close()
