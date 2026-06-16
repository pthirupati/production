from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0002_platform_settings_voices_join"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewcampaign",
            name="is_sample",
            field=models.BooleanField(
                default=False,
                help_text="One-time free trial interview (short duration, no certificate)",
            ),
        ),
        migrations.AddField(
            model_name="interviewentitlement",
            name="sample_interview_used",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="interviewplatformsettings",
            name="sample_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="interviewplatformsettings",
            name="sample_duration_minutes",
            field=models.PositiveSmallIntegerField(default=10),
        ),
    ]
