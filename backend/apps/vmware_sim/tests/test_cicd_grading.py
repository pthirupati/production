"""Fail-CLOSED grading tests for the CI/CD pipeline engine.

The audit found the CI/CD track had no server-side engine or validator, so the
pipeline could not be graded at all. These tests pin the contract the new
`cicd_engine` must uphold:

  * validate_cicd_lab FAILS on a freshly-seeded scenario (the planted fault is
    still present) — fail-closed, never auto-pass.
  * validate_cicd_lab PASSES only after the specific fix action clears the fault
    AND the derived pipeline outcome is green.
  * Each of the four planted fault kinds (bad image tag, missing needs edge,
    unapproved manual gate, failing job) is exercised before/after.
  * The engine contract (get_state / apply_action / drop_session / the
    _ensure_session alias) behaves as the dispatcher expects.

Sessions use plain string ids (no LabSession row) so the engine runs purely on
the Django cache; the DB snapshot mirror is a best-effort no-op in that case.
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import cicd_engine as ce


class CicdGradingTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    # ---- helpers ----------------------------------------------------------
    def _fresh(self, slug):
        sid = f"test-cicd-{slug}"
        ce.drop_session(sid)
        ce.get_state(sid, slug)  # seeds the scenario
        return sid

    # ---- fail-closed on a fresh scenario ----------------------------------
    def test_bad_image_fails_before_and_passes_after(self):
        sid = self._fresh("cicd-bad-image-tag")
        ok, reason = ce.validate_cicd_lab(sid, "cicd-bad-image-tag")
        self.assertFalse(ok, f"should fail before fix, got: {reason}")

        # Wrong image does not clear the fault.
        res = ce.apply_action(sid, "set_image", {"job": "build", "image": "node:99-nope"})
        self.assertTrue(res["ok"])
        ok, _ = ce.validate_cicd_lab(sid, "cicd-bad-image-tag")
        self.assertFalse(ok, "an invalid replacement tag must not pass")

        # Valid image clears it and the pipeline goes green.
        res = ce.apply_action(sid, "set_image", {"job": "build", "image": "node:20"})
        self.assertTrue(res["ok"])
        ok, reason = ce.validate_cicd_lab(sid, "cicd-bad-image-tag")
        self.assertTrue(ok, f"should pass after fix, got: {reason}")

    def test_missing_needs_edge(self):
        sid = self._fresh("cicd-missing-needs-edge")
        ok, reason = ce.validate_cicd_lab(sid, "cicd-missing-needs-edge")
        self.assertFalse(ok, f"should fail before fix, got: {reason}")

        # Restore the dependency edge deploy-prod -> unit-test.
        res = ce.apply_action(sid, "add_needs", {"job": "deploy-prod", "depends_on": "unit-test"})
        self.assertTrue(res["ok"])
        ok, reason = ce.validate_cicd_lab(sid, "cicd-missing-needs-edge")
        self.assertTrue(ok, f"should pass after adding needs edge, got: {reason}")

    def test_unapproved_gate(self):
        sid = self._fresh("cicd-approval-gate")
        ok, reason = ce.validate_cicd_lab(sid, "cicd-approval-gate")
        self.assertFalse(ok, f"should fail while gate unapproved, got: {reason}")

        res = ce.apply_action(sid, "approve_job", {"job": "deploy-prod"})
        self.assertTrue(res["ok"])
        ok, reason = ce.validate_cicd_lab(sid, "cicd-approval-gate")
        self.assertTrue(ok, f"should pass after approval, got: {reason}")

    def test_failing_job(self):
        sid = self._fresh("cicd-failing-job")
        ok, reason = ce.validate_cicd_lab(sid, "cicd-failing-job")
        self.assertFalse(ok, f"should fail while job broken, got: {reason}")

        res = ce.apply_action(sid, "fix_job", {"job": "unit-test", "script": ["npm test"]})
        self.assertTrue(res["ok"])
        ok, reason = ce.validate_cicd_lab(sid, "cicd-failing-job")
        self.assertTrue(ok, f"should pass after repairing job, got: {reason}")

    def test_default_slug_is_still_failing_closed(self):
        # An unrecognized slug falls to the default (failing-job) preset — it
        # must still plant a fault and fail closed, never auto-pass.
        sid = self._fresh("cicd-mystery-scenario")
        ok, _ = ce.validate_cicd_lab(sid, "cicd-mystery-scenario")
        self.assertFalse(ok)

    def test_no_session_fails_closed(self):
        ok, reason = ce.validate_cicd_lab("nonexistent-session", "cicd-bad-image-tag")
        self.assertFalse(ok)
        self.assertIn("session", reason.lower())

    # ---- engine contract --------------------------------------------------
    def test_get_state_shape_and_outcome(self):
        sid = self._fresh("cicd-bad-image-tag")
        state = ce.get_state(sid, "cicd-bad-image-tag")
        self.assertEqual(state["session_id"], sid)
        self.assertIn("outcome", state)
        self.assertEqual(state["outcome"]["status"], "failed")
        self.assertEqual(state["summary"]["fault_kind"], "bad_image")
        # After fix, outcome derives green.
        ce.apply_action(sid, "set_image", {"job": "build", "image": "node:20"})
        state = ce.get_state(sid, "cicd-bad-image-tag")
        self.assertEqual(state["outcome"]["status"], "success")

    def test_run_pipeline_reports_outcome(self):
        sid = self._fresh("cicd-failing-job")
        res = ce.apply_action(sid, "run_pipeline", {})
        self.assertTrue(res["ok"])
        self.assertEqual(res["outcome"]["status"], "failed")
        ce.apply_action(sid, "fix_job", {"job": "unit-test", "script": ["npm test"]})
        res = ce.apply_action(sid, "run_pipeline", {})
        self.assertEqual(res["outcome"]["status"], "success")

    def test_update_job_generic_editor_clears_fault(self):
        sid = self._fresh("cicd-approval-gate")
        res = ce.apply_action(sid, "update_job", {"job": "deploy-prod", "approved": True})
        self.assertTrue(res["ok"])
        ok, reason = ce.validate_cicd_lab(sid, "cicd-approval-gate")
        self.assertTrue(ok, reason)

    def test_ensure_session_alias_exists(self):
        # The dispatcher imports `_ensure_session` — confirm the alias is wired.
        self.assertTrue(hasattr(ce, "_ensure_session"))
        sid = "test-cicd-alias"
        ce.drop_session(sid)
        entry = ce._ensure_session(sid, "cicd-failing-job")
        self.assertEqual(entry["session_id"], sid)

    def test_drop_session_clears_state(self):
        sid = self._fresh("cicd-bad-image-tag")
        ce.drop_session(sid)
        # After drop, cache is cold and there's no DB mirror → load returns None.
        self.assertIsNone(ce._load(sid))

    def test_deploy_without_test_dependency_is_structurally_unsafe(self):
        # Even if every job is individually green, dropping the deploy->test edge
        # keeps the pipeline red (structural safety), so the DAG scenario cannot
        # be gamed by making jobs pass without restoring the dependency.
        sid = self._fresh("cicd-missing-needs-edge")
        # Point deploy at build only (skips the test stage) — still unsafe.
        res = ce.apply_action(sid, "set_needs", {"job": "deploy-prod", "needs": ["build"]})
        self.assertTrue(res["ok"])
        ok, reason = ce.validate_cicd_lab(sid, "cicd-missing-needs-edge")
        self.assertFalse(ok, f"deploy must depend on tests; got pass: {reason}")
