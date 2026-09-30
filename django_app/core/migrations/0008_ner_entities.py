import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0007_replace_claim')]

    operations = [
        migrations.RemoveField(model_name='disease', name='code'),
        migrations.RemoveField(model_name='disease', name='description'),
        migrations.RemoveField(model_name='intervention', name='intervention_type'),
        migrations.RemoveField(model_name='intervention', name='description'),
        migrations.AddField(model_name='disease', name='mesh', field=models.CharField(blank=True, db_index=True, default='', max_length=64)),
        migrations.AddField(model_name='intervention', name='mesh', field=models.CharField(blank=True, db_index=True, default='', max_length=64)),
        migrations.AddField(model_name='ner', name='disease', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ners', to='core.disease')),
        migrations.AddField(model_name='ner', name='intervention', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ners', to='core.intervention')),
    ]
