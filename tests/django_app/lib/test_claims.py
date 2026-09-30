from unittest.mock import patch

from django.test import TestCase

from core.models import Chunk, Claim, Disease, Intervention, Ner, Publication, Trial
from lib.claims import save_claims


class ClaimExtractionTestCase(TestCase):
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

        self.assertEqual(len(prompts), 4)  # title and official_title have no claim and are retried
        claim = Claim.objects.get()
        self.assertEqual((claim.publication, claim.chunk, claim.section, claim.trial),
                         (publication, chunk, "abstract", None))
        self.assertEqual(list(claim.ners.all()), [ner])
        self.assertEqual(list(claim.diseases.all()), [disease])
        self.assertFalse(claim.interventions.exists())
        self.assertEqual(claim.meta, {"evidence": "Imatinib improved leukemia outcomes.",
                                       "ner_ids": [ner.pk]})
        self.assertTrue(any(f'"id": {ner.pk}' in prompt for prompt in prompts))
        self.assertTrue(any("Imatinib" in prompt and "Drug" in prompt for prompt in prompts))

    def test_does_not_save_claim_without_verbatim_evidence(self):
        publication = Publication.objects.create(pmid="456", title="Study of leukemia")
        ner = Ner.objects.create(publication=publication, section="title", text="leukemia", label=["Disease"],
                                 start=9, end=17, score=0.9, method=["gliner"], model_name=["model"])
        with patch("lib.claims.extract_structured", side_effect=lambda response_model, prompt: response_model(
                claims=[{"evidence": "Evidence that is not in this title.", "ner_ids": [ner.pk]}])):
            save_claims()
        self.assertFalse(Claim.objects.exists())

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
