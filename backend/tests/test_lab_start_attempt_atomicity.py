"""Starting a lab lost updates — and quietly un-solved the scenario.

`StartLabView` bumped the attempt counter with the same non-atomic pattern
`record_attempt` had (see tests/test_progress_record_attempt_atomicity.py), except
it appeared *twice*, once per provisioning branch:

    progress, _ = UserScenarioProgress.objects.get_or_create(...)
    progress.attempts += 1
    progress.completed = False
    progress.completed_at = None
    progress.save()

Two separate defects, and the second is the serious one:

1. `attempts += 1` → `save()` is a read-modify-write, so concurrent starts for the
   same (user, scenario) lost increments. And because `save()` writes *every*
   column from a possibly-stale in-memory instance, a start overlapping a
   completion could revert a `best_score` / `best_time` / `hints_used_best` that
   the completion had just committed.

2. It reset `completed=False, completed_at=None` on every start. Replaying a lab
   is not un-solving it, and `completed` is load-bearing well beyond the progress
   badge:

   * `jira_integration.completion.finalize_lab_completion_if_ready` decides
     whether to award XP by checking whether a `completed=True` row already
     exists. Clearing the flag at start time made every replay look like a first
     solve, which re-opened the exact XP grind faucet that
     apps/progress/tests/test_xp_no_replay.py exists to keep shut — that test
     passed the whole time because it finalizes sessions directly and never goes
     through the lab-start path.
   * the leaderboard, certification eligibility, learning-path progress and the
     streak calendar all filter on `completed=True` / `completed_at`, and the
     scenario detail view re-hides `solution_explanation` when it is False. A user
     who started a replay and abandoned it lost all of that permanently.

The fix is one `record_attempt_started` helper replacing both copies. It uses a
single `UPDATE ... SET attempts = attempts + 1` rather than `record_attempt`'s
`select_for_update`, because there are no comparisons to make here — the database
can do the whole read-modify-write in one statement, with no lock held across a
round trip on a path that already queues behind the global capacity advisory lock.

The concurrency tests below use the same trick as the `record_attempt` ones: the
test DB is SQLite in-memory (config/test_settings.py), so real two-connection
concurrency is unavailable and the interleaving is injected directly instead — a
competing write commits between the helper's `get_or_create` and its `UPDATE`.
That is the exact mechanism of the lost update, and it is deterministic.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.jira_integration.completion import finalize_lab_completion_if_ready
from apps.labs.models import LabSession
from apps.progress.models import UserScenarioProgress
from apps.progress.services import record_attempt_started
from apps.question_bank.models import Scenario, Technology

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class _ConcurrentWriter:
    """Commits a competing update to the progress row exactly once, at the moment
    the helper first touches the table.

    `get_or_create` is the seam: in the buggy version that call produced the
    instance that later got saved wholesale, so a write landing right after it is
    guaranteed to be clobbered. In the fixed version the `UPDATE` that follows
    computes `attempts + 1` in the database and names only the columns it owns, so
    this write survives.
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


class _Base(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="medium",
        )
        self.user = User.objects.create_user(
            username="starter", email="starter@example.com", password=PASSWORD
        )

    def _progress(self, scenario=None):
        return UserScenarioProgress.objects.get(
            user=self.user, scenario=scenario or self.scenario
        )


class LabStartConcurrencyTests(_Base):
    """Defect 1 — the lost update."""

    def setUp(self):
        super().setUp()
        # Row already exists so the interleaved writer has something to update.
        UserScenarioProgress.objects.create(user=self.user, scenario=self.scenario)

    def _race(self, **competing_fields):
        writer = _ConcurrentWriter(self.user, self.scenario, **competing_fields)
        with mock.patch.object(
            UserScenarioProgress.objects, "get_or_create", writer
        ):
            record_attempt_started(self.user, self.scenario)
        self.assertTrue(writer.fired, "the competing write never ran")
        return self._progress()

    def test_attempts_are_not_undercounted(self):
        """A concurrent start bumped attempts to 1; ours must land on 2, not 1."""
        self.assertEqual(self._race(attempts=1).attempts, 2)

    def test_a_concurrent_best_score_is_not_clobbered(self):
        """A completion committed a best_score while the start was in flight. The
        start has no business writing that column at all."""
        progress = self._race(best_score=200, hints_used_best=0)
        self.assertEqual(progress.best_score, 200)

    def test_a_concurrent_best_time_is_not_clobbered(self):
        self.assertEqual(self._race(best_time=30).best_time, 30)

    def test_a_concurrent_completion_is_not_clobbered(self):
        """The riskiest interleaving: the user solves the lab in one tab while
        another tab starts it. The solve must survive."""
        solved_at = timezone.now() - timedelta(minutes=1)
        progress = self._race(completed=True, completed_at=solved_at, best_score=150)
        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)
        self.assertEqual(progress.best_score, 150)

    def test_hints_used_best_is_not_clobbered(self):
        self.assertEqual(self._race(hints_used_best=3).hints_used_best, 3)


class LabStartDoesNotUnsolveTests(_Base):
    """Defect 2 — the completed/completed_at reset. No concurrency involved; this
    is what a single user replaying a lab used to do to their own record."""

    def setUp(self):
        super().setUp()
        self.solved_at = timezone.now() - timedelta(days=3)
        UserScenarioProgress.objects.create(
            user=self.user, scenario=self.scenario,
            attempts=1, completed=True, completed_at=self.solved_at,
            best_score=180, best_time=42, hints_used_best=0,
        )

    def test_a_replay_does_not_clear_the_completed_flag(self):
        record_attempt_started(self.user, self.scenario)
        self.assertTrue(
            self._progress().completed,
            "starting a replay marked an already-solved scenario unsolved — this "
            "drops the user off the leaderboard and re-hides the solution",
        )

    def test_a_replay_preserves_the_first_solve_timestamp(self):
        record_attempt_started(self.user, self.scenario)
        completed_at = self._progress().completed_at
        self.assertIsNotNone(completed_at)
        self.assertEqual(
            int(completed_at.timestamp()), int(self.solved_at.timestamp()),
            "completed_at is the first-solve timestamp and feeds the streak "
            "calendar and certification windows",
        )

    def test_a_replay_preserves_the_bests(self):
        record_attempt_started(self.user, self.scenario)
        progress = self._progress()
        self.assertEqual(progress.best_score, 180)
        self.assertEqual(progress.best_time, 42)

    def test_a_replay_still_counts_as_an_attempt(self):
        """The reset had to go, but the counter is the point of the call."""
        record_attempt_started(self.user, self.scenario)
        self.assertEqual(self._progress().attempts, 2)


class ReplayXpFaucetTests(_Base):
    """The consequence that made the reset expensive rather than merely wrong.

    `finalize_lab_completion_if_ready` grants XP only when no `completed=True` row
    exists yet. Clearing that flag on every lab start made each replay read as a
    first solve, so grinding one scenario minted XP indefinitely.
    """

    def setUp(self):
        super().setUp()
        Profile.objects.get_or_create(user=self.user)

    def _xp(self):
        return Profile.objects.get(user=self.user).xp

    def _start(self):
        """What StartLabView does to progress when the user clicks Start Lab."""
        record_attempt_started(self.user, self.scenario)

    def _solve(self, score=100):
        now = timezone.now()
        session = LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="COMPLETED",
            validation_passed=True, score=score,
            started_at=now, ended_at=now, hints_used=0,
        )
        finalize_lab_completion_if_ready(session)

    def test_a_full_start_solve_start_solve_cycle_awards_xp_once(self):
        self._start()
        self._solve()
        after_first = self._xp()
        self.assertGreater(after_first, 0, "the first solve awarded no XP")

        for _ in range(5):
            self._start()
            self._solve()

        self.assertEqual(
            self._xp(), after_first,
            "replaying through the lab-start path minted new XP — starting a lab "
            "cleared `completed`, so every replay looked like a first solve",
        )

    def test_a_start_that_is_never_finished_does_not_revoke_the_solve(self):
        self._start()
        self._solve()
        self._start()  # user opens the lab again, then walks away

        progress = self._progress()
        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)


class ColdStartTests(_Base):
    def test_it_creates_the_row_on_a_first_ever_start(self):
        """`UPDATE` cannot touch a row that does not exist yet, so the
        get_or_create that precedes it has to still work on a cold start."""
        record_attempt_started(self.user, self.scenario)
        progress = self._progress()
        self.assertEqual(progress.attempts, 1)
        self.assertFalse(progress.completed)
        self.assertIsNone(progress.completed_at)

    def test_repeated_starts_accumulate(self):
        for _ in range(3):
            record_attempt_started(self.user, self.scenario)
        self.assertEqual(self._progress().attempts, 3)

    def test_last_attempt_at_is_advanced(self):
        """`last_attempt_at` is auto_now, which only fires on save() — the UPDATE
        has to set it explicitly or it silently stops tracking."""
        stale = timezone.now() - timedelta(days=10)
        UserScenarioProgress.objects.create(user=self.user, scenario=self.scenario)
        UserScenarioProgress.objects.filter(
            user=self.user, scenario=self.scenario
        ).update(last_attempt_at=stale)

        record_attempt_started(self.user, self.scenario)
        self.assertGreater(self._progress().last_attempt_at, stale)

    def test_it_does_not_touch_another_scenarios_progress(self):
        other = Scenario.objects.create(
            technology=self.tech, title="OOM", slug="oom", difficulty="hard",
        )
        UserScenarioProgress.objects.create(
            user=self.user, scenario=other, attempts=7, completed=True,
        )
        record_attempt_started(self.user, self.scenario)

        untouched = self._progress(other)
        self.assertEqual(untouched.attempts, 7)
        self.assertTrue(untouched.completed)


class TheStartViewIsWiredToTheHelperTests(_Base):
    """Both provisioning branches of StartLabView had their own copy of the block.
    These go through the real endpoint so a fix applied to only one is caught."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _start_lab(self):
        with mock.patch(
            "apps.public_api.views.lab_start_block_reason", return_value=None
        ), mock.patch(
            "apps.public_api.views.at_global_capacity", return_value=False
        ), mock.patch(
            "apps.public_api.views.can_start_lab", return_value=True
        ), mock.patch(
            "apps.public_api.views._enqueue_provisioning", return_value=True
        ), mock.patch(
            "apps.public_api.views.get_provisioner"
        ), mock.patch(
            "apps.public_api.views.sync_lab_started", return_value={}
        ):
            return self.client.post(f"/api/labs/{self.scenario.id}/start/", format="json")

    def test_starting_a_lab_records_an_attempt(self):
        response = self._start_lab()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._progress().attempts, 1)

    def test_starting_a_lab_does_not_unsolve_the_scenario(self):
        solved_at = timezone.now() - timedelta(days=2)
        UserScenarioProgress.objects.create(
            user=self.user, scenario=self.scenario,
            attempts=1, completed=True, completed_at=solved_at, best_score=190,
        )

        response = self._start_lab()
        self.assertEqual(response.status_code, 201, response.data)

        progress = self._progress()
        self.assertEqual(progress.attempts, 2)
        self.assertTrue(progress.completed, "the endpoint still clears `completed`")
        self.assertEqual(
            int(progress.completed_at.timestamp()), int(solved_at.timestamp())
        )
        self.assertEqual(progress.best_score, 190)

    def test_neither_branch_still_writes_the_block_inline(self):
        """Belt and braces: the endpoint test above only exercises whichever
        provisioning branch this scenario's infra type selects."""
        import inspect

        from apps.public_api import views

        src = inspect.getsource(views.StartLabView)
        self.assertNotIn(
            "progress.completed = False", src,
            "a copy of the reset survives in StartLabView",
        )
        self.assertNotIn(
            "progress.attempts += 1", src,
            "a copy of the non-atomic increment survives in StartLabView",
        )
        self.assertEqual(
            src.count("record_attempt_started"), 2,
            "both provisioning branches must go through the helper",
        )
