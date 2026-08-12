"""Admin refund action (audit L5828 / L5861).

`RazorpayRefundView` existed but had no caller anywhere — no frontend route, no
admin action — so refunds were done by hand in the Razorpay dashboard. A gateway
refund never bumps ``refunded_amount`` and never revokes the entitlement, so the
refunded user kept paid access and the cumulative-refund ceiling went blind.

These tests pin the two properties that make the admin action safe:
  * it actually refunds AND revokes the technology subscription it paid for;
  * it goes through ``perform_refund``, so the ceiling/idempotency logic applies —
    re-running it does not issue a second gateway refund.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings

from apps.billing.admin import PaymentTransactionAdmin
from apps.billing.models import PaymentTransaction, TechnologySubscription
from apps.question_bank.models import Technology

User = get_user_model()

RZP = dict(
    RAZORPAY_KEY_ID="rzp_test",
    RAZORPAY_KEY_SECRET="test_secret",
)


@override_settings(**RZP)
class AdminRefundActionTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="refundadmin", email="refundadmin@test.com",
            password="Pass123!x", is_staff=True, is_superuser=True,
        )
        self.user = User.objects.create_user(
            username="refundpayer", email="refundpayer@test.com", password="Pass123!x",
        )
        self.tech = Technology.objects.create(name="Kubernetes", slug="kubernetes")
        self.sub = TechnologySubscription.objects.create(
            user=self.user,
            technology=self.tech,
            amount=Decimal("499.00"),
            payment_method="razorpay",
            is_active=True,
            payment_verified=True,
        )
        self.tx = PaymentTransaction.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            currency="INR",
            payment_method="razorpay",
            status="success",
            idempotency_key="admin-refund-key",
            gateway_order_id="order_admin_1",
            gateway_payment_id="pay_admin_1",
            tech_subscription=self.sub,
        )
        self.model_admin = PaymentTransactionAdmin(PaymentTransaction, AdminSite())

    def _request(self):
        req = RequestFactory().post("/admin/billing/paymenttransaction/")
        req.user = self.admin_user
        # Admin actions call message_user, which needs a message store.
        req.session = {}
        req._messages = FallbackStorage(req)
        return req

    def _mock_client(self, refund_id="rfnd_admin"):
        mc = MagicMock()
        mc.payment.refund.return_value = {"id": refund_id, "status": "processed"}
        return mc

    def test_action_is_registered(self):
        """The whole defect was "no caller" — the action must be reachable."""
        self.assertIn("action_refund_full", self.model_admin.actions)

    def test_admin_full_refund_revokes_access_and_records_amount(self):
        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            self.model_admin.action_refund_full(
                self._request(), PaymentTransaction.objects.filter(pk=self.tx.pk)
            )

        mc.payment.refund.assert_called_once()
        # Full captured amount in paise, not float-rounded.
        self.assertEqual(mc.payment.refund.call_args[0][1]["amount"], 49900)

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "refunded")
        self.assertEqual(self.tx.refunded_amount, Decimal("499.00"))
        # The gateway-dashboard refund never did this — it is the whole point.
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)

    def test_admin_refund_reuses_ceiling_and_idempotency(self):
        """Re-running the action must not refund a second time."""
        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            qs = PaymentTransaction.objects.filter(pk=self.tx.pk)
            self.model_admin.action_refund_full(self._request(), qs)
            # Second run: the row is now fully refunded, so there is nothing left.
            self.model_admin.action_refund_full(self._request(), qs)

        self.assertEqual(mc.payment.refund.call_count, 1)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.refunded_amount, Decimal("499.00"))

    def test_admin_refund_tops_up_a_partial_refund_without_exceeding(self):
        """After a ₹200 partial, the action refunds exactly the ₹299 remaining."""
        self.tx.refunded_amount = Decimal("200.00")
        self.tx.save(update_fields=["refunded_amount"])

        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            self.model_admin.action_refund_full(
                self._request(), PaymentTransaction.objects.filter(pk=self.tx.pk)
            )

        self.assertEqual(mc.payment.refund.call_args[0][1]["amount"], 29900)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.refunded_amount, Decimal("499.00"))
        self.assertEqual(self.tx.status, "refunded")

    def test_admin_refund_skips_uncaptured_payment(self):
        self.tx.status = "failed"
        self.tx.save(update_fields=["status"])

        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            self.model_admin.action_refund_full(
                self._request(), PaymentTransaction.objects.filter(pk=self.tx.pk)
            )

        mc.payment.refund.assert_not_called()
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.is_active)
