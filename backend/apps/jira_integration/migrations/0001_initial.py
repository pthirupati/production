# Generated manually for jira_integration app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("labs", "0003_labsession_jira_fields"),
        ("question_bank", "0005_scenario_jira_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="JiraTicketLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_key", models.CharField(max_length=50)),
                ("issue_url", models.URLField(blank=True, max_length=500)),
                ("action", models.CharField(
                    choices=[
                        ("created", "Created"),
                        ("in_progress", "In Progress"),
                        ("reset", "Reset"),
                        ("completed", "Completed"),
                        ("cancelled", "Cancelled"),
                        ("failed", "Failed"),
                        ("comment", "Comment"),
                    ],
                    max_length=20,
                )),
                ("jira_status", models.CharField(blank=True, max_length=50)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="jira_logs",
                    to="labs.labsession",
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UserScenarioJiraTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_key", models.CharField(max_length=50)),
                ("issue_url", models.URLField(blank=True, max_length=500)),
                ("run_count", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_session", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to="labs.labsession",
                )),
                ("scenario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="jira_tickets",
                    to="question_bank.scenario",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="scenario_jira_tickets",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.AddIndex(
            model_name="jiraticketlog",
            index=models.Index(fields=["issue_key"], name="jira_integ_issue_k_idx"),
        ),
        migrations.AddIndex(
            model_name="jiraticketlog",
            index=models.Index(fields=["session", "created_at"], name="jira_integ_session_idx"),
        ),
        migrations.AddIndex(
            model_name="userscenariojiraticket",
            index=models.Index(fields=["issue_key"], name="jira_integ_user_issue_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="userscenariojiraticket",
            unique_together={("user", "scenario")},
        ),
    ]
