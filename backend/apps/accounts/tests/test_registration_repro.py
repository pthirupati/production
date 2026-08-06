"""Regression tests for the email+OTP registration flow.

Root cause covered (views.RegisterView): a verified OTP whose short
``expires_at`` (2 min, the code-ENTRY window) had lapsed was rejected with
"Verification has expired", even though the user entered the code correctly —
so users who took >2 min to fill the form could never register, while OAuth
(no OTP gate) worked. The fix grants a 30-min post-generation grace window to
finish registration.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import EmailVerificationOTP, SocialAccount
from apps.accounts.views import GitHubCallbackView
from common.security import TokenHelper

User = get_user_model()


@override_settings(JWT_SESSION_ENFORCEMENT=False)
class EmailOTPRegistrationTest(APITestCase):
    def _verified_otp(self, email, *, age_minutes=0, window_minutes=2):
        """Create an OTP, mark it verified, optionally back-date it."""
        otp, code, session_token = EmailVerificationOTP.generate(
            email, minutes=window_minutes
        )
        otp.verified = True
        if age_minutes:
            otp.created_at = timezone.now() - timedelta(minutes=age_minutes)
            # The short entry window has long since elapsed.
            otp.expires_at = otp.created_at + timedelta(minutes=window_minutes)
            otp.save(update_fields=["verified", "created_at", "expires_at"])
        else:
            otp.save(update_fields=["verified"])
        return session_token

    def test_register_returns_201_with_tokens(self):
        session_token = self._verified_otp("fresh@example.com")
        resp = self.client.post(
            "/api/auth/register/",
            {
                "session_token": session_token,
                "password": "Sup3rStr0ng!pw",
                "first_name": "Fresh",
                "last_name": "User",
            },
            format="json",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))
        assert resp.data.get("access") and resp.data.get("refresh")
        assert User.objects.filter(email="fresh@example.com").exists()

    def test_register_succeeds_when_entry_window_lapsed_after_verify(self):
        """The 2-min code-entry window lapsing must NOT block a verified user."""
        session_token = self._verified_otp("slow@example.com", age_minutes=5)
        resp = self.client.post(
            "/api/auth/register/",
            {"session_token": session_token, "password": "Sup3rStr0ng!pw"},
            format="json",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))
        assert resp.data.get("access")

    def test_register_rejected_after_grace_window(self):
        """Past the 30-min grace, registration is correctly refused."""
        session_token = self._verified_otp("stale@example.com", age_minutes=45)
        resp = self.client.post(
            "/api/auth/register/",
            {"session_token": session_token, "password": "Sup3rStr0ng!pw"},
            format="json",
        )
        assert resp.status_code == 400, (resp.status_code, dict(resp.data))

    @override_settings(JWT_SESSION_ENFORCEMENT=True)
    def test_register_with_session_enforcement_on(self):
        session_token = self._verified_otp("enf@example.com")
        resp = self.client.post(
            "/api/auth/register/",
            {"session_token": session_token, "password": "Sup3rStr0ng!pw"},
            format="json",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))

    def test_full_otp_http_flow(self):
        """send-otp -> verify-otp -> register, like the real frontend."""
        email = "flow@example.com"
        self._sent_codes = []
        _real_generate = EmailVerificationOTP.generate.__func__

        def _spy(cls, *args, **kwargs):
            instance, code, token = _real_generate(cls, *args, **kwargs)
            self._sent_codes.append(code)
            return instance, code, token

        with mock.patch(
            "apps.notifications.gmail_api.is_gmail_api_configured", return_value=True
        ), mock.patch(
            "apps.accounts.views.dispatch_notification_email", return_value=None
        ), mock.patch.object(
            EmailVerificationOTP, "generate", classmethod(_spy)
        ):
            send = self.client.post(
                "/api/auth/send-otp/", {"email": email}, format="json"
            )
        assert send.status_code == 200, (send.status_code, send.data)
        session_token = send.data["session_token"]
        # The code is no longer readable from the database — it is hashed (Z4-11) —
        # so capture the plaintext where the real flow gets it: the value generate()
        # hands back to be emailed. Reading it out of the DB would have quietly
        # re-required plaintext storage.
        code = self._sent_codes[-1]

        verify = self.client.post(
            "/api/auth/verify-otp/",
            {"session_token": session_token, "code": code},
            format="json",
        )
        assert verify.status_code == 200, (verify.status_code, verify.data)

        reg = self.client.post(
            "/api/auth/register/",
            {"session_token": session_token, "password": "Sup3rStr0ng!pw"},
            format="json",
        )
        assert reg.status_code == 201, (reg.status_code, dict(reg.data))
        assert reg.data.get("access") and reg.data.get("refresh")


@override_settings(JWT_SESSION_ENFORCEMENT=False)
class OAuthSignupStillWorksTest(APITestCase):
    """Guard the social-signup path (verified email -> create account + tokens)."""

    def test_social_register_creates_user_and_tokens(self):
        user, error = GitHubCallbackView._resolve_social_login(
            "github", "gh-12345", "oauth-new@example.com", "OAuth User",
            allow_registration=True, email_verified=True,
        )
        assert error is None
        assert user is not None
        assert SocialAccount.objects.filter(
            provider="github", provider_uid="gh-12345", user=user
        ).exists()

        toks = TokenHelper.create_tokens_with_session(user, "", "")
        assert toks["access"] and toks["refresh"]

    def test_social_login_existing_link_returns_user(self):
        user, error = GitHubCallbackView._resolve_social_login(
            "github", "gh-99", "oauth-existing@example.com", "X",
            allow_registration=True, email_verified=True,
        )
        assert error is None
        # Second call with the same provider_uid logs the same user in.
        again, err2 = GitHubCallbackView._resolve_social_login(
            "github", "gh-99", "oauth-existing@example.com", "X",
            allow_registration=False, email_verified=True,
        )
        assert err2 is None
        assert again.id == user.id
