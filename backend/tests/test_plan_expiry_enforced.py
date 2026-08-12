"""A lapsed plan subscription must stop conferring its plan's limits.

``get_user_subscription`` filtered on ``is_active=True`` only and never looked at
``expires_at``, while ``can_start_lab`` / ``can_extend_lab`` read
``subscription.plan.max_labs_per_day`` straight off the result. So a Pro plan that
lapsed months ago kept its elevated daily lab cap and duration indefinitely.
``get_user_plan_info`` merely *reported* ``expires_at``, which is what made it look
handled.

Uses the GRACE_PERIOD_DAYS window already established for per-technology
subscriptions rather than a second expiry rule — a renewal landing a day late must
not drop a paying user to the free tier.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Plan, Subscription
from apps.billing.services import (
    can_extend_lab,
    can_start_lab,
    get_user_subscription,
    plan_subscription_is_current,
)

User = get_user_model()


class PlanExpiryTests(TestCase):
    def setUp(self):
        self.pro = Plan.objects.create(
            code="pro", name="Pro", price=999,
            max_labs_per_day=50, max_lab_duration_minutes=120,
        )
        self.user = User.objects.create_user(
            username="planuser", email="plan@example.com", password="Str0ng-Pass-1"
        )

    def _sub(self, expires_in_days=None, active=True):
        return Subscription.objects.create(
            user=self.user, plan=self.pro, is_active=active,
            expires_at=(timezone.now() + timedelta(days=expires_in_days))
            if expires_in_days is not None else None,
        )

    # ── the leak ─────────────────────────────────────────────────────────────
    def test_lapsed_plan_loses_elevated_lab_cap(self):
        self._sub(expires_in_days=-30)
        # Pro allows 50/day; free allows 5. 10 must now be refused.
        self.assertFalse(
            can_start_lab(self.user, labs_started_today=10),
            "a plan that lapsed 30 days ago still granted Pro limits",
        )

    def test_lapsed_plan_loses_elevated_duration(self):
        self._sub(expires_in_days=-30)
        self.assertFalse(
            can_extend_lab(self.user, duration_minutes=90),
            "a lapsed plan still allowed the Pro lab duration",
        )

    def test_lapsed_subscription_serves_free_plan(self):
        self._sub(expires_in_days=-30)
        self.assertEqual(get_user_subscription(self.user).plan.code, "free")

    # ── paying users keep working ────────────────────────────────────────────
    def test_current_plan_keeps_its_limits(self):
        self._sub(expires_in_days=30)
        self.assertTrue(can_start_lab(self.user, labs_started_today=10))
        self.assertTrue(can_extend_lab(self.user, duration_minutes=90))

    def test_grace_window_still_honours_the_plan(self):
        """A renewal landing a day late must not demote a paying customer."""
        self._sub(expires_in_days=-1)
        self.assertTrue(
            plan_subscription_is_current(Subscription.objects.get(user=self.user)),
            "expired-by-one-day fell outside the grace window",
        )
        self.assertTrue(can_start_lab(self.user, labs_started_today=10))

    def test_just_past_grace_is_lapsed(self):
        from apps.billing.subscription_utils import GRACE_PERIOD_DAYS

        self._sub(expires_in_days=-(GRACE_PERIOD_DAYS + 1))
        self.assertFalse(
            plan_subscription_is_current(Subscription.objects.get(user=self.user))
        )

    def test_null_expiry_is_perpetual(self):
        """Free tier and comped access legitimately have no expiry."""
        self._sub(expires_in_days=None)
        self.assertTrue(
            plan_subscription_is_current(Subscription.objects.get(user=self.user))
        )
        self.assertTrue(can_start_lab(self.user, labs_started_today=10))

    def test_inactive_subscription_is_not_current(self):
        sub = self._sub(expires_in_days=30, active=False)
        self.assertFalse(plan_subscription_is_current(sub))

    # ── no surprise writes in a read path ────────────────────────────────────
    def test_lapsed_lookup_does_not_flip_is_active(self):
        """get_user_subscription is called on every lab start; a silent write there
        is how concurrency bugs start. Refusing to honour the plan is enough."""
        self._sub(expires_in_days=-30)
        get_user_subscription(self.user)
        self.assertTrue(
            Subscription.objects.get(user=self.user).is_active,
            "the read path wrote to the database",
        )

    def test_staff_keep_unlimited_access_regardless(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self._sub(expires_in_days=-90)
        self.assertTrue(can_start_lab(self.user, labs_started_today=999))
