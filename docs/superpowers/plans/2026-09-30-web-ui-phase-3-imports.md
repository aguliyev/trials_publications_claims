# Web UI Phase 3 — Trial/Publication Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add comma-delimited trial/publication import forms below the upper tables, with per-ID progress, logs, results, warnings, and errors shown in the shared operation modal.

**Architecture:** Keep the existing Django application and PostgreSQL database. Add two same-origin DRF POST endpoints that call the existing `lib.pubmed` / `lib.clinical_trials` upsert helpers synchronously, one ID per request; the page submits sequentially and renders results in the Phase 2 modal's operation mode. Keep the existing JSON health endpoint at `/`.

**Tech Stack:** Existing Django, PostgreSQL and Django test runner; DRF from Phase 1; browser-native HTML/CSS/JavaScript, without React, npm, django-filter, or a separate frontend service.

**Spec:** `docs/superpowers/plans/2026-09-30-web-ui.md` (phase index) and the corresponding user requests (2026-09-30). Requires Phase 1 (`2026-09-30-web-ui-phase-1-backend.md`) and Phase 2 (`2026-09-30-web-ui-phase-2-workspace.md`) complete. No separate approved design document exists; the concrete decisions below make the request executable.

## Global Constraints

- No login, authorization rules, user accounts, or role-specific behavior for this UI. The two import POSTs join claim review as the only writes. Imports can call external services and create related records; unauthenticated access to these operations requires restricting deployment network exposure.
- Keep normal CSRF protection on both import POSTs; DRF `SessionAuthentication` does **not** enforce CSRF for anonymous requests. Do not treat CSRF as authorization.
- Closing an operation modal does not cancel a running import; never log secrets, prompts, raw payloads, or exception tracebacks to browser-visible output.
- All styling stays in `django_app/core/static/core/workspace.css` (exactly one stylesheet); JS changes semantic classes/attributes for visual states. Escape all server-derived content by assigning DOM `textContent`, never raw `innerHTML`.
- Do not modify the existing `django_app/lib/pubmed.py` or `django_app/lib/clinical_trials.py` ingest functions.
- Finish each task with its focused tests and a commit of only that task's files during execution. This document is a plan only; do not commit or modify application code while creating it.

---

## Repository Map And API Contract

Target file responsibilities:

| File | Responsibility |
| --- | --- |
| `django_app/core/api.py` | Two import POST views; no changes to list/detail/review behavior. |
| `django_app/core/urls.py` | Mount import routes ahead of the router. |
| `django_app/core/templates/core/workspace.html` | Tab-specific import forms and shared operation modal region. |
| `django_app/core/static/core/workspace.js` | Import parsing, sequential POSTs, modal progress rendering. |
| `django_app/core/static/core/workspace.css` | Import form and operation-modal styling only. |
| `django_app/core/operation_logs.py` | Capture only this operation's payload-safe `lib.*` log messages for imports. |
| `tests/django_app/core/test_api.py`, `tests/django_app/core/test_workspace.py` | Import contract and form tests. |
| `tests/browser/test_workspace.py` | Intercepted import-flow browser assertions. |

Import contract: a compact form **below the table and pagination within the upper pane** appears only on Trials or Publications. Publications offers a labeled comma-separated PMID textarea and Load publications button. Trials offers a labeled comma-separated NCT-ID textarea, an unchecked-by-default "Load related publications" checkbox, and Load trials button. The page parses comma-delimited input, trims/deduplicates IDs in order, uppercases NCT IDs, rejects invalid/empty input, and limits each submission to 10 distinct IDs. On valid submission, open the shared `<dialog>` immediately in **operation mode**, show the input IDs and a "Starting" entry, then send one same-origin POST per ID sequentially; a failed remote fetch must not stop the remaining IDs. Append timestamped per-ID progress, safe server logs, results, warnings, and errors as responses arrive, with `aria-live="polite"` and an explicit completed/partial/failed summary. Actual server log entries become visible after each ID's HTTP response; do not promise live streaming inside a synchronous fetch. While an import batch runs, disable both import forms and show a compact View progress control in the workspace header so it stays reachable after switching tabs. Closing the modal does not cancel remaining requests; reopening it restores the same in-memory progress. Each saved record has a clickable detail link, and imports refresh the relevant tab's table if still active without losing lower-pane selection. Leave unsuccessful IDs in the textarea for retry and never launch imports automatically on tab switch.

`POST /api/import/publications/` accepts `{"pmid": "41115454"}`; `POST /api/import/trials/` accepts `{"nct_id": "NCT03026140", "load_related_publications": false}`. The server validates a single ASCII-digit PMID (up to the model's 64-character limit) or `NCT` followed by exactly eight ASCII digits (normalize lowercase NCT to uppercase), and requires a real boolean checkbox value; malformed payloads return 400 **before any external call**. These endpoints use `AllowAny`, no authentication, explicit `csrf_protect`, and no GET/PUT/DELETE. A successful publication import calls `lib.pubmed.fetch_and_upsert_publication(pmid)` and returns HTTP 200 `{"id": "41115454", "record_id": 7, "status": "ok", "logs": [{"level": "INFO", "message": "Upserted publication", "time": "2026-09-30T22:00:00Z"}]}`. A successful trial import calls `lib.clinical_trials.fetch_and_upsert_trial(nct_id)` first, then **only if the checkbox is checked** calls `lib.clinical_trials.fetch_trial_publications(nct_id)` and returns HTTP 200 with `id`, `record_id`, `status: "ok"`, `related_publications: 2`, and `logs`; use `null` for `related_publications` when unchecked. The upsert itself may link publications already in the database; unchecked means it does not fetch additional referenced articles. If the source fetch fails, return 502 with a generic per-ID error and captured warnings/logs; if related-publication loading fails after the trial was saved, return 502 with `status: "partial"`, `record_id`, `logs`, and a retryable generic error. Never show raw upstream exceptions or claim a successful import was rolled back. Imports remain one synchronous HTTP request per ID: keep the 10-ID form limit. `fetch_trial_publications()` is the long-running case; timeouts are ignored for now with a TODO in `django_app/lib/clinical_trials.py`. A browser timeout/network error is shown as failed with retry and must not be treated as proof the server finished; the server may still be working, may have been killed, or may have partially saved. Do not add background import processing in this plan.

## Task 7: Import More Trials And Publications

**Files:**
- Create: `django_app/core/operation_logs.py`
- Modify: `django_app/core/api.py`, `django_app/core/urls.py`, `django_app/core/templates/core/workspace.html`, `django_app/core/static/core/workspace.js`, `django_app/core/static/core/workspace.css`, `tests/django_app/core/test_api.py`, `tests/django_app/core/test_workspace.py`, `tests/browser/test_workspace.py`
- Test: `tests/django_app/core/test_api.py`, `tests/django_app/core/test_workspace.py`, `tests/browser/test_workspace.py`

**Interfaces:**
- Consumes: Phase 2 upper pane, CSRF token and existing detail `<dialog>`; existing `lib.pubmed` / `lib.clinical_trials` helpers.
- Produces: `POST /api/import/publications/`, `POST /api/import/trials/` with per-ID `{id, record_id, status, related_publications, logs}` responses and tab-specific import forms.

- [ ] **Step 1: Write the failing API tests**

```python
def test_import_publication_requires_csrf(self):
    response = self.client.post(
        '/api/import/publications/',
        data='{"pmid": "41115454"}',
        content_type='application/json',
    )
    self.assertEqual(response.status_code, 403)
```

Use `Client(enforce_csrf_checks=True)`: missing CSRF is 403; GET/PUT/DELETE are 405; malformed/empty/overlong PMID, malformed NCT ID, and a non-boolean `load_related_publications` are 400 without calling an ingest helper. Patch `lib.pubmed.fetch_and_upsert_publication` and `lib.clinical_trials.fetch_and_upsert_trial` to return saved fixture models and emit a `lib.*` INFO/WARNING record: assert one import call per valid ID, the returned `record_id`, and safe `logs` (including the warning, but not an unrelated request's record or a traceback). Patch `lib.clinical_trials.fetch_trial_publications` to return two links: assert it is called once **after** a successful checked trial import and not called when unchecked or when trial import fails. Test source failures return 502 with logs, and failure in related-publication loading returns 502 with the saved trial ID and `status: "partial"`. No test makes a live PubMed/ClinicalTrials.gov request.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./bin/manage test tests.django_app.core.test_api`
Expected: FAIL with 404 for both missing routes.

- [ ] **Step 3: Write minimal implementation**

Add two DRF POST-only views at `/api/import/publications/` and `/api/import/trials/` in `core/api.py`/`core/urls.py` ahead of the router. Validate ID syntax and boolean input in DRF serializers; use `@method_decorator(csrf_protect, name='dispatch')`, `permission_classes = [AllowAny]`, and `authentication_classes = []`. Import and call the named library helpers **inside the POST handler**, one identifier per request, with default `link_entities=True`. Implement `capture_lib_logs(emit)` as a scoped `logging.Handler` on `lib` with a `ContextVar` so concurrent requests cannot leak each other's messages; capture only INFO/WARNING/ERROR, truncate each message to 1000 characters, strip the ` frames=...` suffix emitted by `lib.logs.logged` on failure, and never serialize traceback/raw payload/credentials. Include timestamped `logs` even on 502. Do not add another fetching mechanism or run claim/NER extraction.

- [ ] **Step 4: Add the forms and modal wiring**

Re-run focused API tests; expect PASS. Add a failing workspace template test for labeled forms shown only under Trials and Publications, each with a comma-delimited textarea, the trial-only unchecked "Load related publications" checkbox, and an operation view within the shared modal with `aria-live="polite"`. Run `./bin/manage test tests.django_app.core.test_workspace`; expect FAIL until template/UI updates.

Add the forms directly below the appropriate tab's table and pagination in the upper pane. In `workspace.js`, split the textarea on commas, trim, normalize/deduplicate while preserving order, reject any invalid ID or more than 10 IDs before the first POST, then open the existing `<dialog>` in operation mode **before** submitting sequential requests with `X-CSRFToken`. Append timestamped starting/progress/server log/result/warning/error rows with `textContent`, levels as text as well as color, and a final count/summary. Disable both import forms during a batch, provide a View progress control in the persistent header to reopen the same dialog if closed or tabs change, keep the JS import running after close or tab switch, retain failed IDs for retry, and refresh the importing tab's table if still active after completion. Link saved IDs to the existing record detail mode; unchecked sends `false`. Style the modal and forms only in `workspace.css`, without another CSS file or inline styles.

- [ ] **Step 5: Run all tests and commit**

Extend `tests/browser/test_workspace.py` using Playwright request interception for both `/api/import/` routes: assert comma input opens the operation modal immediately, one POST per distinct normalized ID, checkbox defaults unchecked and sends false, checked sends true, safe logs/warnings/errors and final results are visible, a mocked failed ID does not prevent a later ID, modal close/reopen preserves progress, errors remain retryable, and saved records are reachable in the refreshed list. Keep the 390px viewport free of page-wide horizontal overflow. Re-run `./bin/manage test tests.django_app.core.test_api tests.django_app.core.test_workspace`, `python -m unittest tests.browser.test_workspace -v`, and `./bin/test`; expect PASS. Commit only this task's API, page, stylesheet, and tests:

```bash
git add django_app/core/api.py django_app/core/urls.py django_app/core/operation_logs.py django_app/core/templates/core/workspace.html django_app/core/static/core/workspace.js django_app/core/static/core/workspace.css tests/django_app/core/test_api.py tests/django_app/core/test_workspace.py tests/browser/test_workspace.py
git commit -m "feat: add trial and publication imports"
```

## Completion Criteria

- Trials and Publications each offer a comma-delimited import form below the upper table; submitting opens a log/results modal, and the trial-only checkbox optionally fetches related publications, with per-ID feedback, CSRF, and no live network calls in tests.
- `fetch_trial_publications()` timeout behavior matches the contract: browser timeouts show as failed with retry and are never treated as proof of server completion.
- `./bin/test` passes with no regressions.

Do not start implementation as part of the planning request.
