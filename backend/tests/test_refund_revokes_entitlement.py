"""A full refund must revoke the access it paid for.

RazorpayRefundView previously touched only the PaymentTransaction row, so a
refunded customer kept a full year of paid access — the money went back and the
product did not. FAQ.jsx publicly promises "refunds within 7 days", so this was a
standing leak rather than an edge case.

Partial refunds must NOT revoke: a goodwill credit or price adjustment should not
strip access that was partly paid for.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.billing.models import PaymentTransaction, TechnologySubscription
from apps.billing.views import _revoke_entitlement_for_transaction
from apps.question_bank.models import Technology

User = get_user_model()


class RefundRevokesEntitlementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="refundee", email="refund@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="RefundTech", slug="refundtech")
        self.sub = TechnologySubscription.objects.create(
            user=self.user, technology=self.tech, is_active=True, payment_verified=True
        )

    def _tx(self, **kwargs):
        defaults = dict(
            user=self.user,
            amount=Decimal("499.00"),
            currency="INR",
            payment_method="razorpay",
            status="success",
            idempotency_key=f"test-{kwargs.pop('key', 'a')}",
        )
        defaults.update(kwargs)
        return PaymentTransaction.objects.create(**defaults)

    def test_full_refund_deactivates_linked_tech_subscription(self):
        tx = self._tx(tech_subscription=self.sub, status="refunded")
        result = _revoke_entitlement_for_transaction(tx)

        self.sub.refresh_from_db()
        self.assertFalse(
            self.sub.is_active,
            "refunded customer kept paid access — the leak is still open",
        )
        self.assertIn("tech_subscription", result)

    def test_resolves_technology_from_gateway_metadata(self):
        """Transactions without a FK still resolve via gateway_response."""
        tx = self._tx(
            key="b",
            status="refunded",
            gateway_response={"technology_id": self.tech.id},
        )
        _revoke_entitlement_for_transaction(tx)

        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)

    def test_only_that_users_subscription_is_touched(self):
        """Revocation must not reach across users."""
        other = User.objects.create_user(
            username="bystander", email="bystander@example.com", password="Str0ng-Pass-1"
        )
        other_sub = TechnologySubscription.objects.create(
            user=other, technology=self.tech, is_active=True, payment_verified=True
        )
        tx = self._tx(key="c", status="refunded", gateway_response={"technology_id": self.tech.id})
        _revoke_entitlement_for_transaction(tx)

        other_sub.refresh_from_db()
        self.assertTrue(
            other_sub.is_active,
            "revocation leaked across users — a refund revoked someone else's access",
        )

    def test_unmatched_transaction_is_reported_not_crashed(self):
        """No matching entitlement is a reconcilable event, not an exception."""
        tx = self._tx(key="d", status="refunded", gateway_response={})
        self.assertEqual(_revoke_entitlement_for_transaction(tx), "")

    def test_never_raises_even_on_bad_metadata(self):
        """A gateway refund already succeeded — bookkeeping must not throw."""
        tx = self._tx(key="e", status="refunded", gateway_response={"technology_id": "not-an-int"})
        try:
            _revoke_entitlement_for_transaction(tx)
        except Exception as exc:  # pragma: no cover
            self.fail(f"revocation raised on bad metadata: {exc}")
