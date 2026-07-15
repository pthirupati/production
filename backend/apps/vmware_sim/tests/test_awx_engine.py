"""Tests for the AWX engine's real job lifecycle + state-backed core views.

Focus:
  * A launched/relaunched job is a real object whose status advances on
    WALL-CLOCK time (pending -> waiting -> running -> successful) in get_state,
    so a fast poller that hits get_state many times per instant never skips a
    state — every poll recomputes the correct status for "now".
  * Each job carries a per-job stdout array that grows (streams) as the job
    advances, and terminal state + stdout stick across later polls.
  * Core views (hosts, activity, organizations, teams, users) are state-backed
    and create actions land in state.
  * None of the lifecycle work changes grading (validate_awx_lab still passes
    once the scenario blockers are cleared).
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import awx_engine as ae


class AwxJobLifecycleTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _login(self, slug=""):
        sid = "test-awx-lifecycle"
        ae.drop_session(sid)
        ae.get_state(sid, slug)
        ae.apply_action(sid, "login", {})
        return sid

    def _job(self, sid, jid):
        state = ae.get_state(sid)["inventory"]
        return next(j for j in state["jobs"] if j["id"] == jid)

    def test_launch_creates_live_pending_job(self):
        sid = self._login("launch-job")
        res = ae.apply_action(sid, "launch_template", {"template_id": 11})
        self.assertTrue(res["ok"])
        jid = res["job_id"]
        job = self._job(sid, jid)
        self.assertEqual(job["status"], "pending")
        self.assertIn("started_ts", self._raw_job(sid, jid))
        self.assertTrue(job.get("stdout"))  # stdout streaming has begun

    def _raw_job(self, sid, jid):
        entry = ae._load(sid)
        return next(j for j in entry["state"]["jobs"] if j["id"] == jid)

    def test_status_advances_on_wall_clock(self):
        sid = self._login("launch-job")
        jid = ae.apply_action(sid, "launch_template", {"template_id": 11})["job_id"]

        # Rewind started_ts to simulate elapsed wall-clock and assert each stage.
        stages = [
            (0.0, "pending"),
            (ae._JOB_WAITING_AT + 0.1, "waiting"),
            (ae._JOB_RUNNING_AT + 0.1, "running"),
            (ae._JOB_FINISH_AT + 0.1, "successful"),
        ]
        for elapsed, expected in stages:
            entry = ae._load(sid)
            raw = next(j for j in entry["state"]["jobs"] if j["id"] == jid)
            raw["started_ts"] = ae._now() - elapsed
            ae._save(sid, entry)
            self.assertEqual(self._job(sid, jid)["status"], expected,
                             f"elapsed={elapsed} expected {expected}")

    def test_fast_poller_never_skips_state(self):
        # Hitting get_state many times back-to-back must not advance past pending
        # while ~no wall-clock has elapsed (time-based, not per-request).
        sid = self._login("launch-job")
        jid = ae.apply_action(sid, "launch_template", {"template_id": 11})["job_id"]
        for _ in range(20):
            self.assertEqual(self._job(sid, jid)["status"], "pending")

    def test_stdout_streams_then_terminal_sticks(self):
        sid = self._login("launch-job")
        jid = ae.apply_action(sid, "launch_template", {"template_id": 11})["job_id"]

        entry = ae._load(sid)
        raw = next(j for j in entry["state"]["jobs"] if j["id"] == jid)
        running_lines = len(raw["stdout_plan"])

        # Mid-run: partial stdout revealed.
        raw["started_ts"] = ae._now() - (ae._JOB_RUNNING_AT + 0.1)
        ae._save(sid, entry)
        mid = self._job(sid, jid)
        self.assertEqual(mid["status"], "running")
        self.assertLess(len(mid["stdout"]), running_lines + 4)

        # Finished: full recap present.
        entry = ae._load(sid)
        raw = next(j for j in entry["state"]["jobs"] if j["id"] == jid)
        raw["started_ts"] = ae._now() - (ae._JOB_FINISH_AT + 5)
        ae._save(sid, entry)
        done = self._job(sid, jid)
        self.assertEqual(done["status"], "successful")
        full = len(done["stdout"])
        self.assertGreater(full, len(mid["stdout"]))

        # Terminal state + stdout stick across later polls (no regression).
        again = self._job(sid, jid)
        self.assertEqual(again["status"], "successful")
        self.assertEqual(len(again["stdout"]), full)

    def test_relaunch_creates_new_live_job(self):
        sid = self._login("launch-job")
        res = ae.apply_action(sid, "relaunch_job", {"job_id": 502})
        self.assertTrue(res["ok"])
        jid = res["job_id"]
        job = self._job(sid, jid)
        self.assertEqual(job["status"], "pending")
        self.assertTrue(job.get("stdout"))

    def test_cancel_stops_live_job(self):
        sid = self._login("launch-job")
        jid = ae.apply_action(sid, "launch_template", {"template_id": 11})["job_id"]
        ae.apply_action(sid, "cancel_job", {"job_id": jid})
        job = self._job(sid, jid)
        self.assertEqual(job["status"], "canceled")
        # Canceled must not later advance to successful.
        entry = ae._load(sid)
        raw = next(j for j in entry["state"]["jobs"] if j["id"] == jid)
        raw["started_ts"] = ae._now() - (ae._JOB_FINISH_AT + 5)
        ae._save(sid, entry)
        self.assertEqual(self._job(sid, jid)["status"], "canceled")

    def test_seed_jobs_have_stdout(self):
        sid = self._login()
        state = ae.get_state(sid)["inventory"]
        for jid in (501, 502):
            job = next(j for j in state["jobs"] if j["id"] == jid)
            self.assertTrue(job.get("stdout"))

    def test_launch_still_grades(self):
        sid = self._login("launch-job")
        ok, _ = ae.validate_awx_lab(sid, "launch-job")
        self.assertFalse(ok)
        ae.apply_action(sid, "launch_template", {"template_id": 11})
        ok, msg = ae.validate_awx_lab(sid, "launch-job")
        self.assertTrue(ok, msg)


class AwxStateBackedViewTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _login(self):
        sid = "test-awx-views"
        ae.drop_session(sid)
        ae.get_state(sid, "")
        ae.apply_action(sid, "login", {})
        return sid

    def test_core_views_are_seeded_in_state(self):
        sid = self._login()
        state = ae.get_state(sid)["inventory"]
        for key in ("hosts", "activity", "organizations", "teams", "users"):
            self.assertTrue(state.get(key), f"{key} should be seeded in state")

    def test_create_objects_land_in_state(self):
        sid = self._login()
        ae.apply_action(sid, "create_organization", {"name": "QA Org"})
        ae.apply_action(sid, "create_team", {"name": "SRE", "organization": "QA Org"})
        ae.apply_action(sid, "create_user", {"username": "jdoe", "name": "Jane"})
        ae.apply_action(sid, "create_host", {"name": "app99.lab", "inventory": "Production"})
        state = ae.get_state(sid)["inventory"]
        self.assertIn("QA Org", [o["name"] for o in state["organizations"]])
        self.assertIn("SRE", [t["name"] for t in state["teams"]])
        self.assertIn("jdoe", [u["username"] for u in state["users"]])
        self.assertIn("app99.lab", [h["name"] for h in state["hosts"]])

    def test_actions_record_activity_stream(self):
        sid = self._login()
        before = len(ae.get_state(sid)["inventory"]["activity"])
        ae.apply_action(sid, "launch_template", {"template_id": 11})
        after = ae.get_state(sid)["inventory"]["activity"]
        self.assertGreater(len(after), before)
        self.assertEqual(after[0]["action"].startswith("Launched"), True)
