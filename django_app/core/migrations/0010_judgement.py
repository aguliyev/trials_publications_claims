from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0009_claim_entity_relations')]

    operations = [
        migrations.CreateModel(
            name='Judgement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('method', models.CharField(max_length=64)),
                ('score', models.FloatField()),
                ('claim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='judgements', to='core.claim')),
            ],
        ),
    ]
