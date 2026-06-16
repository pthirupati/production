from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0005_labsession_completion_finalized"),
    ]

    operations = [
        migrations.AddField(
            model_name="labsession",
            name="simulation_snapshot",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Persisted in-memory simulation engine state for worker restarts",
            ),
        ),
    ]
