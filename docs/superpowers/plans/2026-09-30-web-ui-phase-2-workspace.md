# Web UI Phase 2 — Workspace Review UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide the single-page review workspace: 40%/60% panes, five tabbed tables, full lower details with related-record tables, claim status/notes editing, and the shared detail modal, styled with exactly one biotech-inspired stylesheet.

**Architecture:** Serve one Django template with small, dependency-free JavaScript and exactly one stylesheet from `/app/`; consume the Phase 1 list/detail API over same-origin fetches. The only write in this phase is the claim `status`/`notes` PATCH. Keep the existing JSON health endpoint at `/`.

**Tech Stack:** Existing Django, PostgreSQL and Django test runner; DRF from Phase 1; browser-native HTML/CSS/JavaScript, without React, npm, django-filter, or a separate frontend service.

**Spec:** `docs/superpowers/plans/2026-09-30-web-ui.md` (phase index) and the corresponding user requests (2026-09-30). Requires Phase 1 (`2026-09-30-web-ui-phase-1-backend.md`) complete. No separate approved design document exists; the concrete decisions below make the request executable.

## Global Constraints

- No login, authorization rules, user accounts, or role-specific behavior for this UI. The only write in this phase is claim `status`/`notes`. An unauthenticated writable endpoint is intentionally open to anyone who can reach the deployment; restrict network exposure when deploying.
- Keep normal CSRF protection on the unauthenticated, same-origin claim PATCH; DRF `SessionAuthentication` does **not** enforce CSRF for anonymous requests. Do not treat CSRF as authorization.
- Upper and lower panes occupy 40% and 60% of viewport height, not width. Both scroll independently. The lower pane's content uses left/right columns on wide screens and stacks on narrow screens without overflowing the viewport.
- All workspace styling lives in `django_app/core/static/core/workspace.css`. The page loads exactly one local CSS file: no other stylesheet, CSS framework, `@import`, inline `<style>`, `style` attributes, or JS-generated CSS. JS changes semantic classes/attributes for visual states.
- Empty relations, missing source/section, no judgements, API failures, and out-of-range pages have explicit UI states. Escape all server-derived content by assigning DOM `textContent`, never raw `innerHTML`.
- Prefer existing `ClaimStatus`, model relations, `PublicationTrial`, and source section constants in `django_app/lib/text_tools.py`; do not regenerate claims/judgements in request handlers.
- Finish each task with its focused tests and a commit of only that task's files during execution. This document is a plan only; do not commit or modify application code while creating it.

---

## Visual Guidelines

Make the page feel like a careful clinical research workbench: calm, data-dense, and precise rather than a marketing landing page. Apply these rules entirely within `workspace.css`:

- Establish a small `:root` token set for color, spacing, type, border, and focus. Suggested light palette: canvas `#f3f7f6`, surface `#ffffff`, ink `#183137`, muted ink `#52666a`, hairline `#d5e2df`, primary deep teal `#0b645f`. Use teal for selection, links, and the Save action, not as large colored backgrounds. Use system sans for body and controls and a system monospace stack for IDs, scores, and timestamps; do not load external fonts.
- Keep a clear hierarchy: compact workspace header and tab bar, restrained section labels, readable 14-16px body type with at least 1.45 line-height, consistent 8/12/16/24px spacing, 1px dividers, and subtle 6-8px corner radii. Avoid gradients, illustrations, glass effects, heavy shadows, oversized cards, and decorative laboratory imagery.
- Design dense tables for scanning: aligned numbers/dates, truncation only for list excerpts (full text stays in details), sticky column headings within the upper pane, quiet row separators, a subtle hover state and an unmistakable selected row. The lower pane has a readable left/right divider, clear relationship headings, and a prominent but restrained judgement panel. Use compact status badges with both text and color; never rely on color alone to distinguish pending/approved/rejected.
- Give all controls visible hover, selected, disabled, error, and keyboard-focus states. Maintain at least WCAG AA contrast (4.5:1 for normal text, 3:1 for essential control boundaries/focus indicators); use a darker border than the decorative hairline for controls. Keep target sizes comfortable and respect `prefers-reduced-motion`. The shared modal should use the same surfaces/type scale, with a quiet backdrop, visible close control, scrollable height-bounded timestamped log rows, and text labels alongside INFO/WARNING/ERROR colors.
- Keep the 40%/60% vertical pane ratio across desktop and narrow screens. On mobile, stack only the lower pane's internal columns, keep filter controls wrapping naturally, constrain the dialog to the viewport, and let tables scroll horizontally inside their own container rather than causing page-wide overflow.

## Repository Map And API Contract

Requires Phase 1 routes: `GET /api/<type>/?search=...&ordering=...&page=...` (25/page, `{count, next, previous, results}` with the exact per-type keys), `GET /api/<type>/<id>/` full details with previews and `section_text`, `GET /api/records/<kind>/<id>/` supporting-record lookup. Related claim tables reuse `GET /api/claims/?disease=<id>`, `?intervention=<id>`, `?trial=<id>`, or `?publication=<id>`; trial/publication linkage reuses `GET /api/trials/?publication=<id>` and `GET /api/publications/?trial=<id>`.

Target file responsibilities:

| File | Responsibility |
| --- | --- |
| `django_app/core/api.py` | Claim review PATCH only (Task 5); GET behavior unchanged from Phase 1. |
| `django_app/core/urls.py`, `django_app/core/views.py` | Route `/api/` and serve `/app/`, leaving `/` untouched. |
| `django_app/core/templates/core/workspace.html` | One page's controls, table, detail and shared record modal, including CSRF token. |
| `django_app/core/static/core/workspace.css` | The workspace's only stylesheet: design tokens, 40/60 layout, responsive panels, tables, states, and dialog. |
| `django_app/core/static/core/workspace.js` | Tab/list/detail/review/modal state and same-origin fetches. |
| `tests/django_app/core/test_api.py`, `tests/django_app/core/test_workspace.py` | Review PATCH tests and shell tests. |
| `tests/browser/seed.py`, `tests/browser/test_workspace.py`, `tests/browser/__init__.py`, `tests/browser/requirements.txt` | Repeatable local browser fixture and Playwright interaction check; no frontend build tooling or runtime dependency. |

`PATCH /api/claims/<id>/` accepts **only** `status` and/or `notes`; POST, PUT and DELETE remain unavailable on the five collection/detail routes. Integer `id` is the UI/API route key; show `nct_id` and `pmid` as human-readable identifiers. Switching tabs resets search/filter/page/selection and shows a lower-pane prompt until another row is chosen; changing a list query clears its page to 1.

Related-record tables (Task 6): claim right shows disease table (columns name, MeSH), intervention table (columns name, MeSH), and NER table; disease/intervention right shows an independently paginated claim table; trial right shows a claim table plus a publication table (columns PMID, title, journal, year, relation); publication right shows a claim table plus a trial table (columns NCT ID, title, status, phase, relation). Every related record is a clickable table row opening the same detail modal.

## Task 4: Single-Page Shell And Upper Table

**Files:**
- Create: `django_app/core/templates/core/workspace.html`, `django_app/core/static/core/workspace.css`, `django_app/core/static/core/workspace.js`, `tests/django_app/core/test_workspace.py`
- Modify: `django_app/core/views.py`, `django_app/core/urls.py`
- Test: `tests/django_app/core/test_workspace.py`

**Interfaces:**
- Consumes: Phase 1 `GET /api/<type>/` list routes and exact record keys.
- Produces: `GET /app/` shell, tab/search/filter/sort/page state, selected-row state; consumed by Tasks 5–6.

- [ ] **Step 1: Write the failing test**

```python
def test_workspace_shell(self):
    root = self.client.get('/')
    self.assertEqual(root['Content-Type'], 'application/json')
    page = self.client.get('/app/')
    self.assertEqual(page.status_code, 200)
    html = page.content.decode()
    for label in ['claims', 'diseases', 'interventions', 'trials', 'publications']:
        self.assertIn(label, html.lower())
```

Also assert: search input, filter region, table, upper/lower pane containers, modal/dialog container, static asset references, CSRF token, exactly one stylesheet link to `core/workspace.css` with no `<style>` blocks or `style` attributes. Run `./bin/manage test tests.django_app.core.test_workspace`; expect FAIL with `/app/` 404.

- [ ] **Step 2: Render the shell**

Render `/app/` using `ensure_csrf_cookie`. Build semantic HTML: `{% csrf_token %}` in a hidden control, tab buttons with active state, labeled search/filters, sortable `<th><button>` headings, real `<table>`/`<thead>`/`<tbody>`, previous/next buttons with count, an initial lower-pane instruction, `<dialog>` for details. Use keyboard-accessible buttons inside table cells to open a row and preserve clear focus styles.

- [ ] **Step 3: Implement layout and list behavior**

Implement every visual rule in `workspace.css`, with `:root` tokens and grouped rules for shell, tabs/filters, tables, lower details, review controls, dialog, responsive behavior, and reduced motion. Implement the 40vh/60vh split via CSS grid (`grid-template-rows: 40% 60%`, viewport-height container), independent `overflow: auto`, minimum heights, sticky table header, and horizontal table scroll. At narrow widths retain both vertically stacked panes while stacking only the **lower pane's** left/right columns. Follow the Visual Guidelines above; no inline styles or additional CSS files.

In JS, keep `tab`, `search`, `filters`, `ordering`, `page`, `selected`, and request `AbortController` state. Define an allowlisted per-tab column/filter map using the exact list-response keys; build queries with `URLSearchParams`; debounce search ~250 ms; cancel/ignore stale fetches after switching tabs; render loading, empty, error and page-count states. Header toggles `field`/`-field` and appends `id`/`-id` as tie-breaker. Use `textContent` for values, `aria-selected` for tabs, and clear selection on tab/filter/search changes; toggle classes/attributes rather than writing inline styles.

- [ ] **Step 4: Run tests and commit**

Run: `./bin/manage test tests.django_app.core.test_workspace` and `./bin/manage check`
Expected: PASS. Commit shell, assets, routes and tests.

## Task 5: Claim Review Update And CSRF

**Files:**
- Modify: `django_app/core/api.py`
- Test: `tests/django_app/core/test_api.py`

**Interfaces:**
- Consumes: Task 4 `/app/` CSRF token; Phase 1 claim routes.
- Produces: `PATCH /api/claims/<id>/` returning saved values and read-only `modified`; consumed by Task 6 Save flow.

- [ ] **Step 1: Write the failing tests**

```python
def test_claim_review_requires_csrf(self):
    claim = Claim.objects.create(section='title', claim_type='review')
    response = self.client.patch(
        f'/api/claims/{claim.pk}/',
        data='{"status": "approved"}',
        content_type='application/json',
    )
    self.assertEqual(response.status_code, 403)
```

Use `Client(enforce_csrf_checks=True)`: GET `/app/` sets a CSRF cookie; PATCH without `X-CSRFToken` is 403; PATCH with it saves both fields; invalid status is 400 and does not save notes; attempts to change `evidence`/`trial` are rejected with 400; POST/PUT/DELETE return 405; a nonexistent claim returns 404.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./bin/manage test tests.django_app.core.test_api`
Expected: FAIL with 405 until implementation.

- [ ] **Step 3: Write minimal implementation**

Add a `ClaimReviewSerializer` accepting only `status` and `notes`, exposing `modified` as read-only, rejecting unexpected keys, and validating `status` using `ClaimStatus.choices`. Use DRF partial update (`UpdateModelMixin`) only on the claim viewset with `http_method_names = ['get', 'patch', 'head', 'options']`. Reuse list/detail serializers for GET; do not allow other model writes. Mark the DRF claim view's dispatch with `csrf_protect` explicitly (anonymous DRF session auth does not enforce it).

- [ ] **Step 4: Run tests and commit**

Re-run focused tests, confirm 403/400/405/404 and persisted fields. Commit review API and tests.

## Task 6: Lower Details, Links, Modal, And Save Flow

**Files:**
- Modify: `django_app/core/static/core/workspace.js`, `django_app/core/static/core/workspace.css`, `django_app/core/templates/core/workspace.html`, `tests/django_app/core/test_workspace.py` and focused API tests if a contract discrepancy is found.
- Create: `tests/browser/__init__.py`, `tests/browser/seed.py`, `tests/browser/test_workspace.py`, `tests/browser/requirements.txt`
- Test: `tests/django_app/core/test_workspace.py`, `tests/browser/test_workspace.py`

**Interfaces:**
- Consumes: Task 4 shell/modal/state, Task 5 PATCH, Phase 1 detail and supporting-record endpoints.
- Produces: complete lower-pane renderers, modal record rendering, Save wiring, repeatable browser check; Phase 3 reuses the shared modal in operation mode.

- [ ] **Step 1: Cover the consumed JSON**

Write/extend Django integration tests to cover the JSON that the UI consumes: claim details with linked NER/entity/judgement/source, each related claim filter, reciprocal trial/publication lookup, and modal supporting-record detail. Run them before UI changes; fix missing backend contracts before implementing the corresponding display.

- [ ] **Step 2: Implement detail renderers and modal**

Implement one detail renderer per model: claim left = all fields + visually prominent judgement box (display method, score and verdict from `meta` if present; say "No judgement" if absent) + status select, notes textarea, Save. Claim right = chunk or non-chunk source text (or "Source unavailable or ambiguous"), disease table (columns name, MeSH), intervention table (columns name, MeSH), NER table with clickable records/entities. Disease/intervention right = independently paginated claim table. Trial right = independently paginated claim table plus linked publication table (columns PMID, title, journal, year, relation). Publication right = independently paginated claim table plus linked trial table (columns NCT ID, title, status, phase, relation). Every related record is shown as a table row, never a bare list; each row is clickable and opens the same detail modal. Left-side FKs and displayed related previews also use model links; preserve nulls and empty tables explicitly.

Implement a single modal fetch/render path keyed by the allowlisted model kind and integer ID. Render all persisted fields as labeled values or collapsible JSON; link any displayed foreign records to their detail endpoint. Native `<dialog>` handles Escape; give it an accessible title, restore focus to the opening button on close, and present loading/404/network-error messages.

- [ ] **Step 3: Wire Save**

Wire Save to send `PATCH` with `{status, notes}`, `Content-Type: application/json`, and `X-CSRFToken` read from the template token; disable Save during the request, display success/error, preserve unsaved edits on error, and refresh the selected claim and visible claim row after success. Do not silently submit on select/typing. Related list pagination must not change upper-table pagination.

- [ ] **Step 4: Add the repeatable browser check**

In `tests/browser/seed.py`, add an idempotent `seed()` using `get_or_create` with unique `UI-SMOKE` titles/evidence to create a Trial, Publication, PublicationTrial link, Disease, Intervention, one chunk-backed Claim with Judgement/NER, one title-backed Claim, and enough additional uniquely marked Claims to make 26 total (two pages). Run only on a disposable local database using `./bin/manage shell -c 'from tests.browser.seed import seed; seed()'`; do not invoke this from production startup.

Pin the Playwright Python package version in `tests/browser/requirements.txt` (developer test dependency only; do not add it to `etc/requirements.txt`). Add an automated `unittest` browser check in `tests/browser/test_workspace.py` using Playwright's sync API. Read `WORKSPACE_URL` with default `http://localhost:8001/app/`; use Chromium headless to assert five tabs, search/filter/sort/page, select a seeded claim and verify source text, open/close a related modal, save `approved` plus notes, reload to confirm persistence, and restore the selected claim's original status/notes via the page's CSRF-protected PATCH in `finally` before closing the browser. Assert one stylesheet link/no style tags or inline style attributes, visible focus and status text, and no page-wide horizontal overflow at a 390px viewport. Use the `UI-SMOKE` identifiers to select only fixture records.

- [ ] **Step 5: Run tests and commit**

With `./bin/start` serving the local database, install the browser test dependency outside the Django image using `python -m pip install -r tests/browser/requirements.txt` and `python -m playwright install chromium`, seed as above, then run `python -m unittest tests.browser.test_workspace -v` on the host; expect PASS. Also manually check mobile width, keyboard focus return, API failure/unsaved notes, and both source types at `http://localhost:8001/app/`. Run `./bin/test` for regression; commit UI behavior and tests.

## Completion Criteria

- `/` continues to respond as before and `/app/` is usable without logging in.
- Every top table supports tab-specific filters, text search, sortable allowlisted columns, and server pagination; selecting a row loads a complete lower detail pane.
- Claims show original source text, diseases, interventions, NERs, judgements, and a persisted status/notes edit; invalid/forbidden writes and missing CSRF are rejected.
- Disease/intervention/trial/publication panes show the requested reciprocal relationships as tables with the columns specified above; each related row opens a complete detail modal and return focus on close.
- The workspace uses only `workspace.css` and presents the restrained biotech-inspired design above consistently across both panes and the modal at desktop/mobile widths.
- Full Django tests, the repeatable browser test with its local fixture, and manual mobile/keyboard/error-state checks are complete.

Do not start implementation as part of the planning request.
