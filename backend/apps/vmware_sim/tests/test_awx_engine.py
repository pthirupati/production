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
  * Galaxy artifacts are load-bearing: a project's requirements.yml decides
    which roles exist, only a project SYNC installs them, and a playbook using
    an uninstalled role fails to resolve.
  * Run outcomes come from a convergence ledger, so check mode changes nothing
    and a repeated apply is provably idempotent (changed=0).
"""
import re

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import awx_engine as ae


def _plain(lines) -> str:
    """Strip ANSI so assertions read the text, not the colour codes."""
    return re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(lines or []))


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


class AwxAiInfraGpuSeedTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_ai_infra_driver_rollout_seeds_gpu_templates(self):
        sid = "test-awx-ai-infra"
        ae.drop_session(sid)
        state = ae.get_state(sid, "ai-infra-awx-nvidia-driver-rollout")["inventory"]
        names = [t["name"] for t in state["job_templates"]]
        self.assertIn("GPU Driver Install (H100)", names)
        self.assertIn("DCGM Exporter Deploy", names)
        self.assertIn("Image Repave (jammy-h100)", names)
        inv = [i["name"] for i in state["inventories"]]
        self.assertIn("maas-gpu-nodes", inv)
        hosts = [h["name"] for h in state["hosts"]]
        self.assertIn("gpu-node-01", hosts)
        self.assertNotIn("Patch Linux", names)

    def test_launch_gpu_driver_streams_fleet_recap(self):
        sid = "test-awx-ai-infra-launch"
        ae.drop_session(sid)
        ae.get_state(sid, "ai-infra-awx-nvidia-driver-rollout")
        ae.apply_action(sid, "login", {})
        res = ae.apply_action(sid, "launch_template", {"template_id": 12})
        self.assertTrue(res["ok"])
        jid = res["job_id"]
        entry = ae._load(sid)
        raw = next(j for j in entry["state"]["jobs"] if j["id"] == jid)
        raw["started_ts"] = ae._now() - (ae._JOB_FINISH_AT + 1)
        ae._save(sid, entry)
        job = next(j for j in ae.get_state(sid)["inventory"]["jobs"] if j["id"] == jid)
        self.assertEqual(job["status"], "successful")
        blob = "\n".join(job.get("stdout") or [])
        self.assertIn("gpu-node-01", blob)
        self.assertIn("nvidia", blob.lower())
        ok, msg = ae.validate_awx_lab(sid, "ai-infra-awx-nvidia-driver-rollout")
        self.assertTrue(ok, msg)


class AwxGalaxyArtifactTests(TestCase):
    """requirements.yml is a real artifact: it pins, and only a sync installs."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _login(self, slug="academy-ansible-003-operate-roles"):
        sid = "test-awx-galaxy"
        ae.drop_session(sid)
        ae.get_state(sid, slug)
        ae.apply_action(sid, "login", {})
        return sid

    def _pin_webserver(self, sid):
        """Apply the documented fix: pin the missing role under roles:."""
        req = ae._load(sid)["state"]["projects"][0]["requirements"]
        fixed = req.replace(
            "roles:\n", "roles:\n  - name: fixitlab.webserver\n    version: 2.0.1\n"
        )
        self.assertIn("fixitlab.webserver", fixed)
        return ae.apply_action(sid, "edit_requirements", {"project_id": 1, "content": fixed})

    def test_requirements_parses_roles_collections_and_pins(self):
        parsed = ae._parse_requirements(ae._REQUIREMENTS_YML)
        self.assertEqual(
            {e["name"]: e["version"] for e in parsed["roles"]},
            {"fixitlab.baseline": "1.4.2", "fixitlab.webserver": "2.0.1"},
        )
        self.assertEqual(
            {e["name"]: e["version"] for e in parsed["collections"]},
            {"ansible.posix": "1.5.4", "community.general": "8.6.0"},
        )

    def test_unpinned_entry_is_flagged_by_the_audit(self):
        sid = self._login("")
        ae.apply_action(sid, "edit_requirements",
                        {"project_id": 1, "content": ae._UNPINNED_REQUIREMENTS_YML})
        res = ae.apply_action(sid, "audit_requirements", {})
        self.assertFalse(res["pinned"])
        self.assertIn("fixitlab.webserver", [f["name"] for f in res["unpinned"]])

    def test_pinned_requirements_pass_the_audit(self):
        sid = self._login("")
        res = ae.apply_action(sid, "audit_requirements", {})
        self.assertTrue(res["pinned"], res["unpinned"])

    def test_playbook_using_uninstalled_role_fails_to_resolve(self):
        sid = self._login()
        res = ae.apply_action(sid, "launch_template", {"template_id": 13})
        self.assertTrue(res["will_fail"])
        self.assertIn("fixitlab.webserver", res["failure_reason"])
        self.assertIn("was not found", res["failure_reason"])

    def test_editing_requirements_without_syncing_installs_nothing(self):
        # The whole point of the artifact: saving the manifest is not installing.
        sid = self._login()
        self._pin_webserver(sid)
        self.assertNotIn("fixitlab.webserver", ae._load(sid)["state"]["installed_roles"])
        res = ae.apply_action(sid, "launch_template", {"template_id": 13})
        self.assertTrue(res["will_fail"])
        ok, msg = ae.validate_awx_lab(sid)
        self.assertFalse(ok, msg)

    def test_pin_then_sync_installs_and_lab_becomes_solvable(self):
        sid = self._login()
        ok, _ = ae.validate_awx_lab(sid)
        self.assertFalse(ok)

        self._pin_webserver(sid)
        sync = ae.apply_action(sid, "sync_project", {"project_id": 1})
        self.assertIn("fixitlab.webserver", sync["installed_roles"])

        res = ae.apply_action(sid, "launch_template", {"template_id": 13})
        self.assertFalse(res["will_fail"], res["failure_reason"])
        ok, msg = ae.validate_awx_lab(sid)
        self.assertTrue(ok, msg)

    def test_syncing_the_wrong_project_does_not_clear_the_role_blocker(self):
        # Fail-closed: only installing the role actually resolves the objective.
        sid = self._login()
        self._pin_webserver(sid)
        ae.apply_action(sid, "sync_project", {"project_id": 2})
        ok, msg = ae.validate_awx_lab(sid)
        self.assertFalse(ok, msg)
        self.assertIn("fixitlab.webserver", msg)

    def test_role_from_installed_collection_resolves(self):
        state = ae._base_state()
        self.assertEqual(ae._resolve_role(state, "community.general.myrole"), "")
        self.assertIn("was not found", ae._resolve_role(state, "nope.absent.role"))


class AwxCheckModeIdempotencyTests(TestCase):
    """Run outcomes come from the convergence ledger, not decorative strings."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _login(self, slug="launch-job"):
        sid = "test-awx-idempotency"
        ae.drop_session(sid)
        ae.get_state(sid, slug)
        ae.apply_action(sid, "login", {})
        return sid

    def test_second_identical_apply_reports_zero_changes(self):
        sid = self._login()
        first = ae.apply_action(sid, "launch_template", {"template_id": 11})
        self.assertGreater(first["changed_count"], 0)
        self.assertFalse(first["idempotent"])

        second = ae.apply_action(sid, "launch_template", {"template_id": 11})
        self.assertEqual(second["changed_count"], 0)
        self.assertTrue(second["idempotent"])

    def test_recap_counts_come_from_the_ledger_not_a_fixed_string(self):
        sid = self._login()
        ae.apply_action(sid, "launch_template", {"template_id": 11})
        ae.apply_action(sid, "launch_template", {"template_id": 11})
        recap = _plain(ae._load(sid)["state"]["jobs"][0]["stdout_plan"])
        self.assertIn("changed=0", recap)
        self.assertIn("idempotent: no changes on this run", recap)

    def test_check_mode_converges_nothing_and_is_repeatable(self):
        sid = self._login()
        first = ae.apply_action(sid, "launch_template",
                                {"template_id": 11, "check_mode": True})
        self.assertGreater(first["changed_count"], 0)
        # A dry run must not converge the ledger, so it reports the SAME diff.
        second = ae.apply_action(sid, "launch_template",
                                 {"template_id": 11, "check_mode": True})
        self.assertEqual(second["changed_count"], first["changed_count"])
        self.assertEqual(ae._load(sid)["state"]["converged"], {})

    def test_check_mode_shows_a_diff_and_says_nothing_changed(self):
        sid = self._login()
        ae.apply_action(sid, "launch_template", {"template_id": 11, "check_mode": True})
        out = _plain(ae._load(sid)["state"]["jobs"][0]["stdout_plan"])
        self.assertIn("--- before:", out)
        self.assertIn("+++ after:", out)
        self.assertIn("check mode: no changes were actually made", out)

    def test_check_mode_never_satisfies_grading(self):
        # A dry run must not be a free pass — this is the fail-OPEN guard.
        sid = self._login()
        for _ in range(3):
            ae.apply_action(sid, "launch_template", {"template_id": 11, "check_mode": True})
        ok, msg = ae.validate_awx_lab(sid, "launch-job")
        self.assertFalse(ok, msg)

        ae.apply_action(sid, "launch_template", {"template_id": 11})
        ok, msg = ae.validate_awx_lab(sid, "launch-job")
        self.assertTrue(ok, msg)

    def test_check_mode_does_not_publish_downstream(self):
        # A dry run must not reveal the service on the Linux guest.
        sid = self._login()
        calls = []
        original = ae._bridge_ansible_result
        ae._bridge_ansible_result = lambda *a, **k: calls.append(a)
        try:
            ae.apply_action(sid, "launch_template",
                            {"template_id": 11, "check_mode": True})
            self.assertEqual(calls, [])
            ae.apply_action(sid, "launch_template", {"template_id": 11})
            self.assertEqual(len(calls), 1)
        finally:
            ae._bridge_ansible_result = original

    def test_editing_the_playbook_makes_the_run_changed_again(self):
        # A genuinely different desired state must not look already-converged.
        sid = self._login()
        ae.apply_action(sid, "launch_template", {"template_id": 11})
        self.assertEqual(
            ae.apply_action(sid, "launch_template", {"template_id": 11})["changed_count"], 0)

        text = ae._load(sid)["state"]["playbooks"]["deploy.yml"]
        ae.apply_action(sid, "edit_playbook", {
            "playbook": "deploy.yml",
            "content": text + "    - name: Open the app firewall port\n"
                              "      ansible.builtin.lineinfile:\n"
                              "        path: /etc/firewalld/app.xml\n"
                              "        line: 8080\n",
        })
        after = ae.apply_action(sid, "launch_template", {"template_id": 11})
        self.assertGreater(after["changed_count"], 0)

    def test_failed_run_converges_nothing(self):
        # A play that cannot resolve must leave the fleet exactly as it was.
        sid = self._login("broken-play")
        res = ae.apply_action(sid, "launch_template", {"template_id": 11})
        self.assertTrue(res["will_fail"])
        self.assertEqual(ae._load(sid)["state"]["converged"], {})

    def test_gpu_fleet_recap_is_ledger_derived(self):
        sid = "test-awx-gpu-idempotency"
        ae.drop_session(sid)
        ae.get_state(sid, "ai-infra-awx-nvidia-driver-rollout")
        ae.apply_action(sid, "login", {})
        first = ae.apply_action(sid, "launch_template", {"template_id": 12})
        self.assertGreater(first["changed_count"], 0)
        second = ae.apply_action(sid, "launch_template", {"template_id": 12})
        self.assertEqual(second["changed_count"], 0)
        recap = _plain(ae._load(sid)["state"]["jobs"][0]["stdout_plan"])
        for node in ("gpu-node-01", "gpu-node-02", "gpu-node-03"):
            self.assertIn(f"{node} : ok=", recap)
        self.assertIn("changed=0", recap)
