"""Audit Z2-3 — TOTP multi-factor authentication.

There was no MFA of any kind on a platform that takes payments, stores resumes and
interview transcripts, and sells org seats at Rs 4,999. Every `saml`/`sso` hit in
the repo was simulated lab content.

This covers the TOTP half; SSO/SAML/SCIM needs an IdP decision first.

The tests that matter most are not "a valid code works" — that is the easy half.
They are:

* **Replay.** A TOTP code is valid for a 30-second window, so without recording the
  consumed counter the same code works repeatedly inside it. This is the single
  most commonly omitted control in TOTP implementations, and a shoulder-surfed
  code becomes a free login without it.
* **The challenge token is not a session.** The intermediate token issued between
  password and code is a `TimestampSigner` payload, not a JWT — if it were a JWT,
  every `IsAuthenticated` view would accept it as a Bearer token and "MFA
  required" would mean "MFA optional, and here is a working session".
* **Staff are not locked out on deploy.** Staff MFA is mandatory, but the staff
  accounts that exist today have no device. Refusing them would take every
  administrator offline the moment this ships.
* **Recovery codes are single-use**, or they are just a second password.

The implementation is also checked against the RFC 6238 published test vectors,
because "our TOTP works with our own generator" proves only self-consistency, not
that a real authenticator app will interoperate.
"""
import base64
import time
from unittest import mock

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.mfa_models import (
    TOTP_DIGITS,
    TOTP_INTERVAL,
    MfaDevice,
    mfa_required_for,
)
from common.testing import real_throttling

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class RfcConformanceTests(TestCase):
    """Interoperability, not self-consistency."""

    def test_matches_the_rfc_6238_vectors(self):
        secret = base64.b32encode(b"12345678901234567890").decode()
        totp = pyotp.TOTP(secret, digits=8)
        for at, expected in ((59, "94287082"), (1111111109, "07081804"),
                             (1234567890, "89005924")):
            self.assertEqual(totp.at(at), expected, f"RFC vector at t={at}")

    def test_the_parameters_are_what_authenticator_apps_assume(self):
        """Google Authenticator, Authy and 1Password all assume 6 digits / 30s.
        Changing either silently breaks every already-enrolled device."""
        self.assertEqual(TOTP_DIGITS, 6)
        self.assertEqual(TOTP_INTERVAL, 30)


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mfa", email="mfa@example.com", password=PASSWORD
        )
        self.client = APIClient()

    def _device(self, enabled=True):
        device = MfaDevice.objects.create(
            user=self.user, secret=MfaDevice.new_secret(), enabled=enabled
        )
        self.user.refresh_from_db()
        return device

    def _code(self, device, at=None):
        totp = pyotp.TOTP(device.secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        return totp.at(at) if at is not None else totp.now()

    def _login(self, password=PASSWORD):
        return self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": password},
            format="json",
        )


class TheSecondFactorIsActuallyRequiredTests(_Base):
    def test_login_with_mfa_returns_a_challenge_not_a_session(self):
        self._device()
        resp = self._login()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["mfa_required"])
        self.assertIn("mfa_token", resp.data)
        self.assertNotIn(
            "access", resp.data,
            "the password step handed out an access token — MFA is decorative",
        )

    def test_no_auth_cookie_is_set_at_the_password_step(self):
        """Cookies are how this app authenticates; setting one here would sign the
        user in regardless of what the JSON body says."""
        self._device()
        resp = self._login()
        self.assertNotIn("access_token", resp.cookies)

    def test_the_challenge_token_is_not_a_usable_bearer_token(self):
        """If it were a JWT, every IsAuthenticated view would accept it."""
        self._device()
        token = self._login().data["mfa_token"]
        probe = APIClient()
        probe.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = probe.get("/api/auth/profile/")
        self.assertIn(
            resp.status_code, (401, 403),
            "the MFA challenge token authenticated a normal API request",
        )

    def test_a_correct_code_completes_the_login(self):
        device = self._device()
        token = self._login().data["mfa_token"]
        resp = self.client.post(
            "/api/auth/mfa/verify/",
            {"mfa_token": token, "code": self._code(device)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertIn("access", resp.data)

    def test_a_wrong_code_does_not(self):
        self._device()
        token = self._login().data["mfa_token"]
        resp = self.client.post(
            "/api/auth/mfa/verify/", {"mfa_token": token, "code": "000000"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_a_user_without_mfa_logs_in_normally(self):
        """Guard the guard: if the branch fired for everyone, every other login
        test in the suite would break and this feature would be a lockout."""
        resp = self._login()
        self.assertIn("access", resp.data)

    def test_a_pending_unconfirmed_device_does_not_gate_login(self):
        """Someone who started setup and never scanned the QR must not be locked
        out of their own account."""
        self._device(enabled=False)
        self.assertIn("access", self._login().data)


class ReplayProtectionTests(_Base):
    """The control most TOTP implementations omit."""

    def test_the_same_code_cannot_be_used_twice(self):
        device = self._device()
        code = self._code(device)
        self.assertTrue(device.verify(code))
        self.assertFalse(
            device.verify(code),
            "a TOTP code was accepted twice — an intercepted code is a free replay "
            "for the rest of its 30-second window",
        )

    def test_replay_is_rejected_over_the_api_too(self):
        device = self._device()
        code = self._code(device)
        # Two challenges are minted up front, and the second attempt uses a FRESH
        # client. Reusing the first one fails for an unrelated reason: once the
        # auth cookies are set, the next cookie-authenticated request requires a
        # CSRF header, so the second login 401s before MFA is reached — which would
        # have made this test pass for the wrong reason.
        token_one = self._login().data["mfa_token"]
        token_two = self._login().data["mfa_token"]

        first = self.client.post(
            "/api/auth/mfa/verify/", {"mfa_token": token_one, "code": code},
            format="json",
        )
        self.assertEqual(first.status_code, 200, getattr(first, "data", first))

        second = APIClient().post(
            "/api/auth/mfa/verify/", {"mfa_token": token_two, "code": code},
            format="json",
        )
        self.assertEqual(
            second.status_code, 401,
            "the same TOTP code completed a second login — replay protection is "
            "not reaching the API path",
        )

    def test_the_next_windows_code_still_works(self):
        """Replay protection must not become "one login per account, ever"."""
        device = self._device()
        now = int(time.time())
        self.assertTrue(device.verify(self._code(device, at=now)))
        future = now + TOTP_INTERVAL * 2
        with mock.patch("apps.accounts.mfa_models.timezone") as tz:
            tz.now.return_value = mock.Mock(timestamp=lambda: future)
            with mock.patch("pyotp.TOTP.verify", return_value=True):
                self.assertTrue(device.verify(self._code(device, at=future)))

    def test_an_older_code_is_rejected_after_a_newer_one(self):
        device = self._device()
        now = int(time.time())
        self.assertTrue(device.verify(self._code(device, at=now)))
        self.assertFalse(device.verify(self._code(device, at=now - TOTP_INTERVAL)))


class ClockDriftTests(_Base):
    def test_a_code_from_the_previous_step_is_accepted(self):
        """Phones drift; +/-1 step is the standard tolerance. Zero tolerance
        produces intermittent 'invalid code' that users cannot explain."""
        device = self._device()
        self.assertTrue(device.verify(self._code(device, at=int(time.time()) - TOTP_INTERVAL)))

    def test_a_code_far_outside_the_window_is_rejected(self):
        device = self._device()
        self.assertFalse(device.verify(self._code(device, at=int(time.time()) - 3600)))

    def test_malformed_input_is_rejected_without_raising(self):
        device = self._device()
        for junk in ("", None, "abcdef", "12345", "1234567", "12 34 56x"):
            self.assertFalse(device.verify(junk), junk)


class RecoveryCodeTests(_Base):
    def test_codes_are_issued_on_confirmation(self):
        device = self._device(enabled=False)
        codes = device.generate_recovery_codes()
        self.assertEqual(len(codes), 10)
        self.assertEqual(len(set(codes)), 10)

    def test_they_are_not_stored_in_plaintext(self):
        device = self._device()
        codes = device.generate_recovery_codes()
        stored = set(device.recovery_codes.values_list("code_hash", flat=True))
        self.assertFalse(
            stored & set(codes), "recovery codes are stored in plaintext"
        )

    def test_a_code_works_once(self):
        device = self._device()
        code = device.generate_recovery_codes()[0]
        self.assertTrue(device.consume_recovery_code(code))
        self.assertFalse(
            device.consume_recovery_code(code),
            "a recovery code was reusable — that is just a second password",
        )

    def test_an_unknown_code_is_rejected(self):
        device = self._device()
        device.generate_recovery_codes()
        self.assertFalse(device.consume_recovery_code("deadbeef99"))

    def test_regenerating_invalidates_the_old_set(self):
        """Someone regenerating because they think the old codes leaked must
        actually invalidate them."""
        device = self._device()
        old = device.generate_recovery_codes()
        device.generate_recovery_codes()
        self.assertFalse(device.consume_recovery_code(old[0]))

    def test_a_recovery_code_completes_a_login(self):
        device = self._device()
        code = device.generate_recovery_codes()[0]
        resp = self.client.post(
            "/api/auth/mfa/verify/",
            {"mfa_token": self._login().data["mfa_token"], "recovery_code": code},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertEqual(resp.data["recovery_codes_remaining"], 9)


class StaffAreNotLockedOutTests(TestCase):
    """Staff MFA is mandatory, but the staff accounts that exist today have no
    device. Refusing them would take every administrator offline on deploy."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin2", email="admin2@example.com", password=PASSWORD,
            is_staff=True,
        )
        self.client = APIClient()

    def _login(self):
        return self.client.post(
            "/api/auth/login/",
            {"email": self.staff.email, "password": PASSWORD}, format="json",
        )

    def test_staff_without_a_device_can_still_sign_in(self):
        resp = self._login()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertIn("access", resp.data)

    def test_but_they_are_told_to_enrol(self):
        self.assertTrue(self._login().data["mfa_enrollment_required"])

    def test_mfa_is_reported_as_required_for_staff(self):
        self.assertTrue(mfa_required_for(self.staff))

    def test_it_is_not_required_for_an_ordinary_user(self):
        ordinary = User.objects.create_user(
            username="plain", email="plain@example.com", password=PASSWORD
        )
        self.assertFalse(mfa_required_for(ordinary))

    def test_staff_cannot_disable_their_own_mfa(self):
        """Otherwise the requirement is advisory."""
        device = MfaDevice.objects.create(
            user=self.staff, secret=MfaDevice.new_secret(), enabled=True
        )
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            "/api/auth/mfa/disable/",
            {"password": PASSWORD,
             "code": pyotp.TOTP(device.secret, interval=TOTP_INTERVAL).now()},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(MfaDevice.objects.filter(pk=device.pk).exists())


class EnrolmentTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)

    def test_enrol_returns_a_provisioning_uri(self):
        resp = self.client.post("/api/auth/mfa/enroll/", {}, format="json")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertTrue(resp.data["provisioning_uri"].startswith("otpauth://totp/"))
        self.assertIn("FixitLab", resp.data["provisioning_uri"])

    def test_confirm_requires_a_working_code(self):
        self.client.post("/api/auth/mfa/enroll/", {}, format="json")
        resp = self.client.post(
            "/api/auth/mfa/confirm/", {"code": "000000"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(MfaDevice.objects.get(user=self.user).enabled)

    def test_confirm_enables_and_returns_recovery_codes(self):
        secret = self.client.post("/api/auth/mfa/enroll/", {}, format="json").data["secret"]
        code = pyotp.TOTP(secret, interval=TOTP_INTERVAL).now()
        resp = self.client.post("/api/auth/mfa/confirm/", {"code": code}, format="json")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertTrue(resp.data["enabled"])
        self.assertEqual(len(resp.data["recovery_codes"]), 10)

    def test_re_enrolling_replaces_an_abandoned_secret(self):
        first = self.client.post("/api/auth/mfa/enroll/", {}, format="json").data["secret"]
        second = self.client.post("/api/auth/mfa/enroll/", {}, format="json").data["secret"]
        self.assertNotEqual(first, second)

    def test_enrolling_twice_once_enabled_is_refused(self):
        self._device()
        self.assertEqual(
            self.client.post("/api/auth/mfa/enroll/", {}, format="json").status_code, 409
        )

    def test_disable_needs_both_password_and_code(self):
        device = self._device()
        code = pyotp.TOTP(device.secret, interval=TOTP_INTERVAL).now()
        self.assertEqual(
            self.client.post(
                "/api/auth/mfa/disable/", {"password": "wrong", "code": code},
                format="json",
            ).status_code, 400,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/mfa/disable/", {"password": PASSWORD, "code": "000000"},
                format="json",
            ).status_code, 400,
        )
        self.assertTrue(MfaDevice.objects.filter(pk=device.pk).exists())


class BruteForceTests(_Base):
    def test_code_submission_is_throttled(self):
        """Six digits is a million-guess space against a 30-second window. With no
        limit the second factor is decoration."""
        self._device()
        token = self._login().data["mfa_token"]
        with real_throttling(mfa_verify="3/hour"):
            codes = [
                self.client.post(
                    "/api/auth/mfa/verify/", {"mfa_token": token, "code": "000000"},
                    format="json",
                ).status_code
                for _ in range(6)
            ]
        self.assertIn(429, codes, f"MFA verification was not throttled ({codes})")

    def test_the_scope_is_registered_in_both_settings_modules(self):
        import pathlib

        from django.conf import settings as dj_settings

        root = pathlib.Path(dj_settings.BASE_DIR) / "config"
        for name in ("settings.py", "test_settings.py"):
            self.assertIn(
                '"mfa_verify":', (root / name).read_text(),
                f"the mfa_verify throttle scope is missing from {name}",
            )


class SocialLoginIsNotABypassTests(_Base):
    """MFA was enforced on the password path only.

    That is a real bypass, not a technicality: an account with TOTP enabled could
    be signed into by anyone who compromised the linked GitHub or Google account,
    defeating the control the user explicitly turned on.

    The "the IdP already did MFA" argument holds for *enterprise* SSO, where the
    IdP policy is yours to set. It does not hold for consumer OAuth — there is no
    way to know whether GitHub asked for a second factor, and a user who enabled
    MFA here asked for MFA *here*.
    """

    def _callback_grants_session_without_mfa(self, view_name):
        import inspect

        from apps.accounts import views

        src = inspect.getsource(getattr(views, view_name))
        issues = "create_tokens_with_session" in src
        checks = "mfa_device" in src and "issue_mfa_challenge" in src
        return issues and not checks

    def test_the_github_callback_enforces_mfa(self):
        self.assertFalse(
            self._callback_grants_session_without_mfa("GitHubCallbackView"),
            "GitHubCallbackView issues a session without checking MFA — a user "
            "with TOTP enabled can be signed in via a compromised GitHub account",
        )

    def test_the_google_callback_enforces_mfa(self):
        self.assertFalse(
            self._callback_grants_session_without_mfa("GoogleCallbackView"),
            "GoogleCallbackView issues a session without checking MFA",
        )

    def test_registration_is_deliberately_exempt(self):
        """Guard the guard: a brand-new account cannot have MFA, so requiring it at
        signup would make registration impossible."""
        import inspect

        from apps.accounts import views

        src = inspect.getsource(views.RegisterView)
        self.assertIn("create_tokens_with_session", src)
        self.assertNotIn("issue_mfa_challenge", src)

    def test_every_session_issuing_view_is_accounted_for(self):
        """The bypass existed because MFA was added to one path and the others were
        never enumerated. This fails if a NEW view starts issuing sessions, so the
        next one cannot be forgotten silently."""
        import inspect
        import re

        from apps.accounts import views

        issuing = {
            name for name, obj in vars(views).items()
            if inspect.isclass(obj) and name.endswith("View")
            and "create_tokens_with_session" in inspect.getsource(obj)
        }
        known = {
            "RegisterView",        # no account history yet -- exempt by nature
            "LoginView",           # enforces MFA
            "GitHubCallbackView",  # enforces MFA
            "GoogleCallbackView",  # enforces MFA
        }
        self.assertEqual(
            issuing, known,
            "a view issues sessions but is not in the reviewed list -- decide "
            "whether it must enforce MFA, then add it here",
        )


class ChallengeTokenTests(_Base):
    def test_a_tampered_token_is_rejected(self):
        self._device()
        token = self._login().data["mfa_token"]
        resp = self.client.post(
            "/api/auth/mfa/verify/", {"mfa_token": token + "x", "code": "000000"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_an_expired_token_is_rejected(self):
        from apps.accounts import mfa_views

        device = self._device()
        token = self._login().data["mfa_token"]
        with mock.patch.object(mfa_views, "CHALLENGE_TTL_SECONDS", -1):
            resp = self.client.post(
                "/api/auth/mfa/verify/",
                {"mfa_token": token, "code": self._code(device)}, format="json",
            )
        self.assertEqual(resp.status_code, 401)

    def test_a_token_for_a_deactivated_user_is_rejected(self):
        device = self._device()
        token = self._login().data["mfa_token"]
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        resp = self.client.post(
            "/api/auth/mfa/verify/", {"mfa_token": token, "code": self._code(device)},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)
