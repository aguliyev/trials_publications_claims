import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0006_alter_publicationtrial_relation')]

    operations = [
        migrations.DeleteModel(name='Claim'),  # Billing claims cannot be mapped to scientific claims.
        migrations.CreateModel(
            name='Claim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('section', models.CharField(max_length=64)),
                ('claim_type', models.CharField(db_index=True, max_length=64)),
                ('trial', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='claims', to='core.trial')),
                ('publication', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='claims', to='core.publication')),
                ('chunk', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='claims', to='core.chunk')),
                ('disease', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='claims', to='core.disease')),
                ('intervention', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='claims', to='core.intervention')),
            ],
            options={
                'ordering': ['-created'],
                'verbose_name': 'Claim',
                'verbose_name_plural': 'Claims',
                'constraints': [models.CheckConstraint(
                    condition=(models.Q(trial__isnull=False) | models.Q(publication__isnull=False)
                               | models.Q(chunk__isnull=False) | models.Q(disease__isnull=False)
                               | models.Q(intervention__isnull=False)),
                    name='claim_at_least_one_link',
                )],
            },
        ),
    ]
