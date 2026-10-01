from django.db import migrations, models


def backfill_group_status(apps, schema_editor):
    Claim = apps.get_model('core', 'Claim')
    ClaimGroup = apps.get_model('core', 'ClaimGroup')
    for group in ClaimGroup.objects.using(schema_editor.connection.alias).all().iterator():
        statuses = set(Claim.objects.using(schema_editor.connection.alias).filter(
            claim_group_id=group.pk).values_list('status', flat=True).distinct())
        status = ('pending' if not statuses or 'pending' in statuses else
                  'approved' if 'approved' in statuses else 'rejected')
        if group.status != status:
            ClaimGroup.objects.using(schema_editor.connection.alias).filter(pk=group.pk).update(status=status)


class Migration(migrations.Migration):
    dependencies = [('core', '0015_claim_group')]

    operations = [
        migrations.AddField(
            model_name='claimgroup',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'),
                                           ('rejected', 'Rejected')], default='pending', max_length=8),
        ),
        migrations.AddField(
            model_name='claimgroup',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(backfill_group_status, migrations.RunPython.noop),
    ]
