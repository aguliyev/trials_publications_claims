from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ClaimEvidenceMigrationTestCase(TransactionTestCase):
    migrate_from = ('core', '0011_ner_section')
    migrate_to = ('core', '0014_claim_notes')

    def test_moves_existing_evidence_without_losing_other_metadata(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        trial = old_apps.get_model('core', 'Trial').objects.create(nct_id='NCT1', title='Trial')
        claim = old_apps.get_model('core', 'Claim').objects.create(
            trial=trial, section='title', claim_type='intervention_worked_for_disease',
            meta={'evidence': 'Drug improved survival.', 'ner_ids': [1]},
        )
        old_apps.get_model('core', 'Claim').objects.create(
            trial=trial, section='title', claim_type='intervention_worked_for_disease', meta={'ner_ids': [2]},
        )
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
            new_apps = executor.loader.project_state([self.migrate_to]).apps
            Claim = new_apps.get_model('core', 'Claim')
            migrated = Claim.objects.get(pk=claim.pk)
            self.assertEqual(migrated.evidence, 'Drug improved survival.')
            self.assertEqual(migrated.meta, {'ner_ids': [1]})
            self.assertEqual(migrated.status, 'pending')
            self.assertEqual(migrated.notes, '')
            self.assertEqual(Claim.objects.exclude(pk=claim.pk).get().evidence, '')
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
