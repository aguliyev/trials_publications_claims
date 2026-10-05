import django.contrib.postgres.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


def populate_claim_group_types(apps, schema_editor):
    Claim = apps.get_model('core', 'Claim')
    ClaimGroup = apps.get_model('core', 'ClaimGroup')
    for group in ClaimGroup.objects.iterator():
        claim_types = list(
            Claim.objects.filter(claim_group_id=group.pk)
            .values_list('claim_type', flat=True)
            .distinct()
        )
        group.claim_type = claim_types[0] if len(claim_types) == 1 else ''
        group.save(update_fields=['claim_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_drop_claims_generated'),
    ]

    operations = [
        migrations.CreateModel(
            name='Genetic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(db_index=True, max_length=255, unique=True)),
                ('mesh', models.CharField(blank=True, db_index=True, default='', max_length=64)),
            ],
            options={
                'verbose_name': 'Genetic',
                'verbose_name_plural': 'Genetics',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='claimgroup',
            name='claim_type',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='claimgroup',
            name='genetics',
            field=models.ManyToManyField(blank=True, related_name='claim_groups', to='core.genetic'),
        ),
        migrations.AddField(
            model_name='claim',
            name='genetics',
            field=models.ManyToManyField(blank=True, related_name='claims', to='core.genetic'),
        ),
        migrations.AddField(
            model_name='ner',
            name='genetic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='ners', to='core.genetic'),
        ),
        migrations.AddField(
            model_name='publication',
            name='genetics',
            field=models.ManyToManyField(blank=True, related_name='publications', to='core.genetic'),
        ),
        migrations.AddField(
            model_name='trial',
            name='genetics',
            field=models.ManyToManyField(blank=True, related_name='trials', to='core.genetic'),
        ),
        migrations.AddField(
            model_name='claimtrails',
            name='genetics',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list,
            ),
        ),
        migrations.AddIndex(
            model_name='claimtrails',
            index=django.contrib.postgres.indexes.GinIndex(fields=['genetics'], name='trails_genetics_gin'),
        ),
        migrations.RunPython(populate_claim_group_types, migrations.RunPython.noop),
    ]
