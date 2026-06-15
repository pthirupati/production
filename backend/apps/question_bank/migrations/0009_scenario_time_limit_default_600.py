from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0008_learning_path_interview_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scenario",
            name="time_limit",
            field=models.PositiveIntegerField(
                default=600,
                help_text="Time limit in seconds (default 10 min)",
            ),
        ),
    ]
