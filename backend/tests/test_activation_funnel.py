"""Audit Z6-6 — the funnel, without a third-party processor.

The audit's diagnosis was right (prioritisation was being made blind) and its
remedy was PostHog, which the owner declined. That is not a dead end: seven of the
nine stages it asks for are already recorded, because this platform stores what
users *did* rather than only what they clicked.

Deriving them beats emitting events here for three reasons, and the tests below
pin the two that are easy to get wrong:

* **Cohorting.** Counting "labs started in the last 30 days" against "signups in
  the last 30 days" mixes populations and yields conversion rates above 100% — the
  classic way a funnel dashboard becomes quietly meaningless. Every stage counts
  members *of the signup cohort*.
* **Honest gaps.** `scenario_viewed` and `paywall_viewed` have no server-side
  trace. They are declared in `not_tracked` rather than omitted, so the funnel does
  not overstate its own completeness.

It is also retroactive — it answers questions from launch rather than from install
day — and it cannot drift, because a LabSession row exists when a lab starts,
whereas an event fires only if someone remembered to add it.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.adminpanel.funnel import (
    activation_funnel,
    technology_conversion,
    time_to_activation,
)
from apps.billing.models import PaymentTransaction
from apps.labs.models import CommandHistory, LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class _Base(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )

    def _user(self, name, joined_days_ago=1):
        u = User.objects.create_user(
            username=name, email=f"{name}@example.com", password=PASSWORD
        )
        User.objects.filter(pk=u.pk).update(
            date_joined=timezone.now() - timedelta(days=joined_days_ago)
        )
        u.refresh_from_db()
        return u

    def _session(self, user, finalized=False, status="RUNNING"):
        return LabSession.objects.create(
            user=user, scenario=self.scenario, status=status,
            completion_finalized=finalized,
        )

    def _stage(self, funnel, key):
        return next(s for s in funnel["stages"] if s["key"] == key)


class TheFunnelCountsRealBehaviourTests(_Base):
    def test_an_empty_window_does_not_divide_by_zero(self):
        funnel = activation_funnel(days=30)
        self.assertEqual(funnel["signed_up"], 0)
        self.assertEqual(funnel["stages"], [])

    def test_signups_are_counted(self):
        self._user("a")
        self._user("b")
        self.assertEqual(activation_funnel(30)["signed_up"], 2)

    def test_staff_are_excluded(self):
        """Internal accounts run labs constantly and would inflate every rate."""
        u = self._user("staffer")
        User.objects.filter(pk=u.pk).update(is_staff=True)
        self.assertEqual(activation_funnel(30)["signed_up"], 0)

    def test_starting_a_lab_advances_the_funnel(self):
        u = self._user("starter")
        self._session(u)
        self.assertEqual(self._stage(activation_funnel(30), "lab_started")["users"], 1)

    def test_typing_a_command_is_the_activation_signal(self):
        """Starting a lab and never touching the terminal is the most useful
        drop-off on this platform, and it is invisible to any funnel that stops at
        'lab_started'."""
        started = self._user("looked")
        typed = self._user("typed")
        self._session(started)
        s2 = self._session(typed)
        CommandHistory.objects.create(session=s2, command="ls -la")

        funnel = activation_funnel(30)
        self.assertEqual(self._stage(funnel, "lab_started")["users"], 2)
        self.assertEqual(self._stage(funnel, "lab_first_command")["users"], 1)

    def test_completion_and_purchase_are_counted(self):
        u = self._user("buyer")
        self._session(u, finalized=True)
        PaymentTransaction.objects.create(
            user=u, amount=Decimal("499.00"), taxable_amount=Decimal("499.00"),
            currency="INR", payment_method="razorpay", status="success",
            idempotency_key="funnel-1",
        )
        funnel = activation_funnel(30)
        self.assertEqual(self._stage(funnel, "lab_validated")["users"], 1)
        self.assertEqual(self._stage(funnel, "checkout_started")["users"], 1)
        self.assertEqual(self._stage(funnel, "purchase_completed")["users"], 1)

    def test_a_failed_payment_counts_as_checkout_not_purchase(self):
        u = self._user("tried")
        PaymentTransaction.objects.create(
            user=u, amount=Decimal("499.00"), taxable_amount=Decimal("499.00"),
            currency="INR", payment_method="razorpay", status="failed",
            idempotency_key="funnel-2",
        )
        funnel = activation_funnel(30)
        self.assertEqual(self._stage(funnel, "checkout_started")["users"], 1)
        self.assertEqual(self._stage(funnel, "purchase_completed")["users"], 0)

    def test_a_user_is_counted_once_however_many_labs_they_run(self):
        """Stage counts are people, not events — otherwise one enthusiastic user
        makes the funnel look like ten."""
        u = self._user("busy")
        for _ in range(5):
            s = self._session(u)
            CommandHistory.objects.create(session=s, command="ls")
        self.assertEqual(self._stage(activation_funnel(30), "lab_started")["users"], 1)


class TheCohortingIsCorrectTests(_Base):
    """The failure that makes a funnel meaningless rather than merely wrong."""

    def test_a_lab_by_an_older_user_does_not_inflate_the_window(self):
        old = self._user("veteran", joined_days_ago=200)
        s = self._session(old)
        CommandHistory.objects.create(session=s, command="ls")
        self._user("newcomer", joined_days_ago=1)

        funnel = activation_funnel(30)
        self.assertEqual(funnel["signed_up"], 1)
        self.assertEqual(
            self._stage(funnel, "lab_started")["users"], 0,
            "a lab run by a user who signed up outside the window was counted — "
            "conversion can then exceed 100%",
        )

    def test_no_stage_can_exceed_one_hundred_percent(self):
        for i in range(3):
            u = self._user(f"u{i}")
            s = self._session(u, finalized=True)
            CommandHistory.objects.create(session=s, command="ls")
        for stage in activation_funnel(30)["stages"]:
            self.assertLessEqual(stage["pct_of_signups"], 100.0, stage["key"])
            self.assertLessEqual(stage["pct_of_previous"], 100.0, stage["key"])

    def test_both_rates_are_reported(self):
        """'Of signups' shows absolute health; 'of previous' locates the step that
        actually leaks. One without the other misleads."""
        u = self._user("solo")
        self._session(u)
        stage = self._stage(activation_funnel(30), "lab_started")
        self.assertIn("pct_of_signups", stage)
        self.assertIn("pct_of_previous", stage)


class ItDeclaresWhatItCannotSeeTests(_Base):
    def test_untracked_stages_are_named(self):
        """Silently omitting them would overstate the funnel's completeness."""
        not_tracked = activation_funnel(30)["not_tracked"]
        self.assertIn("scenario_viewed", not_tracked["stages"])
        self.assertIn("paywall_viewed", not_tracked["stages"])
        self.assertTrue(not_tracked["reason"])

    def test_the_reason_explains_why(self):
        self.assertIn(
            "client", activation_funnel(30)["not_tracked"]["reason"].lower()
        )


class PerTechnologyTests(_Base):
    def test_it_separates_content_failure_from_infrastructure_failure(self):
        """A high provision-failure rate is an infrastructure problem wearing a
        content problem's clothes."""
        u = self._user("t")
        self._session(u, finalized=True)
        self._session(u, status="FAILED")

        rows = technology_conversion(days=90)
        row = next(r for r in rows if r["slug"] == "linux")
        self.assertEqual(row["sessions"], 2)
        self.assertEqual(row["completion_rate"], 50.0)
        self.assertEqual(row["provision_failure_rate"], 50.0)

    def test_learners_are_distinct_from_sessions(self):
        u = self._user("repeat")
        self._session(u)
        self._session(u)
        row = next(r for r in technology_conversion(90) if r["slug"] == "linux")
        self.assertEqual(row["sessions"], 2)
        self.assertEqual(row["learners"], 1)


class TimeToActivationTests(_Base):
    def test_no_activations_returns_none_rather_than_zero(self):
        """Zero minutes would read as 'instant activation', which is the opposite
        of the truth."""
        result = time_to_activation(30)
        self.assertEqual(result["activated_users"], 0)
        self.assertIsNone(result["median_minutes"])

    def test_it_measures_from_signup_to_first_command(self):
        u = self._user("timed", joined_days_ago=1)
        s = self._session(u)
        c = CommandHistory.objects.create(session=s, command="ls")
        CommandHistory.objects.filter(pk=c.pk).update(
            timestamp=u.date_joined + timedelta(minutes=30)
        )
        result = time_to_activation(30)
        self.assertEqual(result["activated_users"], 1)
        self.assertAlmostEqual(result["median_minutes"], 30.0, places=0)


class TheEndpointTests(_Base):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username="funneladmin", email="funneladmin@example.com",
            password=PASSWORD, is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_the_route_is_wired(self):
        from django.urls import resolve

        self.assertEqual(
            resolve("/api/admin/funnel/").func.view_class.__name__, "AdminFunnelView"
        )

    def test_it_returns_all_three_sections(self):
        resp = self.client.get("/api/admin/funnel/")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        for key in ("funnel", "by_technology", "time_to_activation"):
            self.assertIn(key, resp.data)

    def test_it_is_admin_only(self):
        """Conversion and revenue shape are not learner-facing data."""
        learner = self._user("nosy")
        client = APIClient()
        client.force_authenticate(user=learner)
        self.assertIn(
            client.get("/api/admin/funnel/").status_code, (401, 403)
        )

    def test_a_junk_days_parameter_does_not_500(self):
        for bad in ("abc", "-5", "99999", ""):
            resp = self.client.get(f"/api/admin/funnel/?days={bad}")
            self.assertEqual(resp.status_code, 200, bad)
