from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class GeneticsMigrationTestCase(TransactionTestCase):
    migrate_from = ('core', '0023_drop_claims_generated')
    migrate_to = ('core', '0024_genetic')

    def test_adds_claim_group_type_and_empty_historical_genetics(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Trial = old_apps.get_model('core', 'Trial')
        Claim = old_apps.get_model('core', 'Claim')
        ClaimGroup = old_apps.get_model('core', 'ClaimGroup')
        ClaimTrails = old_apps.get_model('core', 'ClaimTrails')
        trial = Trial.objects.create(nct_id='NCT08880005', title='Migration trial')
        group = ClaimGroup.objects.create(meta={'prior': 'group'})
        claim = Claim.objects.create(
            trial=trial, claim_group=group, section='title', claim_type='gene_association',
        )
        trail = ClaimTrails.objects.create(
            trial=trial, status_from='pending', new_status='approved',
            meta={'claim': {'id': 31}, 'review': 'unchanged'},
        )

        try:
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
            new_apps = executor.loader.project_state([self.migrate_to]).apps
            NewClaimGroup = new_apps.get_model('core', 'ClaimGroup')
            NewClaimTrails = new_apps.get_model('core', 'ClaimTrails')
            migrated_group = NewClaimGroup.objects.get(pk=group.pk)
            migrated_trail = NewClaimTrails.objects.get(pk=trail.pk)

            self.assertEqual(migrated_group.claim_type, 'gene_association')
            self.assertEqual(list(migrated_group.genetics.all()), [])
            self.assertEqual(migrated_trail.genetics, [])
            self.assertEqual(
                migrated_trail.meta,
                {'claim': {'id': 31}, 'review': 'unchanged'},
            )
            self.assertEqual(NewClaimGroup.objects.get(pk=group.pk).claims.get().pk, claim.pk)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
