from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ClaimsGenerationFlagsMigrationTestCase(TransactionTestCase):
    migrate_from = ('core', '0021_claimtrails_diseases_claimtrails_interventions_and_more')
    migrate_to = ('core', '0022_claims_generation_flags')

    def test_backfills_true_claims_generated_values_without_changing_them(self):
        try:
            MigrationExecutor(connection).migrate([self.migrate_from])
            old_apps = MigrationExecutor(connection).loader.project_state([self.migrate_from]).apps
            OldTrial = old_apps.get_model('core', 'Trial')
            OldPublication = old_apps.get_model('core', 'Publication')
            true_trial = OldTrial.objects.create(nct_id='NCTFLAGTRUE', title='Processed trial', claims_generated=True)
            false_trial = OldTrial.objects.create(nct_id='NCTFLAGFALSE', title='Pending trial', claims_generated=False)
            true_publication = OldPublication.objects.create(
                pmid='FLAGTRUE', title='Processed publication', claims_generated=True,
            )
            false_publication = OldPublication.objects.create(
                pmid='FLAGFALSE', title='Pending publication', claims_generated=False,
            )

            MigrationExecutor(connection).migrate([self.migrate_to])
            new_apps = MigrationExecutor(connection).loader.project_state([self.migrate_to]).apps
            ClaimsGenerationFlags = new_apps.get_model('core', 'ClaimsGenerationFlags')
            Trial = new_apps.get_model('core', 'Trial')
            Publication = new_apps.get_model('core', 'Publication')

            self.assertCountEqual(
                list(ClaimsGenerationFlags.objects.values_list('trial_id', 'publication_id', 'generated_claim_type')),
                [
                    (true_trial.pk, None, 'intervention_worked_for_disease'),
                    (None, true_publication.pk, 'intervention_worked_for_disease'),
                ],
            )
            self.assertTrue(Trial.objects.get(pk=true_trial.pk).claims_generated)
            self.assertFalse(Trial.objects.get(pk=false_trial.pk).claims_generated)
            self.assertTrue(Publication.objects.get(pk=true_publication.pk).claims_generated)
            self.assertFalse(Publication.objects.get(pk=false_publication.pk).claims_generated)
        finally:
            MigrationExecutor(connection).migrate([self.migrate_to])
