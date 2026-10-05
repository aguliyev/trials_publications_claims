from django.test import TestCase

from core.models import Claim, ClaimGroup, Disease, Focus, Genetic, Intervention
from lib.focuses import build_focus_query, focus_state, get_or_create_focus


class FocusQueryTestCase(TestCase):
    def setUp(self):
        self.disease_a = Disease.objects.create(name='  Acute Leukemia  ')
        self.disease_z = Disease.objects.create(name='Zeta syndrome')
        self.intervention_a = Intervention.objects.create(name='Azacitidine')
        self.intervention_v = Intervention.objects.create(name='Venetoclax')
        self.genetic_z = Genetic.objects.create(name='TP53')
        self.genetic_a = Genetic.objects.create(name='apc')

    def test_build_focus_query_orders_diseases_then_interventions(self):
        claim = Claim.objects.create(section='title', claim_type='treatment')
        claim.diseases.add(self.disease_z, self.disease_a)
        claim.interventions.add(self.intervention_v, self.intervention_a)
        claim.genetics.add(self.genetic_z, self.genetic_a)

        self.assertEqual(
            build_focus_query(claim),
            'Acute Leukemia Zeta syndrome Azacitidine Venetoclax apc TP53',
        )

    def test_claim_group_uses_the_same_canonical_query(self):
        group = ClaimGroup.objects.create(evidence_summary='Group')
        group.diseases.add(self.disease_z, self.disease_a)
        group.interventions.add(self.intervention_v, self.intervention_a)
        group.genetics.add(self.genetic_z)

        self.assertEqual(
            build_focus_query(group),
            'Acute Leukemia Zeta syndrome Azacitidine Venetoclax',
        )

    def test_empty_entities_cannot_create_focus(self):
        claim = Claim.objects.create(section='title', claim_type='empty')

        self.assertEqual(build_focus_query(claim), '')
        with self.assertRaisesMessage(ValueError, 'No disease, intervention, or genetic terms'):
            get_or_create_focus(claim)

    def test_genetic_only_claim_can_create_focus(self):
        claim = Claim.objects.create(section='title', claim_type='genetic')
        claim.genetics.add(self.genetic_z)

        focus, created = get_or_create_focus(claim)

        self.assertTrue(created)
        self.assertEqual(focus.query, 'TP53')

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
