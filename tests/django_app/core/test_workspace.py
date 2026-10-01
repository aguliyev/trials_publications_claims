from django.test import TestCase

from core.models import (
    Chunk,
    Claim,
    Disease,
    Intervention,
    Judgement,
    Ner,
    Publication,
    Trial,
)


class WorkspaceShellTestCase(TestCase):
    def test_workspace_shell(self):
        root = self.client.get('/')
        self.assertEqual(root.status_code, 200)
        self.assertTemplateUsed(root, 'core/workspace.html')
        self.assertContains(root, 'core/workspace.js')
        page = self.client.get('/app/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        for label in ['claims', 'diseases', 'interventions', 'trials', 'publications']:
            self.assertIn(label, html.lower())

    def test_status_endpoint(self):
        response = self.client.get('/status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertEqual(response.json()['counts']['claims'], 0)

    def test_workspace_shell_structure(self):
        html = self.client.get('/app/').content.decode()
        lowered = html.lower()
        # Search, filter, table and pane containers.
        self.assertIn('type="search"', lowered)
        self.assertIn('ws-filters', lowered)
        self.assertIn('<table', lowered)
        self.assertIn('<thead', lowered)
        self.assertIn('<tbody', lowered)
        self.assertIn('ws-upper', lowered)
        self.assertIn('ws-lower', lowered)
        self.assertIn('ws-detail', lowered)
        # Modal/dialog container.
        self.assertIn('<dialog', lowered)
        # Static asset references.
        self.assertIn('core/workspace.css', html)
        self.assertIn('core/workspace.js', html)
        # CSRF token for the same-origin PATCH.
        self.assertIn('csrfmiddlewaretoken', lowered)
        # Exactly one local stylesheet, no inline styles.
        self.assertEqual(lowered.count('<link'), 1)
        self.assertIn('rel="stylesheet"', lowered)
        self.assertNotIn('<style', lowered)
        self.assertNotIn('style=', lowered)
        self.assertNotIn('@import', lowered)

    def test_import_forms_and_shared_operation_dialog(self):
        html = self.client.get('/app/').content.decode()
        self.assertNotIn('class="ws-header"', html)
        self.assertIn('id="ws-import-trials"', html)
        self.assertIn('id="ws-import-publications"', html)
        self.assertIn('<input id="ws-trial-ids" name="nct_ids" type="text"', html)
        self.assertIn('<input id="ws-publication-ids" name="pmids" type="text"', html)
        self.assertIn('for="ws-trial-ids"', html)
        self.assertIn('for="ws-publication-ids"', html)
        self.assertIn('name="load_related_publications"', html)
        self.assertNotIn('name="load_related_publications" checked', html)
        self.assertIn('Load trials', html)
        self.assertIn('Load publications', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('id="ws-operation"', html)


class LinkedRelationsContractTestCase(TestCase):
    """JSON the lower-pane related tables consume (Task 6, Step 1)."""

    @classmethod
    def setUpTestData(cls):
        cls.trial = Trial.objects.create(
            nct_id='NCT00909090', title='Linked trial', status='Recruiting', phase='Phase 2')
        cls.pub = Publication.objects.create(
            pmid='90909090', title='Linked paper', journal='Nature', year=2024)
        cls.link = cls.pub.trials.through.objects.create(
            publication=cls.pub, trial=cls.trial, relation='DERIVED')
        cls.disease = Disease.objects.create(name='Linked Disease', mesh='MESH:L1')
        cls.intervention = Intervention.objects.create(name='Linked Drug', mesh='MESH:L2')
        cls.chunk = Chunk.objects.create(
            trial=cls.trial, section='summary', sequ=0, body='Linked chunk body')
        cls.claim = Claim.objects.create(
            section='summary', claim_type='linked_a', evidence='linked evidence',
            status='pending', trial=cls.trial, chunk=cls.chunk)
        cls.claim.diseases.add(cls.disease)
        cls.claim.interventions.add(cls.intervention)
        cls.ner = Ner.objects.create(
            trial=cls.trial, section='summary', text='entity', label=['DISEASE'],
            start=0, end=6, score=0.9, method=['m'], model_name=['m'], links=[],
            disease=cls.disease, intervention=cls.intervention)
        cls.publication_ner = Ner.objects.create(
            publication=cls.pub, section='abstract', text='publication entity',
            label=['DRUG'], start=0, end=18, score=0.8,
            method=['m'], model_name=['m'], links=[])
        cls.claim.ners.add(cls.ner)
        cls.judgement = Judgement.objects.create(
            claim=cls.claim, method='m1', score=0.7, meta={'verdict': 'supports'})

    def test_claim_detail_has_full_review_context(self):
        data = self.client.get(f'/api/claims/{self.claim.pk}/').json()
        self.assertEqual(
            data['diseases'],
            [{'id': self.disease.pk, 'name': 'Linked Disease', 'mesh': 'MESH:L1'}])
        self.assertEqual(
            data['interventions'],
            [{'id': self.intervention.pk, 'name': 'Linked Drug', 'mesh': 'MESH:L2'}])
        self.assertEqual(len(data['ners']), 1)
        self.assertEqual(data['ners'][0]['disease_id'], self.disease.pk)
        self.assertEqual(len(data['judgements']), 1)
        self.assertEqual(data['judgements'][0]['method'], 'm1')
        self.assertEqual(data['judgements'][0]['meta'], {'verdict': 'supports'})
        self.assertEqual(data['section_text']['text'], 'Linked chunk body')

    def test_trial_detail_links_publications_with_relation(self):
        data = self.client.get(f'/api/trials/{self.trial.pk}/').json()
        self.assertEqual(data['linked_publications'], [{
            'id': self.pub.pk, 'pmid': '90909090', 'title': 'Linked paper',
            'journal': 'Nature', 'year': 2024, 'relation': 'DERIVED'}])

    def test_publication_detail_links_trials_with_relation(self):
        data = self.client.get(f'/api/publications/{self.pub.pk}/').json()
        self.assertEqual(data['linked_trials'], [{
            'id': self.trial.pk, 'nct_id': 'NCT00909090', 'title': 'Linked trial',
            'status': 'Recruiting', 'phase': 'Phase 2', 'relation': 'DERIVED'}])

    def test_trial_detail_includes_own_named_entities(self):
        data = self.client.get(f'/api/trials/{self.trial.pk}/').json()
        self.assertEqual(data['ners'], [{
            'id': self.ner.pk, 'text': 'entity', 'label': ['DISEASE'],
            'score': 0.9, 'section': 'summary', 'start': 0, 'end': 6,
            'disease_id': self.disease.pk, 'intervention_id': self.intervention.pk,
        }])

    def test_publication_detail_includes_own_named_entities(self):
        data = self.client.get(f'/api/publications/{self.pub.pk}/').json()
        self.assertEqual(data['ners'], [{
            'id': self.publication_ner.pk, 'text': 'publication entity',
            'label': ['DRUG'], 'score': 0.8, 'section': 'abstract',
            'start': 0, 'end': 18, 'disease_id': None, 'intervention_id': None,
        }])

    def test_reciprocal_claim_and_record_lookups(self):
        self.assertEqual(
            self.client.get(f'/api/claims/?trial={self.trial.pk}').json()['count'], 1)
        self.assertEqual(
            self.client.get(f'/api/claims/?disease={self.disease.pk}').json()['count'], 1)
        self.assertEqual(
            self.client.get(
                f'/api/claims/?intervention={self.intervention.pk}').json()['count'], 1)
        self.assertEqual(
            self.client.get(
                f'/api/trials/?publication={self.pub.pk}').json()['results'][0]['id'],
            self.trial.pk)
        self.assertEqual(
            self.client.get(
                f'/api/publications/?trial={self.trial.pk}').json()['results'][0]['id'],
            self.pub.pk)
        self.assertEqual(
            self.client.get(f'/api/records/ners/{self.ner.pk}/').json()['text'], 'entity')
        self.assertEqual(
            self.client.get(
                f'/api/records/publication-trials/{self.link.pk}/').json()['relation'],
            'DERIVED')
