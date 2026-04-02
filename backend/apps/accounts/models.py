from django.contrib.auth.models import User
from django.db import models
from django.core.validators import RegexValidator
import uuid
import hashlib
from django.utils import timezone


phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be in format: '+999999999'. Up to 15 digits allowed."
)


class Profile(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class EmailVerificationOTP(models.Model):
    """6-digit OTP for email verification during registration."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
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

    @classmethod
    def generate(cls, email, minutes=10):
        """Create a new OTP for email verification."""
        import secrets
        code = f"{secrets.randbelow(1000000):06d}"
        session_token = uuid.uuid4().hex + uuid.uuid4().hex
        # Invalidate any previous OTPs for this email
        cls.objects.filter(email=email, verified=False).update(verified=True)
        instance = cls.objects.create(
            email=email,
            code=code,
            session_token=session_token,
            expires_at=timezone.now() + timezone.timedelta(minutes=minutes),
        )
        return instance, code, session_token

    @classmethod
    def verify(cls, session_token, code):
        """Verify an OTP code. Returns the instance if valid."""
        try:
            instance = cls.objects.get(session_token=session_token)
            if not instance.is_valid:
                return None, "OTP has expired or already been used. Please request a new one."
            instance.attempts += 1
            instance.save(update_fields=["attempts"])
            if instance.code != code:
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

