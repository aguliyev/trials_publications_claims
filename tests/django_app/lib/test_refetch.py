from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase

from core.models import (
    Chunk, Claim, ClaimGroup, ClaimsGenerationFlags, Disease, Intervention, Ner, Publication,
    PublicationTrial, Trial,
)
from core.claim_trails import create_claim_trail


class RefetchSourceTestCase(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(name='Existing disease')
        self.intervention = Intervention.objects.create(name='Existing intervention')
        self.trial = Trial.objects.create(nct_id='NCT03026140', title='Old trial',
                                          references=[{'pmid': '41115454', 'type': 'RESULT'}])
        self.publication = Publication.objects.create(pmid='41115454', title='Old paper')
        self.other = Publication.objects.create(pmid='39278994', title='Unrelated paper')
        self.trial.diseases.add(self.disease)
        self.trial.interventions.add(self.intervention)
        self.publication.diseases.add(self.disease)
        self.publication.interventions.add(self.intervention)
        self.other.diseases.add(self.disease)
        self.group = ClaimGroup.objects.create()

    def add_derivatives(self, source):
        owner = {'trial': source} if isinstance(source, Trial) else {'publication': source}
        ner = Ner.objects.create(**owner, section='title', text='Old', label=['DISEASE'],
                                 start=0, end=3, score=1, method=[], model_name=[], links=[],
                                 disease=self.disease)
        claim = Claim.objects.create(**owner, section='title', claim_type='old',
                                     claim_group=self.group)
        claim.ners.add(ner)
        claim.diseases.add(self.disease)
        claim.interventions.add(self.intervention)
        return ner, claim

    def test_publication_refetch_replaces_derivatives_but_preserves_entities_and_other_records(self):
        from lib.refetch import refetch_source

        ner, claim = self.add_derivatives(self.publication)
        flag = ClaimsGenerationFlags.objects.create(
            publication=self.publication, generated_claim_type='test',
        )
        trail = create_claim_trail(claim, status_from=claim.status)
        snapshot_before_refetch = deepcopy(trail.meta)
        other_ner, other_claim = self.add_derivatives(self.other)
        article = {'pmid': self.publication.pmid, 'title': 'Fresh paper', 'abstract': 'New abstract'}
        with patch('lib.refetch.PubMedFetcher') as fetcher:
            fetcher.return_value.article_by_pmid.return_value = article
            result = refetch_source(self.publication)

        self.assertEqual(result.pk, self.publication.pk)
        self.publication.refresh_from_db()
        self.assertEqual(self.publication.title, 'Fresh paper')
        self.assertFalse(Ner.objects.filter(pk=ner.pk).exists())
        self.assertFalse(Claim.objects.filter(pk=claim.pk).exists())
        self.assertFalse(ClaimsGenerationFlags.objects.filter(pk=flag.pk).exists())
        trail.refresh_from_db()
        self.assertEqual(trail.meta, snapshot_before_refetch)
        self.assertEqual(trail.publication_id, self.publication.pk)
        self.assertTrue(Ner.objects.filter(pk=other_ner.pk).exists())
        self.assertTrue(Claim.objects.filter(pk=other_claim.pk).exists())
        self.assertTrue(Disease.objects.filter(pk=self.disease.pk).exists())
        self.assertTrue(Intervention.objects.filter(pk=self.intervention.pk).exists())
        self.assertFalse(self.publication.diseases.filter(pk=self.disease.pk).exists())
        self.assertFalse(self.publication.interventions.filter(pk=self.intervention.pk).exists())
        self.assertTrue(self.other.diseases.filter(pk=self.disease.pk).exists())

    def test_trial_refetch_only_loads_newly_referenced_publications_when_previously_complete(self):
        from lib.refetch import refetch_source

        ner, claim = self.add_derivatives(self.trial)
        flag = ClaimsGenerationFlags.objects.create(trial=self.trial, generated_claim_type='test')
        trail = create_claim_trail(claim, status_from=claim.status)
        snapshot_before_refetch = deepcopy(trail.meta)
        existing_ner, existing_claim = self.add_derivatives(self.publication)
        study = {'protocolSection': {
            'identificationModule': {'nctId': self.trial.nct_id, 'briefTitle': 'Fresh trial'},
            'referencesModule': {'references': [
                {'pmid': self.publication.pmid, 'type': 'RESULT'},
                {'pmid': '55555555', 'type': 'DERIVED'},
            ]},
        }}
        with patch('lib.refetch.fetch_study_v2', return_value=study), \
                patch('lib.pubmed.PubMedFetcher') as fetcher:
            fetcher.return_value.article_by_pmid.return_value = {'pmid': '55555555', 'title': 'New paper'}
            result = refetch_source(self.trial)

        self.assertEqual(result.pk, self.trial.pk)
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.title, 'Fresh trial')
        self.assertFalse(Ner.objects.filter(pk=ner.pk).exists())
        self.assertFalse(Claim.objects.filter(pk=claim.pk).exists())
        self.assertFalse(ClaimsGenerationFlags.objects.filter(pk=flag.pk).exists())
        trail.refresh_from_db()
        self.assertEqual(trail.meta, snapshot_before_refetch)
        self.assertEqual(trail.trial_id, self.trial.pk)
        self.assertEqual(Publication.objects.get(pk=self.publication.pk).title, 'Old paper')
        self.assertTrue(Ner.objects.filter(pk=existing_ner.pk).exists())
        self.assertTrue(Claim.objects.filter(pk=existing_claim.pk).exists())
        self.assertEqual(fetcher.return_value.article_by_pmid.call_count, 1)
        self.assertTrue(PublicationTrial.objects.filter(trial=self.trial, publication__pmid='55555555').exists())
        self.assertTrue(Disease.objects.filter(pk=self.disease.pk).exists())
        self.assertFalse(self.trial.diseases.filter(pk=self.disease.pk).exists())
        self.assertTrue(Intervention.objects.filter(pk=self.intervention.pk).exists())
        self.assertFalse(self.trial.interventions.filter(pk=self.intervention.pk).exists())

    def test_partially_loaded_trial_does_not_fetch_missing_publications(self):
        from lib.refetch import refetch_source

        self.trial.references.append({'pmid': '55555555', 'type': 'DERIVED'})
        self.trial.save()
        study = {'protocolSection': {
            'identificationModule': {'nctId': self.trial.nct_id, 'briefTitle': 'Fresh trial'},
            'referencesModule': {'references': [
                {'pmid': self.publication.pmid, 'type': 'RESULT'},
                {'pmid': '55555555', 'type': 'DERIVED'},
            ]},
        }}
        with patch('lib.refetch.fetch_study_v2', return_value=study), \
                patch('lib.pubmed.PubMedFetcher') as fetcher:
            refetch_source(self.trial)
        fetcher.assert_not_called()
        self.assertFalse(Publication.objects.filter(pmid='55555555').exists())

    def test_trial_counts_distinct_publications_not_duplicate_relation_rows(self):
        from lib.refetch import refetch_source

        PublicationTrial.objects.create(trial=self.trial, publication=self.publication, relation='BACKGROUND')
        study = {'protocolSection': {
            'identificationModule': {'nctId': self.trial.nct_id, 'briefTitle': 'Fresh trial'},
            'referencesModule': {'references': [
                {'pmid': self.publication.pmid, 'type': 'RESULT'},
                {'pmid': '55555555', 'type': 'DERIVED'},
            ]},
        }}
        with patch('lib.refetch.fetch_study_v2', return_value=study), \
                patch('lib.pubmed.PubMedFetcher') as fetcher:
            fetcher.return_value.article_by_pmid.return_value = {'pmid': '55555555', 'title': 'New paper'}
            refetch_source(self.trial)
        self.assertTrue(Publication.objects.filter(pmid='55555555').exists())

    def test_source_failure_keeps_existing_derivatives(self):
        from lib.refetch import refetch_source

        ner, claim = self.add_derivatives(self.trial)
        with patch('lib.refetch.fetch_study_v2', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                refetch_source(self.trial)
        self.assertTrue(Ner.objects.filter(pk=ner.pk).exists())
        self.assertTrue(Claim.objects.filter(pk=claim.pk).exists())
        self.assertTrue(self.trial.diseases.filter(pk=self.disease.pk).exists())

    def test_claim_owned_by_source_chunk_is_removed_even_without_source_fk(self):
        from lib.refetch import refetch_source

        chunk = Chunk.objects.create(trial=self.trial, section='summary', sequ=0, body='Old body')
        claim = Claim.objects.create(chunk=chunk, section='summary', claim_type='old')
        study = {'protocolSection': {'identificationModule': {
            'nctId': self.trial.nct_id, 'briefTitle': 'Fresh trial'}}}
        with patch('lib.refetch.fetch_study_v2', return_value=study):
            refetch_source(self.trial)
        self.assertFalse(Claim.objects.filter(pk=claim.pk).exists())

    def test_missing_publication_fetch_failure_rolls_back_cleanup(self):
        from lib.refetch import refetch_source

        ner, claim = self.add_derivatives(self.trial)
        flag = ClaimsGenerationFlags.objects.create(trial=self.trial, generated_claim_type='test')
        study = {'protocolSection': {
            'identificationModule': {'nctId': self.trial.nct_id, 'briefTitle': 'Fresh trial'},
            'referencesModule': {'references': [{'pmid': '55555555', 'type': 'RESULT'}]},
        }}
        with patch('lib.refetch.fetch_study_v2', return_value=study), \
                patch('lib.pubmed.PubMedFetcher') as fetcher:
            fetcher.return_value.article_by_pmid.side_effect = RuntimeError('unavailable')
            with self.assertRaises(RuntimeError):
                refetch_source(self.trial)
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.title, 'Old trial')
        self.assertTrue(Ner.objects.filter(pk=ner.pk).exists())
        self.assertTrue(Claim.objects.filter(pk=claim.pk).exists())
        self.assertTrue(ClaimsGenerationFlags.objects.filter(pk=flag.pk).exists())
        self.assertTrue(self.trial.diseases.filter(pk=self.disease.pk).exists())
