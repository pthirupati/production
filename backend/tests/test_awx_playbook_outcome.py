"""AWX job outcome must be DERIVED from playbook content, not preset.

Audit item L996: `_make_job` took a caller-supplied `will_fail` boolean, both
call sites hardcoded it to False, and `launch_template` popped the grading
blocker unconditionally — so launching any template passed validate_awx_lab
whether or not the playbook was ever corrected.

These tests pin the corrected contract:
  * a broken playbook produces a FAILED job whose stdout names the real defect;
  * a failed run leaves the template failed and the blocker in place, so
    grading keeps failing and relaunching without a fix does not rescue it;
  * editing the playbook to something valid makes the next launch go green and
    grading pass;
  * a failed run must not publish its intended end state downstream (the
    Linux bridge stays fail-closed).
"""
from django.core.cache import cache
from django.test import TestCase

from apps.labs.provisioner.simulation import vmware_bridge as vb
from apps.vmware_sim import awx_engine as ae


def _finish(sid, jid):
    """Fast-forward a job past its wall-clock finish line and return it."""
    entry = ae._load(sid)
    raw = next(j for j in entry["state"]["jobs"] if j["id"] == jid)
    raw["started_ts"] = ae._now() - (ae._JOB_FINISH_AT + 1)
    ae._save(sid, entry)
    return next(j for j in ae.get_state(sid)["inventory"]["jobs"] if j["id"] == jid)


class AwxPlaybookDerivedOutcomeTests(TestCase):
    """The repair-objective preset seeds deploy.yml with a misspelled module."""

    slug = "awx-fix-playbook"

    def setUp(self):
        cache.clear()
        self.sid = "test-awx-playbook-outcome"
        ae.drop_session(self.sid)
        ae.get_state(self.sid, self.slug)
        ae.apply_action(self.sid, "login", {})

    def tearDown(self):
        cache.clear()

    def test_broken_playbook_produces_failed_job_naming_the_defect(self):
        res = ae.apply_action(self.sid, "launch_template", {"template_id": 11})
        self.assertTrue(res["ok"])
        self.assertTrue(res["will_fail"], "broken playbook must not launch green")

        job = _finish(self.sid, res["job_id"])
        self.assertEqual(job["status"], "failed")
        blob = "\n".join(job.get("stdout") or [])
        # The fatal line quotes the derived reason, not a generic "task failed".
        self.assertIn("servce", blob)
        self.assertIn("couldn't resolve module/action", blob)
        self.assertNotIn("task failed", blob)

    def test_failed_run_leaves_blocker_so_grading_fails(self):
        ae.apply_action(self.sid, "launch_template", {"template_id": 11})
        ok, msg = ae.validate_awx_lab(self.sid, self.slug)
        self.assertFalse(ok, "launching a broken playbook must not pass grading")
        state = ae.get_state(self.sid)["inventory"]
        jt = next(t for t in state["job_templates"] if t["id"] == 11)
        self.assertEqual(jt["status"], "failed")
        self.assertIn("failed_template_id", state["broken"])

    def test_relaunch_without_a_fix_fails_again(self):
        first = ae.apply_action(self.sid, "launch_template", {"template_id": 11})
        again = ae.apply_action(self.sid, "relaunch_job", {"job_id": first["job_id"]})
        self.assertTrue(again["will_fail"], "retrying is not a fix")
        self.assertEqual(_finish(self.sid, again["job_id"])["status"], "failed")
        ok, _ = ae.validate_awx_lab(self.sid, self.slug)
        self.assertFalse(ok)

    def test_editing_the_playbook_turns_the_next_run_green(self):
        broken = ae.apply_action(self.sid, "launch_template", {"template_id": 11})
        self.assertTrue(broken["will_fail"])

        fixed = ae._DEPLOY_PLAYBOOK  # the same play with the module spelled right
        saved = ae.apply_action(self.sid, "edit_playbook",
                                {"playbook": "deploy.yml", "content": fixed})
        self.assertTrue(saved["ok"])
        self.assertFalse(saved["will_fail"], saved.get("failure_reason"))

        res = ae.apply_action(self.sid, "launch_template", {"template_id": 11})
        self.assertFalse(res["will_fail"])
        self.assertEqual(_finish(self.sid, res["job_id"])["status"], "successful")
        ok, msg = ae.validate_awx_lab(self.sid, self.slug)
        self.assertTrue(ok, msg)

    def test_a_still_broken_edit_does_not_rescue_grading(self):
        # Saving different-but-still-invalid text must not be a backdoor pass.
        bad = ae._DEPLOY_PLAYBOOK.replace("ansible.builtin.service:",
                                          "ansible.builtin.systemdd:")
        saved = ae.apply_action(self.sid, "edit_playbook",
                                {"playbook": "deploy.yml", "content": bad})
        self.assertTrue(saved["will_fail"])
        ae.apply_action(self.sid, "launch_template", {"template_id": 11})
        ok, _ = ae.validate_awx_lab(self.sid, self.slug)
        self.assertFalse(ok)

    def test_failed_run_does_not_publish_downstream(self):
        # A red play must leave the Linux bridge fail-closed.
        ae.apply_action(self.sid, "edit_playbook", {
            "playbook": "deploy.yml",
            "content": ae._DEPLOY_PLAYBOOK.replace("ansible.builtin.service:",
                                                   "ansible.builtin.servce:"),
        })
        ae.apply_action(self.sid, "launch_template",
                        {"template_id": 11, "service": "nginx"})
        self.assertFalse(vb.has_pending_ansible(self.sid),
                         "a failed job must not reveal the service on the guest")


class AwxPlaybookDefectKindTests(TestCase):
    """Each defect the evaluator recognises maps to a real ansible error."""

    def setUp(self):
        cache.clear()
        self.state = ae._base_state()

    def tearDown(self):
        cache.clear()

    def _reason(self, content):
        self.state["playbooks"]["probe.yml"] = content
        return ae._evaluate_playbook(self.state, "Probe", "probe.yml")

    def test_healthy_playbook_has_no_reason(self):
        self.assertEqual(self._reason(ae._PATCH_PLAYBOOK), "")

    def test_unknown_module(self):
        self.assertIn("couldn't resolve module/action",
                      self._reason(ae._PATCH_PLAYBOOK.replace(
                          "ansible.builtin.package:", "ansible.builtin.pakage:")))

    def test_undefined_variable(self):
        # The GPU play targets maas-gpu-nodes, which only the AI-Infra seed has.
        ae._seed_ai_infra_awx(self.state, "ai-infra-awx-nvidia-driver-rollout")
        reason = self._reason(ae._BROKEN_GPU_DRIVER_PLAYBOOK)
        self.assertIn("undefined", reason)
        self.assertIn("nvidia_driver_version", reason)

    def test_defined_variable_is_not_flagged(self):
        ae._seed_ai_infra_awx(self.state, "ai-infra-awx-nvidia-driver-rollout")
        self.assertEqual(self._reason(ae._GPU_DRIVER_PLAYBOOK), "")

    def test_missing_hosts_key(self):
        self.assertIn("'hosts' is required", self._reason(
            ae._PATCH_PLAYBOOK.replace("  hosts: Production\n", "")))

    def test_missing_tasks_block(self):
        self.assertIn("no tasks", self._reason("---\n- name: Empty\n  hosts: Production\n"))

    def test_unknown_host_pattern(self):
        self.assertIn("Could not match supplied host pattern", self._reason(
            ae._PATCH_PLAYBOOK.replace("hosts: Production", "hosts: Producton")))

    def test_all_targets_disabled(self):
        for h in self.state["hosts"]:
            if h["inventory"] == "Production":
                h["enabled"] = False
        self.assertIn("Could not match supplied host pattern",
                      self._reason(ae._PATCH_PLAYBOOK))

    def test_absent_playbook_text_is_fail_open(self):
        # Sessions cached before the content model (and ad-hoc templates) carry
        # no text; there is no authored defect to detect, so they run clean.
        self.assertEqual(ae._evaluate_playbook(self.state, "X", "not-seeded.yml"), "")


class AwxLaunchAndVerifyLabsStillPassTests(TestCase):
    """Regression guard: the launch-and-verify labs ship healthy playbooks, so
    deriving the outcome must not make them unpassable."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _run(self, sid, slug, tid):
        ae.drop_session(sid)
        ae.get_state(sid, slug)
        ae.apply_action(sid, "login", {})
        res = ae.apply_action(sid, "launch_template", {"template_id": tid})
        self.assertFalse(res["will_fail"], res.get("failure_reason"))
        self.assertEqual(_finish(sid, res["job_id"])["status"], "successful")
        ok, msg = ae.validate_awx_lab(sid, slug)
        self.assertTrue(ok, msg)

    def test_generic_launch_job_lab(self):
        self._run("awx-ok-generic", "awx-launch-job", 11)

    def test_ai_infra_driver_rollout_lab(self):
        self._run("awx-ok-gpu", "ai-infra-awx-nvidia-driver-rollout", 12)
