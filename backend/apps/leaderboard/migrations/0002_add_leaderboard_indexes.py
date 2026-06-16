from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="leaderboardentry",
            index=models.Index(fields=["rank"], name="leaderboard_rank_idx"),
        ),
        migrations.AddIndex(
            model_name="leaderboardentry",
            index=models.Index(fields=["scenario", "rank"], name="leaderboard_scenario_rank_idx"),
        ),
    ]
