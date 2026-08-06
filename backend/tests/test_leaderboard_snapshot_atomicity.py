"""Recomputing the leaderboard snapshot must not expose an empty window.

Audit Z3-7. `LeaderboardEntry` is a cache **nobody currently reads** — the live
endpoint aggregates from `UserScenarioProgress` directly, `apps/leaderboard/` has no
`urls.py` so its own views are unreachable, and `adminpanel` imports the model
without querying it. Verified all three before touching anything.

That is exactly why it was worth fixing rather than ignoring. Both recompute
functions did a bare `.delete()` followed by N individual `.create()` calls with **no
transaction**. Harmless while nothing reads the table — and a trap the moment anyone
points a real endpoint at it, because every reader in the recompute window would see
a partial or empty leaderboard, and a mid-loop failure would leave it permanently
truncated. Dead code that is safe to revive is worth more than dead code that
punishes whoever revives it.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, TransactionTestCase

from apps.leaderboard import services
from apps.leaderboard.models import LeaderboardEntry
from apps.leaderboard.services import (
    compute_global_leaderboard,
    compute_scenario_leaderboard,
)
from apps.progress.models import UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


def _seed(n=5):
    tech = Technology.objects.create(name="LbTech", slug="lbtech")
    scenario = Scenario.objects.create(
        title="Lb", slug="lb-scenario", technology=tech, description="d"
    )
    for i in range(n):
        user = User.objects.create_user(
            username=f"lb{i}", email=f"lb{i}@example.com", password="Str0ng-Pass-1"
        )
        UserScenarioProgress.objects.create(
            user=user, scenario=scenario, completed=True, best_score=100 - i,
        )
    return scenario


class SnapshotCorrectnessTests(TestCase):
    def setUp(self):
        self.scenario = _seed()

    def test_global_snapshot_is_populated(self):
        compute_global_leaderboard()
        self.assertEqual(
            LeaderboardEntry.objects.filter(scenario__isnull=True).count(), 5
        )

    def test_ranks_are_ordered_by_score(self):
        compute_global_leaderboard()
        rows = list(
            LeaderboardEntry.objects.filter(scenario__isnull=True).order_by("rank")
        )
        self.assertEqual([r.rank for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(rows[0].score, 100)
        self.assertGreater(rows[0].score, rows[-1].score)

    def test_recompute_replaces_rather_than_duplicates(self):
        compute_global_leaderboard()
        compute_global_leaderboard()
        self.assertEqual(
            LeaderboardEntry.objects.filter(scenario__isnull=True).count(), 5,
            "a second recompute duplicated the snapshot",
        )

    def test_scenario_snapshot_is_scoped_to_its_scenario(self):
        compute_scenario_leaderboard(self.scenario)
        self.assertEqual(
            LeaderboardEntry.objects.filter(scenario=self.scenario).count(), 5
        )
        self.assertEqual(
            LeaderboardEntry.objects.filter(scenario__isnull=True).count(), 0,
            "the per-scenario recompute wrote global rows",
        )

    def test_global_and_scenario_snapshots_coexist(self):
        compute_global_leaderboard()
        compute_scenario_leaderboard(self.scenario)
        self.assertEqual(LeaderboardEntry.objects.count(), 10)


class AtomicityTests(TransactionTestCase):
    """The loaded gun: the delete must not be visible without the inserts."""

    def setUp(self):
        self.scenario = _seed()
        compute_global_leaderboard()

    def test_a_failure_mid_recompute_leaves_the_previous_snapshot(self):
        """Without @transaction.atomic the delete would already have committed and
        the table would be left empty — permanently, until the next successful run."""
        before = LeaderboardEntry.objects.filter(scenario__isnull=True).count()
        self.assertEqual(before, 5)

        class _Boom(Exception):
            pass

        try:
            with transaction.atomic():
                compute_global_leaderboard()
                raise _Boom()
        except _Boom:
            pass

        self.assertEqual(
            LeaderboardEntry.objects.filter(scenario__isnull=True).count(), before,
            "a failed recompute truncated the snapshot instead of rolling back",
        )

    def test_recompute_functions_declare_atomicity(self):
        """Structural guard: the decorator is the whole fix, and removing it would
        still pass every behavioural test above under Django's default autocommit in
        a TestCase."""
        for fn in (compute_global_leaderboard, compute_scenario_leaderboard):
            self.assertTrue(
                hasattr(fn, "__wrapped__"),
                f"{fn.__name__} is no longer wrapped in transaction.atomic",
            )


class BeatTaskDelegationTests(TestCase):
    """The Celery beat task must not carry its own copy of the recompute.

    Audit L1538. `celery_app.tasks.recalculate_leaderboard` held a second,
    near-identical delete + bulk_create that was never migrated to `services.py`.
    Only the services copy was hardened and tested, so the invariant this file
    exists to protect was silently unenforced on the path that actually runs in
    production. These tests fail if the duplicate body ever comes back.
    """

    def setUp(self):
        self.scenario = _seed()

    def test_beat_task_produces_the_snapshot(self):
        from celery_app.tasks import recalculate_leaderboard

        result = recalculate_leaderboard()

        self.assertEqual(result["entries"], 5)
        rows = list(
            LeaderboardEntry.objects.filter(scenario__isnull=True).order_by("rank")
        )
        self.assertEqual([r.rank for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(rows[0].score, 100)

    def test_beat_task_delegates_to_services(self):
        """Behavioural proof of de-duplication: if the task still computed the
        snapshot itself, neutering the service would not stop it writing rows.

        Patched at `apps.leaderboard.services` (not at a name bound inside the
        task) so this stays honest regardless of how the task imports it.
        """
        with mock.patch.object(services, "compute_global_leaderboard") as spy:
            from celery_app.tasks import recalculate_leaderboard

            recalculate_leaderboard()

        spy.assert_called_once()
        self.assertEqual(
            LeaderboardEntry.objects.filter(scenario__isnull=True).count(), 0,
            "the beat task wrote leaderboard rows without calling the service — "
            "it is still carrying its own duplicate recompute",
        )


class ScheduleTests(TestCase):
    def test_recompute_is_not_scheduled_hourly(self):
        """It rebuilds every ranked row for a table with no readers; hourly was pure
        write amplification and dead tuples for autovacuum to chase."""
        from celery_app.beat_schedule import CELERY_BEAT_SCHEDULE

        entries = [
            e for e in CELERY_BEAT_SCHEDULE.values()
            if e["task"] == "celery_app.tasks.recalculate_leaderboard"
        ]
        self.assertEqual(len(entries), 1, "leaderboard recompute is scheduled twice")
        schedule = entries[0]["schedule"]
        self.assertNotEqual(
            set(getattr(schedule, "hour", set())), set(range(24)),
            "leaderboard recompute is still running every hour",
        )
