"""XP must be granted once per scenario, not once per session.

The completion_finalized row lock in jira_integration/completion.py makes the
award idempotent per SESSION — it correctly defeats duplicate Jira webhooks and a
double-clicked Check. But restarting a lab creates a new session with
completion_finalized=False, so re-solving the same scenario re-awarded the full
50 + score + difficulty bonus every time. compute_score also rewards speed, so
the fastest replay paid the most.

Replaying for practice must still work and still update best_score/best_time and
achievements — it just must not mint new XP.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Profile
from apps.jira_integration.completion import finalize_lab_completion_if_ready
from apps.labs.models import LabSession
from apps.progress.models import UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class XpReplayTests(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="XpTech", slug="xptech")
        self.scenario = Scenario.objects.create(
            title="Replayable", slug="xp-replayable",
            technology=self.tech, difficulty="medium",
        )
        self.other = Scenario.objects.create(
            title="Second", slug="xp-second",
            technology=self.tech, difficulty="medium",
        )
        self.user = User.objects.create_user(
            username="xpuser", email="xp@example.com", password="Str0ng-Pass-1"
        )
        Profile.objects.get_or_create(user=self.user)

    def _xp(self):
        return Profile.objects.get(user=self.user).xp

    def _solve(self, scenario, score=100):
        """Create a fresh session for `scenario` and finalize it, as a restart does."""
        now = timezone.now()
        session = LabSession.objects.create(
            user=self.user, scenario=scenario, status="COMPLETED",
            validation_passed=True, score=score,
            started_at=now, ended_at=now, hints_used=0,
        )
        finalize_lab_completion_if_ready(session)
        return session

    def test_first_completion_awards_xp(self):
        before = self._xp()
        self._solve(self.scenario)
        self.assertGreater(self._xp(), before, "first completion awarded no XP")

    def test_replaying_the_same_scenario_awards_no_further_xp(self):
        self._solve(self.scenario)
        after_first = self._xp()

        for _ in range(5):
            self._solve(self.scenario)

        self.assertEqual(
            self._xp(), after_first,
            "replaying the same scenario minted new XP — the grind faucet is open",
        )

    def test_a_different_scenario_still_awards_xp(self):
        """The fix must not block genuine progress."""
        self._solve(self.scenario)
        after_first = self._xp()
        self._solve(self.other)
        self.assertGreater(
            self._xp(), after_first,
            "completing a NEW scenario did not award XP — fix is too aggressive",
        )

    def test_replay_still_improves_best_score(self):
        """Practice must remain useful even though it pays no XP."""
        self._solve(self.scenario, score=60)
        self._solve(self.scenario, score=180)

        progress = UserScenarioProgress.objects.get(
            user=self.user, scenario=self.scenario
        )
        self.assertEqual(progress.best_score, 180)
        self.assertGreaterEqual(progress.attempts, 2)

    def test_duplicate_finalize_on_one_session_is_still_idempotent(self):
        """The original per-session guard must keep working."""
        session = self._solve(self.scenario)
        after = self._xp()
        # Same session, finalized again — the completion_finalized lock bails out.
        finalize_lab_completion_if_ready(session)
        self.assertEqual(self._xp(), after)

    def test_finalize_updates_scenario_avg_completion_time(self):
        """X7c — rolling avg so ScenarioDetail can show est vs learners avg."""
        from datetime import timedelta

        now = timezone.now()
        for seconds in (600, 900, 1200):
            session = LabSession.objects.create(
                user=self.user, scenario=self.scenario, status="COMPLETED",
                validation_passed=True, score=100, hints_used=0,
            )
            # started_at is auto_now_add — set duration after create.
            LabSession.objects.filter(pk=session.pk).update(
                started_at=now - timedelta(seconds=seconds),
                ended_at=now,
            )
            session.refresh_from_db()
            finalize_lab_completion_if_ready(session)

        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.completions_count, 3)
        # ((600 + 900) / 2 = 750; then (750*2 + 1200)/3 = 900)
        self.assertEqual(self.scenario.avg_completion_time, 900)
