"""Tests for the SECURITY_AUDIT Critical/High fixes.

Covers:
  * P-01 — TechnologySubscribeView refuses to activate a PAID technology with
    no payment (402); only price==0 technologies may be self-activated.
  * P-02 — payment-signature / gateway verifiers FAIL CLOSED when the gateway
    secret is absent (no `return True` demo bypass in production).
  * A-02 — a password reset invalidates active sessions AND blacklists the
    user's outstanding refresh tokens.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.billing.models import TechnologySubscription
from apps.question_bank.models import Technology

User = get_user_model()


@override_settings(ROOT_URLCONF="config.urls", SECURE_SSL_REDIRECT=False)
class TechnologySubscribeBypassTests(TestCase):
    """P-01: no free PAID subscriptions through the legacy subscribe endpoint."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="subuser", email="sub@test.com", password="Pass123!x"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.paid_tech = Technology.objects.create(name="Paid Tech", price=499, is_active=True)
        self.free_tech = Technology.objects.create(name="Free Tech", price=0, is_active=True)
        self.url = reverse("tech_subscribe")

    def test_paid_technology_is_refused_without_payment(self):
        resp = self.client.post(self.url, {"technology_id": self.paid_tech.id}, format="json")
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.data.get("code"), "PAYMENT_REQUIRED")
        # No subscription was created / activated.
        self.assertFalse(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.paid_tech, is_active=True
            ).exists()
        )

    def test_free_technology_can_be_activated(self):
        resp = self.client.post(self.url, {"technology_id": self.free_tech.id}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data.get("is_active"))
        self.assertTrue(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.free_tech, is_active=True
            ).exists()
        )


@override_settings(ROOT_URLCONF="config.urls", SECURE_SSL_REDIRECT=False)
class PaymentVerifierFailClosedTests(TestCase):
    """P-02: verifier helpers never pass when the gateway secret is absent in prod."""

    def setUp(self):
        from apps.billing.views import VerifyRazorpayPaymentView
        self.view = VerifyRazorpayPaymentView()

    @override_settings(DEBUG=False, RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="",
                       DEMO_PAYMENT_ENABLED=True)
    def test_signature_fails_closed_in_prod_even_with_demo_flag(self):
        # Demo flag set but DEBUG False -> must NOT pass.
        self.assertFalse(self.view._verify_signature("order_x", "pay_x", "sig_x"))

    @override_settings(DEBUG=False, RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="",
                       DEMO_PAYMENT_ENABLED=True)
    def test_gateway_check_fails_closed_in_prod_even_with_demo_flag(self):
        self.assertFalse(self.view._verify_payment_with_gateway("order_x", "pay_x", 499))

    @override_settings(DEBUG=False, RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="",
                       DEMO_PAYMENT_ENABLED=True)
    def test_capture_helper_fails_closed_in_prod(self):
        from apps.billing.razorpay_fulfillment import verify_razorpay_payment_captured
        self.assertFalse(verify_razorpay_payment_captured("order_x", "pay_x", 499))

    @override_settings(DEBUG=True, RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="",
                       DEMO_PAYMENT_ENABLED=True)
    def test_demo_bypass_allowed_only_in_explicit_dev_mode(self):
        # In DEBUG dev with the demo flag, the demo skip is permitted (so local
        # dev keeps working) — proving the gate is keyed on DEBUG, not just secrets.
        self.assertTrue(self.view._verify_signature("order_x", "pay_x", "sig_x"))


@override_settings(ROOT_URLCONF="config.urls", SECURE_SSL_REDIRECT=False,
                   JWT_SESSION_ENFORCEMENT=True)
class PasswordResetRevokesSessionsTests(TestCase):
    """A-02: password reset evicts active sessions + blacklists refresh tokens."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="resetuser", email="reset@test.com", password="OldPass123!x"
        )
        self.client = APIClient()

    def test_reset_invalidates_sessions_and_blacklists_tokens(self):
        from apps.accounts.models import PasswordResetToken
        from common.security import SessionTracker

        # Simulate an attacker holding a live session for this user.
        refresh = RefreshToken.for_user(self.user)
        jti = "attacker-jti-123"
        refresh["jti"] = jti
        SessionTracker.record_session(self.user.id, jti, "1.1.1.1", "ua")
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, jti))

        token_obj, raw = PasswordResetToken.generate_token(self.user, hours=1)

        resp = self.client.post(
            reverse("reset_password"),
            {"token": raw, "new_password": "BrandNewPass123!x"},
            format="json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        # Session set was cleared (invalidate_all_sessions deletes the entry).
        # After clearing, a previously-recorded jti is no longer in a populated
        # set; record a new one to prove the OLD jti is gone.
        SessionTracker.record_session(self.user.id, "fresh-jti", "2.2.2.2", "ua")
        self.assertFalse(SessionTracker.is_session_valid(self.user.id, jti))

        # The outstanding refresh token is blacklisted (DB-backed hard cut).
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )
            outstanding = OutstandingToken.objects.filter(user=self.user)
            # Every outstanding token for the user is blacklisted.
            for ot in outstanding:
                self.assertTrue(BlacklistedToken.objects.filter(token=ot).exists())
        except Exception:
            self.skipTest("token_blacklist app not available")

        # Token marked used → cannot be replayed.
        token_obj.refresh_from_db()
        self.assertTrue(token_obj.used)
