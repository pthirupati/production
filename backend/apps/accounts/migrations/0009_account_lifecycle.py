# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0008_org_stripe_pending_invite"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountLifecycleEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("event_type", models.CharField(
                    choices=[
                        ("inactive_warning", "Inactive account warning sent"),
                        ("deleted", "Account deleted (no subscription)"),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="lifecycle_events",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="accountlifecycleevent",
            index=models.Index(fields=["user", "event_type"], name="accounts_ac_user_id_8f3c2a_idx"),
        ),
        migrations.AddIndex(
            model_name="accountlifecycleevent",
            index=models.Index(fields=["email", "event_type"], name="accounts_ac_email_4d1b9e_idx"),
        ),
    ]
