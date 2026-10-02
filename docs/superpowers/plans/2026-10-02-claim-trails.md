# Claim Trails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist one immutable claim-review trail whenever a user PATCH actually changes claim status or notes, and let users inspect trails for a trial or publication in a paginated modal table even after source re-fetch deletes the live claims, NERs, and entity links.

**Architecture:** Add the requested `ClaimTrails` model with source foreign keys and no foreign key to `Claim`. The claim review endpoint will lock and update the claim, build a JSON-safe post-update snapshot of the claim and all linked NERs, diseases, and interventions, and insert the trail in the same database transaction. A read-only, source-filtered DRF endpoint will feed a modal table opened from the trial/publication detail pane.

**Tech Stack:** Existing Django models/migrations, Django REST Framework, PostgreSQL JSONField, browser-native JavaScript and the existing workspace dialog/CSS.

**Spec:** User request dated 2026-10-02. No separate design document is required for this scoped extension.

## Global Constraints And Decisions

- Use the requested model class name `ClaimTrails`; expose it at `/api/claim-trails/` and label the UI link `claim trails`.
- `ClaimTrails` inherits `BaseModel`, has nullable `trial` and `publication` foreign keys, `notes`, `status_from`, and `new_status`. At least one source FK is required, but both may be populated. Both status fields use `ClaimStatus.choices` and `max_length=8`.
- Do not add a foreign key from `ClaimTrails` to `Claim`. The original claim ID and every other claim field live in `meta`, so deleting a claim during re-fetch cannot cascade into its trail.
- Copy `claim.trial_id` and `claim.publication_id` directly to the trail. Preserve both when the claim has both. A source-less claim violates the domain rule; reject its review update with 400 and roll back rather than create an unattached trail.
- A successful PATCH creates exactly one trail only when persisted `status` or `notes` changes. A no-op PATCH returns the normal successful response but creates no trail. Invalid payloads, missing CSRF, missing claims, and failed transactions also create none.
- `status_from` is the value locked from the database immediately before the update. `new_status` and `notes` are the persisted post-update values; a notes-only change records the unchanged status in both status columns.
- Store this stable envelope in `ClaimTrails.meta`: `claim` contains every concrete Claim field plus the three relation-ID lists; `ners`, `diseases`, and `interventions` contain every concrete field of each related record. Sort every related collection by primary key for deterministic snapshots.
- The snapshot represents post-update state. Sanitize dates, datetimes, and nested values with the existing `sanitize_json_payload()` before inserting the JSONField.
- Create trails only in the user-facing claim PATCH flow, not in a broad model signal. Pipeline creation, grouping signals, scripts, fixtures, and internal saves must not generate review history.
- Keep trail creation and claim update in one `transaction.atomic()` block and lock the Claim row with `select_for_update()` so concurrent reviews record the correct status transition.
- Re-fetch continues deleting claims and NERs as it does now. It must not query or delete `ClaimTrails`; source deletion may still cascade its trails through the trial/publication foreign keys.
- The paginated list response excludes `meta` to avoid sending up to 25 large snapshots at once. Each row has an expandable Meta control that lazily loads the full trail detail, including `meta`, from `/api/claim-trails/<id>/` and renders it in the modal.
- Reuse the existing `<dialog id="ws-modal">`, `relatedTable()`, pagination styles, and `textContent` rendering. Do not add a second dialog, inline CSS, or raw `innerHTML`.

## Repository Map

| File | Responsibility |
| --- | --- |
| `django_app/core/models.py` | Define `ClaimTrails` and its source/status fields. |
| `django_app/core/migrations/0019_claimtrails.py` | Create the trail table and foreign-key indexes. |
| `django_app/core/admin.py` | Make trails inspectable, searchable, and filterable in Django admin. |
| `django_app/core/claim_trails.py` | Build deterministic JSON-safe snapshots, resolve source ownership, and create a trail. |
| `django_app/core/api.py` | Atomically record a trail during claim PATCH and expose the read-only list serializer/viewset. |
| `django_app/core/urls.py` | Register `/api/claim-trails/`. |
| `django_app/core/static/core/workspace.js` | Add source-detail links and the paginated claim-trails modal table. |
| `django_app/core/static/core/workspace.css` | Style the link and modal pager using the existing visual system. |
| `tests/django_app/core/test_models.py` | Cover model defaults, relations, and allowed review statuses. |
| `tests/django_app/core/test_api.py` | Cover trail creation, complete snapshots, atomic behavior, filtering, and pagination. |
| `tests/django_app/lib/test_refetch.py` | Prove trail rows and snapshots survive derived-data cleanup. |
| `tests/django_app/core/test_workspace.py` | Lock down the link/modal JavaScript contract in the rendered workspace assets. |

---

### Task 1: Add The Persistent ClaimTrails Model

**Files:**
- Modify: `django_app/core/models.py`
- Create: `django_app/core/migrations/0019_claimtrails.py`
- Modify: `django_app/core/admin.py`
- Test: `tests/django_app/core/test_models.py`

**Interfaces:**
- Produces: `ClaimTrails(trial, publication, notes, status_from, new_status, meta)` and reverse relations `Trial.claim_trails` / `Publication.claim_trails`.
- Consumes: existing `BaseModel`, `Trial`, `Publication`, and `ClaimStatus`.

- [ ] **Step 1: Write the failing model test**

Import `ClaimTrails`, create trial-owned and publication-owned rows, and assert inherited timestamps/metadata, blank-note default, status validation, reverse relations, and source deletion behavior:

```python
def test_claim_trails_fields_and_source_relations(self):
    trial = Trial.objects.create(nct_id='NCT08880001', title='Audit trial')
    publication = Publication.objects.create(pmid='8880001', title='Audit publication')
    trial_trail = ClaimTrails.objects.create(
        trial=trial, status_from=ClaimStatus.PENDING,
        new_status=ClaimStatus.APPROVED, meta={'claim': {'id': 17}},
    )
    publication_trail = ClaimTrails.objects.create(
        publication=publication, notes='Rejected after review',
        status_from=ClaimStatus.PENDING, new_status=ClaimStatus.REJECTED,
    )
    self.assertEqual(trial_trail.notes, '')
    self.assertEqual(trial.claim_trails.get(), trial_trail)
    self.assertEqual(publication.claim_trails.get(), publication_trail)
    self.assertIsNotNone(trial_trail.created)
    trial_trail.new_status = 'unknown'
    with self.assertRaises(ValidationError):
        trial_trail.full_clean()
    trial.delete()
    self.assertFalse(ClaimTrails.objects.filter(pk=trial_trail.pk).exists())
```

- [ ] **Step 2: Run the focused test and verify the missing-model failure**

Run: `./bin/manage test tests.django_app.core.test_models`

Expected: FAIL because `ClaimTrails` is not importable.

- [ ] **Step 3: Define the model and migration**

Add after `Claim`:

```python
class ClaimTrails(BaseModel):
    trial = models.ForeignKey(
        Trial, on_delete=models.CASCADE, related_name='claim_trails',
        null=True, blank=True,
    )
    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name='claim_trails',
        null=True, blank=True,
    )
    notes = models.TextField(blank=True, default='')
    status_from = models.CharField(max_length=8, choices=ClaimStatus.choices)
    new_status = models.CharField(max_length=8, choices=ClaimStatus.choices)

    class Meta:
        ordering = ['-created', '-id']
        verbose_name = 'Claim Trail'
        verbose_name_plural = 'Claim Trails'
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(trial__isnull=False)
                           | models.Q(publication__isnull=False)),
                name='claim_trails_has_source',
            ),
        ]
```

Generate `0019_claimtrails.py` with `./bin/manage makemigrations core`, inspect it, and confirm it creates only this table plus the `claim_trails_has_source` constraint. The constraint requires at least one source but deliberately permits both.

- [ ] **Step 4: Register admin inspection**

Register `ClaimTrails` with list columns `id`, `trial`, `publication`, `status_from`, `new_status`, `created`; filters for both statuses and created date; and searches through `trial__nct_id`, `publication__pmid`, and `notes`. Make every field read-only and disable admin add/delete so the admin is an inspection surface rather than an audit-history editor.

- [ ] **Step 5: Run checks and commit**

Run: `./bin/manage test tests.django_app.core.test_models && ./bin/manage makemigrations --check && ./bin/manage check`

Expected: all commands PASS and `makemigrations --check` reports no changes.

Commit: `feat: add persistent claim trails model`

---

### Task 2: Snapshot The Reviewed Claim Atomically

**Files:**
- Create: `django_app/core/claim_trails.py`
- Modify: `django_app/core/api.py`
- Test: `tests/django_app/core/test_api.py`

**Interfaces:**
- Produces: `snapshot_claim(claim) -> dict` and `create_claim_trail(claim, status_from) -> ClaimTrails`.
- Consumes: a saved `Claim` with prefetched or queryable `ners`, `diseases`, and `interventions`.

- [ ] **Step 1: Write failing claim-review audit tests**

Give the existing `ClaimReviewPatchTestCase` claims a valid trial or publication source, then add a trial-owned claim linked to one NER, disease, and intervention. Assert that a valid PATCH creates one trail with the old/new statuses, saved notes, source FK, and exact envelope keys. Assert snapshots contain all concrete field names from each model and relation IDs in deterministic order:

```python
trail = ClaimTrails.objects.get()
self.assertEqual((trail.status_from, trail.new_status), ('pending', 'approved'))
self.assertEqual(trail.notes, 'looks good')
self.assertEqual(trail.trial_id, trial.pk)
self.assertIsNone(trail.publication_id)
self.assertEqual(set(trail.meta), {'claim', 'ners', 'diseases', 'interventions'})
self.assertEqual(trail.meta['claim']['id'], claim.pk)
self.assertEqual(trail.meta['claim']['ners'], [ner.pk])
self.assertEqual(trail.meta['claim']['diseases'], [disease.pk])
self.assertEqual(trail.meta['claim']['interventions'], [intervention.pk])
self.assertEqual(trail.meta['ners'][0]['id'], ner.pk)
```

Also add cases proving:

- a notes-only PATCH records the unchanged status in both status columns;
- two PATCH requests that make different persisted changes create two ordered immutable rows;
- a no-op PATCH with the current status and notes returns 200 and creates no trail;
- a publication claim uses `publication_id`;
- a claim with both trial and publication produces one trail with both FKs;
- a source-less claim update returns 400, creates no trail, and leaves the claim unchanged;
- invalid status, rejected read-only fields, missing CSRF, and missing claim create no trails;
- if trail insertion raises `DatabaseError`, the PATCH fails and the claim status/notes roll back.

- [ ] **Step 2: Run the focused tests and verify audit assertions fail**

Run: `./bin/manage test tests.django_app.core.test_api.ClaimReviewPatchTestCase`

Expected: existing PATCH assertions pass, while new assertions fail with zero trails or missing snapshot helpers.

- [ ] **Step 3: Implement deterministic field snapshots**

In `core/claim_trails.py`, serialize concrete fields by model metadata and sanitize every value:

```python
def _concrete_fields(instance):
    return {
        field.name: sanitize_json_payload(field.value_from_object(instance))
        for field in instance._meta.concrete_fields
    }


def snapshot_claim(claim):
    ners = list(claim.ners.all().order_by('pk'))
    diseases = list(claim.diseases.all().order_by('pk'))
    interventions = list(claim.interventions.all().order_by('pk'))
    claim_data = _concrete_fields(claim)
    claim_data.update({
        'ners': [row.pk for row in ners],
        'diseases': [row.pk for row in diseases],
        'interventions': [row.pk for row in interventions],
    })
    return {
        'claim': claim_data,
        'ners': [_concrete_fields(row) for row in ners],
        'diseases': [_concrete_fields(row) for row in diseases],
        'interventions': [_concrete_fields(row) for row in interventions],
    }
```

Copy both source IDs directly from the Claim. Before inserting, raise DRF `ValidationError` when both IDs are absent; because the helper runs inside the PATCH transaction, this returns 400 and rolls back the claim update. `create_claim_trail()` inserts the post-update notes/status/snapshot and never stores a live Claim relation.

- [ ] **Step 4: Wrap PATCH save and trail insert in one locked transaction**

Override `ClaimViewSet.perform_update()` with `@transaction.atomic`: re-read `serializer.instance.pk` using `select_for_update()`, save the locked pre-update `status` and `notes`, assign the locked object back to `serializer.instance`, and save it. Compare the persisted post-update values with the locked pre-update values; call `create_claim_trail(updated_claim, status_from=locked_status)` only when either field differs. Do not use a signal and do not catch trail insert errors; an insert failure must roll back the claim update and return an error rather than claim success without history.

- [ ] **Step 5: Run audit and existing API tests, then commit**

Run: `./bin/manage test tests.django_app.core.test_api.ClaimReviewPatchTestCase tests.django_app.core.test_signals`

Expected: PASS, including one trail per actual persisted change and no trail for no-op or rejected writes.

Commit: `feat: snapshot claim reviews into trails`

---

### Task 3: Expose Source-Filtered Claim Trails APIs

**Files:**
- Modify: `django_app/core/api.py`
- Modify: `django_app/core/urls.py`
- Test: `tests/django_app/core/test_api.py`

**Interfaces:**
- Produces: `GET /api/claim-trails/?trial=<pk>&page=<n>` and `GET /api/claim-trails/?publication=<pk>&page=<n>` using the existing 25-row page envelope, plus `GET /api/claim-trails/<id>/` for one full snapshot.
- List response row: `id`, `created`, `status_from`, `new_status`, `notes`.
- Detail response: list fields plus `modified`, `trial`, `publication`, and `meta`.

- [ ] **Step 1: Write failing endpoint tests**

Create more than 25 trial trails, a publication-only trail, and a trail with both FKs. Assert filtering isolates the correct source, the dual-source row appears in each source's separate result set, newest trails appear first, pagination uses `{count,next,previous,results}`, row keys exclude `meta`, malformed integer filters return 400, and requests with neither or both source filters return 400. Retrieve one row by ID and assert the detail response contains the complete stored `meta` envelope and both source IDs where applicable.

```python
response = self.client.get(f'/api/claim-trails/?trial={trial.pk}')
self.assertEqual(response.status_code, 200)
self.assertEqual(response.json()['count'], 26)
self.assertEqual(set(response.json()['results'][0]), {
    'id', 'created', 'status_from', 'new_status', 'notes',
})
self.assertNotIn('meta', response.json()['results'][0])
detail = self.client.get(f'/api/claim-trails/{dual_source_trail.pk}/')
self.assertEqual(detail.status_code, 200)
self.assertEqual(detail.json()['meta'], dual_source_trail.meta)
self.assertEqual(detail.json()['trial'], trial.pk)
self.assertEqual(detail.json()['publication'], publication.pk)
```

- [ ] **Step 2: Run the tests and verify the route is missing**

Run: `./bin/manage test tests.django_app.core.test_api.ClaimTrailsApiTestCase`

Expected: FAIL with a 404 for `/api/claim-trails/`.

- [ ] **Step 3: Add the read-only list/detail viewset**

Add `ClaimTrailsListSerializer` with the five compact list fields and `ClaimTrailsDetailSerializer` with the list fields plus `modified`, `trial`, `publication`, and `meta`. Use a `ReadOnlyModelViewSet` with `AllowAny`, no authentication classes, `WorkspacePagination`, and queryset ordering `-created, -id`. For the `list` action, require exactly one of `trial` or `publication`, parse it through `_parse_int_param()`, and filter by that FK. For `retrieve`, load the row by primary key without requiring query parameters and select the detail serializer. POST, PUT, PATCH, and DELETE remain unavailable.

- [ ] **Step 4: Register and verify the route**

Register `router.register('claim-trails', ClaimTrailsViewSet, basename='claim-trail')` in `core/urls.py`.

Run: `./bin/manage test tests.django_app.core.test_api.ClaimTrailsApiTestCase`

Expected: PASS for filtering, order, pagination, validation, compact list response size, and full detail snapshots.

- [ ] **Step 5: Commit the API slice**

Commit: `feat: expose source claim trails api`

---

### Task 4: Show Claim Trails In The Existing Workspace Modal

**Files:**
- Modify: `django_app/core/static/core/workspace.js`
- Modify: `django_app/core/static/core/workspace.css`
- Test: `tests/django_app/core/test_workspace.py`

**Interfaces:**
- Consumes: Task 3 list endpoint and the existing `ws-modal` dialog.
- Produces: a `claim trails` link immediately below the related Claims table in trial and publication detail panes.

- [ ] **Step 1: Add failing static-contract tests**

Read `workspace.js` through Django's staticfiles finder and assert it contains the claim-trails list/detail endpoints, the exact `claim trails` label, calls from both `renderTrialDetail()` and `renderPublicationDetail()`, the five audit columns plus an expandable Meta column, full-snapshot JSON rendering, and previous/next modal pagination. Keep the shell assertion that exactly one dialog and one stylesheet exist.

- [ ] **Step 2: Run the workspace tests and verify the missing-link failure**

Run: `./bin/manage test tests.django_app.core.test_workspace`

Expected: FAIL because no claim-trails endpoint or link exists in `workspace.js`.

- [ ] **Step 3: Implement the source-detail link**

Add `claimTrailsLink(sourceKind, sourceId, sourceLabel)` returning a real `<button type="button">` styled as a text link. Append it immediately after `pagedRelatedTable(... 'Claims' ...)` in both source renderers:

```javascript
pagedRelatedTable(right, 'Claims', '/api/claims/?trial=' + data.id, 'No linked claims.');
right.appendChild(claimTrailsLink('trial', data.id, data.nct_id));
```

Use `publication` in the publication renderer. The click handler records `modalOpener`, sets an accessible title such as `Claim trails — NCT03026140`, switches the existing dialog to record mode, and loads page 1.

- [ ] **Step 4: Render the paginated modal table**

Fetch `/api/claim-trails/?<sourceKind>=<id>&page=<page>`. Render a claim-trails table with columns ID, Created, Status from, New status, Notes, and Meta; format Created with `formatDateTime`, display both statuses as badges, and keep notes as text. The Meta cell contains an accessible Expand button. On first expansion, fetch `/api/claim-trails/<id>/`, verify the response still belongs to that row, and render the complete `meta` object with `JSON.stringify(meta, null, 2)` inside `<pre class="ws-json">` beneath the row. Cache the loaded snapshot in that modal instance so collapse/re-expand does not refetch it.

Add modal-local Previous/Next buttons and a count label; page changes reload only the dialog, never the upper table or related Claims table. Reset expanded snapshots when the modal changes page or is repurposed. While loading, disable only that row's Meta button and show `Loading snapshot…`; on detail failure, retain the row and show `Could not load snapshot. Retry.` without closing the modal.

On loading, show `Loading claim trails…`; on zero results, show `No claim trails.`; on an API/network error, show `Could not load claim trails. Close and retry.` Restore focus through the dialog's existing close handler. Ignore a late response if the dialog was repurposed for another record/operation by tracking a request sequence or modal mode token.

- [ ] **Step 5: Add restrained link styling**

Add one `.ws-text-link` rule group to `workspace.css` using the existing primary color, underline/hover treatment, visible `:focus-visible`, transparent background, and disabled state. Reuse `.ws-related-pager` and table styles; do not add inline style assignments.

- [ ] **Step 6: Run workspace tests and commit**

Run: `./bin/manage test tests.django_app.core.test_workspace && ./bin/manage check`

Expected: PASS; rendered shell still has one dialog and one stylesheet.

Commit: `feat: add claim trails modal to source details`

---

### Task 5: Prove Re-fetch Survival And Run The Full Regression Suite

**Files:**
- Modify: `tests/django_app/lib/test_refetch.py`
- Test: `tests/django_app/lib/test_refetch.py`, all Django tests

**Interfaces:**
- Consumes: Tasks 1–2 persisted trails and existing `refetch_source()` cleanup.
- Produces: a regression guarantee that deleting the live claim graph cannot delete or mutate its audit snapshot.

- [ ] **Step 1: Write the re-fetch survival regression**

For both trial and publication subtests, create a claim with linked NER/disease/intervention, create its trail through `create_claim_trail()`, deep-copy `trail.meta`, run the existing mocked `refetch_source()`, and assert:

```python
self.assertFalse(Claim.objects.filter(pk=claim.pk).exists())
self.assertFalse(Ner.objects.filter(pk=ner.pk).exists())
trail.refresh_from_db()
self.assertEqual(trail.meta, snapshot_before_refetch)
self.assertEqual(trail.trial_id or trail.publication_id, source.pk)
```

Also retain existing assertions that Disease and Intervention rows survive while their source connections are cleared.

- [ ] **Step 2: Run the re-fetch tests**

Run: `./bin/manage test tests.django_app.lib.test_refetch`

Expected: PASS without changing `lib/refetch.py`; the absence of a Claim FK is what preserves the trail.

- [ ] **Step 3: Run migration and full application verification**

Run:

```bash
./bin/manage makemigrations --check
./bin/manage check
./bin/manage test tests.django_app.core.test_models tests.django_app.core.test_api tests.django_app.core.test_workspace tests.django_app.lib.test_refetch
./bin/test
```

Expected: no pending migrations, Django system checks pass, focused suites pass, then the complete disposable-container suite passes.

- [ ] **Step 4: Perform the manual acceptance check**

Open a trial claim, make and save two distinct status/notes changes, then click Save once more without changing either field. Open that trial's lower detail pane and click `claim trails`. Confirm exactly two newest-first rows with correct transitions/notes, pagination controls, Escape/Close behavior, and focus restoration. Re-fetch the trial, reopen `claim trails`, and confirm the same two rows remain although the related Claims table is empty. Repeat once with a publication claim and verify narrow-screen horizontal table scrolling.

- [ ] **Step 5: Commit the regression coverage**

Commit: `test: preserve claim trails across source refetch`

## Completion Criteria

- Every user claim PATCH that changes persisted status or notes creates exactly one immutable `ClaimTrails` row in the same transaction as the claim update; no-op PATCHes create none.
- Each row records old status, new status, final notes, at least one trial/publication FK (including both when present), and a deterministic complete post-update snapshot of the claim, NERs, diseases, and interventions.
- Failed or rejected PATCH requests create no trail, and a trail-write failure rolls back the claim update.
- Trial/publication re-fetch deletes the live derived records but leaves all existing claim trails and their JSON snapshots unchanged.
- `/api/claim-trails/` is read-only, source-filtered, paginated, newest-first, and omits large `meta` payloads from list rows; `/api/claim-trails/<id>/` returns the full stored snapshot.
- Trial and publication details show `claim trails` directly below Claims; the existing accessible modal displays and paginates the requested audit table, and each row can expand its complete Meta snapshot with clear loading, empty, and error states.
- Migration checks, Django checks, focused tests, and `./bin/test` all pass.

Do not start implementation as part of this planning request.
