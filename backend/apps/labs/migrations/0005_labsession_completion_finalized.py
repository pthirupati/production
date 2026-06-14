from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0004_labsession_lab_hosts"),
    ]

    operations = [
        migrations.AddField(
            model_name="labsession",
            name="completion_finalized",
            field=models.BooleanField(
                default=False,
                help_text="True once scenario progress was recorded (after Jira ticket closed)",
            ),
        ),
    ]
