from django.db import migrations, models
import django.db.models.deletion


def backfill_claims_generation_flags(apps, schema_editor):
    ClaimsGenerationFlags = apps.get_model('core', 'ClaimsGenerationFlags')
    Trial = apps.get_model('core', 'Trial')
    Publication = apps.get_model('core', 'Publication')

    ClaimsGenerationFlags.objects.bulk_create(
        ClaimsGenerationFlags(trial=trial, generated_claim_type='intervention_worked_for_disease')
        for trial in Trial.objects.filter(claims_generated=True).iterator()
    )
    ClaimsGenerationFlags.objects.bulk_create(
        ClaimsGenerationFlags(publication=publication, generated_claim_type='intervention_worked_for_disease')
        for publication in Publication.objects.filter(claims_generated=True).iterator()
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_claimtrails_diseases_claimtrails_interventions_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClaimsGenerationFlags',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('generated_claim_type', models.CharField(max_length=64)),
                ('publication', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='claims_generation_flags', to='core.publication',
                )),
                ('trial', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='claims_generation_flags', to='core.trial',
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name='claimsgenerationflags',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(trial__isnull=False, publication__isnull=True)
                    | models.Q(trial__isnull=True, publication__isnull=False)
                ),
                name='cgen_flags_exactly_one_source',
            ),
        ),
        migrations.AddConstraint(
            model_name='claimsgenerationflags',
            constraint=models.UniqueConstraint(
                condition=models.Q(trial__isnull=False),
                fields=('trial', 'generated_claim_type'),
                name='cgen_flags_trial_type_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='claimsgenerationflags',
            constraint=models.UniqueConstraint(
                condition=models.Q(publication__isnull=False),
                fields=('publication', 'generated_claim_type'),
                name='cgen_flags_pub_type_uniq',
            ),
        ),
        migrations.RunPython(backfill_claims_generation_flags, migrations.RunPython.noop),
    ]
