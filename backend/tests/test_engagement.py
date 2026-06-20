"""Tests for the engagement-loop endpoints added as gap-analysis quick wins.

Covers:
  - GET /api/daily-challenge/  — public, deterministic by date, never 500,
    returns a free scenario, and exposes a per-user `completed` flag.
  - GET /api/leaderboard/?scope=weekly|all&technology=<id> — segmented board.
  - GET /api/scenarios/<slug>/stats/ — per-scenario stats, safe defaults, no 500.
  - GET /api/streak/ and /api/xp/ — authed widgets, safe fallbacks.
  - XP + streak persistence on completion (Profile counters go live).
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.labs.models import LabSession
from apps.progress.models import UserScenarioProgress
from apps.progress.services import compute_level, compute_current_streak
from apps.question_bank.models import Scenario, Technology


class EngagementTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.linux = Technology.objects.create(name="Linux", slug="linux", is_active=True)
        cls.k8s = Technology.objects.create(name="Kubernetes", slug="kubernetes", is_active=True)
        # A handful of free + paid scenarios across two techs.
        cls.free1 = Scenario.objects.create(
            technology=cls.linux, slug="fix-nginx", title="Fix nginx",
            category="web", difficulty="easy", description="x",
            is_free=True, is_active=True,
        )
        cls.free2 = Scenario.objects.create(
            technology=cls.linux, slug="fix-dns", title="Fix DNS",
            category="net", difficulty="medium", description="x",
            is_free=True, is_active=True,
        )
        cls.paid1 = Scenario.objects.create(
            technology=cls.k8s, slug="crashloop", title="CrashLoop",
            category="pods", difficulty="hard", description="x",
            is_free=False, is_active=True,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _make_user(self, username="learner"):
        user = User.objects.create_user(username=username, password="pw12345!")
        Profile.objects.get_or_create(user=user)
        return user


class DailyChallengeTests(EngagementTestBase):
    def test_anonymous_gets_a_daily_challenge_200(self):
        resp = self.client.get("/api/daily-challenge/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("date", body)
        self.assertIsNotNone(body["challenge"])
        # The public daily pick must be a FREE scenario so anon users can open it.
        self.assertTrue(body["challenge"]["is_free"])

    def test_deterministic_same_pick_within_a_day(self):
        first = self.client.get("/api/daily-challenge/").json()["challenge"]["slug"]
        cache.clear()  # bust cache to prove determinism comes from the date, not cache
        second = self.client.get("/api/daily-challenge/").json()["challenge"]["slug"]
        self.assertEqual(first, second)

    def test_never_500_when_no_scenarios(self):
        Scenario.objects.all().delete()
        cache.clear()
        resp = self.client.get("/api/daily-challenge/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["challenge"])

    def test_authenticated_completed_flag(self):
        user = self._make_user()
        self.client.force_authenticate(user=user)
        slug = self.client.get("/api/daily-challenge/").json()["challenge"]["slug"]
        scenario = Scenario.objects.get(slug=slug)
        UserScenarioProgress.objects.create(
            user=user, scenario=scenario, completed=True,
            completed_at=timezone.now(),
        )
        cache.clear()
        body = self.client.get("/api/daily-challenge/").json()
        self.assertTrue(body["completed"])


class LeaderboardSegmentTests(EngagementTestBase):
    def setUp(self):
        super().setUp()
        self.u1 = self._make_user("alice")
        self.u2 = self._make_user("bob")
        # Lifetime best scores via progress.
        UserScenarioProgress.objects.create(
            user=self.u1, scenario=self.free1, completed=True,
            best_score=120, best_time=200, completed_at=timezone.now(),
        )
        UserScenarioProgress.objects.create(
            user=self.u2, scenario=self.paid1, completed=True,
            best_score=80, best_time=400, completed_at=timezone.now(),
        )
        # Weekly: a recent validated session for u2, an old one for u1.
        LabSession.objects.create(
            user=self.u2, scenario=self.paid1, status="COMPLETED",
            validation_passed=True, score=95, ended_at=timezone.now(),
        )
        old = LabSession.objects.create(
            user=self.u1, scenario=self.free1, status="COMPLETED",
            validation_passed=True, score=200,
        )
        LabSession.objects.filter(pk=old.pk).update(
            ended_at=timezone.now() - timedelta(days=14)
        )

    def test_all_time_scope_default(self):
        resp = self.client.get("/api/leaderboard/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["scope"], "all")
        # alice (120) ranks above bob (80) lifetime.
        self.assertEqual(body["leaderboard"][0]["username"], "alice")

    def test_weekly_scope_only_recent_sessions(self):
        resp = self.client.get("/api/leaderboard/?scope=weekly")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["scope"], "weekly")
        names = [e["username"] for e in body["leaderboard"]]
        # Only bob has a session within the last 7 days; alice's was 14 days ago.
        self.assertIn("bob", names)
        self.assertNotIn("alice", names)

    def test_per_technology_filter(self):
        resp = self.client.get(f"/api/leaderboard/?technology={self.k8s.id}")
        self.assertEqual(resp.status_code, 200)
        names = [e["username"] for e in resp.json()["leaderboard"]]
        # Only bob completed a k8s scenario.
        self.assertEqual(names, ["bob"])

    def test_garbage_params_never_500(self):
        resp = self.client.get("/api/leaderboard/?scope=bogus&page=abc&page_size=-9&technology=notanint")
        self.assertEqual(resp.status_code, 200)
        # Unknown scope falls back to all-time.
        self.assertEqual(resp.json()["scope"], "all")


class ScenarioStatsTests(EngagementTestBase):
    def test_stats_safe_defaults_for_unknown_slug(self):
        resp = self.client.get("/api/scenarios/does-not-exist/stats/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["learners"], 0)
        self.assertEqual(body["fail_rate_pct"], 0)
        self.assertIsNone(body["avg_solve_seconds"])

    def test_stats_aggregate_from_progress(self):
        u1 = self._make_user("c1")
        u2 = self._make_user("c2")
        u3 = self._make_user("c3")
        # 2 solved (times 100, 300; hints 0, 2), 1 attempted-not-solved.
        UserScenarioProgress.objects.create(
            user=u1, scenario=self.free1, completed=True,
            best_time=100, hints_used_best=0, completed_at=timezone.now(),
        )
        UserScenarioProgress.objects.create(
            user=u2, scenario=self.free1, completed=True,
            best_time=300, hints_used_best=2, completed_at=timezone.now(),
        )
        UserScenarioProgress.objects.create(
            user=u3, scenario=self.free1, completed=False, attempts=3,
        )
        resp = self.client.get(f"/api/scenarios/{self.free1.slug}/stats/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["learners"], 3)
        self.assertEqual(body["solved"], 2)
        self.assertEqual(body["avg_solve_seconds"], 200)  # (100+300)/2
        self.assertEqual(body["fail_rate_pct"], 33)        # (3-2)/3
        self.assertEqual(body["avg_hints_used"], 1.0)      # (0+2)/2


class StreakAndXpWidgetTests(EngagementTestBase):
    def test_streak_endpoint_requires_auth(self):
        self.assertEqual(self.client.get("/api/streak/").status_code, 401)
        self.assertEqual(self.client.get("/api/xp/").status_code, 401)

    def test_streak_calendar_and_count(self):
        user = self._make_user()
        self.client.force_authenticate(user=user)
        today = timezone.now()
        for delta in (0, 1, 2):  # 3 consecutive days
            UserScenarioProgress.objects.create(
                user=user,
                scenario=Scenario.objects.create(
                    technology=self.linux, slug=f"s-{delta}", title=f"S{delta}",
                    category="x", difficulty="easy", description="x", is_active=True,
                ),
                completed=True,
                completed_at=today - timedelta(days=delta),
            )
        resp = self.client.get("/api/streak/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["current_streak"], 3)
        self.assertEqual(body["total_active_days"], 3)
        self.assertEqual(len(body["calendar"]), 3)

    def test_xp_endpoint_reflects_profile(self):
        user = self._make_user()
        Profile.objects.filter(user=user).update(xp=450)
        self.client.force_authenticate(user=user)
        resp = self.client.get("/api/xp/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["xp"], 450)
        self.assertEqual(body["level"], compute_level(450)["level"])


class CompletionPersistsXpAndStreakTests(EngagementTestBase):
    def test_finalize_awards_xp_and_streak_once(self):
        from apps.jira_integration.completion import finalize_lab_completion_if_ready

        user = self._make_user()
        session = LabSession.objects.create(
            user=user, scenario=self.paid1, status="COMPLETED",
            validation_passed=True, score=90, ended_at=timezone.now(),
        )
        # First finalize: records progress, awards XP (50 + 90 + hard 50 = 190).
        self.assertTrue(finalize_lab_completion_if_ready(session))
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.xp, 190)
        self.assertEqual(profile.daily_streak, 1)
        self.assertEqual(profile.last_activity_date, timezone.now().date())

        # Idempotent: a second finalize must NOT double-count XP.
        session.refresh_from_db()
        self.assertFalse(finalize_lab_completion_if_ready(session))
        profile.refresh_from_db()
        self.assertEqual(profile.xp, 190)

    def test_compute_current_streak_breaks_on_gap(self):
        user = self._make_user()
        now = timezone.now()
        # Solved 3 and 4 days ago, but not today/yesterday → streak broken.
        for delta in (3, 4):
            UserScenarioProgress.objects.create(
                user=user,
                scenario=Scenario.objects.create(
                    technology=self.linux, slug=f"g-{delta}", title=f"G{delta}",
                    category="x", difficulty="easy", description="x", is_active=True,
                ),
                completed=True,
                completed_at=now - timedelta(days=delta),
            )
        self.assertEqual(compute_current_streak(user), 0)
