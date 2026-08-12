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


class PeopleSoftMigrationLifecycleTests(TestCase):
    """App Designer / Change Assistant DEV -> TEST -> PROD change packages."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "promote-change-package") -> str:
        sid = f"test-ps-mig-{slug}"
        ps.drop_session(sid)
        ps.get_state(sid, slug)
        ps.apply_action(sid, "login", {"oprid": "PS"})
        return sid

    def _env(self, sid: str, name: str) -> dict:
        envs = ps.get_state(sid)["migration"]["environments"]
        return next(e for e in envs if e["name"] == name)

    # ── the existing flat world shape must be preserved ────────────────────
    def test_migration_does_not_disturb_the_legacy_world_shape(self):
        # The ~150 existing PeopleSoft labs grade against the flat world; adding
        # environments must not move portal/security/process/integration.
        sid = self._session("rerun-process")
        world = ps.get_state(sid)["inventory"]
        for key in ("portal", "process", "security", "integration", "self_service"):
            self.assertIn(key, world)
        self.assertTrue(world["portal"]["modules"])
        self.assertTrue(world["security"]["roles"])
        # and migration is a sibling, not a wrapper
        self.assertIn("migration", world)
        self.assertIn("environments", world["migration"])

    def test_base_environments_start_consistent(self):
        sid = self._session("rerun-process")
        names = [e["name"] for e in ps.get_state(sid)["migration"]["environments"]]
        self.assertEqual(names, ["DEV", "TEST", "PROD"])
        for name in names:
            self.assertEqual(self._env(sid, name)["objects"]["PSU_EXPENSE_AE"]["version"], 2)

    # ── DEV build -> compare -> package ────────────────────────────────────
    def test_compare_report_flags_upgrade_and_customisation(self):
        sid = self._session("promote-change-package")
        res = ps.apply_action(sid, "compare_report",
                              {"source": "DEV", "target": "TEST"})
        self.assertTrue(res["ok"], res)
        rows = {r["object"]: r for r in res["report"]["rows"]}
        # DEV shipped v3 of the expense AE; TEST is still on v2 -> upgrade
        self.assertEqual(rows["PSU_EXPENSE_AE"]["action"], "upgrade")
        # TEST customised the job data page -> conflict
        self.assertEqual(rows["PSU_JOB_DATA_PAGE"]["action"], "customisation")
        self.assertIn("PSU_JOB_DATA_PAGE", res["report"]["conflicts"])
        # untouched object compares equal
        self.assertEqual(rows["PSU_VOUCHER_REC"]["action"], "same")

    def test_project_rejects_objects_absent_from_source(self):
        sid = self._session("promote-change-package")
        res = ps.apply_action(sid, "create_project",
                              {"project": "P1", "objects": ["NO_SUCH_OBJECT"]})
        self.assertFalse(res["ok"])
        self.assertIn("NO_SUCH_OBJECT", res["error"])

    def test_package_payload_is_frozen_at_cut_time(self):
        # Editing DEV after cutting a package must not change the package.
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        ps.apply_action(sid, "edit_object",
                        {"environment": "DEV", "object": "PSU_EXPENSE_AE"})
        self.assertEqual(self._env(sid, "DEV")["objects"]["PSU_EXPENSE_AE"]["version"], 4)
        pkgs = {p["id"]: p for p in ps.get_state(sid)["migration"]["packages"]}
        self.assertEqual(pkgs[pkg_id]["payload"]["PSU_EXPENSE_AE"]["version"], 3)

    # ── promotion path enforcement ─────────────────────────────────────────
    def test_cannot_skip_test_and_apply_straight_to_prod(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        res = ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "PROD"})
        self.assertFalse(res["ok"])
        self.assertIn("TEST", res["error"])
        # PROD untouched
        self.assertEqual(self._env(sid, "PROD")["objects"]["PSU_EXPENSE_AE"]["version"], 2)

    def test_apply_refuses_to_clobber_a_site_customisation(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1",
                         "objects": ["PSU_EXPENSE_AE", "PSU_JOB_DATA_PAGE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        res = ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "TEST"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["conflicts"], ["PSU_JOB_DATA_PAGE"])
        # nothing was applied — the expense fix did not sneak through
        self.assertEqual(self._env(sid, "TEST")["objects"]["PSU_EXPENSE_AE"]["version"], 2)

    def test_keep_customisation_drops_the_object_and_unblocks_the_apply(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1",
                         "objects": ["PSU_EXPENSE_AE", "PSU_JOB_DATA_PAGE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        res = ps.apply_action(sid, "resolve_conflict",
                              {"environment": "TEST", "object": "PSU_JOB_DATA_PAGE",
                               "resolution": "keep_customisation", "package": pkg_id})
        self.assertTrue(res["ok"], res)
        applied = ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "TEST"})
        self.assertTrue(applied["ok"], applied)
        test_env = self._env(sid, "TEST")
        # the fix landed, the local customisation (v4) survived
        self.assertEqual(test_env["objects"]["PSU_EXPENSE_AE"]["version"], 3)
        self.assertEqual(test_env["objects"]["PSU_JOB_DATA_PAGE"]["version"], 4)

    def test_accept_vendor_lets_the_package_overwrite_the_customisation(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1",
                         "objects": ["PSU_EXPENSE_AE", "PSU_JOB_DATA_PAGE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        ps.apply_action(sid, "resolve_conflict",
                        {"environment": "TEST", "object": "PSU_JOB_DATA_PAGE",
                         "resolution": "accept_vendor"})
        applied = ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "TEST"})
        self.assertTrue(applied["ok"], applied)
        # TEST's local v4 was replaced by DEV's v3
        self.assertEqual(self._env(sid, "TEST")["objects"]["PSU_JOB_DATA_PAGE"]["version"], 3)

    # ── promotion copies by value, never by reference ──────────────────────
    def test_applying_to_test_does_not_mutate_prod(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "TEST"})
        self.assertEqual(self._env(sid, "TEST")["objects"]["PSU_EXPENSE_AE"]["version"], 3)
        # PROD must still be on the old version
        self.assertEqual(self._env(sid, "PROD")["objects"]["PSU_EXPENSE_AE"]["version"], 2)

    def test_promotion_copies_objects_by_value_not_reference(self):
        # The aliasing trap the audit flagged: if promotion stored the package's
        # object dict itself, TEST and PROD would end up sharing one dict and a
        # TEST edit would silently corrupt PROD. Driven through _dispatch on a
        # live world because apply_action's cache round-trip goes through JSON,
        # which would launder the shared reference away and hide the bug.
        world = ps._base_world()
        state = {"world": world}
        ps._apply_preset(state, "promote-change-package")
        ps._dispatch(world, state, "create_project",
                     {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps._dispatch(world, state, "create_package",
                              {"project": "P1"})["package_id"]
        for env_name in ("TEST", "PROD"):
            res = ps._dispatch(world, state, "apply_package",
                               {"package": pkg_id, "target": env_name})
            self.assertTrue(res["ok"], res)

        pkg = ps._find_package(world, pkg_id)
        test_obj = ps._find_env(world, "TEST")["objects"]["PSU_EXPENSE_AE"]
        prod_obj = ps._find_env(world, "PROD")["objects"]["PSU_EXPENSE_AE"]
        payload_obj = pkg["payload"]["PSU_EXPENSE_AE"]
        # every environment (and the package payload) owns a distinct dict
        self.assertIsNot(test_obj, prod_obj)
        self.assertIsNot(test_obj, payload_obj)
        self.assertIsNot(prod_obj, payload_obj)

        # and the behavioural consequence: editing TEST leaves PROD alone
        ps._dispatch(world, state, "edit_object",
                     {"environment": "TEST", "object": "PSU_EXPENSE_AE"})
        self.assertEqual(ps._find_env(world, "TEST")["objects"]["PSU_EXPENSE_AE"]["version"], 4)
        self.assertEqual(ps._find_env(world, "PROD")["objects"]["PSU_EXPENSE_AE"]["version"], 3)

    def test_rollback_after_prod_promotion_leaves_prod_clean(self):
        # Rollback must restore PROD's own pre-apply snapshot, not a dict still
        # shared with TEST or the package payload.
        world = ps._base_world()
        state = {"world": world}
        ps._apply_preset(state, "promote-change-package")
        ps._dispatch(world, state, "create_project",
                     {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps._dispatch(world, state, "create_package", {"project": "P1"})["package_id"]
        ps._dispatch(world, state, "apply_package", {"package": pkg_id, "target": "TEST"})
        ps._dispatch(world, state, "apply_package", {"package": pkg_id, "target": "PROD"})
        ps._dispatch(world, state, "rollback_package",
                     {"package": pkg_id, "environment": "PROD"})
        # PROD back to the pre-patch version; TEST keeps the fix
        self.assertEqual(ps._find_env(world, "PROD")["objects"]["PSU_EXPENSE_AE"]["version"], 2)
        self.assertEqual(ps._find_env(world, "TEST")["objects"]["PSU_EXPENSE_AE"]["version"], 3)

    # ── rollback ───────────────────────────────────────────────────────────
    def test_rollback_restores_the_exact_pre_apply_definition(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "TEST"})
        res = ps.apply_action(sid, "rollback_package",
                              {"package": pkg_id, "environment": "TEST"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._env(sid, "TEST")["objects"]["PSU_EXPENSE_AE"]["version"], 2)

    def test_rollback_of_an_unapplied_package_is_refused(self):
        sid = self._session("promote-change-package")
        ps.apply_action(sid, "create_project",
                        {"project": "P1", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps.apply_action(sid, "create_package", {"project": "P1"})["package_id"]
        res = ps.apply_action(sid, "rollback_package",
                              {"package": pkg_id, "environment": "PROD"})
        self.assertFalse(res["ok"])

    # ── grading: fresh session fails, intended remediation passes ──────────
    def test_promote_preset_fails_fresh_and_passes_after_full_promotion(self):
        sid = self._session("promote-change-package")
        ok, _ = ps.validate_peoplesoft_lab(sid, "promote-change-package")
        self.assertFalse(ok, "promotion lab should start broken")
        ps.apply_action(sid, "create_project",
                        {"project": "PSU_EXPENSE_FIX", "objects": ["PSU_EXPENSE_AE"]})
        pkg_id = ps.apply_action(sid, "create_package",
                                 {"project": "PSU_EXPENSE_FIX"})["package_id"]
        ps.apply_action(sid, "compare_report", {"source": "DEV", "target": "TEST"})
        ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "TEST"})
        # still not done — PROD has not received it
        ok, _ = ps.validate_peoplesoft_lab(sid, "promote-change-package")
        self.assertFalse(ok, "should not pass until PROD is promoted")
        ps.apply_action(sid, "apply_package", {"package": pkg_id, "target": "PROD"})
        ok, msg = ps.validate_peoplesoft_lab(sid, "promote-change-package")
        self.assertTrue(ok, msg)

    def test_rollback_preset_fails_fresh_and_passes_after_rollback(self):
        sid = self._session("bad-patch-rollback")
        ok, _ = ps.validate_peoplesoft_lab(sid, "bad-patch-rollback")
        self.assertFalse(ok, "rollback lab should start broken")
        self.assertEqual(self._env(sid, "PROD")["objects"]["PSU_VOUCHER_REC"]["version"], 9)
        res = ps.apply_action(sid, "rollback_package",
                              {"package": "CP-014", "environment": "PROD"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._env(sid, "PROD")["objects"]["PSU_VOUCHER_REC"]["version"], 5)
        ok, msg = ps.validate_peoplesoft_lab(sid, "bad-patch-rollback")
        self.assertTrue(ok, msg)

    def test_rolling_back_the_wrong_environment_does_not_pass_the_lab(self):
        sid = self._session("bad-patch-rollback")
        ps.apply_action(sid, "rollback_package",
                        {"package": "CP-014", "environment": "TEST"})
        ok, _ = ps.validate_peoplesoft_lab(sid, "bad-patch-rollback")
        self.assertFalse(ok, "rolling back TEST must not satisfy the PROD goal")

    # ── preset routing ─────────────────────────────────────────────────────
    def test_slug_routing_prefers_rollback_over_promote(self):
        # The preset dispatcher matches substrings, so a slug containing both
        # "change-package" and "back-out" must land on the rollback lab.
        cases = {
            "ps-promote-change-package": "package_promoted",
            "ps-change-assistant-migration": "package_promoted",
            "ps-bad-patch-rollback": "package_rolled_back",
            "ps-back-out-change-package": "package_rolled_back",
        }
        for slug, kind in cases.items():
            with self.subTest(slug=slug):
                state = {"world": ps._base_world()}
                ps._apply_preset(state, slug)
                self.assertEqual(state["goal"]["kind"], kind)

    # ── malformed input never raises ───────────────────────────────────────
    def test_migration_actions_are_safe_on_bad_input(self):
        sid = self._session("promote-change-package")
        for act, payload in [
            ("create_project", {}),
            ("create_package", {"project": "nope"}),
            ("apply_package", {"package": "nope", "target": "PROD"}),
            ("compare_report", {"source": "DEV"}),
            ("resolve_conflict", {"environment": "TEST", "object": "nope"}),
            ("rollback_package", {"package": "nope", "environment": "PROD"}),
            ("edit_object", {"environment": "NOPE", "object": "x"}),
        ]:
            with self.subTest(act=act):
                res = ps.apply_action(sid, act, payload)
                self.assertFalse(res["ok"], f"{act} should fail cleanly")
                self.assertIn("error", res)
