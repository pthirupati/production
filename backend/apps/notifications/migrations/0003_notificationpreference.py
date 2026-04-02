# Generated for NotificationPreference model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_emaillog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_achievements", models.BooleanField(default=True, help_text="Email when earning achievements")),
                ("email_lab_completed", models.BooleanField(default=True, help_text="Email when completing a lab")),
                ("email_lab_expired", models.BooleanField(default=True, help_text="Email when a lab session expires")),
                ("email_subscription", models.BooleanField(default=True, help_text="Email for subscription confirmations")),
                ("email_marketing", models.BooleanField(default=False, help_text="Marketing and product update emails")),
                ("inapp_achievements", models.BooleanField(default=True)),
                ("inapp_lab_events", models.BooleanField(default=True)),
                ("inapp_system", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Notification Preference",
            },
        ),
    ]
