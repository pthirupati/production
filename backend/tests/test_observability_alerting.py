"""Observability wiring tests (PRODUCTION_AUDIT OBS-01 / OBS-02 / REL-01).

Verifies the additive, env-gated observability features are TRUE no-ops on the
default deploy (no SENTRY_DSN / ALERT_WEBHOOK_URL / ALERT_EMAIL):

  * common.alerting.send_alert performs NO network/email I/O and returns False
    when no channel is configured; when a webhook IS configured it POSTs once.
  * Sentry is NOT initialised when SENTRY_DSN is empty (the test settings case).
  * The Sentry before_send hook scrubs auth cookies / tokens / passwords.
  * The business-signal monitor task runs without raising and fires no alert
    when all signals are within thresholds (and the alerting util is a no-op).
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from common import alerting


class AlertingNoOpTests(TestCase):
    """common.alerting is a safe no-op when no channel is configured."""

    @override_settings(ALERT_WEBHOOK_URL="", ALERT_EMAIL="")
    def test_disabled_when_no_channel(self):
        self.assertFalse(alerting.alerting_enabled())

    @override_settings(ALERT_WEBHOOK_URL="", ALERT_EMAIL="")
    def test_send_alert_is_noop_without_channel(self):
        # No webhook POST and no email send may happen; returns False.
        with patch("common.alerting._urlrequest.urlopen") as mock_open, patch(
            "django.core.mail.send_mail"
        ) as mock_mail:
            result = alerting.send_alert("payment failures spiked", level="warning")
        self.assertFalse(result)
        mock_open.assert_not_called()
        mock_mail.assert_not_called()

    @override_settings(ALERT_WEBHOOK_URL="https://hooks.example.com/abc", ALERT_EMAIL="")
    def test_send_alert_posts_to_webhook_when_configured(self):
        fake_resp = MagicMock()
        fake_resp.status = 200
        fake_resp.__enter__.return_value = fake_resp
        fake_resp.__exit__.return_value = False
        with patch("common.alerting._urlrequest.urlopen", return_value=fake_resp) as mock_open:
            result = alerting.send_alert("deep celery queue", level="critical", title="T")
        self.assertTrue(result)
        self.assertEqual(mock_open.call_count, 1)
        # The request carries a JSON body with the message text.
        sent_request = mock_open.call_args.args[0]
        body = sent_request.data.decode("utf-8")
        self.assertIn("deep celery queue", body)

    @override_settings(ALERT_WEBHOOK_URL="https://hooks.example.com/abc", ALERT_EMAIL="")
    def test_send_alert_never_raises_on_webhook_failure(self):
        with patch(
            "common.alerting._urlrequest.urlopen", side_effect=OSError("boom")
        ):
            # Must swallow the transport error and report not-delivered.
            self.assertFalse(alerting.send_alert("x"))


class SentryGatingTests(TestCase):
    """Sentry is gated on SENTRY_DSN and scrubs PII."""

    def test_sentry_not_initialised_when_dsn_empty(self):
        # The test settings run with SENTRY_DSN="" → the init block is skipped,
        # so no Sentry client is active.
        from django.conf import settings

        self.assertEqual(settings.SENTRY_DSN, "")
        import sentry_sdk

        client = sentry_sdk.get_client()
        self.assertFalse(client.is_active())

    def test_before_send_scrubs_secrets(self):
        from config.settings import _sentry_before_send

        event = {
            "request": {
                "cookies": {"access_token": "leak"},
                "headers": {"Authorization": "Bearer leak", "X-Trace": "keep"},
                "data": {"password": "leak", "email": "a@b.c"},
            },
            "extra": {"token": "leak", "note": "keep"},
        }
        out = _sentry_before_send(event, {})
        self.assertNotIn("cookies", out["request"])
        self.assertEqual(out["request"]["headers"]["Authorization"], "[redacted]")
        self.assertEqual(out["request"]["headers"]["X-Trace"], "keep")
        self.assertEqual(out["request"]["data"]["password"], "[redacted]")
        self.assertEqual(out["request"]["data"]["email"], "a@b.c")
        self.assertEqual(out["extra"]["token"], "[redacted]")
        self.assertEqual(out["extra"]["note"], "keep")


class BusinessSignalMonitorTests(TestCase):
    """The monitor beat task runs cleanly and is alert-no-op by default."""

    @override_settings(ALERT_WEBHOOK_URL="", ALERT_EMAIL="")
    def test_monitor_never_performs_alert_io_without_channel(self):
        from celery_app.tasks_monitoring import check_business_signals

        # Even if probes produce findings (e.g. no backup heartbeat exists in
        # the test env), with no channel configured send_alert must perform NO
        # network/email I/O — the default-deploy no-op contract.
        with patch("common.alerting._urlrequest.urlopen") as mock_open, patch(
            "django.core.mail.send_mail"
        ) as mock_mail:
            result = check_business_signals()
        mock_open.assert_not_called()
        mock_mail.assert_not_called()
        self.assertIsInstance(result, str)

    @override_settings(ALERT_WEBHOOK_URL="", ALERT_EMAIL="")
    def test_monitor_within_thresholds_when_all_probes_quiet(self):
        # Patch the data sources each probe reads so all four report "quiet".
        # read_last_backup_epoch is patched to a fresh timestamp so the
        # dead-man's-switch sees a recent backup.
        import time

        from celery_app import tasks_monitoring

        with patch("apps.billing.models.PaymentTransaction.objects") as pt, patch(
            "apps.audit.models.AuditLog.objects"
        ) as al, patch(
            "common.backup_heartbeat.read_last_backup_epoch", return_value=int(time.time())
        ), patch.object(
            tasks_monitoring, "_check_celery_queue_depth", return_value=[]
        ):
            pt.filter.return_value.count.return_value = 0
            al.filter.return_value.count.return_value = 0
            result = tasks_monitoring.check_business_signals()
        self.assertIn("within thresholds", result)

    @override_settings(ALERT_WEBHOOK_URL="", ALERT_EMAIL="")
    def test_monitor_swallows_probe_errors(self):
        from celery_app import tasks_monitoring

        # A probe raising must be caught — the task returns a string, never raises.
        with patch(
            "apps.billing.models.PaymentTransaction.objects",
            side_effect=RuntimeError("db down"),
        ):
            result = tasks_monitoring.check_business_signals()
        self.assertIsInstance(result, str)
