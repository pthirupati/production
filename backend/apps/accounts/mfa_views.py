"""MFA enrolment and the second login step (audit Z2-3)."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.security import TokenHelper
from common.throttles import MfaVerifyThrottle
from .mfa_models import MFA_PROMPT_SNOOZE_DAYS, MfaDevice, mfa_required_for
from .views import set_auth_cookies

logger = logging.getLogger(__name__)
User = get_user_model()

# The intermediate token issued between password and code.
#
# It is a `TimestampSigner` payload with its own salt, NOT a JWT — deliberately.
# A JWT here would be accepted by every `IsAuthenticated` view in the project the
# moment someone passed it as a Bearer token, which would make "MFA required" mean
# "MFA optional, and here is a working session". This value is only ever read by
# `MfaLoginVerifyView` and carries nothing but a user id and a purpose.
_CHALLENGE_SALT = "fixitlab.mfa.challenge"
CHALLENGE_TTL_SECONDS = 5 * 60


def issue_mfa_challenge(user) -> str:
    return signing.dumps(
        {"uid": user.id, "purpose": "mfa"}, salt=_CHALLENGE_SALT
    )


def read_mfa_challenge(token: str):
    """Return the user for a valid, unexpired challenge, else None."""
    try:
        data = signing.loads(
            token or "", salt=_CHALLENGE_SALT, max_age=CHALLENGE_TTL_SECONDS
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    if data.get("purpose") != "mfa":
        return None
    return User.objects.filter(pk=data.get("uid"), is_active=True).first()


def _issue_session(user, request):
    """Complete a login that has now passed both factors."""
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    ip = getattr(request, "client_ip", "") or ""
    ua = getattr(request, "user_agent", "") or ""
    tokens = TokenHelper.create_tokens_with_session(user, ip, ua)
    response = Response({
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "date_joined": user.date_joined.isoformat(),
        },
    })
    set_auth_cookies(response, tokens["access"], tokens["refresh"])
    return response


def _audit(user, action, **meta):
    try:
        from apps.audit.models import AuditLog

        AuditLog.objects.create(
            user=user, action=action, resource="/api/auth/mfa/", metadata=meta
        )
    except Exception:
        logger.warning("MFA audit write failed for user %s", getattr(user, "id", "?"))


class MfaLoginVerifyView(APIView):
    """Second step of login: exchange a challenge + code for a session."""

    permission_classes = [AllowAny]
    throttle_classes = [MfaVerifyThrottle]

    def post(self, request):
        user = read_mfa_challenge(request.data.get("mfa_token"))
        if not user:
            # One message for expired, tampered and unknown alike — distinguishing
            # them tells an attacker which of the three they hit.
            return Response(
                {"error": "This sign-in attempt has expired. Please sign in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        device = getattr(user, "mfa_device", None)
        if not device or not device.enabled:
            return Response(
                {"error": "Multi-factor authentication is not set up for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = (request.data.get("code") or "").strip()
        recovery = (request.data.get("recovery_code") or "").strip()

        if recovery:
            if not device.consume_recovery_code(recovery):
                _audit(user, "login_failed", event="mfa_recovery_invalid")
                return Response({"error": "Invalid code."}, status=status.HTTP_401_UNAUTHORIZED)
            remaining = device.recovery_codes.count()
            _audit(user, "admin_action", event="mfa_recovery_used", remaining=remaining)
            logger.warning(
                "MFA recovery code used for user %s (%d remaining)", user.id, remaining
            )
            resp = _issue_session(user, request)
            resp.data["recovery_codes_remaining"] = remaining
            return resp

        if not device.verify(code):
            _audit(user, "login_failed", event="mfa_code_invalid")
            return Response({"error": "Invalid code."}, status=status.HTTP_401_UNAUTHORIZED)

        return _issue_session(user, request)


class MfaStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device = getattr(request.user, "mfa_device", None)
        return Response({
            "enabled": bool(device and device.enabled),
            "required": bool(request.user.is_staff or request.user.is_superuser),
            "recovery_codes_remaining": device.recovery_codes.count() if device else 0,
        })


class MfaDismissPromptView(APIView):
    """Snooze the "turn on two-factor" suggestion (audit Z2-3).

    Without this the prompt returns on every login, and a prompt that always
    returns is one people learn to click past without reading — which is worse
    than not asking, because it also trains them to dismiss the next real warning.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import Profile

        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.mfa_prompt_dismissed_at = timezone.now()
        profile.save(update_fields=["mfa_prompt_dismissed_at"])
        return Response({"dismissed_until_days": MFA_PROMPT_SNOOZE_DAYS})


class MfaEnrollView(APIView):
    """Start enrolment: mint a secret and return the provisioning URI."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaVerifyThrottle]

    def post(self, request):
        device = getattr(request.user, "mfa_device", None)
        if device and device.enabled:
            return Response(
                {"error": "Multi-factor authentication is already enabled."},
                status=status.HTTP_409_CONFLICT,
            )
        # Re-enrolling replaces the pending secret. Someone who abandoned a scan
        # halfway must not be stuck with a secret they never stored.
        if device:
            device.secret = MfaDevice.new_secret()
            device.last_used_counter = 0
            device.save(update_fields=["secret", "last_used_counter"])
        else:
            device = MfaDevice.objects.create(
                user=request.user, secret=MfaDevice.new_secret()
            )
        return Response({
            "secret": device.secret,
            "provisioning_uri": device.provisioning_uri(),
            "issuer": getattr(settings, "MFA_ISSUER", "FixitLab"),
        })


class MfaConfirmView(APIView):
    """Finish enrolment by proving the authenticator works."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaVerifyThrottle]

    def post(self, request):
        device = getattr(request.user, "mfa_device", None)
        if not device:
            return Response(
                {"error": "Start setup first."}, status=status.HTTP_400_BAD_REQUEST
            )
        if device.enabled:
            return Response(
                {"error": "Multi-factor authentication is already enabled."},
                status=status.HTTP_409_CONFLICT,
            )
        if not device.verify(request.data.get("code")):
            return Response({"error": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)

        device.enabled = True
        device.confirmed_at = timezone.now()
        device.save(update_fields=["enabled", "confirmed_at"])
        codes = device.generate_recovery_codes()
        _audit(request.user, "admin_action", event="mfa_enabled")
        return Response({
            "enabled": True,
            # Shown once. Regenerating is the only way to see them again, and that
            # invalidates the previous set.
            "recovery_codes": codes,
        })


class MfaDisableView(APIView):
    """Turn MFA off. Requires the current password AND a current code."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaVerifyThrottle]

    def post(self, request):
        user = request.user
        device = getattr(user, "mfa_device", None)
        if not device or not device.enabled:
            return Response(
                {"error": "Multi-factor authentication is not enabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.is_staff or user.is_superuser:
            # Staff MFA is mandatory (see mfa_models.mfa_required_for); letting an
            # admin switch it off themselves would make the requirement advisory.
            return Response(
                {"error": "Multi-factor authentication is mandatory for staff accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Both factors, because disabling MFA is exactly what someone with a stolen
        # session would do first.
        if not user.check_password(request.data.get("password") or ""):
            return Response({"error": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)
        if not device.verify(request.data.get("code")):
            return Response({"error": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)

        device.delete()  # cascades the recovery codes
        _audit(user, "admin_action", event="mfa_disabled")
        return Response({"enabled": False})


class MfaRegenerateRecoveryCodesView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaVerifyThrottle]

    def post(self, request):
        device = getattr(request.user, "mfa_device", None)
        if not device or not device.enabled:
            return Response(
                {"error": "Multi-factor authentication is not enabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not device.verify(request.data.get("code")):
            return Response({"error": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
        codes = device.generate_recovery_codes()
        _audit(request.user, "admin_action", event="mfa_recovery_regenerated")
        return Response({"recovery_codes": codes})


__all__ = [
    "MfaLoginVerifyView", "MfaStatusView", "MfaEnrollView", "MfaConfirmView",
    "MfaDisableView", "MfaRegenerateRecoveryCodesView", "MfaDismissPromptView",
    "issue_mfa_challenge", "mfa_required_for",
]
