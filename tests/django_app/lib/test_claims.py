from unittest.mock import patch

from django.test import TestCase

from core.models import (
    Chunk, Claim, ClaimGroup, ClaimsGenerationFlags, Disease, Intervention, Ner, Publication, Trial,
)
from lib.claims import create_claim, save_claims
from lib.claim_groups import (merge_duplicate_claim_groups, process_claims_to_claim_groups,
                              process_unsynced_claim_groups)


class ClaimExtractionBasicsTestCase(TestCase):
    def test_saves_supported_claims_per_bundle_and_skips_processed_sources(self):
        publication = Publication.objects.create(pmid="123", title="Imatinib worked in leukemia")
        chunk = Chunk.objects.create(publication=publication, section="abstract", sequ=0,
                                     body="Imatinib improved leukemia outcomes.")
        trial = Trial.objects.create(nct_id="NCT123", title="Imatinib trial", official_title="Leukemia study")
        Ner.objects.create(publication=publication, section="title", text="Imatinib", label=["Drug"],
                           start=0, end=8, score=0.9, method=["gliner"], model_name=["model"])
        disease = Disease.objects.create(name="Leukemia")
        ner = Ner.objects.create(publication=publication, chunk=chunk, text="leukemia", label=["Disease"],
                                 disease=disease, start=18, end=26, score=0.9, method=["gliner"], model_name=["model"])
        Ner.objects.create(trial=trial, section="official_title", text="Leukemia", label=["Disease"],
                           start=0, end=8, score=0.9, method=["gliner"], model_name=["model"])
        prompts = []

        def extract(response_model, prompt):
            prompts.append(prompt)
            if "Imatinib improved leukemia outcomes." in prompt:
                return response_model(claims=[{"evidence": "Imatinib improved leukemia outcomes.",
                                               "ner_ids": [ner.pk]}])
            return response_model(claims=[])

        with patch("lib.claims.extract_structured", side_effect=extract):
            save_claims()
            save_claims()

        self.assertEqual(len(prompts), 3)  # zero-claim sources are marked processed, not retried
        self.assertTrue(publication.claims_generation_flags.filter(
            generated_claim_type="intervention_worked_for_disease",
        ).exists())
        self.assertTrue(trial.claims_generation_flags.filter(
            generated_claim_type="intervention_worked_for_disease",
        ).exists())
        claim = Claim.objects.get()
        self.assertEqual((claim.publication, claim.chunk, claim.section, claim.trial),
                         (publication, chunk, "abstract", None))
        self.assertEqual(list(claim.ners.all()), [ner])
        self.assertEqual(list(claim.diseases.all()), [disease])
        self.assertFalse(claim.interventions.exists())
        self.assertEqual(claim.evidence, "Imatinib improved leukemia outcomes.")
        self.assertEqual(claim.meta, {"ner_ids": [ner.pk]})
        self.assertEqual(claim.status, "pending")
        self.assertTrue(any(f'"id": {ner.pk}' in prompt for prompt in prompts))
        self.assertTrue(any("Imatinib" in prompt and "Drug" in prompt for prompt in prompts))

    def test_processes_only_missing_claim_types_for_a_source(self):
        publication = Publication.objects.create(pmid="789", title="Study of leukemia")
        Ner.objects.create(publication=publication, section="title", text="leukemia", label=["Disease"],
                           start=9, end=17, score=0.9, method=["gliner"], model_name=["model"])
        ClaimsGenerationFlags.objects.create(publication=publication, generated_claim_type="first_type")
        prompts = []

        def extract(response_model, prompt):
            prompts.append(prompt)
            return response_model(claims=[])

        with patch("lib.claims.CLAIM_PROMPTS", {
                "first_type": "FIRST_TYPE_INSTRUCTION", "second_type": "SECOND_TYPE_INSTRUCTION"}), \
                patch("lib.claims.extract_structured", side_effect=extract):
            save_claims()

        self.assertEqual(len(prompts), 1)
        self.assertIn("SECOND_TYPE_INSTRUCTION", prompts[0])
        self.assertTrue(publication.claims_generation_flags.filter(generated_claim_type="first_type").exists())
        self.assertTrue(publication.claims_generation_flags.filter(generated_claim_type="second_type").exists())

    def test_does_not_save_claim_without_verbatim_evidence(self):
        publication = Publication.objects.create(pmid="456", title="Study of leukemia")
        ner = Ner.objects.create(publication=publication, section="title", text="leukemia", label=["Disease"],
                                 start=9, end=17, score=0.9, method=["gliner"], model_name=["model"])
        with patch("lib.claims.extract_structured", side_effect=lambda response_model, prompt: response_model(
                claims=[{"evidence": "Evidence that is not in this title.", "ner_ids": [ner.pk]}])):
            save_claims()
        self.assertFalse(Claim.objects.exists())


class ClaimGroupingTestCase(TestCase):
    def make_claim(self, evidence, diseases=(), interventions=()):
        return create_claim(section='title', claim_type='test', evidence=evidence,
                            diseases=diseases, interventions=interventions)

    def test_group_status_tracks_claim_saves_moves_and_deletes(self):
        group = ClaimGroup.objects.create()
        other = ClaimGroup.objects.create()
        first = Claim.objects.create(section='title', claim_type='test', claim_group=group,
                                     status='approved')
        group.refresh_from_db()
        self.assertEqual(group.status, 'approved')
        second = Claim.objects.create(section='title', claim_type='test', claim_group=group)
        group.refresh_from_db()
        self.assertEqual(group.status, 'pending')
        second.status = 'rejected'
        second.save(update_fields=['status'])
        group.refresh_from_db()
        self.assertEqual(group.status, 'approved')
        first.status = 'rejected'
        first.save(update_fields=['status'])
        group.refresh_from_db()
        self.assertEqual(group.status, 'rejected')
        first.claim_group = other
        first.save(update_fields=['claim_group'])
        other.refresh_from_db()
        self.assertEqual(other.status, 'rejected')
        first.delete()
        other.refresh_from_db()
        self.assertEqual(other.status, 'pending')
        second.delete()
        group.refresh_from_db()
        self.assertEqual(group.status, 'pending')

    def test_bulk_regroup_recomputes_status_for_old_and_new_groups(self):
        first = self.make_claim('first')
        first.status = 'approved'
        first.save(update_fields=['status'])
        second = self.make_claim('second')
        old_group = second.claim_group
        second.status = 'approved'
        second.save(update_fields=['status'])
        old_group.refresh_from_db()
        self.assertEqual(old_group.status, 'approved')

        disease = Disease.objects.create(name='Regroup disease')
        second.diseases.add(disease)
        first.diseases.add(disease)
        first.refresh_from_db()
        old_group.refresh_from_db()
        first.claim_group.refresh_from_db()
        self.assertFalse(old_group.claims.exists(), list(old_group.claims.values_list('pk', 'status')))
        self.assertEqual(old_group.status, 'pending')
        self.assertEqual(first.claim_group.status, 'approved')

    def test_exact_sets_and_empty_sets_pair_across_sources(self):
        disease = Disease.objects.create(name='Disease 1')
        other = Disease.objects.create(name='Disease 2')
        intervention = Intervention.objects.create(name='Drug 1')
        first = create_claim(section='title', claim_type='positive', evidence='first',
                             publication=Publication.objects.create(pmid='group-first', title='Source'),
                             diseases=[disease], interventions=[intervention])
        self.assertIsNone(first.claim_group_id)
        different = self.make_claim('different', [disease, other], [intervention])
        self.assertIsNone(different.claim_group_id)
        second = create_claim(section='title', claim_type='negative', evidence='second',
                              trial=Trial.objects.create(nct_id='NCT00000001', title='Source'),
                              diseases=[disease], interventions=[intervention])
        first.refresh_from_db()
        self.assertEqual(first.claim_group_id, second.claim_group_id)
        self.assertCountEqual(first.claim_group.diseases.all(), [disease])
        self.assertCountEqual(first.claim_group.interventions.all(), [intervention])
        third = self.make_claim('third', [disease], [intervention])
        self.assertEqual(third.claim_group_id, first.claim_group_id)
        empty1 = self.make_claim('empty 1')
        empty2 = self.make_claim('empty 2')
        empty1.refresh_from_db()
        self.assertEqual(empty1.claim_group_id, empty2.claim_group_id)
        self.assertNotEqual(empty1.claim_group_id, first.claim_group_id)
        self.assertEqual(ClaimGroup.objects.count(), 2)

    def test_entity_change_moves_claim_and_retains_empty_group(self):
        disease = Disease.objects.create(name='Disease')
        first = self.make_claim('first', [disease])
        second = self.make_claim('second', [disease])
        old_group = second.claim_group
        second.diseases.clear()
        second.refresh_from_db()
        self.assertIsNone(second.claim_group_id)
        self.assertTrue(ClaimGroup.objects.filter(pk=old_group.pk).exists())
        first.diseases.clear()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.claim_group_id, second.claim_group_id)
        self.assertNotEqual(first.claim_group_id, old_group.pk)
        self.assertTrue(ClaimGroup.objects.filter(pk=old_group.pk, synced=False).exists())
        second.diseases.add(disease)
        first.diseases.add(disease)
        first.refresh_from_db()
        self.assertEqual(first.claim_group_id, old_group.pk)

    def test_merge_duplicate_groups_moves_claims_and_marks_winner_stale(self):
        disease = Disease.objects.create(name='Disease')
        winner = ClaimGroup.objects.create(synced=True, evidence_summary='old')
        loser = ClaimGroup.objects.create(synced=True)
        winner.diseases.add(disease)
        loser.diseases.add(disease)
        first = self.make_claim('first', [disease])
        second = self.make_claim('second', [disease])
        Claim.objects.filter(pk=second.pk).update(claim_group=loser)
        merge_duplicate_claim_groups()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.claim_group_id, winner.pk)
        self.assertEqual(second.claim_group_id, winner.pk)
        self.assertFalse(ClaimGroup.objects.filter(pk=loser.pk).exists())
        winner.refresh_from_db()
        self.assertFalse(winner.synced)

    def test_summary_refreshes_only_unsynced_and_invalidates_on_evidence_change(self):
        self.make_claim('Benefit A')
        second = self.make_claim('Benefit B')
        group = second.claim_group
        with patch('lib.claim_groups.extract_structured', side_effect=lambda model, prompt, **kwargs:
                   model(summary='Balanced summary')) as llm:
            process_unsynced_claim_groups()
            self.assertEqual(llm.call_count, 1)
            self.assertIn('Benefit A', llm.call_args.args[1])
            self.assertIn('Benefit B', llm.call_args.args[1])
            process_unsynced_claim_groups()
            self.assertEqual(llm.call_count, 1)
        group.refresh_from_db()
        self.assertEqual(group.evidence_summary, 'Balanced summary')
        self.assertTrue(group.synced)
        second.evidence = 'Updated benefit'
        second.save(update_fields=['evidence'])
        group.refresh_from_db()
        self.assertFalse(group.synced)

    def test_review_notes_do_not_invalidate_evidence_summary(self):
        self.make_claim('First')
        second = self.make_claim('Second')
        group = second.claim_group
        ClaimGroup.objects.filter(pk=group.pk).update(synced=True)
        second.notes = 'reviewed'
        second.save(update_fields=['notes'])
        group.refresh_from_db()
        self.assertTrue(group.synced)

    def test_backfill_pairs_claims_created_without_helper(self):
        first = Claim.objects.create(section='title', claim_type='first')
        second = Claim.objects.create(section='title', claim_type='second')
        process_claims_to_claim_groups()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.claim_group_id, second.claim_group_id)

    def test_change_during_summarization_remains_unsynced(self):
        self.make_claim('Original')
        second = self.make_claim('Other')
        group = second.claim_group

        def summarize(model, prompt):
            second.evidence = 'Changed while summarizing'
            second.save(update_fields=['evidence'])
            return model(summary='Outdated summary')

        with patch('lib.claim_groups.extract_structured', side_effect=summarize):
            process_unsynced_claim_groups()
        group.refresh_from_db()
        self.assertFalse(group.synced)

    def test_group_updates_and_claim_deletion_invalidate_summary(self):
        self.make_claim('First')
        second = self.make_claim('Second')
        group = second.claim_group
        ClaimGroup.objects.filter(pk=group.pk).update(synced=True)
        group.meta = {'reviewed': True}
        group.save(update_fields=['meta'])
        group.refresh_from_db()
        self.assertFalse(group.synced)
        ClaimGroup.objects.filter(pk=group.pk).update(synced=True)
        second.delete()
        group.refresh_from_db()
        self.assertFalse(group.synced)

    def test_changing_group_signature_disconnects_mismatched_claims(self):
        self.make_claim('First')
        second = self.make_claim('Second')
        old_group = second.claim_group
        disease = Disease.objects.create(name='New disease')
        old_group.diseases.add(disease)
        second.refresh_from_db()
        self.assertNotEqual(second.claim_group_id, old_group.pk)
        self.assertFalse(old_group.claims.exists())

class ClaimExtractionTestCase(TestCase):
    def test_trial_chunk_claim_keeps_trial_and_section(self):
        trial = Trial.objects.create(nct_id="NCT789", title="Trial results")
        chunk = Chunk.objects.create(trial=trial, section="summary", sequ=0, body="Drug A improved cancer outcomes.")
        intervention = Intervention.objects.create(name="Drug A")
        ner = Ner.objects.create(trial=trial, chunk=chunk, text="Drug A", label=["Drug"], intervention=intervention,
                                 start=0, end=6, score=0.9, method=["gliner"], model_name=["model"])
        with patch("lib.claims.extract_structured", side_effect=lambda response_model, prompt: response_model(
                claims=[{"evidence": "Drug A improved cancer outcomes.", "ner_ids": [ner.pk]}])):
            save_claims()
        claim = Claim.objects.get()
        self.assertEqual((claim.trial, claim.chunk, claim.section, claim.publication),
                         (trial, chunk, "summary", None))
        self.assertEqual(list(claim.interventions.all()), [intervention])

    def test_links_only_selected_ners_and_all_their_entities(self):
        publication = Publication.objects.create(pmid="multi", title="Combination worked")
        chunk = Chunk.objects.create(publication=publication, section="abstract", sequ=0,
                                     body="Drug A and Drug B improved cancer A and cancer B outcomes.")
        interventions = [Intervention.objects.create(name=name) for name in ("Drug A", "Drug B")]
        diseases = [Disease.objects.create(name=name) for name in ("cancer A", "cancer B")]
        selected = [Ner.objects.create(publication=publication, chunk=chunk, text=entity.name, label=["Drug" if kind == "intervention" else "Disease"],
                                       **{kind: entity}, start=0, end=6, score=0.9)
                    for kind, entities in (("intervention", interventions), ("disease", diseases)) for entity in entities]
        irrelevant = Disease.objects.create(name="unrelated")
        unselected = Ner.objects.create(publication=publication, chunk=chunk, text="unrelated", label=["Disease"],
                                        disease=irrelevant, start=0, end=9, score=0.9)
        foreign = Ner.objects.create(publication=Publication.objects.create(pmid="other", title="Other"),
                                     text="wrong source", label=["Drug"], start=0, end=12, score=0.9)
        with patch("lib.claims.extract_structured", side_effect=lambda model, prompt: model(claims=[{
                "evidence": chunk.body, "ner_ids": [ner.pk for ner in selected] + [foreign.pk]}])):
            save_claims()

        claim = Claim.objects.get()
        self.assertCountEqual(claim.ners.all(), selected)
        self.assertCountEqual(claim.interventions.all(), interventions)
        self.assertCountEqual(claim.diseases.all(), diseases)
        self.assertNotIn(unselected, claim.ners.all())
        self.assertEqual(claim.meta["ner_ids"], [ner.pk for ner in selected])

    def test_ignores_claims_without_valid_supporting_ner(self):
        publication = Publication.objects.create(pmid="unsupported", title="Study")
        Ner.objects.create(publication=publication, section="title", text="Study", label=["Disease"],
                           start=0, end=5, score=0.9)
        with patch("lib.claims.extract_structured", side_effect=lambda model, prompt: model(claims=[{
                "evidence": "Study", "ner_ids": [987654321]}])):
            save_claims()
        self.assertFalse(Claim.objects.exists())
