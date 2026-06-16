# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0003_sample_interview"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewentitlement",
            name="renewal_reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
