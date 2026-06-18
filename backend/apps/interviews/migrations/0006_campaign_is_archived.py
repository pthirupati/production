from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0005_interview_maintenance"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewcampaign",
            name="is_archived",
            field=models.BooleanField(
                default=False,
                help_text="Soft-deleted by user from history; excluded from list view",
            ),
        ),
    ]
