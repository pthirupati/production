"""Audit Z5-15 — `celery_beat` was a silent single point of failure.

Its healthcheck confirmed the pidfile existed and the process was alive. Neither
says anything about whether beat is still *scheduling*, so a wedged-but-running
beat looked perfectly healthy — meaning no expiry cleanup, no orphan cleanup, no
retention sweep, and **no alert**.

**The obvious alternative was measured and rejected.** Watching the mtime of beat's
own schedule file seems like a config-only fix: a live beat keeps rewriting it. Ran
`celery beat` against a schedule whose next task was an hour away and watched the
file for 21 seconds — the mtime never advanced. That check would report a healthy
beat as dead whenever nothing is due soon, producing a restart loop in place of a
missing alert, which is worse than the bug.

So liveness is proven by beat doing its actual job: a task on a one-minute schedule
writes a timestamp, and the healthcheck fails when that timestamp goes stale.

Two properties are load-bearing:

* the write is **atomic**. A healthcheck reading a half-written file would flap,
  and the whole point of this task is to be the one thing that does not;
* the task is **trivial**. A heartbeat that can fail for its own reasons — a
  database query, a network call — reports false alarms about everything else.
"""
import os
import pathlib
import time

from django.test import SimpleTestCase

from celery_app.tasks import (
    BEAT_HEARTBEAT_INTERVAL_SECONDS,
    BEAT_HEARTBEAT_MAX_AGE_SECONDS,
    BEAT_HEARTBEAT_PATH,
    beat_heartbeat,
)


class TheHeartbeatWritesTests(SimpleTestCase):
    def setUp(self):
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        try:
            os.unlink(BEAT_HEARTBEAT_PATH)
        except OSError:
            pass

    def test_it_writes_the_file(self):
        beat_heartbeat()
        self.assertTrue(os.path.exists(BEAT_HEARTBEAT_PATH))

    def test_the_file_is_fresh(self):
        beat_heartbeat()
        age = time.time() - os.path.getmtime(BEAT_HEARTBEAT_PATH)
        self.assertLess(age, 5)

    def test_it_records_a_parseable_timestamp(self):
        beat_heartbeat()
        content = pathlib.Path(BEAT_HEARTBEAT_PATH).read_text().strip()
        self.assertTrue(content.isdigit(), f"unparseable heartbeat: {content!r}")
        self.assertLess(abs(time.time() - int(content)), 5)

    def test_running_twice_refreshes_rather_than_appends(self):
        """A growing file would still look fresh while telling you nothing."""
        beat_heartbeat()
        first = pathlib.Path(BEAT_HEARTBEAT_PATH).read_text()
        beat_heartbeat()
        second = pathlib.Path(BEAT_HEARTBEAT_PATH).read_text()
        self.assertEqual(len(second.strip().splitlines()), 1)
        self.assertGreaterEqual(int(second.strip()), int(first.strip()))

    def test_it_leaves_no_temporary_files_behind(self):
        """It writes via a temp file and renames; a leaked temp per minute would
        fill /tmp within days."""
        directory = pathlib.Path(BEAT_HEARTBEAT_PATH).parent
        before = set(directory.glob(".beat-hb-*"))
        for _ in range(5):
            beat_heartbeat()
        after = set(directory.glob(".beat-hb-*"))
        self.assertEqual(after - before, set())

    def test_the_write_is_atomic(self):
        """`os.replace` is the mechanism — a healthcheck must never read a
        partially-written file and flap."""
        import inspect

        src = inspect.getsource(beat_heartbeat)
        self.assertIn("os.replace", src)


class TheThresholdsAreCoherentTests(SimpleTestCase):
    def test_the_max_age_allows_several_missed_beats(self):
        """Equal to the interval would restart the scheduler on a single slow tick
        under load, which is a worse failure than the one being fixed."""
        self.assertGreaterEqual(
            BEAT_HEARTBEAT_MAX_AGE_SECONDS, BEAT_HEARTBEAT_INTERVAL_SECONDS * 2
        )

    def test_the_max_age_is_still_tight_enough_to_be_useful(self):
        """An hour-long window would mean the alert arrives after the damage."""
        self.assertLessEqual(BEAT_HEARTBEAT_MAX_AGE_SECONDS, 15 * 60)

    def test_the_compose_healthcheck_matches_the_code(self):
        """The threshold lives in two places — Python and a compose shell string.
        If they drift, the healthcheck silently stops meaning what it says."""
        root = pathlib.Path(__file__).resolve().parent.parent.parent
        for name in ("docker-compose.app.yml", "docker-compose.prod.yml"):
            text = (root / name).read_text()
            self.assertIn("celerybeat-heartbeat", text, name)
            self.assertIn(
                f"-lt {BEAT_HEARTBEAT_MAX_AGE_SECONDS}", text,
                f"{name} uses a staleness threshold that differs from "
                f"BEAT_HEARTBEAT_MAX_AGE_SECONDS ({BEAT_HEARTBEAT_MAX_AGE_SECONDS})",
            )

    def test_the_healthcheck_still_checks_the_process_too(self):
        """Guard the guard: a heartbeat file can outlive a dead process by up to
        the staleness window, so the pidfile check is not redundant."""
        root = pathlib.Path(__file__).resolve().parent.parent.parent
        text = (root / "docker-compose.app.yml").read_text()
        self.assertIn("celerybeat.pid", text)


class ItIsScheduledTests(SimpleTestCase):
    def test_beat_runs_it_every_minute(self):
        from celery_app.beat_schedule import CELERY_BEAT_SCHEDULE

        entry = next(
            (e for e in CELERY_BEAT_SCHEDULE.values()
             if e["task"] == "celery_app.tasks.beat_heartbeat"),
            None,
        )
        self.assertIsNotNone(
            entry,
            "the heartbeat task exists but beat never runs it — the healthcheck "
            "would fail permanently",
        )

    def test_it_is_frequent_enough_for_the_threshold(self):
        """Guard the guard: scheduling it hourly against a 200s staleness window
        would mark a healthy beat unhealthy within four minutes of every restart."""
        from celery_app.beat_schedule import CELERY_BEAT_SCHEDULE

        entry = next(
            e for e in CELERY_BEAT_SCHEDULE.values()
            if e["task"] == "celery_app.tasks.beat_heartbeat"
        )
        # celery expands `crontab(minute="*")` into the full set of 60 minutes, so
        # assert the property (runs every minute) rather than the string form.
        minutes = entry["schedule"].minute
        self.assertEqual(
            len(minutes), 60,
            f"heartbeat runs on {len(minutes)} minute(s) of the hour; the "
            f"{BEAT_HEARTBEAT_MAX_AGE_SECONDS}s staleness window needs every minute",
        )
