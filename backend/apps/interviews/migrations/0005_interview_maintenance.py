from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0004_interview_renewal_reminder"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewplatformsettings",
            name="maintenance_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="interviewplatformsettings",
            name="maintenance_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="interviewplatformsettings",
            name="maintenance_scheduled_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="interviewplatformsettings",
            name="maintenance_scheduled_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
