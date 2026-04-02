from django.db import models
from django.conf import settings
from django.utils import timezone
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


