"""Guided-step failures must say WHY, without handing over the answer.

Audit L2335. ValidateGuidedStepView returned three fixed strings — "Apply the
documented fix, then verify this step again.", "Run the fix command in the
terminal, then verify again.", and "Command failed (exit N). Check output and
retry." — none of which named the failing step or what the check was looking
for. A stuck learner got no signal to act on.

The spoiler boundary is the other half of the requirement: the message may only
echo fields the guided panel already shows the learner (``title``,
``expected_output``). It must never carry ``solution``, ``validation_script``, or
hidden test source, and it must not swallow raw validator output — that stays in
its own response field so it reads as check output, not platform guidance.
"""
from django.test import SimpleTestCase

from apps.public_api.views import _step_failure_message


class GuidedStepFailureMessageTests(SimpleTestCase):
    STEP = {
        "step": 2,
        "title": "Restart the nginx service",
        "instruction": "Run systemctl restart nginx.",
        "expected_output": "nginx is active (running)",
        "explanation": "The unit was left stopped by the broken preset.",
    }

    def test_names_the_failing_step(self):
        msg = _step_failure_message(self.STEP)
        self.assertIn("Restart the nginx service", msg)

    def test_states_what_the_check_still_wants(self):
        msg = _step_failure_message(self.STEP)
        self.assertIn("nginx is active (running)", msg)

    def test_includes_exit_code_when_a_command_failed(self):
        msg = _step_failure_message(self.STEP, output="bash: nope", exit_code=127)
        self.assertIn("127", msg)

    def test_is_not_the_old_generic_string(self):
        # The three strings this change replaced. Any of them reappearing means
        # a call site was reverted to a hardcoded message.
        msg = _step_failure_message(self.STEP)
        self.assertNotEqual(msg, "Apply the documented fix, then verify this step again.")
        self.assertNotEqual(msg, "Run the fix command in the terminal, then verify again.")

    def test_degrades_to_actionable_text_for_a_bare_step(self):
        # Not every seeded scenario sets title/expected_output.
        msg = _step_failure_message({})
        self.assertIn("did not pass", msg)
        self.assertIn("verify this step again", msg)

    def test_never_leaks_solution_or_validation_script(self):
        # Even if a malformed scenario stuffs the answer into the step dict, the
        # message is built from an allowlist of two fields — not from the dict.
        poisoned = dict(
            self.STEP,
            solution="systemctl restart nginx && systemctl enable nginx",
            validation_script="test $(systemctl is-active nginx) = active",
            hidden_tests=["assert nginx_running()"],
            answer="the answer",
        )
        msg = _step_failure_message(poisoned, output="checked 1 unit")
        for secret in ("systemctl enable", "is-active", "nginx_running", "the answer"):
            self.assertNotIn(secret, msg)

    def test_does_not_swallow_validator_output_into_the_message(self):
        # Previously `output or <generic>` made raw validator text the entire
        # message, so a validator echoing the expected value became the answer.
        msg = _step_failure_message(self.STEP, output="EXPECTED: listen 8443;")
        self.assertNotIn("listen 8443", msg)
        # ...but the learner is told where to look for it.
        self.assertIn("output", msg.lower())

    def test_clips_a_runaway_expected_output(self):
        msg = _step_failure_message({"expected_output": "x" * 5000})
        self.assertLess(len(msg), 500)
