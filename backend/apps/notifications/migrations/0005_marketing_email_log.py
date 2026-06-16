from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0004_alter_notificationpreference_lab_email_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationpreference",
            name="email_marketing",
            field=models.BooleanField(
                default=True,
                help_text="Subscribe reminders, product tips, and benefit emails",
            ),
        ),
        migrations.CreateModel(
            name="MarketingEmailLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "campaign",
                    models.CharField(
                        choices=[
                            ("interview_sample_nudge", "Interview sample → subscribe"),
                            ("technology_subscribe_nudge", "No tech subscription nudge"),
                        ],
                        db_index=True,
                        max_length=64,
                    ),
                ),
                ("sent_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="marketing_emails",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-sent_at"],
                "indexes": [
                    models.Index(fields=["user", "campaign", "-sent_at"], name="notificatio_user_id_8a1f2c_idx"),
                ],
            },
        ),
    ]
