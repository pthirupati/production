"""Monitoring for the Docker-socket outage that makes coding labs ungradeable.

AUDIT L2690. The fail-closed policy (SECURITY_AUDIT S-01) is correct — when the
container sandbox is unreachable in production the grader returns needs_review
rather than executing untrusted code in the backend process. But it used to be
*silent*: a single logger.error and nothing else, so an outage on the labs
Docker engine quietly turned every coding submission into needs_review with no
operator signal.

These tests pin the monitoring, not the policy:

  * every fail-closed grade increments a counter operators can read;
  * an operational alert (common.alerting) fires on the outage;
  * the alert is rate-limited so a broken engine doesn't spam the webhook once
    per submission;
  * the sandbox probe records *why* it failed, so the alert can say more than
    "it's down";
  * monitoring is best-effort — a broken alert channel must never change the
    verdict or raise out of the grading path.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.labs import code_exec, sandbox_runner


def _python_tests():
    return [{"name": "t", "code": "assert add(2, 3) == 5", "hidden": False}]


_GOOD_SOLUTION = "def add(a, b):\n    return a + b\n"


class _NoContainer:
    """Context manager: pretend the container engine is unreachable."""

    def __enter__(self):
        self._orig = sandbox_runner.docker_runtime_available
        sandbox_runner.docker_runtime_available = lambda *a, **k: False
        return self

    def __exit__(self, *exc):
        sandbox_runner.docker_runtime_available = self._orig
        return False


@override_settings(DEBUG=False, SANDBOX_DOCKER=True)
class FailClosedGradingIsObservableTests(TestCase):
    def setUp(self):
        # Module-level counters are process-global; isolate each test.
        code_exec.reset_failclosed_grading_stats()
        sandbox_runner.reset_sandbox_health()
        self.addCleanup(code_exec.reset_failclosed_grading_stats)
        self.addCleanup(sandbox_runner.reset_sandbox_health)

    def test_failclosed_grade_increments_counter(self):
        with _NoContainer(), patch("common.alerting.send_alert"):
            self.assertEqual(code_exec.failclosed_grading_stats()["count"], 0)
            result = code_exec.grade_submission("python", _GOOD_SOLUTION, _python_tests())

        # Policy unchanged: still needs_review, still never an auto-pass.
        self.assertTrue(result.needs_review)
        self.assertFalse(result.all_passed)
        # ...and now it is *counted*.
        self.assertEqual(code_exec.failclosed_grading_stats()["count"], 1)

    def test_failclosed_grade_fires_an_operational_alert(self):
        with _NoContainer(), patch("common.alerting.send_alert") as mock_alert:
            code_exec.grade_submission("python", _GOOD_SOLUTION, _python_tests())

        self.assertEqual(mock_alert.call_count, 1)
        message = mock_alert.call_args.args[0]
        kwargs = mock_alert.call_args.kwargs
        # The alert must be actionable: severity, and the operator-facing cause.
        self.assertEqual(kwargs.get("level"), "critical")
        self.assertIn("SANDBOX_DOCKER", message)
        self.assertIn("DOCKER_SOCKET", message)

    def test_alert_is_rate_limited_but_counter_is_not(self):
        # A dead engine fails EVERY submission. The counter must track all of
        # them; the webhook must be hit once per cooldown, not once per learner.
        with _NoContainer(), patch("common.alerting.send_alert") as mock_alert:
            for _ in range(5):
                code_exec.grade_submission("python", _GOOD_SOLUTION, _python_tests())

        self.assertEqual(code_exec.failclosed_grading_stats()["count"], 5)
        self.assertEqual(mock_alert.call_count, 1)

    def test_alert_carries_probe_failure_reason(self):
        # sandbox_health is what makes the alert diagnosable rather than "down".
        sandbox_runner._record_probe(False, "docker ping failed: socket refused")
        with _NoContainer(), patch("common.alerting.send_alert") as mock_alert:
            code_exec.grade_submission("python", _GOOD_SOLUTION, _python_tests())

        self.assertIn("socket refused", mock_alert.call_args.args[0])

    def test_broken_alert_channel_does_not_break_grading(self):
        # Monitoring is strictly best-effort: an exploding alerting backend must
        # still yield the safe needs_review verdict, not a 500.
        with _NoContainer(), patch(
            "common.alerting.send_alert", side_effect=RuntimeError("webhook exploded")
        ):
            result = code_exec.grade_submission("python", _GOOD_SOLUTION, _python_tests())

        self.assertTrue(result.needs_review)
        self.assertFalse(result.all_passed)
        self.assertEqual(code_exec.failclosed_grading_stats()["count"], 1)

    @override_settings(SANDBOX_DOCKER=False)
    def test_healthy_dev_path_never_alerts(self):
        # Sandbox off (dev/CI/tests): in-process grading is the accepted backend,
        # so there is no outage and no alert should ever fire.
        with patch("common.alerting.send_alert") as mock_alert:
            result = code_exec.grade_submission("python", _GOOD_SOLUTION, _python_tests())

        self.assertTrue(result.all_passed)
        mock_alert.assert_not_called()
        self.assertEqual(code_exec.failclosed_grading_stats()["count"], 0)


class SandboxHealthProbeTests(TestCase):
    def setUp(self):
        sandbox_runner.reset_sandbox_health()
        self.addCleanup(sandbox_runner.reset_sandbox_health)

    def test_health_starts_unknown(self):
        health = sandbox_runner.sandbox_health()
        self.assertIsNone(health["last_ok"])
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertIsNone(health["seconds_since_ok"])

    def test_consecutive_failures_accumulate_and_reset_on_success(self):
        sandbox_runner._record_probe(False, "ping failed: no such host")
        sandbox_runner._record_probe(False, "ping failed: no such host")
        health = sandbox_runner.sandbox_health()
        self.assertEqual(health["consecutive_failures"], 2)
        self.assertIn("no such host", health["last_error"])

        sandbox_runner._record_probe(True)
        health = sandbox_runner.sandbox_health()
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertEqual(health["last_error"], "")
        self.assertIsNotNone(health["seconds_since_ok"])

    @override_settings(SANDBOX_DOCKER=True)
    def test_failed_probe_records_reason(self):
        # An engine that raises on ping must leave a readable reason behind.
        class _Boom:
            def ping(self):
                raise OSError("connection refused")

            def close(self):
                pass

        with patch.object(sandbox_runner, "_get_client", return_value=_Boom()):
            self.assertFalse(sandbox_runner.docker_runtime_available(force=True))

        health = sandbox_runner.sandbox_health()
        self.assertFalse(health["last_ok"])
        self.assertTrue(health["enabled"])
        self.assertIn("connection refused", health["last_error"])
