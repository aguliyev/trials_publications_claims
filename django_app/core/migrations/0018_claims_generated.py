from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0017_expand_publicationtrial_relation')]

    operations = [
        migrations.AddField(
            model_name='trial',
            name='claims_generated',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='publication',
            name='claims_generated',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
