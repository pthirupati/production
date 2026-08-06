"""Audit L1516 — `record_attempt` lost updates under concurrent attempts.

The original body was `get_or_create(...)` → mutate the Python instance →
`save()`. Every field is a read-modify-write on that instance: `attempts += 1`,
`score > best_score`, `time_seconds < best_time`, `if not completed_at`. Two
attempts for the same (user, scenario) that overlapped therefore raced — the
later `save()` wrote a full row snapshot taken *before* the earlier one
committed, so it undercounted `attempts` and could silently revert a higher
`best_score`, a faster `best_time`, or an already-set `completed_at`.

Testing this properly needs two real connections, and the default test DB here is
SQLite in-memory (config/test_settings.py) where that is not available. So
instead of faking threads, these tests inject the interleaving directly: a writer
commits to the row in between `record_attempt`'s fetch and its save. That is the
exact mechanism of the lost update, and it is deterministic.

`select_for_update()` is what makes these pass: it forces a fresh read of
committed state at the point of the lock. Note that `F("attempts") + 1` alone
would fix only `test_attempts_are_not_undercounted` and would leave the
best_score / completed_at tests failing — which is why the fix is a lock over
the whole block rather than an F() expression on the counter.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.progress.models import UserScenarioProgress
from apps.progress.services import record_attempt
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class _ConcurrentWriter:
    """Commits a competing update to the progress row exactly once, at the
    moment `record_attempt` first touches the table.

    Patching `get_or_create` is the seam: in the buggy version that call is what
    produced the instance that later got saved wholesale, so a write landing
    right after it is guaranteed to be clobbered. In the fixed version the
    subsequent `select_for_update().get()` re-reads the row and sees this write.
    """

    def __init__(self, user, scenario, **fields):
        self.user = user
        self.scenario = scenario
        self.fields = fields
        self.fired = False
        self._real = UserScenarioProgress.objects.get_or_create

    def __call__(self, *args, **kwargs):
        result = self._real(*args, **kwargs)
        if not self.fired:
            self.fired = True
            UserScenarioProgress.objects.filter(
                user=self.user, scenario=self.scenario
            ).update(**self.fields)
        return result


class RecordAttemptConcurrencyTests(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )
        self.user = User.objects.create_user(
            username="racer", email="racer@example.com", password="Str0ng-Pass-1"
        )
        # Row already exists so the interleaved writer has something to update.
        UserScenarioProgress.objects.create(user=self.user, scenario=self.scenario)

    def _race(self, competing_fields, **record_kwargs):
        writer = _ConcurrentWriter(self.user, self.scenario, **competing_fields)
        with mock.patch.object(
            UserScenarioProgress.objects, "get_or_create", writer
        ):
            record_attempt(
                user=self.user, scenario=self.scenario,
                **record_kwargs,
            )
        self.assertTrue(writer.fired, "the competing write never ran")
        return UserScenarioProgress.objects.get(
            user=self.user, scenario=self.scenario
        )

    def test_attempts_are_not_undercounted(self):
        """A concurrent attempt bumped attempts to 1; ours must land on 2, not 1."""
        progress = self._race({"attempts": 1}, score=50)
        self.assertEqual(progress.attempts, 2)

    def test_a_higher_concurrent_best_score_is_not_clobbered(self):
        """The other attempt scored 200. Ours scored 50 and must not win."""
        progress = self._race({"best_score": 200, "hints_used_best": 0}, score=50)
        self.assertEqual(progress.best_score, 200)

    def test_a_faster_concurrent_best_time_is_not_clobbered(self):
        progress = self._race(
            {"best_time": 30, "completed": True},
            score=50, completed=True, time_seconds=900,
        )
        self.assertEqual(progress.best_time, 30)

    def test_an_existing_completed_at_is_not_reset(self):
        """completed_at is the first-solve timestamp; a later attempt must not
        move it forward."""
        first_solve = timezone.now() - timedelta(days=3)
        progress = self._race(
            {"completed": True, "completed_at": first_solve},
            score=50, completed=True, time_seconds=100,
        )
        self.assertIsNotNone(progress.completed_at)
        self.assertEqual(
            int(progress.completed_at.timestamp()), int(first_solve.timestamp())
        )

    def test_uncontended_attempt_still_records_normally(self):
        """Guard against the lock changing single-writer behaviour."""
        record_attempt(
            user=self.user, scenario=self.scenario,
            score=180, completed=True, time_seconds=42, hints_used=1,
        )
        progress = UserScenarioProgress.objects.get(
            user=self.user, scenario=self.scenario
        )
        self.assertEqual(progress.attempts, 1)
        self.assertEqual(progress.best_score, 180)
        self.assertEqual(progress.best_time, 42)
        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)

    def test_creates_the_row_when_absent(self):
        """select_for_update cannot lock a nonexistent row — the get_or_create
        that precedes the lock has to still work on a cold start."""
        other = Scenario.objects.create(
            technology=self.tech, title="OOM", slug="oom", difficulty="hard",
        )
        record_attempt(user=self.user, scenario=other, score=120)
        progress = UserScenarioProgress.objects.get(user=self.user, scenario=other)
        self.assertEqual(progress.attempts, 1)
        self.assertEqual(progress.best_score, 120)
