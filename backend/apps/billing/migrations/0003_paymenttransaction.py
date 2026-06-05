from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_plan_stripe_price_id_subscription_stripe_customer_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("payment_method", models.CharField(
                    choices=[("razorpay", "Razorpay"), ("stripe", "Stripe"), ("demo", "Demo")],
                    max_length=20,
                )),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"), ("processing", "Processing"),
                        ("success", "Success"), ("failed", "Failed"),
                        ("cancelled", "Cancelled"), ("refunded", "Refunded"),
                    ],
                    default="pending", max_length=20,
                )),
                ("idempotency_key", models.CharField(db_index=True, max_length=128, unique=True)),
                ("gateway_order_id", models.CharField(blank=True, db_index=True, max_length=200)),
                ("gateway_payment_id", models.CharField(blank=True, db_index=True, max_length=200)),
                ("gateway_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("plan", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="transactions", to="billing.plan",
                )),
                ("tech_subscription", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="transactions", to="billing.technologysubscription",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="paymenttransaction",
            index=models.Index(fields=["user", "-created_at"], name="billing_pay_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="paymenttransaction",
            index=models.Index(fields=["status"], name="billing_pay_status_idx"),
        ),
    ]
