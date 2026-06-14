import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0007_technology_coming_soon_scenario_lab_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0005_subscriptioninvoice"),
    ]

    operations = [
        migrations.CreateModel(
            name="CouponCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("percent", "Percentage"), ("fixed", "Fixed amount (INR)")],
                        default="percent",
                        max_length=10,
                    ),
                ),
                (
                    "discount_value",
                    models.DecimalField(decimal_places=2, help_text="Percent or INR amount", max_digits=8),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "max_uses",
                    models.PositiveIntegerField(blank=True, help_text="Leave blank for unlimited", null=True),
                ),
                ("used_count", models.PositiveIntegerField(default=0)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="UserCertificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("certificate_id", models.CharField(max_length=120, unique=True)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "technology",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificates",
                        to="question_bank.technology",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-issued_at"],
                "unique_together": {("user", "technology")},
            },
        ),
    ]
