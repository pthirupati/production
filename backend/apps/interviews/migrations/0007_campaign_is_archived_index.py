from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0006_campaign_is_archived"),
    ]

    operations = [
        migrations.AlterField(
            model_name="interviewcampaign",
            name="is_archived",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Soft-deleted by user from history; excluded from list view",
            ),
        ),
    ]
