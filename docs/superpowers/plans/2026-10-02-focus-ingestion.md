# Focus Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add editable Focus records, create them from Claim and ClaimGroup entity terms, and consume their pending trial/publication counts by importing only records that are not already in the database.

**Architecture:** `Focus` is a normal `BaseModel` exposed through the existing DRF list/detail workspace pattern. A focused domain module owns deterministic disease/intervention query construction and idempotent Focus creation; source-specific libraries expose paginated identifier iterators; and `jobs/ingest_focus.py` coordinates durable, one-at-a-time pending-count decrements after successful imports. The browser uses server-provided Focus state so duplicate detection and query construction remain authoritative on the server.

**Tech Stack:** Django ORM and migrations, Django REST Framework, PostgreSQL, vanilla JavaScript/CSS, `httpx`, existing ClinicalTrials.gov/PubMed ingestion libraries, Django `TestCase`/`SimpleTestCase`, Docker Compose shell launchers.

**Spec:** User-approved requirements from the 2026-10-02 conversation; this plan is self-contained and is the repository implementation reference.

## Global Constraints

- Name the persisted fields `ingest_trials_count` and `ingest_publications_count`; “ingest” is the canonical spelling in Python and API payloads.
- Treat both ingest counts as one-time pending work. Decrement a count only after one previously absent record has been saved successfully.
- Importing a trial must call only the trial importer; it must not fetch the trial's referenced publications.
- Existing Trial and Publication rows never satisfy or decrement a pending count. Skip them and continue through search results for unseen identifiers.
- A failed import does not decrement a count. Continue with later search results; leave any unfilled remainder pending.
- If a search is exhausted before its quota is met, leave the remainder pending and log the shortfall.
- Focus creation from a Claim or ClaimGroup starts with both counts at zero.
- Build generated queries deterministically: nonblank disease names in case-insensitive alphabetical order, followed by nonblank intervention names in case-insensitive alphabetical order, with names trimmed and joined by one space.
- A generated query with no disease or intervention names cannot create a Focus.
- `query` is unique. API updates and create-from-record actions must return validation/conflict responses instead of producing duplicates.
- The Focuses UI tab is the final tab, immediately after Sources.
- Keep source-network calls mocked in tests. Do not require live ClinicalTrials.gov or PubMed access.
- Follow the existing 25-row DRF pagination, CSRF protection, table sorting, search, modal, and lower-pane conventions.

---

## File map

- `django_app/core/models.py` — define `Focus`.
- `django_app/core/migrations/0020_focus.py` — create the Focus table and constraints after the pending ClaimTrails migration.
- `django_app/lib/focuses.py` — canonical query construction, Focus lookup state, and idempotent creation from a Claim or ClaimGroup.
- `django_app/core/api.py` — Focus serializers/viewset/action plus computed Focus state on Claim and ClaimGroup details.
- `django_app/core/urls.py` — register `/api/focuses/`.
- `django_app/lib/clinical_trials.py` — yield paginated, relevance-ordered NCT identifiers for batch ingestion.
- `django_app/lib/pubmed.py` — yield paginated, relevance-ordered PMIDs for batch ingestion.
- `jobs/ingest_focus.py` — process pending Focus counts and decrement durable work only after successful new imports.
- `bin/ingest_focus` — run the job inside the running `django-app` container.
- `django_app/core/templates/core/workspace.html` — append the Focuses tab after Sources.
- `django_app/core/static/core/workspace.js` — Focus list/detail UI, editable fields, create buttons, duplicate link, and modal integration.
- `django_app/core/static/core/workspace.css` — layout and feedback styling needed by the Focus editor/action.
- `tests/django_app/core/test_models.py` — model defaults and validation.
- `tests/django_app/core/test_api.py` — Focus CRUD contracts and create-from-record behavior.
- `tests/django_app/lib/test_focuses.py` — deterministic query and duplicate-handling domain tests.
- `tests/django_app/lib/test_clinical_trials.py` — ClinicalTrials.gov pagination tests.
- `tests/django_app/lib/test_pubmed.py` — PubMed pagination tests.
- `tests/bin/test_ingest_focus.py` — ingestion orchestration and launcher tests.
- `tests/django_app/core/test_workspace.py` — final-tab placement and workspace UI contracts.
- `README.md` — document the pending-count workflow and launcher.

---

### Task 1: Persist Focus records

**Files:**
- Modify: `django_app/core/models.py` after `BaseModel`
- Create: `django_app/core/migrations/0020_focus.py`
- Modify: `tests/django_app/core/test_models.py`

**Interfaces:**
- Consumes: existing `BaseModel(created, modified, meta)`.
- Produces: `core.models.Focus` with `query: str`, `ingest_trials_count: int`, `ingest_publications_count: int`, and `notes: str`.

- [ ] **Step 1: Write failing Focus model tests**

Add `Focus` to the import list and add these tests to `ModelSanityTestCase`:

```python
def test_focus_defaults_and_audit_fields(self):
    focus = Focus.objects.create(query='Colon cancer Nivolumab')

    self.assertEqual(focus.ingest_trials_count, 0)
    self.assertEqual(focus.ingest_publications_count, 0)
    self.assertEqual(focus.notes, '')
    self.assertEqual(focus.meta, {})
    self.assertIsNotNone(focus.created)
    self.assertIsNotNone(focus.modified)
    self.assertEqual(str(focus), 'Colon cancer Nivolumab')

def test_focus_counts_must_be_non_negative(self):
    focus = Focus(
        query='Colon cancer',
        ingest_trials_count=-1,
        ingest_publications_count=-2,
    )

    with self.assertRaises(ValidationError):
        focus.full_clean()
```

- [ ] **Step 2: Run the model tests and verify they fail**

Run:

```bash
./bin/manage test tests.django_app.core.test_models.ModelSanityTestCase
```

Expected: import failure because `core.models.Focus` does not exist.

- [ ] **Step 3: Add the Focus model**

Add this model after `BaseModel` so it is easy to find with other top-level concepts:

```python
class Focus(BaseModel):
    """A saved search with durable pending source-ingestion counts."""

    query = models.CharField(max_length=500, unique=True, db_index=True)
    ingest_trials_count = models.PositiveIntegerField(default=0)
    ingest_publications_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created', '-id']
        verbose_name = 'Focus'
        verbose_name_plural = 'Focuses'

    def __str__(self):
        return self.query
```

- [ ] **Step 4: Generate and inspect the migration**

Run:

```bash
./bin/makemigrations core
```

Expected: after the separate pending ClaimTrails work owns migration `0019`, `django_app/core/migrations/0020_focus.py` creates the four Focus fields plus inherited `id`, `created`, `modified`, and `meta`, and applies the model ordering/verbose names. If migration `0019` has not landed when execution starts, finish that independent work first rather than combining unrelated models in one migration.

- [ ] **Step 5: Run model and migration checks**

Run:

```bash
./bin/manage test tests.django_app.core.test_models.ModelSanityTestCase tests.bin.test_migrations
```

Expected: PASS.

- [ ] **Step 6: Commit the model slice**

```bash
git add django_app/core/models.py django_app/core/migrations/0020_focus.py tests/django_app/core/test_models.py
git commit -m "feat: add focus model"
```

---

### Task 2: Centralize generated Focus queries and creation

**Files:**
- Create: `django_app/lib/focuses.py`
- Create: `tests/django_app/lib/test_focuses.py`

**Interfaces:**
- Consumes: `Claim.diseases`, `Claim.interventions`, `ClaimGroup.diseases`, `ClaimGroup.interventions`, and `Focus.query`.
- Produces: `build_focus_query(source: Claim | ClaimGroup) -> str`, `focus_state(source: Claim | ClaimGroup) -> dict[str, object]`, and `get_or_create_focus(source: Claim | ClaimGroup) -> tuple[Focus, bool]`.

- [ ] **Step 1: Write failing query-construction tests**

Create `tests/django_app/lib/test_focuses.py`:

```python
from django.test import TestCase

from core.models import Claim, ClaimGroup, Disease, Focus, Intervention
from lib.focuses import build_focus_query, focus_state, get_or_create_focus


class FocusQueryTestCase(TestCase):
    def setUp(self):
        self.disease_a = Disease.objects.create(name='  Acute Leukemia  ')
        self.disease_z = Disease.objects.create(name='Zeta syndrome')
        self.intervention_a = Intervention.objects.create(name='Azacitidine')
        self.intervention_v = Intervention.objects.create(name='Venetoclax')

    def test_build_focus_query_orders_diseases_then_interventions(self):
        claim = Claim.objects.create(section='title', claim_type='treatment')
        claim.diseases.add(self.disease_z, self.disease_a)
        claim.interventions.add(self.intervention_v, self.intervention_a)

        self.assertEqual(
            build_focus_query(claim),
            'Acute Leukemia Zeta syndrome Azacitidine Venetoclax',
        )

    def test_claim_group_uses_the_same_canonical_query(self):
        group = ClaimGroup.objects.create(evidence_summary='Group')
        group.diseases.add(self.disease_z, self.disease_a)
        group.interventions.add(self.intervention_v, self.intervention_a)

        self.assertEqual(
            build_focus_query(group),
            'Acute Leukemia Zeta syndrome Azacitidine Venetoclax',
        )

    def test_empty_entities_cannot_create_focus(self):
        claim = Claim.objects.create(section='title', claim_type='empty')

        self.assertEqual(build_focus_query(claim), '')
        with self.assertRaisesMessage(ValueError, 'No disease or intervention terms'):
            get_or_create_focus(claim)

    def test_get_or_create_is_idempotent_and_counts_start_at_zero(self):
        claim = Claim.objects.create(section='title', claim_type='treatment')
        claim.diseases.add(self.disease_a)

        first, first_created = get_or_create_focus(claim)
        second, second_created = get_or_create_focus(claim)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.ingest_trials_count, 0)
        self.assertEqual(first.ingest_publications_count, 0)

    def test_focus_state_links_an_existing_focus(self):
        group = ClaimGroup.objects.create(evidence_summary='Group')
        group.interventions.add(self.intervention_v)
        focus = Focus.objects.create(query='Venetoclax')

        self.assertEqual(focus_state(group), {
            'query': 'Venetoclax',
            'exists': True,
            'focus_id': focus.pk,
        })
```

- [ ] **Step 2: Run the domain tests and verify they fail**

Run:

```bash
./bin/manage test tests.django_app.lib.test_focuses
```

Expected: import failure because `lib.focuses` does not exist.

- [ ] **Step 3: Implement the Focus domain module**

Create `django_app/lib/focuses.py`:

```python
from core.models import Claim, ClaimGroup, Focus


FocusSource = Claim | ClaimGroup


def _ordered_names(manager) -> list[str]:
    names = [name.strip() for name in manager.values_list('name', flat=True)]
    return sorted((name for name in names if name), key=str.casefold)


def build_focus_query(source: FocusSource) -> str:
    if not isinstance(source, (Claim, ClaimGroup)):
        raise TypeError('Focus source must be a Claim or ClaimGroup.')
    terms = _ordered_names(source.diseases) + _ordered_names(source.interventions)
    return ' '.join(terms)


def focus_state(source: FocusSource) -> dict[str, object]:
    query = build_focus_query(source)
    focus_id = Focus.objects.filter(query=query).values_list('pk', flat=True).first() if query else None
    return {'query': query, 'exists': focus_id is not None, 'focus_id': focus_id}


def get_or_create_focus(source: FocusSource) -> tuple[Focus, bool]:
    query = build_focus_query(source)
    if not query:
        raise ValueError('No disease or intervention terms are available for this focus.')
    return Focus.objects.get_or_create(query=query)
```

- [ ] **Step 4: Run the domain tests**

Run:

```bash
./bin/manage test tests.django_app.lib.test_focuses
```

Expected: PASS.

- [ ] **Step 5: Commit the domain slice**

```bash
git add django_app/lib/focuses.py tests/django_app/lib/test_focuses.py
git commit -m "feat: derive focuses from review entities"
```

---

### Task 3: Expose Focus list, detail, editing, and create-from-record APIs

**Files:**
- Modify: `django_app/core/api.py`
- Modify: `django_app/core/urls.py`
- Modify: `tests/django_app/core/test_api.py`

**Interfaces:**
- Consumes: Task 1 `Focus`; Task 2 `focus_state()` and `get_or_create_focus()`.
- Produces: `GET /api/focuses/`, `GET/PATCH /api/focuses/{id}/`, `POST /api/focuses/from-record/`, and a `focus` object in Claim/ClaimGroup detail JSON.

- [ ] **Step 1: Write failing Focus API tests**

Add a `FocusApiTestCase(TestCase)` to `tests/django_app/core/test_api.py` covering list/search/order/filter/detail/edit:

```python
class FocusApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.focus = Focus.objects.create(
            query='Colon cancer Nivolumab',
            ingest_trials_count=3,
            ingest_publications_count=4,
            notes='Priority topic',
        )

    def test_focus_list_search_order_and_pending_filters(self):
        Focus.objects.create(query='Inactive', ingest_trials_count=0, ingest_publications_count=0)

        searched = self.client.get('/api/focuses/', {'search': str(self.focus.pk)}).json()
        self.assertEqual(searched['results'][0]['id'], self.focus.pk)
        self.assertEqual(
            self.client.get('/api/focuses/', {'ingest_trials_count': 3}).json()['count'],
            1,
        )
        ordered = self.client.get('/api/focuses/', {'ordering': '-ingest_publications_count'}).json()
        self.assertEqual(ordered['results'][0]['id'], self.focus.pk)

    def test_focus_detail_exposes_editable_and_audit_fields(self):
        data = self.client.get(f'/api/focuses/{self.focus.pk}/').json()
        self.assertEqual(data['query'], 'Colon cancer Nivolumab')
        self.assertEqual(data['ingest_trials_count'], 3)
        self.assertEqual(data['ingest_publications_count'], 4)
        self.assertEqual(data['notes'], 'Priority topic')
        self.assertIn('created', data)
        self.assertIn('modified', data)

    def test_focus_patch_requires_csrf_and_validates_input(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/app/')
        url = f'/api/focuses/{self.focus.pk}/'
        payload = json.dumps({
            'query': 'Updated query',
            'ingest_trials_count': 2,
            'ingest_publications_count': 1,
            'notes': 'Updated',
        })
        self.assertEqual(client.patch(url, data=payload, content_type='application/json').status_code, 403)
        token = client.cookies['csrftoken'].value
        response = client.patch(
            url, data=payload, content_type='application/json', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['query'], 'Updated query')
        invalid = client.patch(
            url,
            data='{"ingest_trials_count": -1}',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(invalid.status_code, 400)
```

Import `json`, `Client`, and `Focus` in the test module if not already imported.

- [ ] **Step 2: Write failing create-from-record and detail-state tests**

Add tests that use the same canonical server query for both supported sources:

```python
def test_claim_and_group_details_report_focus_state(self):
    disease = Disease.objects.create(name='Colon cancer')
    intervention = Intervention.objects.create(name='Nivolumab')
    group = ClaimGroup.objects.create(evidence_summary='Summary')
    group.diseases.add(disease)
    group.interventions.add(intervention)
    claim = Claim.objects.create(section='title', claim_type='worked', claim_group=group)
    claim.diseases.add(disease)
    claim.interventions.add(intervention)

    self.assertEqual(self.client.get(f'/api/claims/{claim.pk}/').json()['focus'], {
        'query': 'Colon cancer Nivolumab', 'exists': False, 'focus_id': None,
    })
    self.assertEqual(self.client.get(f'/api/claim-groups/{group.pk}/').json()['focus'], {
        'query': 'Colon cancer Nivolumab', 'exists': False, 'focus_id': None,
    })

def test_create_focus_from_record_is_idempotent(self):
    disease = Disease.objects.create(name='Colon cancer')
    claim = Claim.objects.create(section='title', claim_type='worked')
    claim.diseases.add(disease)
    client = Client(enforce_csrf_checks=True)
    client.get('/app/')
    token = client.cookies['csrftoken'].value
    payload = json.dumps({'kind': 'claims', 'id': claim.pk})

    first = client.post(
        '/api/focuses/from-record/', data=payload, content_type='application/json',
        HTTP_X_CSRFTOKEN=token,
    )
    second = client.post(
        '/api/focuses/from-record/', data=payload, content_type='application/json',
        HTTP_X_CSRFTOKEN=token,
    )

    self.assertEqual(first.status_code, 201)
    self.assertEqual(second.status_code, 200)
    self.assertEqual(first.json()['focus']['id'], second.json()['focus']['id'])
    self.assertEqual(Focus.objects.count(), 1)
```

Add these methods to the same test class:

```python
def test_create_focus_from_claim_group(self):
    group = ClaimGroup.objects.create(evidence_summary='Summary')
    group.interventions.add(Intervention.objects.create(name='Nivolumab'))
    response = self.csrf_client.post(
        '/api/focuses/from-record/',
        data=json.dumps({'kind': 'claim-groups', 'id': group.pk}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=self.csrf_token,
    )
    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.json()['focus']['query'], 'Nivolumab')

def test_create_focus_rejects_unknown_kind(self):
    response = self.csrf_client.post(
        '/api/focuses/from-record/',
        data=json.dumps({'kind': 'trials', 'id': 1}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=self.csrf_token,
    )
    self.assertEqual(response.status_code, 400)

def test_create_focus_returns_404_for_missing_record(self):
    response = self.csrf_client.post(
        '/api/focuses/from-record/',
        data=json.dumps({'kind': 'claims', 'id': 999999}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=self.csrf_token,
    )
    self.assertEqual(response.status_code, 404)

def test_create_focus_rejects_record_without_terms(self):
    claim = Claim.objects.create(section='title', claim_type='empty')
    response = self.csrf_client.post(
        '/api/focuses/from-record/',
        data=json.dumps({'kind': 'claims', 'id': claim.pk}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=self.csrf_token,
    )
    self.assertEqual(response.status_code, 400)
    self.assertIn('No disease or intervention terms', str(response.json()))
```

Create `self.csrf_client` and `self.csrf_token` in `setUp()` by requesting `/app/` with `Client(enforce_csrf_checks=True)`.

- [ ] **Step 3: Run the Focus API tests and verify they fail**

Run:

```bash
./bin/manage test tests.django_app.core.test_api.FocusApiTestCase
```

Expected: failure because the Focus API and detail `focus` field do not exist.

- [ ] **Step 4: Add serializers and Focus detail state**

Import `Focus` and the Task 2 helpers. Add:

```python
class FocusListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Focus
        fields = ('id', 'query', 'ingest_trials_count', 'ingest_publications_count', 'modified')


class FocusDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Focus
        fields = ('id', 'query', 'ingest_trials_count', 'ingest_publications_count',
                  'notes', 'meta', 'created', 'modified')
        read_only_fields = ('id', 'meta', 'created', 'modified')

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError('Expected a JSON object.')
        allowed = {'query', 'ingest_trials_count', 'ingest_publications_count', 'notes'}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValidationError({key: 'This field cannot be updated.' for key in unknown})
        return super().to_internal_value(data)

    def validate_query(self, value):
        value = value.strip()
        if not value:
            raise ValidationError('Enter a nonblank query.')
        return value


class FocusSourceSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=('claims', 'claim-groups'))
    id = serializers.IntegerField(min_value=1)
```

In `ClaimDetailSerializer.to_representation()` and `ClaimGroupDetailSerializer.to_representation()`, add:

```python
data['focus'] = focus_state(instance)
```

- [ ] **Step 5: Add the Focus viewset and create action**

Implement the existing list/detail/update conventions:

```python
@method_decorator(require_csrf_token, name='dispatch')
class FocusViewSet(UpdateModelMixin, BaseReadOnlyViewSet):
    search_fields = ('=id', 'query', 'notes')
    ordering_fields = ('id', 'query', 'ingest_trials_count',
                       'ingest_publications_count', 'created', 'modified')
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_serializer_class(self):
        return FocusListSerializer if self.action == 'list' else FocusDetailSerializer

    def get_queryset(self):
        qs = Focus.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        for field in ('ingest_trials_count', 'ingest_publications_count'):
            if field in self.request.query_params:
                value = _parse_int_param(field, self.request.query_params[field])
                if value < 0:
                    raise ValidationError({field: 'Enter a non-negative integer.'})
                qs = qs.filter(**{field: value})
        return qs

    @action(detail=False, methods=['post'], url_path='from-record')
    def from_record(self, request):
        payload = FocusSourceSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        kind = payload.validated_data['kind']
        model = Claim if kind == 'claims' else ClaimGroup
        source = model.objects.prefetch_related('diseases', 'interventions').filter(
            pk=payload.validated_data['id'],
        ).first()
        if source is None:
            raise Http404
        try:
            focus, created = get_or_create_focus(source)
        except ValueError as exc:
            raise ValidationError({'source': str(exc)})
        return Response(
            {'created': created, 'focus': FocusDetailSerializer(focus).data},
            status=201 if created else 200,
        )
```

Ensure `FocusDetailSerializer` remains the serializer for retrieve, PATCH, and the custom action response; do not accept direct `POST /api/focuses/` creation.

- [ ] **Step 6: Register the router and run API tests**

Import `FocusViewSet` in `django_app/core/urls.py` and add:

```python
router.register('focuses', FocusViewSet, basename='focus')
```

Run:

```bash
./bin/manage test tests.django_app.core.test_api.FocusApiTestCase tests.django_app.lib.test_focuses
```

Expected: PASS.

- [ ] **Step 7: Run the existing Claim and ClaimGroup API contracts**

Run:

```bash
./bin/manage test tests.django_app.core.test_api.ClaimGroupApiTestCase tests.django_app.core.test_api.WorkspaceDetailApiTestCase
```

Expected: PASS after updating any whole-dictionary assertions to include the new `focus` object only where they assert detail payloads exactly.

- [ ] **Step 8: Commit the API slice**

```bash
git add django_app/core/api.py django_app/core/urls.py tests/django_app/core/test_api.py
git commit -m "feat: expose focus workspace api"
```

---

### Task 4: Add paginated source identifier iterators

**Files:**
- Modify: `django_app/lib/clinical_trials.py`
- Modify: `django_app/lib/pubmed.py`
- Modify: `tests/django_app/lib/test_clinical_trials.py`
- Modify: `tests/django_app/lib/test_pubmed.py`

**Interfaces:**
- Consumes: ClinicalTrials.gov v2 `studies`/`nextPageToken`; PubMed ESearch `idlist`/`count` with `retstart` and `retmax`.
- Produces: `iter_trial_search_ids(query: str, page_size: int = 100) -> Iterator[str]` and `iter_publication_search_ids(query: str, page_size: int = 100) -> Iterator[str]`.

- [ ] **Step 1: Write failing ClinicalTrials.gov pagination tests**

Add this test beside `ClinicalTrialsSearchTestCase`:

```python
@patch('lib.clinical_trials.httpx.get')
def test_iter_trial_search_ids_follows_next_page_tokens(self, get):
    get.side_effect = [
        _response({
            'studies': [
                {'protocolSection': {'identificationModule': {'nctId': 'NCT00000001'}}},
                {'protocolSection': {'identificationModule': {'nctId': 'NCT00000002'}}},
            ],
            'nextPageToken': 'token-2',
        }),
        _response({
            'studies': [
                {'protocolSection': {'identificationModule': {'nctId': 'NCT00000003'}}},
            ],
        }),
    ]

    self.assertEqual(
        list(iter_trial_search_ids('colon cancer', page_size=2)),
        ['NCT00000001', 'NCT00000002', 'NCT00000003'],
    )
    self.assertNotIn('pageToken', get.call_args_list[0].kwargs['params'])
    self.assertEqual(get.call_args_list[1].kwargs['params']['pageToken'], 'token-2')
```

Add this local response helper and final-page test:

```python
def _response(data):
    from unittest.mock import Mock
    response = Mock()
    response.json.return_value = data
    return response


@patch('lib.clinical_trials.httpx.get')
def test_iter_trial_search_ids_stops_on_final_empty_page(self, get):
    get.return_value = _response({'studies': []})

    self.assertEqual(list(iter_trial_search_ids('no matches')), [])
    get.assert_called_once()
```

- [ ] **Step 2: Write failing PubMed pagination tests**

Add:

```python
@patch('lib.pubmed.httpx.get')
def test_iter_publication_search_ids_pages_until_count(self, get):
    get.side_effect = [
        _response({'esearchresult': {
            'count': '3', 'retstart': '0', 'retmax': '2',
            'idlist': ['100', '101'],
        }}),
        _response({'esearchresult': {
            'count': '3', 'retstart': '2', 'retmax': '2',
            'idlist': ['102'],
        }}),
    ]

    self.assertEqual(
        list(iter_publication_search_ids('colon cancer', page_size=2)),
        ['100', '101', '102'],
    )
    self.assertEqual(get.call_args_list[0].kwargs['params']['retstart'], 0)
    self.assertEqual(get.call_args_list[1].kwargs['params']['retstart'], 2)
```

Add this inconsistent-count termination test:

```python
@patch('lib.pubmed.httpx.get')
def test_iter_publication_search_ids_stops_on_empty_page(self, get):
    get.return_value = _response({'esearchresult': {
        'count': '50', 'retstart': '0', 'retmax': '100', 'idlist': [],
    }})

    self.assertEqual(list(iter_publication_search_ids('no matches')), [])
    get.assert_called_once()
```

- [ ] **Step 3: Run the new iterator tests and verify they fail**

Run:

```bash
./bin/manage test tests.django_app.lib.test_clinical_trials.ClinicalTrialsSearchTestCase tests.django_app.lib.test_pubmed.PubMedSearchTestCase
```

Expected: import/name failure for both iterator functions.

- [ ] **Step 4: Implement the trial identifier iterator**

Add to `django_app/lib/clinical_trials.py` without changing `search_trials()`:

```python
def iter_trial_search_ids(query: str, page_size: int = 100):
    page_token = None
    while True:
        params = {
            'query.term': query,
            'pageSize': page_size,
            'sort': '@relevance',
            'fields': 'NCTId',
        }
        if page_token:
            params['pageToken'] = page_token
        response = httpx.get(CTGOV_V2_URL, params=params, timeout=30.0)
        response.raise_for_status()
        payload = response.json()
        for study in payload.get('studies', []):
            nct_id = (
                study.get('protocolSection', {})
                .get('identificationModule', {})
                .get('nctId')
            )
            if nct_id:
                yield str(nct_id).strip().upper()
        page_token = payload.get('nextPageToken')
        if not page_token:
            return
```

- [ ] **Step 5: Implement the PubMed identifier iterator**

Add to `django_app/lib/pubmed.py` without changing `search_publications()`:

```python
def iter_publication_search_ids(query: str, page_size: int = 100):
    retstart = 0
    while True:
        response = httpx.get(
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            params={
                'db': 'pubmed', 'term': query, 'retmode': 'json',
                'retstart': retstart, 'retmax': page_size, 'sort': 'relevance',
            },
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()['esearchresult']
        ids = [str(pmid).strip() for pmid in result.get('idlist', []) if str(pmid).strip()]
        yield from ids
        retstart += len(ids)
        total = int(result.get('count') or 0)
        if not ids or retstart >= total:
            return
```

- [ ] **Step 6: Run all source-library tests**

Run:

```bash
./bin/manage test tests.django_app.lib.test_clinical_trials tests.django_app.lib.test_pubmed
```

Expected: PASS, including the unchanged first-100 UI search contracts.

- [ ] **Step 7: Commit the pagination slice**

```bash
git add django_app/lib/clinical_trials.py django_app/lib/pubmed.py tests/django_app/lib/test_clinical_trials.py tests/django_app/lib/test_pubmed.py
git commit -m "feat: paginate focus source searches"
```

---

### Task 5: Consume pending Focus counts in a restart-safe job

**Files:**
- Create: `jobs/ingest_focus.py`
- Create: `tests/bin/test_ingest_focus.py`

**Interfaces:**
- Consumes: Task 1 `Focus`; Task 4 identifier iterators; existing `fetch_and_upsert_trial(id)` and `fetch_and_upsert_publication(id)`.
- Produces: `ingest_kind(focus, spec) -> int`, `ingest_focus(focus) -> dict[str, int]`, and `run() -> None`.

- [ ] **Step 1: Write failing job tests for skipping and durable decrements**

Create Django tests in `tests/bin/test_ingest_focus.py`:

```python
from unittest.mock import patch

from django.test import TestCase

from core.models import Focus, Publication, Trial
from jobs.ingest_focus import ingest_focus, run


class FocusIngestionJobTestCase(TestCase):
    @patch('jobs.ingest_focus.iter_trial_search_ids')
    @patch('jobs.ingest_focus.fetch_and_upsert_trial')
    def test_trials_skip_existing_and_decrement_only_successful_new_rows(
            self, fetch_trial, trial_ids):
        Trial.objects.create(nct_id='NCT00000001', title='Existing')
        focus = Focus.objects.create(query='colon cancer', ingest_trials_count=2)
        trial_ids.return_value = iter([
            'NCT00000001', 'NCT00000002', 'NCT00000003', 'NCT00000004',
        ])

        def save_trial(nct_id):
            if nct_id == 'NCT00000002':
                raise RuntimeError('temporary failure')
            return Trial.objects.create(nct_id=nct_id, title=nct_id)

        fetch_trial.side_effect = save_trial

        result = ingest_focus(focus)

        focus.refresh_from_db()
        self.assertEqual(result['trials'], 2)
        self.assertEqual(focus.ingest_trials_count, 0)
        self.assertEqual(
            list(Trial.objects.order_by('nct_id').values_list('nct_id', flat=True)),
            ['NCT00000001', 'NCT00000003', 'NCT00000004'],
        )
        self.assertEqual(
            [call.args[0] for call in fetch_trial.call_args_list],
            ['NCT00000002', 'NCT00000003', 'NCT00000004'],
        )
```

The test demonstrates all three count rules: an existing row is skipped, a failed import remains pending, and only two successfully persisted new rows consume the quota.

- [ ] **Step 2: Add publication, exhaustion, and inactive-Focus tests**

Add:

```python
@patch('jobs.ingest_focus.iter_publication_search_ids')
@patch('jobs.ingest_focus.fetch_and_upsert_publication')
def test_publication_exhaustion_leaves_remainder_pending(self, fetch_publication, publication_ids):
    focus = Focus.objects.create(query='colon cancer', ingest_publications_count=3)
    publication_ids.return_value = iter(['100', '101'])
    fetch_publication.side_effect = lambda pmid: Publication.objects.create(pmid=pmid, title=pmid)

    result = ingest_focus(focus)

    focus.refresh_from_db()
    self.assertEqual(result['publications'], 2)
    self.assertEqual(focus.ingest_publications_count, 1)

@patch('jobs.ingest_focus.ingest_focus')
def test_run_processes_only_focuses_with_pending_counts(self, process):
    inactive = Focus.objects.create(query='inactive')
    trial_focus = Focus.objects.create(query='trials', ingest_trials_count=1)
    publication_focus = Focus.objects.create(query='publications', ingest_publications_count=1)

    run()

    self.assertEqual(
        {call.args[0].pk for call in process.call_args_list},
        {trial_focus.pk, publication_focus.pk},
    )
    self.assertNotIn(inactive.pk, {call.args[0].pk for call in process.call_args_list})
```

Also add a trial test that patches `jobs.ingest_focus.fetch_and_upsert_trial` and asserts there is no import or call site for `fetch_trial_publications` in the job module.

- [ ] **Step 3: Run the job tests and verify they fail**

Run:

```bash
./bin/manage test tests.bin.test_ingest_focus.FocusIngestionJobTestCase
```

Expected: import failure because `jobs.ingest_focus` does not exist.

- [ ] **Step 4: Implement source specifications and atomic decrementing**

Create `jobs/ingest_focus.py` with Django setup matching `jobs/pipeline.py`, then define:

```python
from dataclasses import dataclass
from typing import Callable, Iterable

from django.db.models import F, Q

from core.models import Focus, Publication, Trial
from lib.clinical_trials import fetch_and_upsert_trial, iter_trial_search_ids
from lib.logs import get_logger
from lib.pubmed import fetch_and_upsert_publication, iter_publication_search_ids

logger = get_logger('lib.jobs.ingest_focus')


@dataclass(frozen=True)
class IngestSpec:
    label: str
    count_field: str
    model: type
    identifier_field: str
    search: Callable[[str], Iterable[str]]
    fetch: Callable[[str], object]


def _decrement(focus: Focus, field: str) -> None:
    updated = Focus.objects.filter(pk=focus.pk, **{f'{field}__gt': 0}).update(
        **{field: F(field) - 1},
    )
    if updated != 1:
        raise RuntimeError(f'Could not decrement {field} for Focus {focus.pk}.')
    setattr(focus, field, getattr(focus, field) - 1)
```

The `F()` update makes every completed record durable even if the process is interrupted before the next result.

- [ ] **Step 5: Implement quota processing**

Add:

```python
def ingest_kind(focus: Focus, spec: IngestSpec) -> int:
    pending = getattr(focus, spec.count_field)
    if pending <= 0:
        return 0
    completed = 0
    for identifier in spec.search(focus.query):
        if completed >= pending:
            break
        lookup = {spec.identifier_field: identifier}
        if spec.model.objects.filter(**lookup).exists():
            logger.info(
                'Skipping existing %s focus_id=%s identifier=%s',
                spec.label, focus.pk, identifier,
            )
            continue
        try:
            spec.fetch(identifier)
        except Exception:
            logger.error(
                'Failed %s focus_id=%s identifier=%s',
                spec.label, focus.pk, identifier, exc_info=True,
            )
            continue
        if not spec.model.objects.filter(**lookup).exists():
            logger.error(
                'Importer returned without saving %s focus_id=%s identifier=%s',
                spec.label, focus.pk, identifier,
            )
            continue
        _decrement(focus, spec.count_field)
        completed += 1
        logger.info(
            'Imported %s focus_id=%s identifier=%s remaining=%s',
            spec.label, focus.pk, identifier, getattr(focus, spec.count_field),
        )
    if completed < pending:
        logger.warning(
            'Search exhausted focus_id=%s kind=%s imported=%s pending=%s',
            focus.pk, spec.label, completed, getattr(focus, spec.count_field),
        )
    return completed


def ingest_focus(focus: Focus) -> dict[str, int]:
    trials = IngestSpec(
        label='trials', count_field='ingest_trials_count', model=Trial,
        identifier_field='nct_id', search=iter_trial_search_ids,
        fetch=fetch_and_upsert_trial,
    )
    publications = IngestSpec(
        label='publications', count_field='ingest_publications_count', model=Publication,
        identifier_field='pmid', search=iter_publication_search_ids,
        fetch=fetch_and_upsert_publication,
    )
    return {
        'trials': ingest_kind(focus, trials),
        'publications': ingest_kind(focus, publications),
    }


def run() -> None:
    focuses = Focus.objects.filter(
        Q(ingest_trials_count__gt=0) | Q(ingest_publications_count__gt=0),
    ).order_by('id')
    for focus in focuses.iterator():
        logger.info(
            'Starting Focus focus_id=%s trials=%s publications=%s query=%r',
            focus.pk, focus.ingest_trials_count, focus.ingest_publications_count, focus.query,
        )
        result = ingest_focus(focus)
        logger.info(
            'Completed Focus focus_id=%s imported_trials=%s imported_publications=%s',
            focus.pk, result['trials'], result['publications'],
        )


if __name__ == '__main__':
    run()
```

Do not import or call `fetch_trial_publications`. Add this test to make that boundary explicit:

```python
def test_job_does_not_expose_related_publication_fetcher(self):
    import jobs.ingest_focus as job_module

    self.assertFalse(hasattr(job_module, 'fetch_trial_publications'))
```

- [ ] **Step 6: Run the job tests**

Run:

```bash
./bin/manage test tests.bin.test_ingest_focus.FocusIngestionJobTestCase
```

Expected: PASS.

- [ ] **Step 7: Commit the job slice**

```bash
git add jobs/ingest_focus.py tests/bin/test_ingest_focus.py
git commit -m "feat: consume focus ingestion quotas"
```

---

### Task 6: Add the container launcher and documentation

**Files:**
- Create: `bin/ingest_focus`
- Modify: `tests/bin/test_ingest_focus.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 5 `jobs/ingest_focus.py` and the running `django-app` Compose service.
- Produces: executable `./bin/ingest_focus`.

- [ ] **Step 1: Write the failing launcher test**

Add a non-Django `unittest.TestCase` modeled on `tests/bin/test_pipeline.py`:

```python
class FocusIngestionLauncherTestCase(TestCase):
    def test_launcher_executes_job_in_running_django_container(self):
        project = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            log = Path(tmp) / 'docker.log'
            env = {**os.environ, 'PATH': f'{tmp}:{os.environ["PATH"]}', 'DOCKER_LOG': str(log)}

            subprocess.run(
                ['bash', str(project / 'bin/ingest_focus')],
                env=env, check=True, capture_output=True,
            )

            self.assertEqual(log.read_text().splitlines(), [
                'compose', '--env-file', 'etc/.env', 'exec', '-T',
                'django-app', 'python', 'jobs/ingest_focus.py',
            ])
```

Import `os`, `subprocess`, `tempfile`, `Path`, and the standard-library `TestCase` under an unambiguous name if the module also imports Django's `TestCase`.

- [ ] **Step 2: Run the launcher test and verify it fails**

Run:

```bash
./bin/manage test tests.bin.test_ingest_focus.FocusIngestionLauncherTestCase
```

Expected: failure because `bin/ingest_focus` does not exist.

- [ ] **Step 3: Add the launcher**

Create `bin/ingest_focus` using the established launcher contract:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "etc/.env" ]; then
    echo "Error: etc/.env not found. Run ./bin/install first."
    exit 1
fi

docker compose --env-file etc/.env exec -T django-app python jobs/ingest_focus.py
```

Make it executable:

```bash
chmod +x bin/ingest_focus
```

- [ ] **Step 4: Document the workflow**

Add a Focus ingestion subsection to `README.md` that states:

~~~markdown
### Ingest saved focuses

Focus records hold a search query and one-time pending counts for trials and publications.
Run the following against the active Django container:

```bash
./bin/ingest_focus
```

The job skips records already present in the database. Each successfully imported new trial or publication decrements its corresponding pending count; failures and exhausted search results leave the remainder pending for a later run. Trial imports do not automatically import referenced publications.
~~~

- [ ] **Step 5: Run the launcher tests**

Run:

```bash
./bin/manage test tests.bin.test_ingest_focus
```

Expected: PASS.

- [ ] **Step 6: Commit the launcher slice**

```bash
git add bin/ingest_focus tests/bin/test_ingest_focus.py README.md
git commit -m "feat: add focus ingestion launcher"
```

---

### Task 7: Add Focuses as the final workspace tab

**Files:**
- Modify: `django_app/core/templates/core/workspace.html`
- Modify: `django_app/core/static/core/workspace.js`
- Modify: `django_app/core/static/core/workspace.css`
- Modify: `tests/django_app/core/test_workspace.py`

**Interfaces:**
- Consumes: Task 3 Focus APIs and Claim/ClaimGroup detail `focus` state.
- Produces: final Focuses tab, upper-pane Focus table, lower-pane editor, create button, disabled duplicate state, and existing-Focus modal link.

- [ ] **Step 1: Write failing tab-order and asset-contract tests**

Add to `WorkspaceShellTestCase`, importing `Path` from `pathlib`:

```python
def test_focuses_tab_is_last_after_sources(self):
    html = self.client.get('/app/').content.decode()
    self.assertIn('data-tab="focuses"', html)
    self.assertLess(html.index('data-tab="sources"'), html.index('data-tab="focuses"'))
    self.assertEqual(html.rfind('data-tab="focuses"'), html.rfind('data-tab='))

def test_workspace_assets_include_focus_contracts(self):
    project = Path(__file__).resolve().parents[3]
    js = (project / 'django_app/core/static/core/workspace.js').read_text()
    self.assertIn("focuses: '/api/focuses/'", js)
    self.assertIn("'/api/focuses/from-record/'", js)
    self.assertIn('Focus already exists', js)
    self.assertIn('ingest_trials_count', js)
    self.assertIn('ingest_publications_count', js)
```

Use the module's existing path-reading convention if it already provides a helper for static assets.

- [ ] **Step 2: Run the workspace tests and verify they fail**

Run:

```bash
./bin/manage test tests.django_app.core.test_workspace.WorkspaceShellTestCase
```

Expected: failure because the tab and JavaScript contracts are absent.

- [ ] **Step 3: Append the template tab after Sources**

In `workspace.html`, keep Sources in place and append:

```html
<button type="button" role="tab" data-tab="sources" aria-selected="false">Sources</button>
<button type="button" role="tab" data-tab="focuses" aria-selected="false">Focuses</button>
```

- [ ] **Step 4: Register the Focus table as the last JavaScript tab**

Append this entry after `sources` in `TABS`:

```javascript
focuses: {
  label: 'Focuses',
  endpoint: '/api/focuses/',
  columns: [
    { key: 'id', label: 'ID', sortable: true, numeric: true },
    { key: 'query', label: 'Query', sortable: true, excerpt: true },
    { key: 'ingest_trials_count', label: 'Pending trials', sortable: true, numeric: true },
    { key: 'ingest_publications_count', label: 'Pending publications', sortable: true, numeric: true },
    { key: 'modified', label: 'Modified', sortable: true, mono: true, datetime: true }
  ],
  filters: [
    { name: 'ingest_trials_count', label: 'Pending trials', type: 'text' },
    { name: 'ingest_publications_count', label: 'Pending publications', type: 'text' }
  ]
}
```

Add `focuses: '/api/focuses/'` to `MAIN_KINDS` and `focuses: 'Focus'` to `KIND_LABELS`. This automatically enables `recordUrl('focuses', id)` and modal loading.

- [ ] **Step 5: Implement the lower-pane Focus editor**

Add `focusEditForm(focus)` that renders:

- a text input for `query` with `maxlength=500` and `required`;
- number inputs for both counts with `min=0` and `step=1`;
- a notes textarea;
- one Save button and `role=status` feedback;
- a CSRF-protected `PATCH /api/focuses/{id}/` request containing exactly the four editable fields;
- preservation of entered values on errors;
- list refresh and detail refresh after success.

Use this payload exactly:

```javascript
var payload = {
  query: query.value.trim(),
  ingest_trials_count: Number(trials.value),
  ingest_publications_count: Number(publications.value),
  notes: notes.value
};
```

Add:

```javascript
function renderFocusDetail(data) {
  clear(els.detail);
  var wrap = make('div', 'ws-col-left');
  wrap.appendChild(make('h2', null, 'Focus ' + String(data.id)));
  wrap.appendChild(fieldList([
    ['ID', data.id, 'mono'],
    ['Created', data.created, 'mono'],
    ['Modified', data.modified, 'mono']
  ]));
  wrap.appendChild(focusEditForm(data));
  els.detail.appendChild(wrap);
}
```

Route `tab === 'focuses'` to `renderFocusDetail(data)` in `renderDetail()`.

- [ ] **Step 6: Implement Add focus and duplicate-link controls**

Add a shared function used by both Claim and ClaimGroup details:

```javascript
function focusControl(kind, id, focusState) {
  var wrap = make('div', 'ws-focus-action');
  var button = make('button', 'ws-btn ws-btn-primary', 'Add focus');
  button.type = 'button';
  var feedback = make('p', 'ws-save-status');
  feedback.setAttribute('role', 'status');
  var stateValue = focusState || { query: '', exists: false, focus_id: null };

  function renderState() {
    clear(feedback);
    button.disabled = stateValue.exists || !stateValue.query;
    if (stateValue.exists) {
      feedback.appendChild(openButton('Focus already exists', 'focuses', stateValue.focus_id));
    } else if (!stateValue.query) {
      feedback.textContent = 'No disease or intervention terms are available.';
    }
  }

  button.addEventListener('click', function () {
    button.disabled = true;
    feedback.textContent = 'Adding focus…';
    fetch('/api/focuses/from-record/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRFToken': csrfToken()
      },
      body: JSON.stringify({ kind: kind, id: id })
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Create failed');
        }
        return response.json();
      })
      .then(function (data) {
        stateValue = {
          query: data.focus.query,
          exists: true,
          focus_id: data.focus.id
        };
        renderState();
      })
      .catch(function () {
        feedback.setAttribute('class', 'ws-save-status is-error');
        feedback.textContent = 'Could not add focus. Retry.';
        button.disabled = false;
      });
  });

  wrap.appendChild(button);
  wrap.appendChild(feedback);
  renderState();
  return wrap;
}
```

Append `focusControl('claim-groups', data.id, data.focus)` to the left column in `renderClaimGroupDetail()` and `focusControl('claims', data.id, data.focus)` to the left column in `renderClaimDetail()`.

The disabled Add focus button satisfies the inactive-button requirement. `openButton('Focus already exists', ...)` provides the linked message and opens the existing shared record modal.

- [ ] **Step 7: Add focused CSS without changing the global layout**

Add styles consistent with `.ws-review`:

```css
.ws-focus-action {
  margin-top: 1rem;
}

.ws-focus-action .ws-save-status {
  margin-bottom: 0;
}

.ws-focus-editor input[type="text"],
.ws-focus-editor input[type="number"] {
  width: 100%;
  min-width: 0;
}
```

Give the Focus editor both `ws-review` and `ws-focus-editor` classes so existing label, textarea, and button spacing remains reusable.

- [ ] **Step 8: Run workspace and API tests**

Run:

```bash
./bin/manage test tests.django_app.core.test_workspace tests.django_app.core.test_api.FocusApiTestCase
```

Expected: PASS.

- [ ] **Step 9: Commit the UI slice**

```bash
git add django_app/core/templates/core/workspace.html django_app/core/static/core/workspace.js django_app/core/static/core/workspace.css tests/django_app/core/test_workspace.py
git commit -m "feat: add focus workspace tab and actions"
```

---

### Task 8: Verify the complete feature

**Files:**
- Verify all files changed in Tasks 1–7

**Interfaces:**
- Consumes: every interface defined above.
- Produces: a migration-clean, fully tested Focus workflow ready for manual review.

- [ ] **Step 1: Confirm there are no uncommitted generated migrations**

Run:

```bash
./bin/manage makemigrations --check --dry-run
```

Expected: `No changes detected`.

- [ ] **Step 2: Run the complete automated test suite**

Run:

```bash
./bin/test
```

Expected: all environment, Django, library, API, workspace, and launcher tests PASS.

- [ ] **Step 3: Apply the migration in the development stack**

Run:

```bash
./bin/migrate
```

Expected: `core.0020_focus` applies successfully, or reports that it is already applied.

- [ ] **Step 4: Perform a focused browser smoke test**

Open `/app/` and verify this sequence:

1. Focuses is the final tab, after Sources.
2. Focus list search, exact pending-count filters, sorting, and pagination work.
3. Selecting a Focus shows editable query, two pending counts, and notes in the lower pane.
4. Saving valid edits refreshes the selected detail and upper table.
5. A negative count is rejected without losing the entered values.
6. A Claim or ClaimGroup with entities shows an enabled Add focus button.
7. Clicking it creates a zero-count Focus and changes the control to a disabled Add focus button plus a Focus already exists link.
8. Clicking Focus already exists opens that Focus in the shared modal.
9. A Claim or ClaimGroup with no entities shows a disabled button and the no-terms message.

- [ ] **Step 5: Perform a restart-safety ingestion smoke test**

Create or edit one Focus so each count is `1`, then run:

```bash
./bin/ingest_focus
```

Expected:

- at most one previously absent Trial and one previously absent Publication are added;
- each successfully satisfied pending count becomes `0`;
- no referenced publications are imported as a side effect of the trial;
- re-running with both counts at `0` performs no imports;
- if a source request fails, its count remains pending.

- [ ] **Step 6: Review the final diff for scope and secrets**

Run:

```bash
git status --short
git diff --check
git diff --stat
```

Expected: only intended source, migration, test, documentation, and launcher changes; no environment files, credentials, generated caches, or model artifacts.

- [ ] **Step 7: Close verification**

If verification required a correction, return to the task that owns that file, repeat its explicit test command, and use that task's explicit `git add` list and commit message. If no correction was required, do not create an empty commit.
