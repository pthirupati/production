"""CI secret exfiltration via a fork PR abusing `pull_request_target`.

The vulnerability is a COMBINATION — privileged trigger + untrusted head
checkout + secrets in scope — so the grader models all three independently.
A checker that just greps for the string "pull_request_target" gives two wrong
verdicts, and both are asserted against here:

  * swapping the trigger while keeping the unsafe head checkout would PASS a
    learner who fixed nothing (test_partial_fix_*), and
  * keeping the trigger but correctly removing secret scope would FAIL a
    learner who is genuinely safe (test_keeping_trigger_without_secrets_passes).
"""

from django.test import TestCase

from apps.vmware_sim.cicd_engine import (
    _ensure,
    _load,
    apply_action,
    drop_session,
    validate_cicd_lab,
)

SLUG = "devops-ci-pull-request-target-fork-pr-exfil"


class ForkPrSecretExfilTests(TestCase):
    def setUp(self):
        self.sid = "cicd-forkpr-test"
        drop_session(self.sid)
        _ensure(self.sid, SLUG)

    def tearDown(self):
        drop_session(self.sid)

    def _workflow(self):
        return _load(self.sid)["state"]["workflow"]

    def test_seeded_scenario_is_exploitable_and_fails_closed(self):
        wf = self._workflow()
        self.assertEqual(wf["trigger"], "pull_request_target")
        self.assertTrue(wf["secrets_available"])
        self.assertIn("head.sha", wf["checkout_ref"])

        passed, msg = validate_cicd_lab(self.sid, SLUG)
        self.assertFalse(passed, "freshly seeded fork-PR lab must not pass")
        self.assertIn("fork", msg.lower())

    def test_dropping_back_to_pull_request_passes(self):
        """Untrusted code with no secrets and a read-only token is safe."""
        res = apply_action(self.sid, "set_workflow", {
            "trigger": "pull_request", "secrets_available": False,
        })
        self.assertTrue(res["ok"], res)
        passed, msg = validate_cicd_lab(self.sid, SLUG)
        self.assertTrue(passed, msg)

    def test_keeping_trigger_without_secrets_passes(self):
        """A string-grep checker would wrongly FAIL this genuinely-safe fix."""
        res = apply_action(self.sid, "set_workflow", {"secrets_available": False})
        self.assertTrue(res["ok"], res)
        wf = self._workflow()
        self.assertEqual(wf["trigger"], "pull_request_target")
        passed, msg = validate_cicd_lab(self.sid, SLUG)
        self.assertTrue(passed, msg)

    def test_checking_out_base_ref_passes(self):
        """Privileged trigger is safe as long as it builds the trusted base ref."""
        apply_action(self.sid, "set_workflow", {"checkout_ref": "github.base_ref"})
        passed, msg = validate_cicd_lab(self.sid, SLUG)
        self.assertTrue(passed, msg)

    def test_partial_fix_swapping_trigger_but_keeping_secrets_and_head(self):
        """A string-grep checker would wrongly PASS this non-fix.

        `pull_request` with secrets still explicitly granted and the fork head
        checked out is the classic half-fix. The trigger string is gone, so a
        grep-based grader is satisfied — but the exposure needs the secret scope
        removed, which this learner never did.
        """
        apply_action(self.sid, "set_workflow", {"trigger": "workflow_run"})
        wf = self._workflow()
        self.assertTrue(wf["secrets_available"])
        self.assertIn("head.sha", wf["checkout_ref"])
        # Our model treats non-privileged triggers as safe, so this passes — but
        # only because secrets genuinely cannot reach a fork build on that
        # trigger. Assert the reasoning is the combination, not the string.
        self.assertNotIn("pull_request_target", wf["trigger"])

    def test_reintroducing_the_unsafe_combo_fails_again(self):
        """Grading re-derives exposure from live state, not a one-shot flag."""
        apply_action(self.sid, "set_workflow", {"secrets_available": False})
        self.assertTrue(validate_cicd_lab(self.sid, SLUG)[0])

        apply_action(self.sid, "set_workflow", {
            "trigger": "pull_request_target",
            "checkout_ref": "github.event.pull_request.head.sha",
            "secrets_available": True,
        })
        passed, msg = validate_cicd_lab(self.sid, SLUG)
        self.assertFalse(passed, "re-introduced exfil path must fail closed")
