# Claims Generation Flags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace runtime use of `Trial.claims_generated` and `Publication.claims_generated` with per-source, per-claim-type processing records while retaining the old fields for a later consistency check.

**Architecture:** Add a `ClaimsGenerationFlags` model with exactly one source FK and a unique row per source and claim type. Backfill rows for existing true booleans, update claim processing to record each completed type even when no claims were saved, and clear those records when refetch deletes derived claims. Keep the old booleans in the schema and stop changing them at runtime.

**Tech Stack:** Django ORM, Django migrations, Django `TestCase` and `TransactionTestCase`, PostgreSQL constraints.

**Spec:** Approved design in the conversation on 2026-10-05.

## Global Constraints

- Do not read or write `docs/scratchpad.md`.
- Do not remove either `claims_generated` field in this change.
- Backfill true boolean values as processed for `intervention_worked_for_disease`, the claim type configured in `CLAIM_PROMPTS` at this migration.
- Record a processed type even when it produced zero saved claims.

---

### Task 1: Add the generation flag model and backfill migration

**Files:**
- Modify: `django_app/core/models.py`
- Create: `django_app/core/migrations/0022_claims_generation_flags.py`
- Test: `tests/django_app/core/test_claims_generation_flags_migration.py`
- Test: `tests/django_app/core/test_models.py`

**Interfaces:**
- Produces `ClaimsGenerationFlags`, with `trial`, `publication`, and `generated_claim_type` fields, reverse relation `claims_generation_flags`, and inherited audit fields.
- Each row belongs to exactly one of a trial or publication. A source cannot have duplicate rows for one `generated_claim_type`.

- [ ] **Step 1: Add model constraint tests**

Add tests in `tests/django_app/core/test_models.py` for trial and publication ownership, duplicate type rejection, and the exactly-one-owner check. Wrap each expected database error in its own `transaction.atomic()` block so the test transaction remains usable. The core invalid-owner assertion should follow this shape:

```python
with self.assertRaises(IntegrityError):
    with transaction.atomic():
        ClaimsGenerationFlags.objects.create(generated_claim_type='test')
```

- [ ] **Step 2: Run the focused model tests and confirm they fail**

Run `docker compose --env-file etc/.env run --rm django-app python django_app/manage.py test tests.django_app.core.test_models`. Expected: the new tests fail because the model or database constraints are absent.

- [ ] **Step 3: Implement `ClaimsGenerationFlags`**

Place it near `Claim` in `django_app/core/models.py`, inheriting `BaseModel`. Use `models.CharField(max_length=64)` for `generated_claim_type`, matching `Claim.claim_type`. Set both FKs to `null=True`, `blank=True`, and `on_delete=models.CASCADE`; use `related_name='claims_generation_flags'` on each. Add a `CheckConstraint` equivalent to:

```python
models.Q(trial__isnull=False, publication__isnull=True)
| models.Q(trial__isnull=True, publication__isnull=False)
```

Add conditional `UniqueConstraint`s for `(trial, generated_claim_type)` when `trial` is non-null and `(publication, generated_claim_type)` when `publication` is non-null.

- [ ] **Step 4: Add and test the migration backfill**

Create migration `0022` depending on `0021_claimtrails_diseases_claimtrails_interventions_and_more`. Create the table and constraints, then use historical models from `apps.get_model()` to insert one flag for each trial and publication whose old `claims_generated` value is true. Use the literal `'intervention_worked_for_disease'` in the migration so its behavior remains stable if `CLAIM_PROMPTS` changes later. Include true and false rows for both source models in the migration test; assert that only true rows receive flags and that the old boolean values remain present and unchanged. Implement the migration test as a `TransactionTestCase` with `migrate_from = ('core', '0021_claimtrails_diseases_claimtrails_interventions_and_more')` and `migrate_to = ('core', '0022_claims_generation_flags')`. Wrap migration and fixture work in `try/finally`; in `finally`, use a fresh `MigrationExecutor(connection)` to migrate back to `migrate_to`, so a failed assertion cannot leave the test database at `0021`.

- [ ] **Step 5: Run focused model and migration tests**

Run `docker compose --env-file etc/.env run --rm django-app python django_app/manage.py test tests.django_app.core.test_models tests.django_app.core.test_claims_generation_flags_migration`. Expected: all new constraints and backfill assertions pass.

- [ ] **Step 6: Commit the model and migration**

```bash
git add django_app/core/models.py django_app/core/migrations/0022_claims_generation_flags.py tests/django_app/core/test_models.py tests/django_app/core/test_claims_generation_flags_migration.py
git commit -m "feat: add per-type claim generation flags"
```

### Task 2: Process claim types independently and persist completion flags

**Files:**
- Modify: `django_app/lib/claims.py`
- Test: `tests/django_app/lib/test_claims.py`

**Interfaces:**
- `save_claims() -> int` continues to return the number of claims saved.
- A completed source/type pair is represented by one `ClaimsGenerationFlags` row, regardless of how many claims that type saved.

- [ ] **Step 1: Add claim processing tests**

Update the existing zero-claim test to assert a flag row exists for `intervention_worked_for_disease` on both processed sources and that a second `save_claims()` call makes no additional LLM calls. Add a test with two configured claim types where one source already has a flag for the first type; assert that only the missing type is requested and flagged. Patch `CLAIM_PROMPTS` in that test so it does not depend on future production prompt additions.

The zero-claim assertion should check persisted processing state directly:

```python
self.assertTrue(ClaimsGenerationFlags.objects.filter(
    publication=publication,
    generated_claim_type='intervention_worked_for_disease',
).exists())
```

- [ ] **Step 2: Run the focused claim tests and confirm the new assertions fail**

Run `docker compose --env-file etc/.env run --rm django-app python django_app/manage.py test tests.django_app.lib.test_claims`. Expected: tests fail because `save_claims()` still relies on the boolean fields and creates no generation flags.

- [ ] **Step 3: Process only missing types and flag each completed type**

Refactor the claim extraction flow to process one `claim_type` across all source bundles at a time. For each eligible source, load its existing `claims_generation_flags` types, skip those types, and process each remaining key from `CLAIM_PROMPTS`. After a type has completed across all bundles, create its flag with `get_or_create()` or equivalent uniqueness-safe insertion. A type with no valid claim suggestions still receives a flag after its processing finishes. If processing raises before completion, do not create that type's flag.

- [ ] **Step 4: Remove boolean-based selection and updates**

Keep selecting only sources with NERs, but determine completion from their flag rows. Remove `claims_generated=False` from the query and remove the `update(claims_generated=True)` write. Do not otherwise change claim validation or the `save_claims()` return count.

- [ ] **Step 5: Run the focused claim tests**

Run `docker compose --env-file etc/.env run --rm django-app python django_app/manage.py test tests.django_app.lib.test_claims`. Expected: successful claims, zero-claim completion, per-type skipping, and repeated-call behavior all pass.

- [ ] **Step 6: Commit claim processing changes**

```bash
git add django_app/lib/claims.py tests/django_app/lib/test_claims.py
git commit -m "feat: track processed claim types"
```

### Task 3: Clear flags when refetch discards claims

**Files:**
- Modify: `django_app/lib/refetch.py`
- Modify: `django_app/lib/clinical_trials.py`
- Modify: `django_app/lib/pubmed.py`
- Test: `tests/django_app/lib/test_refetch.py`
- Test: `tests/django_app/lib/test_clinical_trials.py`
- Test: `tests/django_app/lib/test_pubmed.py`

**Interfaces:**
- Refetch removes all generation flags owned by the refreshed source in the same transaction that removes its claims and NERs.
- Fetch/upsert no longer changes the retained boolean field.

- [ ] **Step 1: Add refetch flag cleanup assertions**

In both publication and trial refetch tests, create a `ClaimsGenerationFlags` row before calling `refetch_source()`, then assert the row is deleted after successful refetch. In the failure/rollback test, create a flag before the failing refetch and assert it remains after the transaction rolls back.

The successful refetch assertion should check that no source flags remain:

```python
self.assertFalse(ClaimsGenerationFlags.objects.filter(publication=self.publication).exists())
```

- [ ] **Step 2: Add fetch/upsert boolean stability assertions**

For existing trial and publication upsert tests, set `claims_generated=True` before a second upsert and assert the value stays true. This confirms fetch code no longer toggles the legacy field while it remains available for consistency checks.

- [ ] **Step 3: Run focused refetch and upsert tests and confirm they fail**

Run `docker compose --env-file etc/.env run --rm django-app python django_app/manage.py test tests.django_app.lib.test_refetch tests.django_app.lib.test_clinical_trials tests.django_app.lib.test_pubmed`. Expected: the new cleanup and stability assertions fail before the implementation changes.

- [ ] **Step 4: Delete flags with derived claims during refetch**

In `refetch_source()`, delete flags for the locked source alongside `source.claims.all().delete()` within the existing `transaction.atomic()` block. Leave flags untouched if refresh fails, relying on the transaction rollback already used by this flow.

- [ ] **Step 5: Stop resetting legacy booleans during upsert**

Remove `"claims_generated": False` from the defaults passed by `fetch_and_upsert_trial()` and `fetch_and_upsert_publication()`. Do not drop the fields or add writes to them elsewhere.

- [ ] **Step 6: Run focused refetch and upsert tests**

Run `docker compose --env-file etc/.env run --rm django-app python django_app/manage.py test tests.django_app.lib.test_refetch tests.django_app.lib.test_clinical_trials tests.django_app.lib.test_pubmed`. Expected: successful refetch clears flags, failed refetch preserves them, and upserts leave legacy booleans unchanged.

- [ ] **Step 7: Commit refetch and upsert changes**

```bash
git add django_app/lib/refetch.py django_app/lib/clinical_trials.py django_app/lib/pubmed.py tests/django_app/lib/test_refetch.py tests/django_app/lib/test_clinical_trials.py tests/django_app/lib/test_pubmed.py
git commit -m "feat: clear claim flags on source refetch"
```

### Task 4: Review the full change and retain legacy fields

**Files:**
- Review: `django_app/core/models.py`
- Review: `django_app/core/migrations/0022_claims_generation_flags.py`
- Review: `django_app/lib/claims.py`
- Review: `django_app/lib/refetch.py`
- Review: `django_app/lib/clinical_trials.py`
- Review: `django_app/lib/pubmed.py`

- [ ] **Step 1: Search for remaining runtime boolean writes**

Search Python source outside migrations for `claims_generated`. Expected: model field declarations and deliberate read-only consistency/test references only; no runtime query filter or assignments.

- [ ] **Step 2: Run the relevant core and library test suites**

Run `./bin/test`. Expected: environment verification and the complete Django test suite pass in disposable test databases.

- [ ] **Step 3: Confirm the migration does not remove old fields**

Review migration `0022` and the model state. Expected: it creates/backfills `ClaimsGenerationFlags` and contains no `RemoveField` operation for either `claims_generated` field.

- [ ] **Step 4: Commit any final fixes**

Commit only files in this feature with a message describing the correction.
