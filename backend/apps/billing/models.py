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
    payment_method = models.CharField(max_length=20, blank=True, default="")
    is_active = models.BooleanField(default=True)
    payment_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    renewal_reminder_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "technology")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"], name="billing_tec_user_id_706c8d_idx"),
            models.Index(fields=["subscription_id"], name="billing_tec_subscri_084dfb_idx"),
            models.Index(fields=["is_active", "expires_at"], name="techsub_active_expires_idx"),
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


class SalesInquiry(models.Model):
    """Teams / Org "Contact Sales" inquiry.

    Captured from the public /contact-sales page. Admins triage these and can
    attach a custom quote (amount + currency + notes + validity) that the org
    negotiates to.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("quoted", "Quoted"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Submitter details
    full_name = models.CharField(max_length=150)
    organization = models.CharField(max_length=200)
    work_email = models.EmailField()
    company = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    team_size = models.CharField(max_length=50, blank=True, default="")
    message = models.TextField(blank=True, default="")

    # Triage
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handled_sales_inquiries",
    )

    # Custom quote the org negotiates to (nullable until an admin sets it)
    custom_quote_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    custom_quote_currency = models.CharField(max_length=3, blank=True, default="USD")
    custom_quote_notes = models.TextField(blank=True, default="")
    custom_quote_valid_until = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sales inquiry"
        verbose_name_plural = "Sales inquiries"
        indexes = [
            models.Index(fields=["status", "-created_at"], name="sales_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.organization} ({self.work_email}) — {self.status}"

    @property
    def has_quote(self):
        return self.custom_quote_amount is not None


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
    # ``amount`` is the GST-INCLUSIVE total actually charged (what the customer
    # paid and what the Razorpay order is created for). The tax breakup below is
    # extracted from it server-side (PRODUCTION_AUDIT FIN-01).
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # GST breakup (Indian tax compliance). taxable_amount + gst_amount == amount.
    # Zero tax when GST is disabled / no GSTIN — see apps.billing.gst.
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    place_of_supply = models.CharField(max_length=100, blank=True, default="")
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
    # Cumulative amount refunded (INR). The refund path enforces that this can
    # never exceed ``amount`` and is incremented atomically under a row lock
    # (PRODUCTION_AUDIT FIN-02).
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="billing_pay_user_created_idx"),
            models.Index(fields=["status"], name="billing_pay_status_idx"),
            models.Index(fields=["gateway_order_id"], name="billing_pay_gateway_order_idx"),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.amount} {self.currency} ({self.status})"

    @classmethod
    def generate_idempotency_key(cls, user_id, amount, currency, scope=""):
        """Stable key for one logical payment attempt.

        This used to mix in ``timezone.now().isoformat()``, which made every call
        return a fresh value — so the duplicate check it feeds in
        ``payment_service.create_transaction`` ("Check for existing transaction
        (idempotency)") could never match, and two rapid checkouts produced two
        pending transactions and two gateway orders. It also broke
        ``get_or_create(idempotency_key=...)`` in the Stripe interview path: a
        replayed webhook computed a *different* key, so ``created`` was True
        again and the plan was activated twice on one payment.

        ``scope`` is where a gateway order id belongs when the caller has one —
        that keeps two genuinely separate purchases of the same product distinct
        while still collapsing retries of the same one.
        """
        key_str = f"{user_id}-{amount}-{currency}-{scope}"
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


class SubscriptionInvoice(models.Model):
    """Downloadable invoice for successful subscription payments."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription_invoices",
    )
    payment_transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice",
    )
    tech_subscription = models.ForeignKey(
        TechnologySubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    technology_name = models.CharField(max_length=200)
    subscription_id = models.CharField(max_length=200, blank=True)
    # ``amount`` is the GST-inclusive total paid. The GST breakup below is
    # rendered on the tax invoice (PRODUCTION_AUDIT FIN-01); taxable_amount +
    # gst_amount == amount.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    place_of_supply = models.CharField(max_length=100, blank=True, default="")
    gstin = models.CharField(max_length=20, blank=True, default="")
    hsn_sac = models.CharField(max_length=20, blank=True, default="")
    currency = models.CharField(max_length=3, default="INR")
    payment_method = models.CharField(max_length=50, blank=True)
    gateway_payment_id = models.CharField(max_length=200, blank=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="billing_sub_user_id_idx"),
            models.Index(fields=["invoice_number"], name="billing_sub_invoice_num_idx"),
        ]

    def __str__(self):
        return self.invoice_number


class CouponCode(models.Model):
    """Admin-managed promo / discount codes."""

    DISCOUNT_TYPE_CHOICES = [
        ("percent", "Percentage"),
        ("fixed", "Fixed amount (INR)"),
    ]

    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="percent")
    discount_value = models.DecimalField(max_digits=8, decimal_places=2, help_text="Percent or INR amount")
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def is_valid_now(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def apply_to_amount(self, amount_inr: int) -> int:
        """Return discounted amount in INR (integer)."""
        from decimal import Decimal
        amount = Decimal(amount_inr)
        if self.discount_type == "percent":
            discount = amount * (self.discount_value / Decimal("100"))
        else:
            discount = self.discount_value
        result = max(Decimal("1"), amount - discount)
        return int(result)


class CouponRedemption(models.Model):
    """One row per (coupon, user) redemption.

    SECURITY_AUDIT P-03: enforces a per-user redemption limit. The
    ``unique_together`` makes a second redemption of the same coupon by the same
    user impossible at the DB level (a duplicate insert raises IntegrityError),
    which closes the "same user redeems a single-use coupon repeatedly" hole and
    makes ``redeem_coupon`` idempotent under concurrency.
    """

    coupon = models.ForeignKey(
        CouponCode,
        on_delete=models.CASCADE,
        related_name="redemptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coupon_redemptions",
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("coupon", "user")
        indexes = [
            models.Index(fields=["coupon", "user"]),
        ]

    def __str__(self):
        return f"{self.coupon_id}:{self.user_id}"


class ProcessedWebhookEvent(models.Model):
    """Durable record of a processed payment-provider webhook event.

    The webhook handler dedups fast via Redis (``cache.add``), but a Redis flush
    would reopen a double-fulfillment window on replay. This table is the
    authoritative, durable idempotency gate: fulfillment is guarded on
    ``get_or_create(event_id=...)`` so a replayed event is a no-op.
    """

    event_id = models.CharField(max_length=200, unique=True, db_index=True)
    provider = models.CharField(max_length=32, default="razorpay")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Processed webhook event"
        verbose_name_plural = "Processed webhook events"

    def __str__(self):
        return f"{self.provider}:{self.event_id}"


class UserCertificate(models.Model):
    """Stored certificate with issue and expiry dates."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    certificate_id = models.CharField(max_length=120, unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "technology")
        ordering = ["-issued_at"]

    def __str__(self):
        return self.certificate_id

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

