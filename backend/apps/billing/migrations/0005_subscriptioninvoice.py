import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0004_technologysubscription_renewal_reminder"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionInvoice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("invoice_number", models.CharField(db_index=True, max_length=64, unique=True)),
                ("technology_name", models.CharField(max_length=200)),
                ("subscription_id", models.CharField(blank=True, max_length=200)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("payment_method", models.CharField(blank=True, max_length=50)),
                ("gateway_payment_id", models.CharField(blank=True, max_length=200)),
                ("period_start", models.DateTimeField(blank=True, null=True)),
                ("period_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "payment_transaction",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoice",
                        to="billing.paymenttransaction",
                    ),
                ),
                (
                    "tech_subscription",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoices",
                        to="billing.technologysubscription",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="billing_sub_user_id_idx"),
                    models.Index(fields=["invoice_number"], name="billing_sub_invoice_num_idx"),
                ],
            },
        ),
    ]
