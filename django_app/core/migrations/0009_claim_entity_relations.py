from django.db import migrations, models


def copy_claim_entities(apps, schema_editor):
    Claim = apps.get_model('core', 'Claim')
    disease_links = Claim._meta.get_field('diseases').remote_field.through
    intervention_links = Claim._meta.get_field('interventions').remote_field.through
    db = schema_editor.connection.alias
    disease_links.objects.using(db).bulk_create(
        disease_links(claim_id=claim.pk, disease_id=claim.disease_id)
        for claim in Claim.objects.using(db).filter(disease__isnull=False).iterator()
    )
    intervention_links.objects.using(db).bulk_create(
        intervention_links(claim_id=claim.pk, intervention_id=claim.intervention_id)
        for claim in Claim.objects.using(db).filter(intervention__isnull=False).iterator()
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0008_ner_entities')]

    operations = [
        migrations.AddField(
            model_name='claim', name='diseases',
            field=models.ManyToManyField(blank=True, db_table='claim_disease', related_name='claims', to='core.disease'),
        ),
        migrations.AddField(
            model_name='claim', name='interventions',
            field=models.ManyToManyField(blank=True, db_table='claim_intervention', related_name='claims', to='core.intervention'),
        ),
        migrations.AddField(
            model_name='claim', name='ners',
            field=models.ManyToManyField(blank=True, db_table='claim_ner', related_name='claims', to='core.ner'),
        ),
        migrations.RunPython(copy_claim_entities),
        migrations.RemoveConstraint(model_name='claim', name='claim_at_least_one_link'),
        migrations.RemoveField(model_name='claim', name='disease'),
        migrations.RemoveField(model_name='claim', name='intervention'),
    ]
