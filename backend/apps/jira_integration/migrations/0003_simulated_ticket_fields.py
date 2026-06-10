from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jira_integration", "0002_jira_webhooks"),
    ]

    operations = [
        migrations.AddField(
            model_name="userscenariojiraticket",
            name="summary",
            field=models.CharField(blank=True, max_length=255, default=""),
        ),
        migrations.AddField(
            model_name="userscenariojiraticket",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="userscenariojiraticket",
            name="priority",
            field=models.CharField(blank=True, default="Medium", max_length=30),
        ),
        migrations.AddField(
            model_name="userscenariojiraticket",
            name="simulated",
            field=models.BooleanField(default=False),
        ),
    ]
