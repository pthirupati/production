"""Audit Z1-11 — cancelling took away months the customer had already paid for.

`CancelTechSubscriptionView` set `is_active = False` and saved. These are prepaid
**annual** terms with no auto-renewal, so there was no future charge for the
cancellation to stop — it purely destroyed remaining entitlement. Someone
cancelling in month two lost ten months. That is a refund dispute, not a
cancellation, and every comparable service (KodeKloud, Pluralsight, GitHub)
honours the paid term.

The fix is deliberately small: `is_active` stays True and a `cancelled_at`
timestamp is recorded, so the existing `is_tech_subscription_active` expiry check
ends access at `expires_at` with no new machinery. What `cancelled_at` changes is
intent — no renewal reminders, and the status payload says `cancelled` so the UI
does not invite someone to renew what they just cancelled.

Two consequences are load-bearing and easy to get backwards:

* the customer must **still have access** immediately after cancelling — this is
  the whole point, and a fix that only renamed the field would fail it;
* they must **not** be able to buy the same technology again while they still hold
  it, or a cancel-then-repurchase loop charges twice for one entitlement.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import TechnologySubscription
from apps.billing.subscription_utils import (
    is_tech_subscription_active,
    subscription_status_payload,
    user_has_technology_access,
)
from apps.question_bank.models import Technology

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sub", email="sub@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux", price=499)
        self.sub = TechnologySubscription.objects.create(
            user=self.user, technology=self.tech,
            subscription_id="LINUX-SUB-2026-FIXITLAB",
            amount=499, is_active=True, payment_verified=True,
            expires_at=timezone.now() + timedelta(days=300),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/billing/subscribe/cancel/"

    def test_the_url_is_routed(self):
        """Checked by resolving the path, not by inferring from a status code.

        The first version of this guard lived inside `_cancel()` and asserted the
        response was not a 404 — which is wrong for the tests below that *expect* a
        404 (someone else's subscription, an unknown id). Resolving the URL answers
        the routing question directly and cannot conflict with what any individual
        test expects.
        """
        from django.urls import resolve

        self.assertEqual(
            resolve(self.url).func.view_class.__name__,
            "CancelTechSubscriptionView",
        )

    def _cancel(self, sub_id=None):
        return self.client.post(
            self.url,
            {"subscription_id": sub_id or self.sub.subscription_id},
            format="json",
        )


class AccessSurvivesCancellationTests(_Base):
    def test_cancelling_succeeds(self):
        self.assertEqual(self._cancel().status_code, 200, getattr(self._cancel(), "data", None))

    def test_the_customer_still_has_access_afterwards(self):
        """The entire point. 300 paid days remain."""
        self._cancel()
        self.assertTrue(
            user_has_technology_access(self.user, self.tech.id),
            "cancelling destroyed 300 days of paid access",
        )

    def test_the_subscription_is_still_considered_active(self):
        self._cancel()
        self.sub.refresh_from_db()
        self.assertTrue(is_tech_subscription_active(self.sub))

    def test_the_cancellation_is_recorded(self):
        self._cancel()
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.cancelled_at)

    def test_the_response_says_when_access_ends(self):
        data = self._cancel().data
        self.assertTrue(data["cancelled"])
        self.assertIsNotNone(data["access_until"])

    def test_access_does_end_when_the_term_expires(self):
        """Guard the guard: if cancellation never ended anything, this would be a
        free subscription rather than a fixed one."""
        self._cancel()
        TechnologySubscription.objects.filter(pk=self.sub.pk).update(
            expires_at=timezone.now() - timedelta(days=10)
        )
        self.assertFalse(user_has_technology_access(self.user, self.tech.id))

    def test_renewal_reminders_stop(self):
        TechnologySubscription.objects.filter(pk=self.sub.pk).update(
            renewal_reminder_at=timezone.now()
        )
        self._cancel()
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.renewal_reminder_at)


class TheStatusPayloadTellsTheTruthTests(_Base):
    def test_it_reports_cancelled(self):
        self._cancel()
        self.sub.refresh_from_db()
        self.assertTrue(subscription_status_payload(self.sub)["cancelled"])

    def test_it_does_not_ask_a_cancelled_customer_to_renew(self):
        TechnologySubscription.objects.filter(pk=self.sub.pk).update(
            expires_at=timezone.now() + timedelta(days=3)
        )
        self.sub.refresh_from_db()
        self.assertTrue(
            subscription_status_payload(self.sub)["needs_renewal"],
            "a subscription expiring in 3 days should prompt a renewal",
        )
        self._cancel()
        self.sub.refresh_from_db()
        self.assertFalse(
            subscription_status_payload(self.sub)["needs_renewal"],
            "the UI would invite the customer to renew what they just cancelled",
        )

    def test_it_still_reports_access(self):
        self._cancel()
        self.sub.refresh_from_db()
        self.assertTrue(subscription_status_payload(self.sub)["has_access"])

    def test_an_uncancelled_subscription_is_not_marked_cancelled(self):
        self.assertFalse(subscription_status_payload(self.sub)["cancelled"])


class NoDoubleChargeTests(_Base):
    def test_cancelling_does_not_open_a_repurchase_loop(self):
        """If cancelling freed the slot, a customer could cancel and buy the same
        technology again while still holding it — paying twice for one entitlement."""
        self._cancel()
        resp = self.client.post(
            "/api/billing/stripe/tech-checkout/",
            {"technology_id": self.tech.id},
            format="json",
        )
        self.assertNotEqual(
            resp.status_code, 404,
            "the checkout route moved — this test must fail loudly rather than "
            "pass on a 404",
        )
        # 409 = correctly refused; 503 = Stripe unconfigured in tests, which is
        # checked *before* the duplicate guard and so proves nothing either way.
        self.assertIn(
            resp.status_code, (409, 503),
            f"a cancelled-but-live subscription allowed a second purchase "
            f"({resp.status_code})",
        )

    def test_cancelling_twice_is_refused(self):
        self._cancel()
        self.assertEqual(self._cancel().status_code, 409)


class OtherPeoplesSubscriptionsTests(_Base):
    def test_you_cannot_cancel_someone_elses(self):
        stranger = User.objects.create_user(
            username="other", email="other@example.com", password="Str0ng-Pass-1"
        )
        self.client.force_authenticate(user=stranger)
        self.assertEqual(self._cancel().status_code, 404)
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.cancelled_at)

    def test_an_unknown_subscription_id_is_a_404(self):
        self.assertEqual(self._cancel("NOPE-2026-FIXITLAB").status_code, 404)

    def test_a_missing_subscription_id_is_a_400(self):
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 400)
