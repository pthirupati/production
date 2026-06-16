from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0010_alter_scenario_simulation_type"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="scenario",
            index=models.Index(fields=["is_active", "technology"], name="scenario_active_tech_idx"),
        ),
        migrations.AddIndex(
            model_name="scenario",
            index=models.Index(fields=["is_active", "difficulty"], name="scenario_active_diff_idx"),
        ),
    ]
