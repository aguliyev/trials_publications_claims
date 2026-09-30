# Web UI Phase 1 — Backend API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist claim notes and expose the read-only DRF list/detail API the workspace will consume.

**Architecture:** Keep the existing Django application and PostgreSQL database. Add `Claim.notes` via migration, register DRF, and serve paginated, searchable, sortable list endpoints plus full detail endpoints with source-text resolution and related-record filters. No UI in this phase; no writes except the notes migration.

**Tech Stack:** Existing Django, PostgreSQL and Django test runner; add `djangorestframework` to `etc/requirements.txt`.

**Spec:** `docs/superpowers/plans/2026-09-30-web-ui.md` (phase index) and the corresponding user requests (2026-09-30). No separate approved design document exists; the concrete decisions below make the request executable.

## Global Constraints

- No login, authorization rules, user accounts, or role-specific behavior for this UI. Phase 1 adds no write endpoints; the only data change is the new `notes` column.
- Do not send `Trial.raw`, `Publication.raw`, or other large JSON fields in paginated list responses. Retrieve all persisted scalar/JSON fields only on detail or modal requests.
- Prefer existing `ClaimStatus`, model relations, `PublicationTrial`, and source section constants in `django_app/lib/text_tools.py`; do not create duplicate tables, duplicate status fields, or regenerate claims/judgements in request handlers.
- Finish each task with its focused tests and a commit of only that task's files during execution. This document is a plan only; do not commit or modify application code while creating it.

---

## Repository Map And API Contract

Existing relevant files: `django_app/core/models.py` defines all entities and `Claim.status` (`pending`, `approved`, `rejected`); `Claim.notes` does not yet exist. `Claim` has nullable trial/publication/chunk FKs and disease/intervention/NER M2Ms. `Judgement` belongs to a claim; `PublicationTrial` is the explicit trial/publication join. `django_app/core/views.py` and `django_app/core/urls.py` currently serve only JSON at `/`. `django_app/settings.py` includes `core` but not DRF. Tests run through `python django_app/manage.py test tests.django_app` in the Docker-backed `./bin/test` workflow.

Target file responsibilities:

| File | Responsibility |
| --- | --- |
| `django_app/core/models.py`, `django_app/core/migrations/0014_claim_notes.py` | Persist claim notes, preserve existing data. |
| `etc/requirements.txt`, `django_app/settings.py` | Install/register DRF. |
| `django_app/core/api.py` | Narrow serializers, list/retrieve viewsets, relationship filters, source-text resolution, supporting-record modal lookup. |
| `django_app/core/urls.py` | Route `/api/`, leaving `/` untouched. |
| `tests/django_app/core/test_api.py`, `tests/django_app/core/test_models.py` | Model/API contract tests; existing migration test updated for the new leaf migration. |

The list contract is `GET /api/<type>/?search=...&ordering=...&page=...`, where `<type>` is one of `claims`, `diseases`, `interventions`, `trials`, `publications`. Page size is 25; response is DRF's `{count, next, previous, results}`. `GET /api/<type>/<id>/` gives all persisted fields and required related previews. All Phase 1 APIs are read-only. Integer `id` is the UI/API route key; show `nct_id` and `pmid` as human-readable identifiers.

List `results` contain these exact keys (and no other fields are needed by the table):

| Type | List record keys |
| --- | --- |
| `claims` | `id`, `claim_type`, `evidence_excerpt`, `source_kind`, `source_id`, `source_label`, `section`, `status`, `created` |
| `diseases`, `interventions` | `id`, `name`, `mesh`, `created` |
| `trials` | `id`, `nct_id`, `title`, `status`, `phase`, `start_date` |
| `publications` | `id`, `pmid`, `title`, `journal`, `year`, `pub_date` |

For claims, `evidence_excerpt` is the first 160 characters of `evidence` (do not ship the full field in the list). If both Trial and Publication FKs exist or a chunk contradicts either FK/section, return `source_kind: null`, `source_id: null`, `source_label: "Ambiguous source"`. Otherwise, a single Trial/Publication FK provides `source_kind` (`trials` or `publications`), integer `source_id` and `source_label` (NCT ID or PMID); if neither FK exists but `chunk_id` does, show `chunks`, its ID and `Chunk #<id>`. With no FK or chunk, return null IDs and `"No source"`. Detail responses use the field names and relationships below; a list response never substitutes for detail.

| Tab | Search fields | Exact filters | Sortable fields (allowlist) | Upper-table columns |
| --- | --- | --- | --- | --- |
| Claims | `evidence`, `claim_type`, `section`, `trial__nct_id`, `publication__pmid` | `status`, `claim_type`, `trial`, `publication`, `disease`, `intervention` | `id`, `created`, `status`, `claim_type`, `section` | ID, type, evidence excerpt, source, section, status, created |
| Diseases | `name`, `mesh` | `mesh` | `id`, `name`, `mesh`, `created` | ID, name, MeSH, created |
| Interventions | `name`, `mesh` | `mesh` | `id`, `name`, `mesh`, `created` | ID, name, MeSH, created |
| Trials | `nct_id`, `title`, `official_title`, `acronym` | `status`, `phase`, `has_results`, `publication` | `id`, `nct_id`, `title`, `status`, `phase`, `start_date`, `created` | NCT ID, title, status, phase, start date |
| Publications | `pmid`, `title`, `doi`, `journal`, `first_author` | `year`, `journal`, `trial` | `id`, `pmid`, `title`, `journal`, `year`, `pub_date`, `created` | PMID, title, journal, year, publication date |

All string filters are exact matches, search uses DRF `SearchFilter` (`search`), and sort uses DRF `OrderingFilter` (`ordering`). Reject malformed numeric/bool filters with HTTP 400 rather than treating them as empty results or producing server errors. Apply filter backends and exact filters **only** for the `list` action: DRF also applies filter backends to retrieve by default, which would make an existing record return 404 under stale table filters. Detail requests use a clean URL without list parameters, and the API must still return the record if someone appends `?search=unlikely&status=other` to a detail URL. Use `distinct()` on M2M/through filters; default ordering is newest first with `id` as a tie-breaker. Related claim tables reuse `GET /api/claims/?disease=<id>`, `?intervention=<id>`, `?trial=<id>`, or `?publication=<id>` with their own pagination state. Related trial/publication lists reuse `GET /api/trials/?publication=<id>` and `GET /api/publications/?trial=<id>`; do not infer linkage from JSON `references` or `raw`.

Detail contract: claim data includes full model fields, `judgements` (`id`, `method`, `score`, `meta`, timestamps), linked diseases/interventions (`id`, `name`, `mesh`), NER preview rows (`id`, `text`, `label`, `score`, `section`, `start`, `end`, `disease_id`, `intervention_id`), and `section_text`. `section_text` is `{kind, id, section, text}` from `chunk.body` if `chunk_id` exists **and its owner and section do not contradict the claim**. When there is no chunk, use `Claim.section` against the single owning Trial/Publication's allowed source text fields, including non-chunked titles. If both Trial and Publication FKs are set, or a chunk's owner/section conflicts with the claim, return `null` and display "Source unavailable or ambiguous"; do not fall back to a different source. Also return `null` for no owner/allowed field; never guess or look up an arbitrary model attribute supplied by the claim. Trial/publication, disease, and intervention details include all persisted fields, while their large related claim lists are fetched separately. For a displayed linked `Chunk`, `Ner`, `Judgement`, `Biomarker`, `Observation`, or `PublicationTrial`, use `GET /api/records/<kind>/<id>/` with a fixed model allowlist and a full read-only serializer. Unknown kinds/IDs return 404.

## Task 1: Claim Notes Persistence

**Files:**
- Create: `django_app/core/migrations/0014_claim_notes.py`
- Modify: `django_app/core/models.py`, `tests/django_app/core/test_models.py`, `tests/django_app/core/test_claim_evidence_migration.py`
- Test: `tests/django_app/core/test_models.py`

**Interfaces:**
- Consumes: existing `Claim` model and `0013_claim_status` migration.
- Produces: `Claim.notes: str` (blank by default) for Phase 2 review editing.

- [ ] **Step 1: Write the failing test**

```python
def test_claim_notes_default_and_edit(self):
    claim = Claim.objects.create(section='title', claim_type='review')
    self.assertEqual(claim.notes, '')
    claim.notes = 'Reviewed source text.'
    claim.save(update_fields=['notes'])
    self.assertEqual(Claim.objects.get(pk=claim.pk).notes, 'Reviewed source text.')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./bin/manage test tests.django_app.core.test_models.ModelSanityTestCase.test_claim_notes_default_and_edit`
Expected: FAIL because `notes` is missing (ensure `etc/.env` exists and run `./bin/start` first; `./bin/makemigrations` uses `docker compose exec django-app` and requires a running container).

- [ ] **Step 3: Write minimal implementation**

Add `notes = models.TextField(blank=True, default='')` on `Claim`. Generate migration `0014_claim_notes` with `./bin/makemigrations core`, verify dependency `('core', '0013_claim_status')`; update the migration test's `migrate_to` from `0013_claim_status` to `0014_claim_notes` and assert old claims have empty notes after migrating.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./bin/manage migrate` and `./bin/manage test tests.django_app.core.test_models tests.django_app.core.test_claim_evidence_migration`
Expected: PASS with prior evidence/status intact.

- [ ] **Step 5: Commit**

```bash
git add django_app/core/models.py django_app/core/migrations/0014_claim_notes.py tests/django_app/core/test_models.py tests/django_app/core/test_claim_evidence_migration.py
git commit -m "feat: add claim notes column"
```

## Task 2: Paginated, Searchable List API

**Files:**
- Create: `django_app/core/api.py`, `tests/django_app/core/test_api.py`
- Modify: `etc/requirements.txt`, `django_app/settings.py`, `django_app/core/urls.py`
- Test: `tests/django_app/core/test_api.py`

**Interfaces:**
- Consumes: `Claim.notes` from Task 1; model relations from the contract above.
- Produces: `GET /api/<type>/` list routes with the exact per-type record keys; consumed by Phase 2 tables and related lists.

- [ ] **Step 1: Write the failing tests**

```python
def test_claim_list_contract(self):
    response = self.client.get('/api/claims/')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(set(response.json().keys()), {'count', 'next', 'previous', 'results'})
```

Cover: two records per tab, 25/page on a 26-record fixture, `search` per matrix, ascending/descending `ordering`, each exact filter (including M2M disease/intervention and through-table trial/publication), 400 on invalid `year`, `trial`, `has_results`, `evidence_excerpt == evidence[:160]`, and no `raw`, `meta`, or full claim `evidence` in lists.

- [ ] **Step 2: Run test to verify it fails**

Run: `./bin/manage test tests.django_app.core.test_api`
Expected: FAIL with 404 for missing `/api/` routes.

- [ ] **Step 3: Write minimal implementation**

Add `djangorestframework` to requirements and `rest_framework` to `INSTALLED_APPS`; rebuild and recreate the running Django service via `docker compose --env-file etc/.env up -d --build django-app` before browser checks. Define a shared paginator in `core/api.py`:

```python
from rest_framework.pagination import PageNumberPagination

class WorkspacePagination(PageNumberPagination):
    page_size = 25
```

Add five read-only list/retrieve viewsets and register them with a DRF `SimpleRouter` under `path('api/', include(router.urls))` in `core/urls.py`. Set `permission_classes = [AllowAny]`, `authentication_classes = []`, `pagination_class = WorkspacePagination`, explicit `search_fields`/`ordering_fields` per matrix, and `filter_backends = [SearchFilter, OrderingFilter]`. In `get_queryset()`, apply exact filters only for `self.action == 'list'`; override `filter_queryset()` to bypass search/ordering backends whenever `self.action != 'list'`. Use `distinct()` on joins; avoid large fields in list serializers. Scope `select_related` to list FK display and `prefetch_related` to detail requests to avoid N+1 queries.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./bin/manage test tests.django_app.core.test_api`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add etc/requirements.txt django_app/settings.py django_app/core/urls.py django_app/core/api.py tests/django_app/core/test_api.py
git commit -m "feat: add paginated workspace list API"
```

## Task 3: Full Details, Source Text, And Related Records

**Files:**
- Modify: `django_app/core/api.py`, `django_app/core/urls.py`
- Test: `tests/django_app/core/test_api.py`

**Interfaces:**
- Consumes: Task 2 list viewsets and routes.
- Produces: `GET /api/<type>/<id>/` detail payloads, `section_text` resolution, related-list filters, `GET /api/records/<kind>/<id>/` modal lookup; consumed by Phase 2 detail panes and modal.

- [ ] **Step 1: Write the failing tests**

```python
def test_chunk_backed_claim_section_text(self):
    response = self.client.get(f'/api/claims/{self.chunk_claim.pk}/')
    self.assertEqual(response.json()['section_text']['text'], self.chunk.body)
```

Cover: trial-title and publication-title claims without chunk; orphan/invalid-section, dual-owner unchunked, conflicting-owner chunk, and conflicting-section chunk claims yield `section_text: null`; linked diseases, interventions, NER rows, multiple judgements and source IDs; full trial/publication JSON field in detail but not list; detail 200 with disqualifying `?search=unlikely&status=other`; disease/intervention/trial/publication related filters; through-table distinctness; supporting-record details and 404 for unknown kinds/IDs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./bin/manage test tests.django_app.core.test_api`
Expected: FAIL on missing detail payload/route.

- [ ] **Step 3: Write minimal implementation**

Resolve section text using the existing source field tuples (import from `lib.text_tools`) rather than string interpolation or arbitrary `getattr`:

```python
if claim.chunk_id:
    if (claim.section != claim.chunk.section
            or (claim.trial_id and claim.trial_id != claim.chunk.trial_id)
            or (claim.publication_id and claim.publication_id != claim.chunk.publication_id)):
        return None
    return {'kind': 'chunks', 'id': claim.chunk_id,
            'section': claim.chunk.section, 'text': claim.chunk.body}
if bool(claim.publication_id) == bool(claim.trial_id):
    return None
owner = claim.publication if claim.publication_id else claim.trial
allowed = (PUBLICATION_FIELDS_TO_CHUNK + PUBLICATION_FIELDS_NOT_TO_CHUNK
           if claim.publication_id else TRIAL_FIELDS_TO_CHUNK + TRIAL_FIELDS_NOT_TO_CHUNK)
if owner is None or claim.section not in allowed:
    return None
return {'kind': 'publications' if claim.publication_id else 'trials',
        'id': owner.pk, 'section': claim.section, 'text': getattr(owner, claim.section)}
```

Add dedicated detail serializers (`ModelSerializer` read-only `fields='__all__'` for model fields, with explicit nested previews for claim), `get_serializer_class()` selecting list vs detail, and a retrieve-only supporting-record view with a static kind-to-model/serializer map accepting only `chunks`, `ners`, `judgements`, `biomarkers`, `observations`, `publication-trials`. Ensure invalid kinds do not reveal arbitrary models. `prefetch_related('judgements', 'ners', 'diseases', 'interventions')` and `select_related('chunk', 'trial', 'publication')` for claim details.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./bin/manage test tests.django_app.core.test_api`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add django_app/core/api.py django_app/core/urls.py tests/django_app/core/test_api.py
git commit -m "feat: add workspace detail API"
```

## Completion Criteria

- `Claim.notes` persists with `''` default; existing claims migrate with empty notes.
- Every list route returns `{count, next, previous, results}` with exactly the per-type keys, 25/page, search, allowlisted ordering, exact filters, and 400 on malformed filters.
- Detail routes return full fields, previews, `section_text` with ambiguity rules, related-list filters, supporting-record lookup, and 404 for unknown kinds/IDs.
- `/` continues to respond as before.

DRF references: [filtering](https://www.django-rest-framework.org/api-guide/filtering/), [pagination](https://www.django-rest-framework.org/api-guide/pagination/), [viewsets](https://www.django-rest-framework.org/api-guide/viewsets/). Do not start implementation as part of the planning request.
