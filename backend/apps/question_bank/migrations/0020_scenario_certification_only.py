from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0019_technology_is_free"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenario",
            name="certification_only",
            field=models.BooleanField(
                default=False,
                help_text="Show only under certification tracks — excluded from normal technology scenario lists",
            ),
        ),
    ]
