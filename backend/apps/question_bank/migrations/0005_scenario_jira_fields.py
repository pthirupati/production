from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0004_scenario_blocked_commands"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenario",
            name="jira_priority",
            field=models.CharField(
                blank=True, default="",
                help_text="Jira priority name (e.g. High, Medium, Low)",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="jira_issue_template",
            field=models.TextField(
                blank=True,
                help_text="Optional custom Jira ticket body override (plain text)",
            ),
        ),
    ]
