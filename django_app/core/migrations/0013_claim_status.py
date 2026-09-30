from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0012_claim_evidence')]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                default='pending', max_length=8,
            ),
        ),
    ]
