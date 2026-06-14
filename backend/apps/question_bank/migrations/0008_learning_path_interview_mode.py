from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0007_technology_coming_soon_scenario_lab_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="technology",
            name="learning_path",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Ordered learning path steps: [{title, scenario_slug, description}]",
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="interview_mode",
            field=models.BooleanField(
                default=False,
                help_text="Timed interview-style scenario with stricter hints",
            ),
        ),
    ]
