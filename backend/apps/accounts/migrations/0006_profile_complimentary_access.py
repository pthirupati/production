from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_profile_currency_preference"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="complimentary_access",
            field=models.BooleanField(
                default=False,
                help_text="Admin-granted free access to all technologies",
            ),
        ),
    ]
