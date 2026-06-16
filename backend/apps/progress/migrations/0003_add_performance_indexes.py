from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0002_learningpathprogress"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="userscenarioprogress",
            index=models.Index(fields=["user", "completed"], name="progress_user_completed_idx"),
        ),
        migrations.AddIndex(
            model_name="userscenarioprogress",
            index=models.Index(fields=["scenario", "completed"], name="progress_scenario_completed_idx"),
        ),
        migrations.AddIndex(
            model_name="userscenarioprogress",
            index=models.Index(fields=["completed", "best_score"], name="progress_completed_score_idx"),
        ),
    ]
