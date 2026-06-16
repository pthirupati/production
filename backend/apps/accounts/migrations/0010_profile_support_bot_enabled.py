from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_account_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="support_bot_enabled",
            field=models.BooleanField(default=True, help_text="Show the floating FixitLab support assistant"),
        ),
    ]
