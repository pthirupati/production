from django.contrib.auth.models import User
from django.db import models
from django.core.validators import RegexValidator
import uuid
import hashlib
import secrets
import string
from django.utils import timezone


phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be in format: '+999999999'. Up to 15 digits allowed."
)


class Profile(models.Model):
    CURRENCY_CHOICES = [
        ("INR", "Indian Rupees (₹)"),
        ("USD", "US Dollars ($)"),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(
        max_length=17, blank=True, null=True,
        validators=[phone_validator],
        help_text="Phone number in international format"
    )
    country = models.CharField(
        max_length=100, blank=True, default="",
        help_text="User's country or location"
    )
    # Which legal text this account agreed to, and when (audit Z4-8). Recorded from
    # the server's current version at the moment of acceptance — never from a value
    # the client supplies, since the client is not the authority on what it was
    # shown. Blank means "predates this field", which is a truthful answer and a
    # different one from "accepted an unknown version".
    # When the user last dismissed the "turn on two-factor" nudge (audit Z2-3).
    # A prompt that returns on every single login is one people learn to click
    # past without reading, which is worse than not asking.
    mfa_prompt_dismissed_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=32, blank=True, default="")
    privacy_version = models.CharField(max_length=32, blank=True, default="")
    billing_state = models.CharField(
        max_length=100, blank=True, default="",
        help_text=(
            "Indian state/UT used as the GST place of supply. Blank means no "
            "address on record, which under the CGST place-of-supply rules for "
            "B2C services falls back to the seller's state (audit Z1-13)."
        ),
    )
    currency_preference = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default="INR",
        help_text="Preferred currency for pricing display"
    )
    complimentary_access = models.BooleanField(
        default=False,
        help_text="Admin-granted free access to all technologies",
    )
    support_bot_enabled = models.BooleanField(
        default=True,
        help_text="Show the floating FixitLab support assistant",
    )
    daily_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    xp = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    referral_code = models.CharField(max_length=20, unique=True, blank=True, default="")
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Ambiguous characters removed: these codes get read aloud, typed from a
    # screenshot and dictated over a call. O/0 and I/1/L are where that goes wrong,
    # and a mistyped code silently attributes the signup to nobody.
    REFERRAL_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    REFERRAL_CODE_LENGTH = 8

    @classmethod
    def generate_referral_code(cls) -> str:
        """A code that is not already taken.

        `referral_code` is `unique=True` and the previous version generated one
        random string with no collision check, so a duplicate would surface as an
        IntegrityError **during signup** (audit Z6-16). At 31^8 that is vanishingly
        unlikely, but the failure mode is a user unable to create an account, and
        the retry costs one indexed lookup.
        """
        for _ in range(5):
            code = "".join(
                secrets.choice(cls.REFERRAL_ALPHABET)
                for _ in range(cls.REFERRAL_CODE_LENGTH)
            )
            if not cls.objects.filter(referral_code=code).exists():
                return code
        # Five collisions means something is badly wrong with the RNG; fall back to
        # a longer code rather than failing the signup.
        return "".join(
            secrets.choice(cls.REFERRAL_ALPHABET)
            for _ in range(cls.REFERRAL_CODE_LENGTH + 4)
        )

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.username


class EmailVerificationOTP(models.Model):
    """6-digit OTP for email verification during registration."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    # Hashed, not plaintext (audit Z4-11). The 6-digit code used to be stored as-is
    # for its whole lifetime, so a database dump — or a staff member reading the
    # Django admin, where it was a readonly_field — yielded a live credential good
    # for immediate account takeover. It is only ever compared, never replayed, so
    # there is no reason to keep it recoverable.
    code_hash = models.CharField(max_length=128)
    session_token = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.email}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.verified and not self.is_expired and self.attempts < 5

    def _code_matches(self, code, check_password) -> bool:
        """Compare a submitted code against the stored hash.

        No plaintext fallback: migration 0013 drops the old column rather than
        renaming it, so a plaintext code cannot survive into `code_hash`. An empty
        hash therefore means a malformed row and must not match anything — returning
        True on empty is the classic fail-open here.
        """
        stored = self.code_hash or ""
        if not stored:
            return False
        return check_password(str(code), stored)

    @classmethod
    def generate(cls, email, minutes=10):
        """Create a new OTP for email verification."""
        import secrets
        code = f"{secrets.randbelow(1000000):06d}"
        session_token = uuid.uuid4().hex + uuid.uuid4().hex
        # Invalidate any previous OTPs for this email
        cls.objects.filter(email=email, verified=False).update(verified=True)
        from django.contrib.auth.hashers import make_password

        instance = cls.objects.create(
            email=email,
            code_hash=make_password(code),
            session_token=session_token,
            expires_at=timezone.now() + timezone.timedelta(minutes=minutes),
        )
        # The plaintext code is RETURNED (to email it) and never persisted.
        return instance, code, session_token

    @classmethod
    def verify(cls, session_token, code):
        """Verify an OTP code. Returns the instance if valid."""
        from django.contrib.auth.hashers import check_password

        try:
            instance = cls.objects.get(session_token=session_token)
            if not instance.is_valid:
                return None, "OTP has expired or already been used. Please request a new one."
            instance.attempts += 1
            instance.save(update_fields=["attempts"])
            if not instance._code_matches(code, check_password):
                remaining = 5 - instance.attempts
                if remaining <= 0:
                    return None, "Too many failed attempts. Please request a new OTP."
                return None, f"Invalid OTP code. {remaining} attempts remaining."
            instance.verified = True
            instance.save(update_fields=["verified"])
            return instance, None
        except cls.DoesNotExist:
            return None, "Invalid session. Please request a new OTP."


class SocialAccount(models.Model):
    """Linked social OAuth account (GitHub, Google)."""
    PROVIDER_CHOICES = [
        ("github", "GitHub"),
        ("google", "Google"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_uid = models.CharField(max_length=255)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "provider_uid")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}:{self.provider_uid} → {self.user.email}"


class PasswordResetToken(models.Model):
    """Token for email-based password reset flow."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PasswordReset for {self.user.email}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.used and not self.is_expired

    @classmethod
    def generate_token(cls, user, hours=1):
        """Create a new password reset token valid for given hours."""
        raw_token = uuid.uuid4().hex + uuid.uuid4().hex
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        instance = cls.objects.create(
            user=user,
            token=hashed_token,
            expires_at=timezone.now() + timezone.timedelta(hours=hours),
        )
        return instance, raw_token  # Return raw token for email, store hash

    @classmethod
    def verify_token(cls, raw_token):
        """Verify a raw token and return the instance if valid."""
        hashed = hashlib.sha256(raw_token.encode()).hexdigest()
        try:
            instance = cls.objects.select_related("user").get(token=hashed)
            if instance.is_valid:
                return instance
        except cls.DoesNotExist:
            pass
        return None


class ContactMessage(models.Model):
    """Messages submitted via the public contact form."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=300)
    message = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.name} ({self.email})"


class Organization(models.Model):
    """Enterprise / team account with shared technology access."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_organizations")
    seat_limit = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    billing_email = models.EmailField(blank=True, default="")
    stripe_customer_id = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    # Outbound webhook for org events (lab completed, member joined, etc.)
    webhook_url = models.URLField(max_length=500, blank=True, default="")
    webhook_secret = models.CharField(max_length=100, blank=True, default="")
    # Branding
    logo_url = models.URLField(max_length=500, blank=True, default="")
    primary_color = models.CharField(max_length=7, blank=True, default="", help_text="Hex color, e.g. #6366f1")
    custom_domain = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()


class OrganizationMember(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="organization_memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    invited_email = models.EmailField(blank=True, default="")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "user")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user.username} @ {self.organization.name}"


class OrganizationTechnologyGrant(models.Model):
    """Team-wide access to a technology track."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="technology_grants")
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.CASCADE,
        related_name="organization_grants",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "technology")]

    def is_valid_now(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class PendingOrgInvite(models.Model):
    """Invite sent before user registers — auto-join on OTP signup with matching email."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="pending_invites")
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=20, choices=OrganizationMember.ROLE_CHOICES, default="member")
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_org_invites",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "email")]
        ordering = ["-created_at"]

    def is_valid(self) -> bool:
        return self.accepted_at is None and timezone.now() < self.expires_at


class AccountLifecycleEvent(models.Model):
    """Tracks inactive-account warnings and deletions (audit survives user delete)."""

    EVENT_CHOICES = [
        ("inactive_warning", "Inactive account warning sent"),
        ("deleted", "Account deleted (no subscription)"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_events",
    )
    email = models.EmailField(db_index=True)
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "event_type"], name="accounts_ac_user_id_8f3c2a_idx"),
            models.Index(fields=["email", "event_type"], name="accounts_ac_email_4d1b9e_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} — {self.email}"


# TOTP multi-factor authentication (audit Z2-3). Defined in their own module for
# readability; re-exported here so Django's app loader registers them.
from .mfa_models import MfaDevice, MfaRecoveryCode, mfa_required_for  # noqa: E402,F401
