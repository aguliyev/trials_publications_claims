from django.db import migrations, models


def move_claim_evidence(apps, schema_editor):
    Claim = apps.get_model('core', 'Claim')
    for claim in Claim.objects.using(schema_editor.connection.alias).iterator():
        if isinstance(claim.meta, dict) and 'evidence' in claim.meta:
            claim.evidence = claim.meta['evidence']
            claim.meta = {key: value for key, value in claim.meta.items() if key != 'evidence'}
            claim.save(update_fields=['evidence', 'meta'])


class Migration(migrations.Migration):
    dependencies = [('core', '0011_ner_section')]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='evidence',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(move_claim_evidence, migrations.RunPython.noop),
    ]
