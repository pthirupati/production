import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jira_integration", "0003_simulated_ticket_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingTeamReply",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("issue_key", models.CharField(db_index=True, max_length=50)),
                ("session_id", models.CharField(blank=True, default="", max_length=64)),
                ("author", models.TextField()),
                ("message", models.TextField()),
                ("actions", models.JSONField(default=list)),
                (
                    "scenario_slug",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("deliver_at", models.DateTimeField(db_index=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["deliver_at"],
            },
        ),
    ]
