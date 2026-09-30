from django.test import Client, TestCase

from core.models import (
    Biomarker,
    Chunk,
    Claim,
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
            ('/api/diseases/', {'id', 'name', 'mesh', 'created'}),
            ('/api/interventions/', {'id', 'name', 'mesh', 'created'}),
            ('/api/trials/', {'id', 'nct_id', 'title', 'status', 'phase', 'start_date'}),
            ('/api/publications/', {'id', 'pmid', 'title', 'journal', 'year', 'pub_date'}),
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
