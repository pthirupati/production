# Generated manually for cert addon pricing + track subscriptions

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("certifications", "0003_certificationtrack_coming_soon_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="certificationtrack",
            name="addon_price",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Addon price (INR) on top of the linked technology subscription (0 = use standalone price only)",
            ),
        ),
        migrations.AlterField(
            model_name="certificationtrack",
            name="price",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Standalone price (INR) — full cert prep + mock exam without buying the base technology separately",
            ),
        ),
        migrations.CreateModel(
            name="CertificationTrackSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subscription_id", models.CharField(max_length=200, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "track",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="certifications.certificationtrack",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cert_track_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "is_active"], name="cert_sub_user_active_idx"),
                ],
                "unique_together": {("user", "track")},
            },
        ),
    ]
