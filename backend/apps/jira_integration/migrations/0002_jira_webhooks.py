from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0003_labsession_jira_fields"),
        ("jira_integration", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userscenariojiraticket",
            name="jira_status",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AlterField(
            model_name="jiraticketlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("in_progress", "In Progress"),
                    ("reset", "Reset"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                    ("failed", "Failed"),
                    ("comment", "Comment"),
                    ("webhook", "Webhook"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="JiraCommentLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_key", models.CharField(db_index=True, max_length=50)),
                ("jira_comment_id", models.CharField(db_index=True, max_length=50, unique=True)),
                ("author", models.CharField(max_length=255)),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField()),
                ("logged_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="jira_comments", to="labs.labsession",
                )),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="JiraWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("webhook_type", models.CharField(db_index=True, max_length=80)),
                ("jira_issue_key", models.CharField(db_index=True, max_length=50)),
                ("payload", models.JSONField()),
                ("processed", models.BooleanField(default=False)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["jira_issue_key", "processed"], name="jira_webhook_issue_proc_idx")],
            },
        ),
    ]
