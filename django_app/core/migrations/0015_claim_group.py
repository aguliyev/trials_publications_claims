from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0014_claim_notes')]

    operations = [
        migrations.CreateModel(
            name='ClaimGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('meta', models.JSONField(default=dict, blank=True)),
                ('evidence_summary', models.TextField(blank=True, default='')),
                ('synced', models.BooleanField(default=False)),
                ('diseases', models.ManyToManyField(blank=True, related_name='claim_groups', to='core.disease')),
                ('interventions', models.ManyToManyField(blank=True, related_name='claim_groups', to='core.intervention')),
            ],
        ),
        migrations.AddField(
            model_name='claim',
            name='claim_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='claims', to='core.claimgroup'),
        ),
    ]
