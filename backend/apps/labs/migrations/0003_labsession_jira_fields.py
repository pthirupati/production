from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0002_alter_provider_commandhistory_sessionrecording"),
    ]

    operations = [
        migrations.AddField(
            model_name="labsession",
            name="jira_issue_key",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="labsession",
            name="jira_issue_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
