"""TOTP multi-factor authentication (audit Z2-3).

There was no MFA of any kind, on a platform that takes payments, stores resumes
and interview transcripts, and sells org seats at Rs 4,999 each. Every `saml`/`sso`
hit in the repo was simulated lab content.

This is the TOTP half. SSO/SAML/SCIM is a separate, much larger piece of work that
needs an IdP decision first; TOTP is the industry baseline and closes the part that
matters most immediately — an administrator account protected by a password alone.

Four things distinguish a real TOTP implementation from a decorative one, and each
is the reason for a field below:

1. **Replay protection.** A code is valid for a 30-second window, so without
   recording the last consumed counter the same code works repeatedly inside that
   window — an attacker who shoulder-surfs or intercepts one code gets a free
   replay. `last_used_counter` makes each code single-use. This is the single most
   commonly omitted control.
2. **Recovery codes.** Without them a lost phone is a permanently locked account
   and support ends up disabling MFA on request, which quietly reduces the whole
   scheme to a password again. Stored hashed and single-use.
3. **Clock drift.** Phones drift. A +/-1 step window is the standard tolerance;
   wider starts trading real security for convenience.
4. **Confirmed-before-enforced.** A secret that is generated but never verified
   must not gate login, or a user who scans nothing locks themselves out. `enabled`
   only becomes true after one successful verification.
"""

import base64
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

# +/-1 step of 30s. Google Authenticator, Authy and 1Password all assume this.
TOTP_VALID_WINDOW = 1
TOTP_DIGITS = 6
TOTP_INTERVAL = 30

RECOVERY_CODE_COUNT = 10


def _hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage.

    These are 80 bits of `secrets.token_hex` entropy, not user-chosen passwords, so
    a single SHA-256 is appropriate — a slow KDF exists to make *guessable* secrets
    expensive to attack, and there is nothing to guess here. Using bcrypt would
    cost 10 hashes per verification attempt for no added protection.
    """
    return hashlib.sha256(code.encode()).hexdigest()


class MfaDevice(models.Model):
    """One TOTP authenticator bound to a user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mfa_device",
    )
    # Base32, as the authenticator apps expect. Not encrypted at rest: it lives in
    # the same database as the password hashes and session data, so anyone who can
    # read it has already lost the account by other means. Encrypting with
    # SECRET_KEY would also make MFA break on key rotation, trading a real
    # availability failure for an imagined confidentiality gain.
    secret = models.CharField(max_length=64)
    enabled = models.BooleanField(
        default=False,
        help_text="False until the user proves they can generate a code (see module docstring).",
    )
    # Replay guard: the last TOTP counter successfully consumed.
    last_used_counter = models.BigIntegerField(default=0)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MFA device"

    def __str__(self):
        return f"MFA({self.user_id}, {'on' if self.enabled else 'pending'})"

    @staticmethod
    def new_secret() -> str:
        # 160 bits, the RFC 4226 recommendation.
        return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")

    def provisioning_uri(self) -> str:
        """otpauth:// URI for the QR code."""
        import pyotp

        issuer = getattr(settings, "MFA_ISSUER", "FixitLab")
        return pyotp.TOTP(
            self.secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL
        ).provisioning_uri(name=self.user.email, issuer_name=issuer)

    def verify(self, code: str, *, consume: bool = True) -> bool:
        """Check `code`, rejecting a replay of one already used.

        `consume=False` is only for the enrolment preview; every login path must
        consume, or the replay guard does nothing.
        """
        import pyotp

        code = (code or "").strip().replace(" ", "")
        if not code.isdigit() or len(code) != TOTP_DIGITS:
            return False

        totp = pyotp.TOTP(self.secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        if not totp.verify(code, valid_window=TOTP_VALID_WINDOW):
            return False

        counter = int(timezone.now().timestamp()) // TOTP_INTERVAL
        # The accepted code may belong to an adjacent step; find which, so the
        # guard advances to the right counter rather than always to "now".
        for offset in range(-TOTP_VALID_WINDOW, TOTP_VALID_WINDOW + 1):
            candidate = counter + offset
            if hmac.compare_digest(totp.at(candidate * TOTP_INTERVAL), code):
                if candidate <= self.last_used_counter:
                    return False  # replay
                if consume:
                    self.last_used_counter = candidate
                    self.save(update_fields=["last_used_counter"])
                return True
        return False

    def generate_recovery_codes(self) -> list[str]:
        """Replace all recovery codes, returning the plaintext ONCE.

        Regenerating wipes the old set on purpose: a user who regenerates because
        they think the old codes leaked must actually invalidate them.
        """
        self.recovery_codes.all().delete()
        codes = []
        for _ in range(RECOVERY_CODE_COUNT):
            raw = secrets.token_hex(5)  # 80 bits, shown as 10 hex chars
            codes.append(raw)
            MfaRecoveryCode.objects.create(device=self, code_hash=_hash_recovery_code(raw))
        return codes

    def consume_recovery_code(self, code: str) -> bool:
        """Spend a recovery code. Single-use by deletion."""
        code = (code or "").strip().replace("-", "").replace(" ", "").lower()
        if not code:
            return False
        match = self.recovery_codes.filter(code_hash=_hash_recovery_code(code)).first()
        if not match:
            return False
        match.delete()
        return True


class MfaRecoveryCode(models.Model):
    """A single-use recovery code, stored hashed."""

    device = models.ForeignKey(
        MfaDevice, on_delete=models.CASCADE, related_name="recovery_codes"
    )
    code_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"recovery({self.device_id})"


# How long a dismissal lasts. Long enough not to nag, short enough that someone
# who uploaded a resume months ago is asked again.
MFA_PROMPT_SNOOZE_DAYS = 30


def mfa_recommended_for(user) -> bool:
    """Whether to *suggest* MFA — never to require it.

    Mandating TOTP for every learner would cost more signups than it protects: a
    typical account holds course progress. But this platform is not typical. The
    AI Interview Studio stores resumes, interview transcripts, `current_company`
    and `current_package_lpa`, so a compromised account there leaks that a named
    person is job-hunting and what they currently earn. That is materially more
    sensitive than which Kubernetes lab someone finished, and it is attached to
    ordinary non-staff accounts.

    So the split is not "learner versus admin" — it is how much of this person's
    data is actually sensitive. Anyone in that position gets asked; nobody gets
    blocked.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    device = getattr(user, "mfa_device", None)
    if device and device.enabled:
        return False        # already protected; nothing to suggest
    if user.is_staff or user.is_superuser:
        return False        # required, not recommended -- a different message

    profile = getattr(user, "profile", None)
    dismissed = getattr(profile, "mfa_prompt_dismissed_at", None) if profile else None
    if dismissed and (timezone.now() - dismissed).days < MFA_PROMPT_SNOOZE_DAYS:
        return False

    return user_holds_sensitive_career_data(user)


def user_holds_sensitive_career_data(user) -> bool:
    """True when the account carries resume or interview content.

    Kept separate and narrow: it names the specific fields rather than "has a
    CandidateProfile", because the row is created as soon as someone opens the
    interview section and an empty profile is not sensitive.
    """
    try:
        from apps.interviews.models import CandidateProfile, InterviewCampaign
    except Exception:
        return False

    has_profile_data = CandidateProfile.objects.filter(user=user).exclude(
        resume_file="", resume_text="", current_company="", target_role="",
        current_package_lpa__isnull=True,
    ).exists()
    if has_profile_data:
        return True
    # `InterviewRound` hangs off `InterviewCampaign`, which is what carries the
    # user — there is no direct candidate_profile relation. Getting this wrong
    # would have made the whole recommendation silently return False.
    return InterviewCampaign.objects.filter(user=user).exists()


def mfa_required_for(user) -> bool:
    """Whether this account must complete MFA to sign in.

    Mandatory for staff and superusers — they can grant paid access, read audit
    logs and reset passwords, so a password alone is not a defensible control on
    those accounts. Optional for everyone else: forcing TOTP on a learner signing
    up for a Rs 499 lab would cost more signups than it protects.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    device = getattr(user, "mfa_device", None)
    return bool(device and device.enabled)
