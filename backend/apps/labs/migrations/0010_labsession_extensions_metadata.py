from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0009_alter_labsession_expires_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='labsession',
            name='metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Arbitrary session metadata (e.g. ai_review generated post-lab)',
            ),
        ),
        migrations.AddField(
            model_name='labsession',
            name='extensions_used',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Free self-service time extensions used today (quota: 2/day)',
            ),
        ),
        migrations.AddField(
            model_name='labsession',
            name='last_extension_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Date the last self-service extension was granted',
            ),
        ),
    ]
