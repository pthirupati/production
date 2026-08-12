"""Every fulfilled sale must leave a financial record.

Audit Z1-6: the Stripe-technology and org-seat paths called
`_create_technology_subscription` / granted seats directly and **never wrote a
PaymentTransaction**. Those sales had no invoice, no GST breakup and no
`gateway_payment_id` — invisible to payment history and revenue totals, and
impossible to refund through the product, because `RazorpayRefundView` refunds a
PaymentTransaction and a sale with no row cannot be refunded at all.

Access granted with no financial record is the worse half of a payment to get wrong:
the customer has what they bought, and the business has no way to reverse it, invoice
it, or count it.

The gateway identifier is the part that makes the record useful rather than
decorative — a transaction with no `gateway_payment_id` still cannot be refunded — so
it is asserted separately from the row's existence.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.billing.extended_views import (
    _create_technology_subscription,
    record_payment_transaction,
)
from apps.billing.models import PaymentTransaction, TechnologySubscription
from apps.question_bank.models import Technology

User = get_user_model()


class TechnologySaleIsRecordedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(
            name="PayTech", slug="paytech", price=499
        )

    def test_subscription_grant_writes_a_transaction(self):
        _create_technology_subscription(
            self.user, self.tech, 499, payment_method="stripe",
            gateway_payment_id="pi_123", gateway_order_id="cs_123",
        )
        self.assertEqual(PaymentTransaction.objects.filter(user=self.user).count(), 1)

    def test_the_transaction_carries_a_gateway_id_so_it_can_be_refunded(self):
        _create_technology_subscription(
            self.user, self.tech, 499, payment_method="stripe",
            gateway_payment_id="pi_123", gateway_order_id="cs_123",
        )
        txn = PaymentTransaction.objects.get(user=self.user)
        self.assertEqual(txn.gateway_payment_id, "pi_123")
        self.assertEqual(txn.gateway_order_id, "cs_123")

    def test_the_gst_split_is_internally_consistent(self):
        """taxable + tax == total, which must hold whether or not GST is charged.

        My first version asserted `gst_amount > 0` — wrong: `compute_gst` correctly
        returns a zero-tax breakup when `gst_should_charge()` is False (no GSTIN
        configured, which is the case under test settings). The invariant that always
        holds is the sum, so that is what gets pinned here; the rate itself is
        exercised where GST is switched on.
        """
        _create_technology_subscription(
            self.user, self.tech, 499, payment_method="stripe",
            gateway_payment_id="pi_1",
        )
        txn = PaymentTransaction.objects.get(user=self.user)
        self.assertEqual(txn.taxable_amount + txn.gst_amount, txn.amount)
        self.assertGreater(txn.amount, 0)

    def test_gst_is_broken_out_when_gst_is_enabled(self):
        from decimal import Decimal
        from unittest import mock

        with mock.patch("apps.billing.gst.gst_should_charge", return_value=True), \
             mock.patch("apps.billing.gst.gst_rate", return_value=Decimal("0.18")):
            _create_technology_subscription(
                self.user, self.tech, 499, payment_method="stripe",
                gateway_payment_id="pi_gst",
            )
        txn = PaymentTransaction.objects.get(user=self.user)
        self.assertGreater(txn.gst_amount, 0, "GST enabled but the split is empty")
        self.assertEqual(txn.taxable_amount + txn.gst_amount, txn.amount)

    def test_the_subscription_is_still_granted(self):
        _create_technology_subscription(
            self.user, self.tech, 499, payment_method="stripe",
            gateway_payment_id="pi_1",
        )
        self.assertTrue(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.tech, is_active=True
            ).exists()
        )

    def test_a_bookkeeping_failure_does_not_revoke_paid_access(self):
        """Best-effort by design: the customer has paid, so a failed transaction
        write must not cost them the thing they bought. It is logged loudly instead."""
        with mock.patch(
            "apps.billing.extended_views.record_payment_transaction",
            side_effect=RuntimeError("db down"),
        ):
            _create_technology_subscription(
                self.user, self.tech, 499, payment_method="stripe",
            )
        self.assertTrue(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.tech, is_active=True
            ).exists()
        )


class ReplayDoesNotInflateRevenueTests(TestCase):
    """A retried webhook or a double-clicked verify must not book the sale twice."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="replay", email="replay@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="RepTech", slug="reptech", price=499)

    def test_same_gateway_payment_id_yields_one_transaction(self):
        for _ in range(3):
            _create_technology_subscription(
                self.user, self.tech, 499, payment_method="stripe",
                gateway_payment_id="pi_same",
            )
        self.assertEqual(
            PaymentTransaction.objects.filter(user=self.user).count(), 1,
            "a replayed webhook booked the sale more than once",
        )

    def test_distinct_payments_are_recorded_separately(self):
        record_payment_transaction(
            self.user, 499, payment_method="razorpay",
            product_type="technology", gateway_payment_id="pay_A",
        )
        record_payment_transaction(
            self.user, 499, payment_method="razorpay",
            product_type="technology", gateway_payment_id="pay_B",
        )
        self.assertEqual(PaymentTransaction.objects.filter(user=self.user).count(), 2)

    def test_product_type_is_recorded_for_reconciliation(self):
        record_payment_transaction(
            self.user, 1999, payment_method="razorpay",
            product_type="organization", gateway_payment_id="pay_org",
            extra={"seats": 10},
        )
        txn = PaymentTransaction.objects.get(gateway_payment_id="pay_org")
        self.assertEqual(txn.gateway_response["product_type"], "organization")
        self.assertEqual(txn.gateway_response["seats"], 10)


class RefundCanActuallyRevokeTheseSalesTests(TestCase):
    """Recording a transaction only helps if the refund path can act on it.

    Z1-6 made Stripe-technology and org-seat sales refundable for the first time.
    That creates a seam: `_revoke_entitlement_for_transaction` has to understand the
    rows this code writes, or a refund returns the money and leaves access intact —
    strictly worse than being unrefundable, because the admin reasonably assumes
    revocation happened, as it does for every other product type.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="rev", email="rev@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="RevTech", slug="revtech", price=499)

    def test_technology_id_survives_the_round_trip(self):
        """It is written as a string; the resolver checks isinstance(int) first."""
        from apps.billing.razorpay_fulfillment import technology_id_from_transaction

        _create_technology_subscription(
            self.user, self.tech, 499, payment_method="stripe",
            gateway_payment_id="pi_rev",
        )
        txn = PaymentTransaction.objects.get(user=self.user)
        self.assertEqual(technology_id_from_transaction(txn), self.tech.id)

    def test_refunding_a_stripe_technology_sale_revokes_access(self):
        from apps.billing.views import _revoke_entitlement_for_transaction

        _create_technology_subscription(
            self.user, self.tech, 499, payment_method="stripe",
            gateway_payment_id="pi_rev2",
        )
        txn = PaymentTransaction.objects.get(user=self.user)
        self.assertTrue(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.tech, is_active=True
            ).exists()
        )
        _revoke_entitlement_for_transaction(txn)
        self.assertFalse(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.tech, is_active=True
            ).exists(),
            "a refunded technology sale left the subscription active",
        )


class OrgRefundRevokesGrantsTests(TestCase):
    """The gap this change closed: `organization` was not a case the revoke path knew."""

    def setUp(self):
        from apps.accounts.models import Organization, OrganizationTechnologyGrant
        from django.utils import timezone as tz
        from datetime import timedelta

        self.owner = User.objects.create_user(
            username="orgowner", email="orgowner@example.com", password="Str0ng-Pass-1"
        )
        self.org = Organization.objects.create(
            name="RefOrg", slug="reforg", owner=self.owner, seat_limit=5
        )
        self.tech = Technology.objects.create(name="OrgTech", slug="orgtech", price=999)
        OrganizationTechnologyGrant.objects.create(
            organization=self.org, technology=self.tech,
            expires_at=tz.now() + timedelta(days=365), is_active=True,
        )
        self.org.seat_limit = 25
        self.org.save(update_fields=["seat_limit"])
        self.txn = record_payment_transaction(
            self.owner, 9990, payment_method="razorpay",
            product_type="organization", gateway_payment_id="pay_org_rev",
            extra={
                "org_id": str(self.org.id),
                "org": self.org.slug,
                "seats": 25,
                "previous_seat_limit": 5,
                "granted_technology_ids": [str(self.tech.id)],
            },
        )

    def test_refund_deactivates_the_technology_grants(self):
        from apps.accounts.models import OrganizationTechnologyGrant
        from apps.billing.views import _revoke_entitlement_for_transaction

        _revoke_entitlement_for_transaction(self.txn)
        self.assertFalse(
            OrganizationTechnologyGrant.objects.filter(
                organization=self.org, is_active=True
            ).exists(),
            "a refunded org purchase kept its technology grants",
        )

    def test_refund_restores_the_previous_seat_limit(self):
        from apps.accounts.models import Organization
        from apps.billing.views import _revoke_entitlement_for_transaction

        _revoke_entitlement_for_transaction(self.txn)
        self.assertEqual(
            Organization.objects.get(id=self.org.id).seat_limit, 5,
            "seat_limit was not restored — it is set with max() at fulfilment, so "
            "the prior value must come from the recorded undo information",
        )

    def test_members_are_not_silently_removed(self):
        """Choosing whom to drop when a seat block is refunded belongs to the org
        owner; deleting memberships here would be destructive and unrecoverable."""
        from apps.accounts.models import OrganizationMember
        from apps.billing.views import _revoke_entitlement_for_transaction

        member = User.objects.create_user(
            username="m1", email="m1@example.com", password="Str0ng-Pass-1"
        )
        OrganizationMember.objects.create(
            organization=self.org, user=member, role="member"
        )
        _revoke_entitlement_for_transaction(self.txn)
        self.assertTrue(
            OrganizationMember.objects.filter(
                organization=self.org, user=member
            ).exists()
        )

    def test_revocation_never_raises(self):
        """A refund that succeeded at the gateway must not be reported as failed
        because bookkeeping afterwards had a problem."""
        self.txn.gateway_response = {"product_type": "organization", "org_id": "nope"}
        self.txn.save(update_fields=["gateway_response"])
        from apps.billing.views import _revoke_entitlement_for_transaction

        _revoke_entitlement_for_transaction(self.txn)  # must not raise
