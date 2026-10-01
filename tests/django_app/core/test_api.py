import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, TestCase

from core.operation_logs import capture_lib_logs
from core.models import (
    Biomarker,
    Chunk,
    Claim,
    ClaimGroup,
    Disease,
    Intervention,
    Judgement,
    Ner,
    Observation,
    Publication,
    Trial,
)


class WorkspaceListApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d1 = Disease.objects.create(name="Lung Cancer", mesh="MESH:D001")
        cls.d2 = Disease.objects.create(name="Breast Cancer", mesh="MESH:D002")
        cls.i1 = Intervention.objects.create(name="Nivolumab", mesh="MESH:C001")
        cls.i2 = Intervention.objects.create(name="Chemo", mesh="MESH:C002")
        cls.t1 = Trial.objects.create(
            nct_id="NCT00000001", title="Lung trial alpha", official_title="Official A",
            acronym="LUNG-A", status="Recruiting", phase="Phase 2", has_results=True,
        )
        cls.t2 = Trial.objects.create(
            nct_id="NCT00000002", title="Breast trial beta", official_title="Official B",
            acronym="BREAST-B", status="Completed", phase="Phase 1", has_results=False,
        )
        cls.p1 = Publication.objects.create(
            pmid="10000001", title="Lung paper alpha", doi="10.1/a", journal="Nature",
            first_author="Smith", year=2023,
        )
        cls.p2 = Publication.objects.create(
            pmid="10000002", title="Breast paper beta", doi="10.1/b", journal="Science",
            first_author="Jones", year=2024,
        )
        cls.c1 = Claim.objects.create(
            section="title", claim_type="type_a", evidence="x" * 200,
            status="pending", trial=cls.t1,
        )
        cls.c1.diseases.add(cls.d1)
        cls.c1.interventions.add(cls.i1)
        cls.c2 = Claim.objects.create(
            section="abstract", claim_type="type_b", evidence="y" * 50,
            status="approved", publication=cls.p1,
        )
        cls.c2.diseases.add(cls.d2)
        cls.c2.interventions.add(cls.i2)

    def test_claim_list_contract(self):
        response = self.client.get('/api/claims/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json().keys()), {'count', 'next', 'previous', 'results'})

    def test_list_keys_and_no_large_fields(self):
        for url, keys in [
            ('/api/claims/', {'id', 'claim_type', 'evidence_excerpt', 'source_kind', 'source_id', 'source_label', 'section', 'status', 'created'}),
            ('/api/diseases/', {'id', 'name', 'mesh', 'created', 'claims_count'}),
            ('/api/interventions/', {'id', 'name', 'mesh', 'created', 'claims_count'}),
            ('/api/trials/', {'id', 'nct_id', 'title', 'status', 'phase', 'start_date', 'claims_count'}),
            ('/api/publications/', {'id', 'pmid', 'title', 'journal', 'year', 'pub_date', 'claims_count'}),
        ]:
            with self.subTest(url=url):
                data = self.client.get(url).json()
                self.assertEqual(data['count'], 2)
                self.assertEqual(len(data['results']), 2)
                for row in data['results']:
                    self.assertEqual(set(row.keys()), keys)
                raw_text = str(data)
                self.assertNotIn('raw', raw_text)
                self.assertNotIn('meta', raw_text)
        # full evidence must not leak in claim list
        data = self.client.get('/api/claims/').json()
        for row in data['results']:
            self.assertNotIn('evidence', row)
            self.assertNotIn('notes', row)

    def test_evidence_excerpt(self):
        data = self.client.get('/api/claims/').json()
        by_id = {r['id']: r for r in data['results']}
        self.assertEqual(by_id[self.c1.pk]['evidence_excerpt'], "x" * 160)
        self.assertEqual(by_id[self.c2.pk]['evidence_excerpt'], "y" * 50)

    def test_claim_counts_match_related_claim_filters_and_are_sortable(self):
        extra = Claim.objects.create(section='title', claim_type='counts', trial=self.t1, publication=self.p1)
        extra.diseases.add(self.d1, self.d2)
        extra.interventions.add(self.i1, self.i2)
        cases = [
            ('diseases', 'disease', self.d1.pk, self.d2.pk, 2, 2),
            ('interventions', 'intervention', self.i1.pk, self.i2.pk, 2, 2),
            ('trials', 'trial', self.t1.pk, self.t2.pk, 2, 0),
            ('publications', 'publication', self.p1.pk, self.p2.pk, 2, 0),
        ]
        for resource, filter_key, first_id, second_id, first_count, second_count in cases:
            with self.subTest(resource=resource):
                rows = self.client.get(f'/api/{resource}/?ordering=-claims_count').json()['results']
                by_id = {row['id']: row for row in rows}
                for pk, expected in ((first_id, first_count), (second_id, second_count)):
                    related = self.client.get(f'/api/claims/?{filter_key}={pk}').json()
                    self.assertEqual(by_id[pk]['claims_count'], expected)
                    self.assertEqual(related['count'], expected)
                self.assertEqual([row['claims_count'] for row in rows],
                                 sorted([row['claims_count'] for row in rows], reverse=True))

    def test_pagination_25_per_page(self):
        for i in range(24):
            Disease.objects.create(name=f"Extra {i}", mesh=f"MESH:X{i}")
        data = self.client.get('/api/diseases/').json()
        self.assertEqual(data['count'], 26)
        self.assertEqual(len(data['results']), 25)
        self.assertIsNotNone(data['next'])
        data2 = self.client.get('/api/diseases/?page=2').json()
        self.assertEqual(len(data2['results']), 1)

    def test_search(self):
        self.assertEqual(self.client.get('/api/claims/?search=type_a').json()['count'], 1)
        self.assertEqual(self.client.get('/api/diseases/?search=Lung').json()['count'], 1)
        self.assertEqual(self.client.get('/api/interventions/?search=Nivolumab').json()['count'], 1)
        self.assertEqual(self.client.get('/api/trials/?search=LUNG-A').json()['count'], 1)
        self.assertEqual(self.client.get('/api/publications/?search=10.1/b').json()['count'], 1)
        self.assertEqual(self.client.get('/api/trials/?search=NCT00000001').json()['count'], 1)
        self.assertEqual(self.client.get('/api/publications/?search=Jones').json()['count'], 1)

    def test_ordering(self):
        asc = self.client.get('/api/diseases/?ordering=name').json()['results']
        self.assertEqual([r['name'] for r in asc], sorted([r['name'] for r in asc]))
        desc = self.client.get('/api/diseases/?ordering=-name').json()['results']
        self.assertEqual([r['name'] for r in desc], sorted([r['name'] for r in desc], reverse=True))

    def test_exact_filters(self):
        self.assertEqual(self.client.get(f'/api/claims/?status=pending').json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/claims/?claim_type=type_b').json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/claims/?trial={self.t1.pk}').json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/claims/?publication={self.p1.pk}').json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/claims/?disease={self.d1.pk}').json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/claims/?intervention={self.i2.pk}').json()['count'], 1)
        self.assertEqual(self.client.get('/api/diseases/?mesh=MESH:D001').json()['count'], 1)
        self.assertEqual(self.client.get('/api/trials/?status=Recruiting').json()['count'], 1)
        self.assertEqual(self.client.get('/api/trials/?phase=Phase 1').json()['count'], 1)
        self.assertEqual(self.client.get('/api/trials/?has_results=true').json()['count'], 1)
        self.assertEqual(self.client.get('/api/publications/?year=2023').json()['count'], 1)
        self.assertEqual(self.client.get('/api/publications/?journal=Nature').json()['count'], 1)

    def test_through_table_filters(self):
        link = self.p1.trials.through.objects.create(
            publication=self.p1, trial=self.t1, relation='RELATED')
        self.assertEqual(self.client.get(f'/api/trials/?publication={self.p1.pk}').json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/publications/?trial={self.t1.pk}').json()['count'], 1)

    def test_malformed_filters_400(self):
        for url in ['/api/publications/?year=abc', f'/api/claims/?trial=abc',
                    '/api/trials/?has_results=maybe']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 400)

    def test_detail_ignores_list_filters(self):
        url = f'/api/diseases/{self.d1.pk}/?search=unlikely&mesh=other'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ClaimGroupApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = ClaimGroup.objects.create(evidence_summary='Summary ' + 'a' * 200)
        cls.empty = ClaimGroup.objects.create(evidence_summary='No claims')
        cls.diseases = [Disease.objects.create(name=name) for name in ('D1', 'D2')]
        cls.interventions = [Intervention.objects.create(name=name) for name in ('I1', 'I2')]
        cls.group.diseases.add(*cls.diseases)
        cls.group.interventions.add(*cls.interventions)
        cls.claims = [Claim.objects.create(section='title', claim_type='test', claim_group=cls.group)
                      for _ in range(2)]
        Judgement.objects.create(claim=cls.claims[0], method='one', score=0.4)
        Judgement.objects.create(claim=cls.claims[0], method='two', score=0.9)
        Judgement.objects.create(claim=cls.claims[1], method='three', score=0.7)

    def test_list_counts_distinct_claims_and_highest_judgement(self):
        response = self.client.get('/api/claim-groups/')
        self.assertEqual(response.status_code, 200)
        rows = response.json()['results']
        self.assertEqual(len(rows), 2)
        by_id = {row['id']: row for row in rows}
        self.assertEqual(by_id[self.group.pk], {
            'id': self.group.pk, 'evidence_summary_excerpt': self.group.evidence_summary[:160],
            'max_judgement_score': 0.9, 'claims_count': 2,
            'diseases_count': 2, 'interventions_count': 2,
        })
        self.assertEqual(by_id[self.empty.pk]['claims_count'], 0)
        self.assertIsNone(by_id[self.empty.pk]['max_judgement_score'])
        self.assertNotIn(self.group.evidence_summary, str(rows))

    def test_detail_lists_entities_and_claim_filter(self):
        response = self.client.get(f'/api/claim-groups/{self.group.pk}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['evidence_summary'], self.group.evidence_summary)
        self.assertCountEqual(data['diseases'], [
            {'id': item.pk, 'name': item.name, 'mesh': item.mesh} for item in self.diseases])
        self.assertCountEqual(data['interventions'], [
            {'id': item.pk, 'name': item.name, 'mesh': item.mesh} for item in self.interventions])
        claims = self.client.get(f'/api/claims/?claim_group={self.group.pk}&page=1').json()
        self.assertEqual(claims['count'], 2)
        self.assertCountEqual([row['id'] for row in claims['results']], [item.pk for item in self.claims])
        self.assertEqual(self.client.get(f'/api/claims/?claim_group={self.empty.pk}').json()['count'], 0)


class WorkspaceDetailApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trial = Trial.objects.create(
            nct_id="NCT00000009", title="Detail trial title",
            summary="Trial summary body", has_results=True,
            raw={"protocolSection": {"identificationModule": {"nctId": "NCT00000009"}}},
        )
        cls.pub = Publication.objects.create(
            pmid="90000001", title="Detail paper title", abstract="Paper abstract body",
            journal="Nature", year=2023, raw={"pmid": "90000001"},
        )
        cls.chunk = Chunk.objects.create(
            trial=cls.trial, section="summary", sequ=0, body="Chunk summary body")
        cls.chunk_claim = Claim.objects.create(
            section="summary", claim_type="detail_a", evidence="chunk evidence",
            status="pending", trial=cls.trial, chunk=cls.chunk)
        cls.disease = Disease.objects.create(name="Detail Disease", mesh="MESH:D999")
        cls.intervention = Intervention.objects.create(name="Detail Drug", mesh="MESH:C999")
        cls.chunk_claim.diseases.add(cls.disease)
        cls.chunk_claim.interventions.add(cls.intervention)
        cls.ner = Ner.objects.create(
            trial=cls.trial, section="summary", text="entity", label=["DISEASE"],
            start=0, end=6, score=0.9, method=["m"], model_name=["m"], links=[],
            disease=cls.disease, intervention=cls.intervention)
        cls.chunk_claim.ners.add(cls.ner)
        cls.j1 = Judgement.objects.create(claim=cls.chunk_claim, method="m1", score=0.5)
        cls.j2 = Judgement.objects.create(claim=cls.chunk_claim, method="m2", score=0.8)

    def test_chunk_backed_claim_section_text(self):
        response = self.client.get(f'/api/claims/{self.chunk_claim.pk}/')
        self.assertEqual(response.json()['section_text']['text'], self.chunk.body)

    def test_chunk_section_text_contract(self):
        data = self.client.get(f'/api/claims/{self.chunk_claim.pk}/').json()
        self.assertEqual(data['section_text'], {
            'kind': 'chunks', 'id': self.chunk.pk,
            'section': 'summary', 'text': self.chunk.body})

    def test_trial_title_claim_without_chunk(self):
        claim = Claim.objects.create(
            section="title", claim_type="detail_a", trial=self.trial)
        data = self.client.get(f'/api/claims/{claim.pk}/').json()
        self.assertEqual(data['section_text'], {
            'kind': 'trials', 'id': self.trial.pk,
            'section': 'title', 'text': self.trial.title})

    def test_publication_title_claim_without_chunk(self):
        claim = Claim.objects.create(
            section="title", claim_type="detail_a", publication=self.pub)
        data = self.client.get(f'/api/claims/{claim.pk}/').json()
        self.assertEqual(data['section_text'], {
            'kind': 'publications', 'id': self.pub.pk,
            'section': 'title', 'text': self.pub.title})

    def test_ambiguous_section_text_is_null(self):
        other = Trial.objects.create(nct_id="NCT00000010", title="Other")
        other_chunk = Chunk.objects.create(
            trial=other, section="summary", sequ=0, body="other body")
        cases = [
            Claim.objects.create(section="abstract", claim_type="x"),  # orphan, no chunk
            Claim.objects.create(section="bogus", claim_type="x", trial=self.trial),  # invalid section
            Claim.objects.create(  # dual owner, no chunk
                section="title", claim_type="x", trial=self.trial, publication=self.pub),
            Claim.objects.create(  # chunk owned by another trial
                section="summary", claim_type="x", trial=self.trial, chunk=other_chunk),
            Claim.objects.create(  # chunk section conflicts with claim
                section="title", claim_type="x", trial=self.trial, chunk=self.chunk),
            Claim.objects.create(  # dual owner with chunk
                section="summary", claim_type="x", trial=self.trial,
                publication=self.pub, chunk=self.chunk),
        ]
        for claim in cases:
            with self.subTest(claim=claim.pk):
                data = self.client.get(f'/api/claims/{claim.pk}/').json()
                self.assertIsNone(data['section_text'])

    def test_claim_detail_nested_previews(self):
        data = self.client.get(f'/api/claims/{self.chunk_claim.pk}/').json()
        for field in ('evidence', 'notes', 'status', 'trial', 'publication', 'chunk'):
            self.assertIn(field, data)
        self.assertEqual(
            data['diseases'],
            [{'id': self.disease.pk, 'name': 'Detail Disease', 'mesh': 'MESH:D999'}])
        self.assertEqual(
            data['interventions'],
            [{'id': self.intervention.pk, 'name': 'Detail Drug', 'mesh': 'MESH:C999'}])
        self.assertEqual(len(data['ners']), 1)
        ner = data['ners'][0]
        self.assertEqual(
            set(ner.keys()),
            {'id', 'text', 'label', 'score', 'section', 'start', 'end',
             'disease_id', 'intervention_id'})
        self.assertEqual(ner['disease_id'], self.disease.pk)
        self.assertEqual(ner['intervention_id'], self.intervention.pk)
        self.assertEqual(len(data['judgements']), 2)
        for row in data['judgements']:
            self.assertEqual(
                set(row.keys()), {'id', 'method', 'score', 'meta', 'created', 'modified'})
        self.assertEqual({r['method'] for r in data['judgements']}, {'m1', 'm2'})
        self.assertEqual(data['trial'], self.trial.pk)
        self.assertEqual(data['chunk'], self.chunk.pk)

    def test_detail_full_fields_not_in_list(self):
        list_data = self.client.get('/api/trials/').json()
        self.assertNotIn('raw', str(list_data))
        detail = self.client.get(f'/api/trials/{self.trial.pk}/').json()
        self.assertEqual(detail['raw']['protocolSection']['identificationModule']['nctId'], 'NCT00000009')
        list_pub = self.client.get('/api/publications/').json()
        self.assertNotIn('raw', str(list_pub))
        pub_detail = self.client.get(f'/api/publications/{self.pub.pk}/').json()
        self.assertEqual(pub_detail['raw'], {'pmid': '90000001'})

    def test_claim_detail_ignores_disqualifying_filters(self):
        url = f'/api/claims/{self.chunk_claim.pk}/?search=unlikely&status=other'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_related_claim_filters(self):
        self.assertEqual(
            self.client.get(f'/api/claims/?disease={self.disease.pk}').json()['count'], 1)
        self.assertEqual(
            self.client.get(f'/api/claims/?intervention={self.intervention.pk}').json()['count'], 1)
        self.assertEqual(
            self.client.get(f'/api/claims/?trial={self.trial.pk}').json()['count'], 1)

    def test_through_table_distinctness(self):
        link = self.pub.trials.through.objects.create(
            publication=self.pub, trial=self.trial, relation='RELATED')
        link2 = self.pub.trials.through.objects.create(
            publication=self.pub, trial=self.trial, relation='DERIVED')
        try:
            data = self.client.get(f'/api/trials/?publication={self.pub.pk}').json()
            ids = [r['id'] for r in data['results']]
            self.assertEqual(data['count'], 1)
            self.assertEqual(ids, [self.trial.pk])
        finally:
            link2.delete()
            link.delete()

    def test_supporting_records(self):
        bio = Biomarker.objects.create(name="Detail Biomarker")
        obs = Observation.objects.create(
            observation_type="Efficacy", summary="It worked.", trial=self.trial)
        link = self.pub.trials.through.objects.create(
            publication=self.pub, trial=self.trial, relation='RELATED')
        try:
            cases = [
                ('chunks', self.chunk.pk, 'body'),
                ('ners', self.ner.pk, 'text'),
                ('judgements', self.j1.pk, 'method'),
                ('biomarkers', bio.pk, 'name'),
                ('observations', obs.pk, 'summary'),
                ('publication-trials', link.pk, 'relation'),
            ]
            for kind, pk, field in cases:
                with self.subTest(kind=kind):
                    response = self.client.get(f'/api/records/{kind}/{pk}/')
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(field, response.json())
            self.assertEqual(self.client.get('/api/records/unknown/1/').status_code, 404)
            self.assertEqual(self.client.get('/api/records/chunks/999999/').status_code, 404)
        finally:
            link.delete()


class ClaimReviewPatchTestCase(TestCase):
    def setUp(self):
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.get('/app/')
        self.token = self.csrf_client.cookies['csrftoken'].value

    def patch(self, pk, payload, token=True):
        kwargs = {'content_type': 'application/json'}
        if token:
            kwargs['HTTP_X_CSRFTOKEN'] = self.token
        return self.csrf_client.patch(f'/api/claims/{pk}/', data=payload, **kwargs)

    def test_claim_review_requires_csrf(self):
        claim = Claim.objects.create(section='title', claim_type='review')
        response = self.client.patch(
            f'/api/claims/{claim.pk}/',
            data='{"status": "approved"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_patch_without_token_is_403(self):
        claim = Claim.objects.create(section='title', claim_type='review')
        response = self.patch(claim.pk, '{"status": "approved"}', token=False)
        self.assertEqual(response.status_code, 403)
        claim.refresh_from_db()
        self.assertEqual(claim.status, 'pending')

    def test_patch_saves_status_and_notes(self):
        claim = Claim.objects.create(section='title', claim_type='review')
        response = self.patch(claim.pk, '{"status": "approved", "notes": "looks good"}')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'approved')
        self.assertEqual(body['notes'], 'looks good')
        self.assertIn('modified', body)
        claim.refresh_from_db()
        self.assertEqual(claim.status, 'approved')
        self.assertEqual(claim.notes, 'looks good')

    def test_patch_invalid_status_is_400_and_keeps_notes(self):
        claim = Claim.objects.create(section='title', claim_type='review', notes='keep me')
        response = self.patch(claim.pk, '{"status": "bogus", "notes": "overwrite"}')
        self.assertEqual(response.status_code, 400)
        claim.refresh_from_db()
        self.assertEqual(claim.status, 'pending')
        self.assertEqual(claim.notes, 'keep me')

    def test_patch_rejects_read_only_fields(self):
        claim = Claim.objects.create(section='title', claim_type='review', evidence='orig')
        for payload in ('{"evidence": "changed"}', '{"trial": 1}', '{"status": "approved", "trial": 1}'):
            with self.subTest(payload=payload):
                response = self.patch(claim.pk, payload)
                self.assertEqual(response.status_code, 400)
        claim.refresh_from_db()
        self.assertEqual(claim.evidence, 'orig')
        self.assertEqual(claim.status, 'pending')

    def test_collection_writes_not_allowed(self):
        claim = Claim.objects.create(section='title', claim_type='review')
        payload = '{"status": "approved"}'
        for method in ('post', 'put', 'delete'):
            with self.subTest(method=method):
                caller = getattr(self.csrf_client, method)
                response = caller(
                    f'/api/claims/{claim.pk}/', data=payload,
                    content_type='application/json', HTTP_X_CSRFTOKEN=self.token)
                self.assertEqual(response.status_code, 405)
        response = self.csrf_client.post(
            '/api/claims/', data=payload,
            content_type='application/json', HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 405)
        # Without a token the CSRF rejection precedes the method check.
        response = self.csrf_client.post(
            f'/api/claims/{claim.pk}/', data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_patch_missing_claim_is_404(self):
        response = self.patch(999999, '{"status": "approved"}')
        self.assertEqual(response.status_code, 404)


class SourceSearchApiTestCase(TestCase):
    def test_trial_detail_fetches_upstream_metadata_without_saving(self):
        study = {'protocolSection': {
            'identificationModule': {'nctId': 'NCT03026140', 'briefTitle': 'Cancer trial',
                                     'officialTitle': 'Official cancer study'},
            'statusModule': {'overallStatus': 'RECRUITING'},
            'designModule': {'phases': ['PHASE2'], 'enrollmentInfo': {'count': 120}},
            'descriptionModule': {'briefSummary': 'Study treatment outcomes.'},
            'conditionsModule': {'conditions': ['Colorectal cancer']},
            'armsInterventionsModule': {'interventions': [{'name': 'Nivolumab'}]},
            'referencesModule': {'references': [{'pmid': '41115454'}, {'citation': 'No PMID'}]},
        }}
        with patch('lib.clinical_trials.fetch_study_v2', return_value=study) as fetch:
            response = self.client.get('/api/sources/trials/NCT03026140/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['summary'], 'Study treatment outcomes.')
        self.assertEqual(response.json()['status'], 'RECRUITING')
        self.assertEqual(response.json()['conditions'], ['Colorectal cancer'])
        self.assertEqual(response.json()['interventions_list'], [{'name': 'Nivolumab'}])
        self.assertIsNone(response.json()['database_record_id'])
        self.assertEqual(response.json()['publication_count'], 1)
        self.assertNotIn('raw', response.json())
        self.assertFalse(Trial.objects.filter(nct_id='NCT03026140').exists())
        fetch.assert_called_once_with('NCT03026140')

    def test_publication_detail_fetches_abstract_without_saving(self):
        article = {'pmid': '41115454', 'title': 'Cancer paper',
                   'abstract': 'Treatment results and conclusions.', 'journal': 'Nature',
                   'year': '2025', 'doi': '10.1000/example', 'first_author': 'Smith'}
        with patch('lib.pubmed.PubMedFetcher') as fetcher:
            fetcher.return_value.article_by_pmid.return_value = article
            response = self.client.get('/api/sources/publications/41115454/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['abstract'], 'Treatment results and conclusions.')
        self.assertEqual(response.json()['journal'], 'Nature')
        self.assertEqual(response.json()['year'], 2025)
        self.assertIsNone(response.json()['database_record_id'])
        self.assertNotIn('raw', response.json())
        self.assertFalse(Publication.objects.filter(pmid='41115454').exists())
        fetcher.return_value.article_by_pmid.assert_called_once_with('41115454')

    def test_source_detail_reports_matching_database_records(self):
        trial = Trial.objects.create(nct_id='NCT03026140', title='Stored trial')
        publication = Publication.objects.create(pmid='41115454', title='Stored paper')
        with patch('lib.clinical_trials.fetch_study_v2', return_value={'protocolSection': {}}):
            response = self.client.get('/api/sources/trials/nct03026140/')
        self.assertEqual(response.json()['database_record_id'], trial.pk)
        with patch('lib.pubmed.PubMedFetcher') as fetcher:
            fetcher.return_value.article_by_pmid.return_value = {'pmid': '41115454', 'title': 'Stored paper'}
            response = self.client.get('/api/sources/publications/41115454/')
        self.assertEqual(response.json()['database_record_id'], publication.pk)

    def test_source_detail_rejects_invalid_identifiers_without_upstream_call(self):
        with patch('lib.clinical_trials.fetch_study_v2') as trial_fetch, \
                patch('lib.pubmed.PubMedFetcher') as publication_fetch:
            for path in ('trials/invalid', 'publications/not-a-pmid', 'unknown/41115454'):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get('/api/sources/' + path + '/').status_code, 400)
            trial_fetch.assert_not_called()
            publication_fetch.assert_not_called()

    def test_source_detail_upstream_failure_does_not_leak_exception(self):
        with patch('lib.clinical_trials.fetch_study_v2', side_effect=RuntimeError('secret')):
            response = self.client.get('/api/sources/trials/NCT03026140/')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secret', str(response.json()))

    def test_search_routes_to_selected_source_without_saving(self):
        trials = [{'id': 'NCT03026140', 'title': 'Cancer trial',
                   'link': 'https://clinicaltrials.gov/study/NCT03026140'}]
        publications = [{'id': '41115454', 'title': 'Cancer paper',
                         'link': 'https://pubmed.ncbi.nlm.nih.gov/41115454/'}]
        with patch('lib.clinical_trials.search_trials', return_value=trials) as search_trials, \
                patch('lib.pubmed.search_publications', return_value=publications) as search_publications:
            response = self.client.get('/api/sources/', {'kind': 'trials', 'query': '  cancer  '})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'results': [dict(trials[0], database_record_id=None)], 'count': 1})
            search_trials.assert_called_once_with('cancer')
            search_publications.assert_not_called()
            response = self.client.get('/api/sources/', {'kind': 'publications', 'query': 'cancer'})
            self.assertEqual(response.json(), {'results': [dict(publications[0], database_record_id=None)], 'count': 1})
            search_publications.assert_called_once_with('cancer')

    def test_search_marks_existing_trials_and_publications(self):
        trial = Trial.objects.create(nct_id='NCT03026140', title='Stored trial')
        publication = Publication.objects.create(pmid='41115454', title='Stored paper')
        with patch('lib.clinical_trials.search_trials', return_value=[
            {'id': 'NCT03026140', 'title': 'Stored trial'},
            {'id': 'NCT00000001', 'title': 'New trial'},
        ]):
            rows = self.client.get('/api/sources/', {'kind': 'trials', 'query': 'cancer'}).json()['results']
        self.assertEqual([row['database_record_id'] for row in rows], [trial.pk, None])
        with patch('lib.pubmed.search_publications', return_value=[
            {'id': '41115454', 'title': 'Stored paper'},
            {'id': '12345678', 'title': 'New paper'},
        ]):
            rows = self.client.get('/api/sources/', {'kind': 'publications', 'query': 'cancer'}).json()['results']
        self.assertEqual([row['database_record_id'] for row in rows], [publication.pk, None])

    def test_bad_search_does_not_call_upstream(self):
        with patch('lib.clinical_trials.search_trials') as search_trials, \
                patch('lib.pubmed.search_publications') as search_publications:
            for params in ({'kind': 'trials', 'query': '   '},
                           {'kind': 'other', 'query': 'cancer'}, {'query': 'cancer'}):
                with self.subTest(params=params):
                    self.assertEqual(self.client.get('/api/sources/', params).status_code, 400)
            search_trials.assert_not_called()
            search_publications.assert_not_called()

    def test_upstream_failure_is_safe(self):
        with patch('lib.pubmed.search_publications', side_effect=RuntimeError('secret')):
            response = self.client.get('/api/sources/', {'kind': 'publications', 'query': 'cancer'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secret', str(response.json()))


class ImportApiTestCase(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get('/app/')
        self.token = self.client.cookies['csrftoken'].value
        self.publication = Publication.objects.create(pmid='41115454', title='Imported paper')
        self.trial = Trial.objects.create(nct_id='NCT03026140', title='Imported trial')

    def post_import(self, kind, payload, token=True):
        kwargs = {'content_type': 'application/json'}
        if token:
            kwargs['HTTP_X_CSRFTOKEN'] = self.token
        return self.client.post('/api/import/' + kind + '/', json.dumps(payload), **kwargs)

    def test_import_requires_csrf_and_post_method(self):
        for kind, payload in [('publications', {'pmid': '41115454'}),
                              ('trials', {'nct_id': 'NCT03026140', 'load_related_publications': False})]:
            with self.subTest(kind=kind):
                self.assertEqual(self.post_import(kind, payload, token=False).status_code, 403)
                for method in ('get', 'put', 'delete'):
                    response = getattr(self.client, method)('/api/import/' + kind + '/',
                                                            HTTP_X_CSRFTOKEN=self.token)
                    self.assertEqual(response.status_code, 405)

    def test_invalid_payloads_do_not_call_ingest(self):
        cases = [('publications', {'pmid': value}) for value in
                 ('', '123,456', '１２３', '123x', '1' * 65, '123\n', 123)]
        cases += [('publications', {})]
        cases += [('trials', {'nct_id': value, 'load_related_publications': False}) for value in
                  ('', 'NCT123', 'NCT123456789', 'NCT1234567x', 'NCT１２３４５６７８', 'NCT03026140\n')]
        cases += [('trials', {'nct_id': 'NCT03026140', 'load_related_publications': value}) for value in
                  ('false', 0, None)]
        cases += [('trials', {'nct_id': 'NCT03026140'})]
        with patch('lib.pubmed.fetch_and_upsert_publication', return_value=self.publication) as publication_import, \
                patch('lib.clinical_trials.fetch_and_upsert_trial', return_value=self.trial) as trial_import:
            for kind, payload in cases:
                with self.subTest(kind=kind, payload=payload):
                    self.assertEqual(self.post_import(kind, payload).status_code, 400)
            publication_import.assert_not_called()
            trial_import.assert_not_called()

    def test_publication_import_returns_record_and_scoped_safe_logs(self):
        def ingest(pmid):
            logging.getLogger('lib.pubmed').info('Upserted publication')
            logging.getLogger('lib.pubmed').warning('Reference skipped')
            logging.getLogger('other.lib').warning('unrelated secret')
            return self.publication

        with patch('lib.pubmed.fetch_and_upsert_publication', side_effect=ingest) as helper:
            response = self.post_import('publications', {'pmid': '41115454'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual((data['id'], data['record_id'], data['status']),
                         ('41115454', self.publication.pk, 'ok'))
        self.assertEqual([entry['level'] for entry in data['logs']], ['INFO', 'WARNING'])
        self.assertEqual([entry['message'] for entry in data['logs']],
                         ['Upserted publication', 'Reference skipped'])
        self.assertTrue(all(entry['time'] for entry in data['logs']))
        helper.assert_called_once_with('41115454')

    def test_trials_only_load_related_after_checked_success(self):
        second_publication = Publication.objects.create(pmid='39278994', title='Second paper')
        links = [SimpleNamespace(publication=self.publication),
                 SimpleNamespace(publication=second_publication)]
        with patch('lib.clinical_trials.fetch_and_upsert_trial', return_value=self.trial) as ingest, \
                patch('lib.clinical_trials.fetch_trial_publications', return_value=links) as related:
            response = self.post_import('trials', {'nct_id': 'nct03026140',
                                                   'load_related_publications': False})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['related_publications'], None)
            self.assertEqual(response.json()['related_publication_ids'], None)
            related.assert_not_called()
            response = self.post_import('trials', {'nct_id': 'NCT03026140',
                                                   'load_related_publications': True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['id'], 'NCT03026140')
            self.assertEqual(response.json()['record_id'], self.trial.pk)
            self.assertEqual(response.json()['related_publications'], 2)
            self.assertEqual(response.json()['related_publication_ids'], ['41115454', '39278994'])
            self.assertEqual(ingest.call_count, 2)
            related.assert_called_once_with('NCT03026140')

    def test_failed_source_is_generic_and_does_not_load_related(self):
        def fail(_):
            logging.getLogger('lib.clinical_trials').warning('Source unavailable')
            logging.getLogger('lib.clinical_trials').error(
                'fetch failed error_type=RuntimeError frames=[(\'secret\', 42)]')
            raise RuntimeError('secret payload')

        with patch('lib.clinical_trials.fetch_and_upsert_trial', side_effect=fail), \
                patch('lib.clinical_trials.fetch_trial_publications') as related:
            response = self.post_import('trials', {'nct_id': 'NCT03026140',
                                                   'load_related_publications': True})
            related.assert_not_called()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['status'], 'failed')
        self.assertNotIn('record_id', response.json())
        self.assertIn('Source unavailable', str(response.json()['logs']))
        self.assertNotIn('secret', str(response.json()))
        self.assertIn('error', response.json())

    def test_related_failure_is_partial_and_retryable(self):
        with patch('lib.clinical_trials.fetch_and_upsert_trial', return_value=self.trial), \
                patch('lib.clinical_trials.fetch_trial_publications', side_effect=RuntimeError('secret')):
            response = self.post_import('trials', {'nct_id': 'NCT03026140',
                                                   'load_related_publications': True})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['status'], 'partial')
        self.assertEqual(response.json()['record_id'], self.trial.pk)
        self.assertNotIn('secret', str(response.json()))

    def test_publication_source_failure_is_generic(self):
        with patch('lib.pubmed.fetch_and_upsert_publication', side_effect=RuntimeError('private')):
            response = self.post_import('publications', {'pmid': '41115454'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['status'], 'failed')
        self.assertNotIn('private', str(response.json()))

    def test_concurrent_import_log_capture_is_request_scoped(self):
        barrier = Barrier(2)

        def capture(message):
            entries = []
            with capture_lib_logs(entries.append):
                barrier.wait(timeout=5)
                logging.getLogger('lib.pubmed').warning(message)
            return entries

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(capture, 'first request')
            second = pool.submit(capture, 'second request')
            self.assertEqual([entry['message'] for entry in first.result()], ['first request'])
            self.assertEqual([entry['message'] for entry in second.result()], ['second request'])

    def test_import_logs_only_include_safe_levels_and_bounded_messages(self):
        entries = []
        logger = logging.getLogger('lib.pubmed')
        with capture_lib_logs(entries.append):
            logger.error('fetch failed frames=[(\'secret\', 1)]')
            logger.warning('x' * 1001)
            logger.critical('not an import progress level')
        self.assertEqual([entry['level'] for entry in entries], ['ERROR', 'WARNING'])
        self.assertEqual(entries[0]['message'], 'fetch failed')
        self.assertEqual(entries[1]['message'], 'x' * 1000)
