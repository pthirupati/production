# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_marketing_email_log"),
    ]

    operations = [
        migrations.AlterField(
            model_name="marketingemaillog",
            name="campaign",
            field=models.CharField(
                choices=[
                    ("interview_sample_nudge", "Interview sample → subscribe"),
                    ("technology_subscribe_nudge", "No tech subscription nudge"),
                    ("combined_subscribe_nudge", "Interview + technology combined nudge"),
                    ("interview_renewal_reminder", "Interview plan renewal reminder"),
                ],
                db_index=True,
                max_length=64,
            ),
        ),
    ]
