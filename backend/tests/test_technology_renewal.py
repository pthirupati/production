"""Re-subscribing to a lapsed technology must work.

Audit Z1-7. The duplicate guard in `CreatePaymentOrderView` filters
`is_active=True, payment_verified=True`, so a lapsed or cancelled subscription passes
it — and the code then did a bare `TechnologySubscription.objects.create()` against
`unique_together = ("user", "technology")`. Every renewal of an expired technology
raised IntegrityError and returned 500.

That is the worst possible row to fail on: the customer most likely to pay is the one
who already paid once. It also fails *silently* from the product's point of view —
the user sees a generic error, and nothing distinguishes it from a gateway outage.

Now routed through `get_or_create_technology_subscription`, which holds
`select_for_update` and catches the IntegrityError, so it is safe under two
concurrent checkouts as well as sequential renewal.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.billing.models import TechnologySubscription
from apps.question_bank.models import Technology

User = get_user_model()


class _RenewalBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="renew", email="renew@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(
            name="RenewTech", slug="renewtech", price=Decimal("499.00")
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/billing/create-order/"

    def _order(self):
        """Create an order with the gateway stubbed — we are testing the DB path."""
        with mock.patch(
            "apps.billing.payment_service.PaymentService.create_razorpay_order",
            return_value={"order_id": "order_test123", "amount": 49900},
        ):
            return self.client.post(
                self.url, {"technology_id": str(self.tech.id)}, format="json"
            )


class LapsedSubscriptionCanRenewTests(_RenewalBase):
    def test_renewing_an_inactive_subscription_does_not_500(self):
        TechnologySubscription.objects.create(
            user=self.user, technology=self.tech, amount=Decimal("499.00"),
            is_active=False, payment_verified=True,
        )
        resp = self._order()
        self.assertNotEqual(
            resp.status_code, 500,
            "renewing a lapsed technology subscription still 500s on unique_together",
        )
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp))

    def test_renewal_reuses_the_row_rather_than_duplicating(self):
        TechnologySubscription.objects.create(
            user=self.user, technology=self.tech, amount=Decimal("499.00"),
            is_active=False, payment_verified=True,
        )
        self._order()
        self.assertEqual(
            TechnologySubscription.objects.filter(
                user=self.user, technology=self.tech
            ).count(),
            1,
        )

    def test_renewal_resets_the_row_to_pending(self):
        """The new order is not paid yet — leaving a stale verified/active row would
        grant access before verification."""
        TechnologySubscription.objects.create(
            user=self.user, technology=self.tech, amount=Decimal("499.00"),
            is_active=False, payment_verified=True,
        )
        self._order()
        sub = TechnologySubscription.objects.get(user=self.user, technology=self.tech)
        self.assertFalse(sub.is_active)
        self.assertFalse(sub.payment_verified)

    def test_price_is_refreshed_on_renewal(self):
        """A price change between purchases must apply to the new order."""
        TechnologySubscription.objects.create(
            user=self.user, technology=self.tech, amount=Decimal("199.00"),
            is_active=False, payment_verified=True,
        )
        self._order()
        sub = TechnologySubscription.objects.get(user=self.user, technology=self.tech)
        self.assertEqual(sub.amount, Decimal("499.00"))


class FirstPurchaseStillWorksTests(_RenewalBase):
    def test_first_time_purchase_creates_a_pending_row(self):
        resp = self._order()
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp))
        sub = TechnologySubscription.objects.get(user=self.user, technology=self.tech)
        self.assertFalse(sub.is_active)
        self.assertFalse(sub.payment_verified)
        self.assertEqual(sub.amount, Decimal("499.00"))


class ActiveSubscriptionIsStillRefusedTests(_RenewalBase):
    def test_active_verified_subscription_returns_409(self):
        """The guard must keep doing its job — renewal-safety is not permission to
        charge twice for access the user already has."""
        TechnologySubscription.objects.create(
            user=self.user, technology=self.tech, amount=Decimal("499.00"),
            is_active=True, payment_verified=True,
        )
        resp = self._order()
        self.assertEqual(resp.status_code, 409)


class CurrencyIsServerSideTests(_RenewalBase):
    def test_client_cannot_choose_the_currency(self):
        """Audit Z1-10 — {"currency": "USD"} produced a $499 order for a ₹499
        product, and it then passed verification against the stored value."""
        with mock.patch(
            "apps.billing.payment_service.PaymentService.__init__", return_value=None
        ) as init, mock.patch(
            "apps.billing.payment_service.PaymentService.create_razorpay_order",
            return_value={"order_id": "o1", "amount": 49900},
        ):
            self.client.post(
                self.url,
                {"technology_id": str(self.tech.id), "currency": "USD"},
                format="json",
            )
        self.assertEqual(init.call_args.kwargs.get("currency"), "INR")
