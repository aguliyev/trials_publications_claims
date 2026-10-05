import importlib

from django.test import TestCase

from core.models import Claim, ClaimGroup, Disease, Genetic, Intervention, Ner, Publication, Trial
from lib.clinical_trials import fetch_and_upsert_trial
from lib.diseases import save_ner_diseases
from lib.interventions import save_ner_interventions


class NerEntitiesTest(TestCase):
    def genetics_functions(self):
        spec = importlib.util.find_spec('lib.genetics')
        self.assertIsNotNone(spec, 'Genetic linking module should exist')
        module = importlib.import_module('lib.genetics')
        return module.save_ner_genetic

    def make_ner(self, owner, text, labels, links=None):
        return Ner.objects.create(
            **{owner._meta.model_name: owner}, text=text, label=labels,
            links=links or [], start=0, end=len(text), score=0.9,
        )

    def test_diseases_match_mesh_then_name_and_link_both_owners(self):
        trial = Trial.objects.create(nct_id="NCT00000001", title="Trial")
        publication = Publication.objects.create(pmid="123", title="Paper")
        existing = Disease.objects.create(name="leukemia", mesh="MESH:D015464")
        by_mesh = self.make_ner(trial, "chronic myeloid leukemia", ["DISEASE", "Cancer"],
                                [{"id": "MESH:D015464", "score": 203.8}])
        by_name = self.make_ner(publication, "Leukemia", ["disease"])
        other = self.make_ner(trial, "imatinib", ["Drug"])

        save_ner_diseases()
        save_ner_diseases()

        by_mesh.refresh_from_db()
        by_name.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(by_mesh.disease, existing)
        self.assertEqual(by_name.disease, existing)
        self.assertIsNone(other.disease)
        self.assertEqual(Disease.objects.count(), 1)
        self.assertEqual(list(trial.diseases.all()), [existing])
        self.assertEqual(list(publication.diseases.all()), [existing])

    def test_diseases_enrich_existing_name_with_mesh(self):
        publication = Publication.objects.create(pmid="456", title="Paper")
        existing = Disease.objects.create(name="Leukemia")
        mention = self.make_ner(publication, "leukemia", ["Cancer"], [{"id": "MESH:D015464"}])

        save_ner_diseases()

        mention.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(mention.disease, existing)
        self.assertEqual(existing.mesh, "MESH:D015464")

    def test_interventions_create_without_mesh_and_match_names_case_insensitively(self):
        trial = Trial.objects.create(nct_id="NCT00000002", title="Trial")
        publication = Publication.objects.create(pmid="789", title="Paper")
        first = self.make_ner(trial, "imatinib", ["CHEM", "simple_CHEMICAL"])
        second = self.make_ner(publication, "Imatinib", ["Drug", "Chemical"])
        other = self.make_ner(trial, "leukemia", ["Disease"])

        save_ner_interventions()
        save_ner_interventions()

        first.refresh_from_db()
        second.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(first.intervention, second.intervention)
        self.assertEqual(first.intervention.mesh, "")
        self.assertIsNone(other.intervention)
        self.assertEqual(Intervention.objects.count(), 1)
        self.assertEqual(list(trial.interventions.all()), [first.intervention])
        self.assertEqual(list(publication.interventions.all()), [first.intervention])

    def test_interventions_reuse_mesh_for_different_name(self):
        publication = Publication.objects.create(pmid="999", title="Paper")
        existing = Intervention.objects.create(name="old name", mesh="MESH:D000001")
        mention = self.make_ner(publication, "new name", ["Chemical"], [{"id": "MESH:D000001"}])

        save_ner_interventions()

        mention.refresh_from_db()
        self.assertEqual(mention.intervention, existing)
        self.assertEqual(Intervention.objects.count(), 1)

    def test_ner_enriches_entities_created_by_trial_fetch(self):
        trial = fetch_and_upsert_trial({"protocolSection": {
            "identificationModule": {"nctId": "NCT00000003", "briefTitle": "Trial"},
            "conditionsModule": {"conditions": ["Leukemia"]},
            "armsInterventionsModule": {"interventions": [{"name": "Imatinib"}]},
        }})
        disease = trial.diseases.get()
        intervention = trial.interventions.get()
        disease_ner = self.make_ner(trial, "leukemia", ["Disease"], [{"id": "MESH:D015464"}])
        intervention_ner = self.make_ner(trial, "imatinib", ["Drug"], [{"id": "MESH:D000001"}])

        save_ner_diseases()
        save_ner_interventions()

        disease.refresh_from_db()
        intervention.refresh_from_db()
        disease_ner.refresh_from_db()
        intervention_ner.refresh_from_db()
        self.assertEqual(disease_ner.disease, disease)
        self.assertEqual(intervention_ner.intervention, intervention)
        self.assertEqual(disease.mesh, "MESH:D015464")
        self.assertEqual(intervention.mesh, "MESH:D000001")
        self.assertEqual(Disease.objects.count(), 1)
        self.assertEqual(Intervention.objects.count(), 1)

    def test_genetics_match_casefolded_labels_mesh_and_names_for_both_owners(self):
        save_ner_genetic = self.genetics_functions()
        trial = Trial.objects.create(nct_id='NCT00000004', title='Trial')
        publication = Publication.objects.create(pmid='1000', title='Paper')
        existing = Genetic.objects.create(name='KRAS', mesh='MESH:D020540')
        by_mesh = self.make_ner(trial, 'KRAS G12C', ['GENE_OR_GENE_PRODUCT'],
                                [{'id': 'MESH:D020540'}])
        by_name = self.make_ner(publication, 'kras', ['gEnE'])
        other = self.make_ner(trial, 'BRAF', ['Biomarker'])
        blank = self.make_ner(publication, '   ', ['Gene'])

        save_ner_genetic()
        save_ner_genetic()

        for mention in (by_mesh, by_name, other, blank):
            mention.refresh_from_db()
        self.assertEqual(by_mesh.genetic, existing)
        self.assertEqual(by_name.genetic, existing)
        self.assertIsNone(other.genetic)
        self.assertIsNone(blank.genetic)
        self.assertEqual(Genetic.objects.count(), 1)
        self.assertEqual(list(trial.genetics.all()), [existing])
        self.assertEqual(list(publication.genetics.all()), [existing])

    def test_genetic_linker_trims_and_truncates_names_without_populating_claims_or_groups(self):
        save_ner_genetic = self.genetics_functions()
        trial = Trial.objects.create(nct_id='NCT00000005', title='Trial')
        mention = self.make_ner(trial, f"  {'X' * 260}  ", ['Gene'])
        claim = Claim.objects.create(trial=trial, section='title', claim_type='gene_association')
        group = ClaimGroup.objects.create(claim_type='gene_association')

        save_ner_genetic()

        mention.refresh_from_db()
        self.assertEqual(mention.genetic.name, 'X' * 255)
        self.assertEqual(claim.genetics.count(), 0)
        self.assertEqual(group.genetics.count(), 0)
