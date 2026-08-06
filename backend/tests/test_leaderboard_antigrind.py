"""Weekly leaderboard must not reward re-solving the same lab.

_build_weekly used Sum("score") over every validated LabSession in the window, so
solving one 30-second scenario 200 times added 200 scores and topped the board.
The all-time board already summed per-scenario bests (UserScenarioProgress
.best_score); this asserts weekly now matches.

The bug was visible in its own output: scenarios_completed used distinct=True, so
a grinder appeared as "1 scenario" beside an enormous total, and nothing rejected
it.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.labs.models import LabSession
from apps.public_api.views import LeaderboardView
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class WeeklyLeaderboardAntiGrindTests(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="AntiGrind", slug="antigrind")
        self.easy = Scenario.objects.create(
            title="Easy lab", slug="ag-easy", technology=self.tech, difficulty="easy"
        )
        self.other = Scenario.objects.create(
            title="Other lab", slug="ag-other", technology=self.tech, difficulty="medium"
        )
        self.grinder = User.objects.create_user(
            username="grinder", email="grind@example.com", password="Str0ng-Pass-1"
        )
        self.honest = User.objects.create_user(
            username="honest", email="honest@example.com", password="Str0ng-Pass-1"
        )

    def _session(self, user, scenario, score):
        now = timezone.now()
        return LabSession.objects.create(
            user=user,
            scenario=scenario,
            status="COMPLETED",
            validation_passed=True,
            score=score,
            started_at=now,
            ended_at=now,
        )

    def _row_for(self, username):
        rows = LeaderboardView._build_weekly(None)
        return next((r for r in rows if r["username"] == username), None)

    def test_replaying_one_scenario_does_not_inflate_total(self):
        """40 replays of one lab must count once, at its best score."""
        for _ in range(40):
            self._session(self.grinder, self.easy, 100)

        row = self._row_for("grinder")
        self.assertIsNotNone(row)
        self.assertEqual(
            row["total_score"], 100,
            "replays inflated the weekly total — the grind faucet is open",
        )
        self.assertEqual(row["scenarios_completed"], 1)

    def test_best_score_wins_across_attempts(self):
        """Improving on a retry should count, at the better score."""
        self._session(self.grinder, self.easy, 60)
        self._session(self.grinder, self.easy, 145)
        self._session(self.grinder, self.easy, 90)

        self.assertEqual(self._row_for("grinder")["total_score"], 145)

    def test_distinct_scenarios_still_add_up(self):
        """The fix must not flatten genuine breadth."""
        self._session(self.honest, self.easy, 120)
        self._session(self.honest, self.other, 130)

        row = self._row_for("honest")
        self.assertEqual(row["total_score"], 250)
        self.assertEqual(row["scenarios_completed"], 2)

    def test_honest_breadth_outranks_grinding(self):
        """The whole point: two real solves must beat forty replays of one."""
        for _ in range(40):
            self._session(self.grinder, self.easy, 100)
        self._session(self.honest, self.easy, 120)
        self._session(self.honest, self.other, 130)

        rows = LeaderboardView._build_weekly(None)
        order = [r["username"] for r in rows]
        self.assertLess(
            order.index("honest"), order.index("grinder"),
            "grinding still outranks genuine breadth",
        )

    def test_failed_sessions_are_excluded(self):
        now = timezone.now()
        LabSession.objects.create(
            user=self.honest, scenario=self.easy, status="COMPLETED",
            validation_passed=False, score=999, started_at=now, ended_at=now,
        )
        self.assertIsNone(self._row_for("honest"))
