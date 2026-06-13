from django.db import models
from django.conf import settings
from django.utils import timezone
import hashlib
import uuid


class Plan(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    code = models.CharField(max_length=50, unique=True, choices=PLAN_CHOICES)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    stripe_price_id = models.CharField(max_length=100, blank=True, default="")

    max_labs_per_day = models.PositiveIntegerField(default=3)
    max_lab_duration_minutes = models.PositiveIntegerField(default=60)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT
    )

    stripe_customer_id = models.CharField(max_length=100, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=100, blank=True, default="")

    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user} - {self.plan.code}"


class TechnologySubscription(models.Model):
    """Per-technology subscription for paid access to specific technologies."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tech_subscriptions",
    )
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    subscription_id = models.CharField(
        max_length=200,
        unique=True,
        help_text="Unique subscription ID: TECH-USERNAME-YEAR-FIXITLAB",
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    payment_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    renewal_reminder_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "technology")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["subscription_id"]),
        ]

    def __str__(self):
        return self.subscription_id

    @classmethod
    def generate_subscription_id(cls, technology_name, username, year=None):
        """Generate unique subscription ID: TECH-USERNAME-YEAR-FIXITLAB"""
        if year is None:
            year = timezone.now().year
        tech = technology_name.upper().replace(" ", "-")
        user = username.upper().replace(" ", "-")
        return f"{tech}-{user}-{year}-FIXITLAB"

    def save(self, *args, **kwargs):
        if not self.subscription_id:
            self.subscription_id = self.generate_subscription_id(
                self.technology.name,
                self.user.username,
            )
        super().save(*args, **kwargs)


class PaymentTransaction(models.Model):
    """Track all payment transactions with idempotency and audit trail."""

    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]
    PAYMENT_METHOD = [
        ("razorpay", "Razorpay"),
        ("stripe", "Stripe"),
        ("demo", "Demo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="pending")
    idempotency_key = models.CharField(max_length=128, unique=True, db_index=True)
    gateway_order_id = models.CharField(max_length=200, blank=True, db_index=True)
    gateway_payment_id = models.CharField(max_length=200, blank=True, db_index=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    tech_subscription = models.ForeignKey(
        TechnologySubscription, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions",
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["gateway_order_id"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.amount} {self.currency} ({self.status})"

    @classmethod
    def generate_idempotency_key(cls, user_id, amount, currency):
        key_str = f"{user_id}-{amount}-{currency}-{timezone.now().isoformat()}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def mark_success(self, gateway_payment_id=None, gateway_response=None):
        self.status = "success"
        self.verified_at = timezone.now()
        if gateway_payment_id:
            self.gateway_payment_id = gateway_payment_id
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=[
            "status", "verified_at", "gateway_payment_id", "gateway_response",
        ])

    def mark_failed(self, error_message=""):
        self.status = "failed"
        self.error_message = error_message
        self.save(update_fields=["status", "error_message"])

    def mark_cancelled(self, error_message=""):
        self.status = "cancelled"
        self.error_message = error_message
        self.save(update_fields=["status", "error_message"])


