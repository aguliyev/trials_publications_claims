from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0016_claim_group_status_notes')]

    operations = [
        migrations.AlterField(
            model_name='publicationtrial',
            name='relation',
            field=models.CharField(
                choices=[('RESULT', 'RESULT'), ('BACKGROUND', 'BACKGROUND'), ('PRIMARY', 'PRIMARY'),
                         ('SECONDARY', 'SECONDARY'), ('CONCLUSION', 'CONCLUSION'),
                         ('SUPPORTING', 'SUPPORTING'), ('DERIVED', 'DERIVED'),
                         ('DERIVED_FROM_TRIAL', 'DERIVED_FROM_TRIAL'),
                         ('BACKGROUND_FOR_TRIAL', 'BACKGROUND_FOR_TRIAL'),
                         ('REPORTS_TRIAL_RESULT', 'REPORTS_TRIAL_RESULT'),
                         ('SUPPORTS_MECHANISM', 'SUPPORTS_MECHANISM'), ('RELATED', 'RELATED')],
                db_index=True, default='RELATED', max_length=64),
        ),
    ]
