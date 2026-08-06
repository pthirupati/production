"""Audit Z3-10 — ratings that anyone could manufacture.

`RateView` was `IsAuthenticated` and nothing else: no throttle, no completion
gate, and two unvalidated inputs that turned bad requests into 500s. One fresh
account could 1★ every scenario on the platform in a loop, and the resulting
scores were indistinguishable from ratings left by people who did the labs.

The listing side had its own problem: `average_score` was published from any
sample size, so a single 5★ rendered exactly like a thousand. That flatters new
content and lets one hostile rating define a scenario's score permanently.

Two things here are easy to get wrong and are pinned deliberately:

* the completion gate uses `completion_finalized`, not `status == "COMPLETED"` —
  the status is set while grading may still be in flight, so gating on it would
  let a rating in before the run was actually recorded;
* `average_score` is suppressed to **null**, not to 0. A suppressed average that
  reported 0.0 would render as a zero-star scenario, which is a stronger and more
  damaging claim than the one it was meant to avoid making.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology
from apps.ratings.models import Rating
from apps.ratings.views import MAX_REVIEW_LENGTH, MIN_RATINGS_FOR_AVERAGE
from common.testing import real_throttling

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )
        self.other = Scenario.objects.create(
            technology=self.tech, title="DNS down", slug="dns-down",
            difficulty="easy",
        )
        self.user = User.objects.create_user(
            username="rater", email="rater@example.com", password="Str0ng-Pass-1"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/ratings/rate/"
        self.list_url = "/api/ratings/"

    def _complete(self, user, scenario, finalized=True):
        return LabSession.objects.create(
            user=user, scenario=scenario, status="COMPLETED",
            completion_finalized=finalized,
        )

    def test_the_urls_are_routed(self):
        """Resolved, not inferred from a status code.

        This guard used to live inside `_rate()` as "assert the status is not 404
        — unless a `scenario` kwarg was passed", which only avoided colliding with
        the tests that legitimately expect a 404 by coincidence of which keyword
        they happened to use. The same trick did break in
        `test_cancel_at_period_end`. Resolving answers the routing question
        directly.
        """
        from django.urls import resolve

        self.assertEqual(resolve(self.url).func.view_class.__name__, "RateView")
        self.assertEqual(
            resolve(self.list_url).func.view_class.__name__, "RatingsListView"
        )

    def _rate(self, **payload):
        body = {"rating_type": "scenario", "scenario": self.scenario.id, "score": 5}
        body.update(payload)
        return self.client.post(self.url, body, format="json")


class TheCompletionGateTests(_Base):
    def test_rating_a_lab_you_never_ran_is_refused(self):
        resp = self._rate()
        self.assertEqual(resp.status_code, 403, getattr(resp, "data", resp))
        self.assertEqual(resp.data["error_code"], "not_completed")
        self.assertEqual(Rating.objects.count(), 0)

    def test_rating_a_lab_you_completed_works(self):
        self._complete(self.user, self.scenario)
        resp = self._rate()
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp))
        self.assertEqual(Rating.objects.get().score, 5)

    def test_completing_one_lab_does_not_unlock_rating_another(self):
        """Otherwise the gate is one lab's worth of work for the whole catalog."""
        self._complete(self.user, self.scenario)
        resp = self._rate(scenario=self.other.id)
        self.assertEqual(resp.status_code, 403)

    def test_an_unfinalised_session_does_not_count(self):
        """`status` flips to COMPLETED before grading finishes; only
        `completion_finalized` means the run was actually recorded."""
        self._complete(self.user, self.scenario, finalized=False)
        self.assertEqual(self._rate().status_code, 403)

    def test_another_users_completion_does_not_count(self):
        stranger = User.objects.create_user(
            username="stranger", email="stranger@example.com", password="Str0ng-Pass-1"
        )
        self._complete(stranger, self.scenario)
        self.assertEqual(self._rate().status_code, 403)

    def test_staff_can_rate_without_completing(self):
        """Spot-checking the catalog should not require running every lab."""
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertEqual(self._rate().status_code, 201)

    def test_updating_an_existing_rating_still_works(self):
        self._complete(self.user, self.scenario)
        self._rate(score=5)
        resp = self._rate(score=2)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Rating.objects.get().score, 2)

    def test_the_platform_rating_is_not_gated(self):
        """It is about the product, not a lab; requiring a completion would mean
        only finishers could ever give feedback."""
        resp = self.client.post(
            self.url, {"rating_type": "platform", "score": 4}, format="json"
        )
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp))


class BadInputIsA4xxNotA500Tests(_Base):
    """`int(score)` and a raw `scenario_id` both raised, so a malformed request
    was an unhandled server error rather than a rejection."""

    def setUp(self):
        super().setUp()
        self._complete(self.user, self.scenario)

    def test_a_non_numeric_score_is_rejected(self):
        self.assertEqual(self._rate(score="five").status_code, 400)

    def test_a_missing_score_is_rejected(self):
        resp = self.client.post(
            self.url,
            {"rating_type": "scenario", "scenario": self.scenario.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_a_null_score_is_rejected(self):
        self.assertEqual(self._rate(score=None).status_code, 400)

    def test_a_score_out_of_range_is_rejected(self):
        for bad in (0, 6, -1, 99):
            self.assertEqual(self._rate(score=bad).status_code, 400, bad)

    def test_a_nonexistent_scenario_is_a_404(self):
        self.assertEqual(self._rate(scenario=999999).status_code, 404)

    def test_a_non_numeric_scenario_is_a_404_not_a_crash(self):
        self.assertEqual(self._rate(scenario="'; DROP TABLE").status_code, 404)

    def test_an_unknown_rating_type_is_rejected(self):
        self.assertEqual(self._rate(rating_type="banana").status_code, 400)

    def test_an_oversized_review_is_rejected(self):
        resp = self._rate(review="x" * (MAX_REVIEW_LENGTH + 1))
        self.assertEqual(resp.status_code, 400)

    def test_a_review_at_the_limit_is_accepted(self):
        """Guard the guard: an off-by-one here would reject legitimate reviews."""
        self.assertIn(self._rate(review="x" * MAX_REVIEW_LENGTH).status_code, (200, 201))

    def test_nothing_was_written_by_any_rejected_request(self):
        for bad in ({"score": "five"}, {"score": 9}, {"scenario": 999999}):
            self._rate(**bad)
        self.assertEqual(Rating.objects.count(), 0)


class TheWriteThrottleTests(_Base):
    """The gate is per-scenario and the platform rating is not gated at all, so a
    rate limit is what bounds the remaining surface."""

    def test_a_burst_of_platform_ratings_is_cut_off(self):
        with real_throttling(rating_write="3/hour"):
            codes = [
                self.client.post(
                    self.url, {"rating_type": "platform", "score": 1}, format="json"
                ).status_code
                for _ in range(6)
            ]
        self.assertIn(429, codes, f"RateView accepted 6 rapid writes ({codes})")

    def test_reading_ratings_is_not_throttled_by_the_write_limit(self):
        """A brigading attempt must not take the public listing down with it."""
        with real_throttling(rating_write="1/hour"):
            self.client.post(self.url, {"rating_type": "platform", "score": 1}, format="json")
            self.client.post(self.url, {"rating_type": "platform", "score": 1}, format="json")
            resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)

    def test_the_scope_is_registered_in_both_settings_modules(self):
        """`test_settings` REPLACES DEFAULT_THROTTLE_RATES, so a scope added only to
        `config/settings.py` raises ImproperlyConfigured at request time — every
        rating POST would 500 in tests while looking correct in production."""
        import pathlib

        from django.conf import settings as dj_settings

        root = pathlib.Path(dj_settings.BASE_DIR) / "config"
        for name in ("settings.py", "test_settings.py"):
            self.assertIn(
                '"rating_write":', (root / name).read_text(),
                f"the rating_write throttle scope is missing from {name}",
            )

    def test_the_view_is_throttled_at_all(self):
        from apps.ratings.views import RateView

        self.assertTrue(RateView.throttle_classes, "RateView has no throttle")


class SmallSampleSuppressionTests(_Base):
    def _seed(self, n, score=5):
        # Unique per call, not per index: two _seed() calls in one test would
        # otherwise collide on `auth_user.username`.
        for i in range(n):
            tag = f"u{score}x{Rating.objects.count()}x{i}"
            u = User.objects.create_user(
                username=tag, email=f"{tag}@example.com", password="Str0ng-Pass-1"
            )
            Rating.objects.create(
                user=u, rating_type="scenario", scenario=self.scenario, score=score
            )

    def _summary(self):
        resp = self.client.get(
            self.list_url, {"type": "scenario", "scenario": self.scenario.id}
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        return resp.data

    def test_one_rating_does_not_produce_a_public_average(self):
        self._seed(1)
        data = self._summary()
        self.assertIsNone(data["average_score"])
        self.assertFalse(data["has_enough_ratings"])

    def test_suppression_is_null_not_zero(self):
        """0.0 would render as a zero-star scenario — a stronger and more damaging
        claim than the one suppression exists to avoid."""
        self._seed(1)
        self.assertIsNot(self._summary()["average_score"], 0)

    def test_the_average_appears_once_there_is_a_real_sample(self):
        self._seed(MIN_RATINGS_FOR_AVERAGE)
        data = self._summary()
        self.assertTrue(data["has_enough_ratings"])
        self.assertEqual(data["average_score"], 5.0)

    def test_the_count_is_always_shown(self):
        """Suppressing the average while hiding the count would leave the reader
        unable to tell 'new' from 'unrated'."""
        self._seed(1)
        self.assertEqual(self._summary()["total_ratings"], 1)

    def test_the_distribution_is_still_accurate(self):
        self._seed(2, score=1)
        self._seed(1, score=4)
        data = self._summary()
        self.assertEqual(data["distribution"]["1"], 2)
        self.assertEqual(data["distribution"]["4"], 1)
        self.assertEqual(data["distribution"]["5"], 0)

    def test_the_client_is_told_where_the_floor_is(self):
        self.assertEqual(
            self._summary()["min_ratings_for_average"], MIN_RATINGS_FOR_AVERAGE
        )


class ListingQueryCountTests(_Base):
    """The summary ran a `.count()` per star inside a loop — 7 queries for a page
    element that appears on every scenario."""

    def test_the_summary_is_a_small_fixed_number_of_queries(self):
        for i in range(5):
            u = User.objects.create_user(
                username=f"q{i}", email=f"q{i}@example.com", password="Str0ng-Pass-1"
            )
            Rating.objects.create(
                user=u, rating_type="scenario", scenario=self.scenario,
                score=(i % 5) + 1, review="good",
            )
        with self.assertNumQueries(2):
            self.client.get(
                self.list_url, {"type": "scenario", "scenario": self.scenario.id}
            )

    def test_a_bad_type_is_rejected_rather_than_returning_nothing(self):
        resp = self.client.get(self.list_url, {"type": "nonsense"})
        self.assertEqual(resp.status_code, 400)

    def test_a_non_numeric_scenario_filter_is_rejected(self):
        resp = self.client.get(self.list_url, {"type": "scenario", "scenario": "abc"})
        self.assertEqual(resp.status_code, 400)
