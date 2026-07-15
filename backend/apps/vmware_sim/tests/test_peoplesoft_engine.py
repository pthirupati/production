"""Tests for the Oracle PeopleSoft (PIA) engine — self-service wiring + grading.

Covers the Employee Self-Service (ESS) records keyed off OPRID, the self-service
submission actions that enqueue Process Scheduler runs, the wall-clock process
lifecycle (queued -> running -> success), and the preserved grading contract
(a fresh session fails; only the intended remediation passes). Wall-clock is
driven by patching ``time.time`` so tests run instantly and deterministically.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import peoplesoft_engine as ps


class PeopleSoftSelfServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "rerun-process", oprid: str = "PS") -> str:
        sid = f"test-ps-{slug}-{oprid}"
        ps.drop_session(sid)
        ps.get_state(sid, slug)
        ps.apply_action(sid, "login", {"oprid": oprid})
        return sid

    # ── self-service inventory keyed off OPRID ─────────────────────────────
    def test_self_service_records_present_and_keyed_by_oprid(self):
        sid = self._session("rerun-process", "HCMADMIN")
        state = ps.get_state(sid)
        # inventory carries the self_service block
        self.assertIn("self_service", state["inventory"])
        profiles = state["inventory"]["self_service"]["profiles"]
        self.assertIn("HCMADMIN", profiles)
        # ess_profile is the signed-in operator's record
        self.assertEqual(state["summary"]["current_oprid"], "HCMADMIN")
        self.assertIsNotNone(state["ess_profile"])
        self.assertEqual(state["ess_profile"]["oprid"], "HCMADMIN")
        self.assertEqual(state["ess_profile"]["empl_id"], profiles["HCMADMIN"]["empl_id"])
        # each ESS profile has job / paycheck / benefits sub-records
        prof = state["ess_profile"]
        for key in ("job", "paycheck", "benefits"):
            self.assertIn(key, prof)

    def test_ess_profile_follows_current_operator(self):
        sid = self._session("rerun-process", "PS")
        self.assertEqual(ps.get_state(sid)["ess_profile"]["oprid"], "PS")
        ps.apply_action(sid, "login", {"oprid": "FINUSER"})
        self.assertEqual(ps.get_state(sid)["ess_profile"]["oprid"], "FINUSER")

    # ── self-service submissions enqueue Process Scheduler runs ────────────
    def test_submit_benefits_enqueues_run_and_records_election(self):
        sid = self._session("rerun-process", "HCMADMIN")
        before = len(ps.get_state(sid)["inventory"]["process"]["runs"])
        res = ps.apply_action(sid, "submit_benefits", {"plan": "hdhp"})
        self.assertTrue(res["ok"], res)
        self.assertIn("instance", res)
        state = ps.get_state(sid)
        runs = state["inventory"]["process"]["runs"]
        self.assertEqual(len(runs), before + 1)
        top = runs[0]
        self.assertEqual(top["name"], "BEN_ENROLL")
        self.assertEqual(top["instance"], res["instance"])
        self.assertIn(top["status"], ("queued", "running"))
        # election recorded on the ESS record
        ben = state["ess_profile"]["benefits"]
        self.assertEqual(ben["event_status"], "Submitted")
        self.assertEqual(ben["submitted_plan"], "hdhp")

    def test_submit_benefits_rejects_unknown_plan(self):
        sid = self._session("rerun-process", "HCMADMIN")
        res = ps.apply_action(sid, "submit_benefits", {"plan": "no_such_plan"})
        self.assertFalse(res["ok"])

    def test_save_job_data_updates_record_and_enqueues_run(self):
        sid = self._session("rerun-process", "FINUSER")
        res = ps.apply_action(sid, "save_job_data", {"job": {"location": "Chennai"}})
        self.assertTrue(res["ok"], res)
        state = ps.get_state(sid)
        self.assertEqual(state["ess_profile"]["job"]["location"], "Chennai")
        self.assertEqual(state["inventory"]["process"]["runs"][0]["name"], "PERSONAL_DATA_SYNC")

    def test_request_paycheck_enqueues_reprint_run(self):
        sid = self._session("rerun-process", "PS")
        res = ps.apply_action(sid, "request_paycheck", {})
        self.assertTrue(res["ok"], res)
        top = ps.get_state(sid)["inventory"]["process"]["runs"][0]
        self.assertEqual(top["name"], "PAY_ADVICE_PRINT")

    def test_self_service_uses_signed_in_operator_when_oprid_omitted(self):
        sid = self._session("rerun-process", "FINUSER")
        res = ps.apply_action(sid, "submit_benefits", {})
        self.assertTrue(res["ok"], res)
        self.assertIn("FINUSER", res["message"])

    # ── wall-clock process lifecycle ───────────────────────────────────────
    def test_enqueued_run_advances_queued_running_success_on_wallclock(self):
        sid = self._session("rerun-process", "HCMADMIN")
        base = 1_000_000.0
        with mock.patch("apps.vmware_sim.peoplesoft_engine.time.time", return_value=base):
            res = ps.apply_action(sid, "submit_benefits", {"plan": "ppo"})
            inst = res["instance"]

        def status_at(t):
            with mock.patch("apps.vmware_sim.peoplesoft_engine.time.time", return_value=t):
                runs = ps.get_state(sid)["inventory"]["process"]["runs"]
                return next(r for r in runs if r["instance"] == inst)["status"]

        # just after submit: still queued
        self.assertEqual(status_at(base + 1), "queued")
        # past the running threshold
        self.assertEqual(status_at(base + ps._RUN_TO_RUNNING_S + 0.5), "running")
        # past the success threshold
        final = status_at(base + ps._RUN_TO_SUCCESS_S + 0.5)
        self.assertEqual(final, "success")
        # and it stays success (idempotent, epoch cleared)
        self.assertEqual(status_at(base + 60), "success")

    def test_lifecycle_does_not_touch_preset_error_run(self):
        # The rerun-process preset seeds instance 1009 in 'error' with no
        # enqueued_epoch; wall-clock advancement must leave it broken.
        sid = self._session("rerun-process", "PS")
        with mock.patch("apps.vmware_sim.peoplesoft_engine.time.time", return_value=9_999_999.0):
            runs = ps.get_state(sid)["inventory"]["process"]["runs"]
        run_1009 = next(r for r in runs if r["instance"] == 1009)
        self.assertEqual(run_1009["status"], "error")

    # ── grading contract preserved across all six presets ──────────────────
    def test_all_presets_fail_fresh_and_pass_after_intended_fix(self):
        cases = [
            ("rerun-process", "rerun_process", {"instance": 1009}),
            ("grant-role", "assign_role", {"user": "FINUSER", "role": "AP_PROCESSOR"}),
            ("add-permission", "add_permission",
             {"permission_list": "HCCPPRM", "permission": "HC_POSITION_DATA"}),
            ("ib-node-down", "restart_ib_node", {"node": "PSFT_HR"}),
            ("locked-account", "unlock_user", {"user": "HCMADMIN"}),
        ]
        for slug, action, payload in cases:
            with self.subTest(slug=slug):
                sid = self._session(slug, "PS")
                ok_before, _ = ps.validate_peoplesoft_lab(sid, slug)
                self.assertFalse(ok_before, f"{slug} should start broken")
                ps.apply_action(sid, action, payload)
                ok_after, msg = ps.validate_peoplesoft_lab(sid, slug)
                self.assertTrue(ok_after, f"{slug} should pass after fix: {msg}")

    def test_component_config_preset_grading(self):
        sid = self._session("component-config", "PS")
        ok_before, _ = ps.validate_peoplesoft_lab(sid, "component-config")
        self.assertFalse(ok_before)
        ps.apply_action(sid, "navigate", {"component": "position_data"})
        ps.apply_action(sid, "set_component_config",
                        {"component": "position_data",
                         "config": {"auto_create_position": "Y", "max_head_count": 1}})
        ok_after, msg = ps.validate_peoplesoft_lab(sid, "component-config")
        self.assertTrue(ok_after, msg)

    def test_self_service_submission_does_not_break_process_grading(self):
        # Enqueuing self-service runs must not satisfy the rerun goal on its own;
        # the seeded error run still needs the intended rerun.
        sid = self._session("rerun-process", "HCMADMIN")
        ps.apply_action(sid, "submit_benefits", {"plan": "ppo"})
        ps.apply_action(sid, "request_paycheck", {})
        ok, _ = ps.validate_peoplesoft_lab(sid, "rerun-process")
        self.assertFalse(ok)
        ps.apply_action(sid, "rerun_process", {"instance": 1009})
        ok, msg = ps.validate_peoplesoft_lab(sid, "rerun-process")
        self.assertTrue(ok, msg)

    # ── unknown action still safe ──────────────────────────────────────────
    def test_unknown_action_is_safe(self):
        sid = self._session("rerun-process", "PS")
        res = ps.apply_action(sid, "totally_unknown", {})
        self.assertFalse(res["ok"])
        self.assertIn("error", res)
