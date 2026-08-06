"""Audit Z6-16 — hard-bounced addresses were retried forever.

There was no bounce, complaint or suppression handling of any kind. On most
platforms that is a sender-reputation problem; here it is also a **capacity**
problem, and that is the sharper edge. Transactional mail runs on a shared Gmail
allowance of roughly 500 messages a day (ADR 0005), and OTP and password reset come
out of the same pool — so every send to a dead address is one fewer message
available to somebody trying to sign in.

Built on `EmailLog`, which was already recording failures that nothing read. A
separate store would have created two sources of truth about the same address.

Three decisions carry this, and each is the difference between a suppression list
that helps and one that loses mail:

* **critical mail is never suppressed** — suppressing OTP or password reset turns a
  delivery problem into a permanent account lockout;
* **suppression expires** — mailboxes come back, and a permanent list quietly
  accumulates users who can never be contacted again;
* **it needs consecutive failures** — one timeout is a network blip, and
  suppressing on a single failure would silence real users during an outage of
  *our* own making.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import EmailLog
from apps.notifications.suppression import (
    SUPPRESSION_DURATION_DAYS,
    SUPPRESSION_FAILURE_THRESHOLD,
    SUPPRESSION_LOOKBACK_DAYS,
    is_suppressed,
    suppression_status,
)

User = get_user_model()
DEAD = "bounced@example.com"


def _log(email, status, days_ago=0):
    row = EmailLog.objects.create(
        subject="s", to_email=email, template="t", status=status
    )
    if days_ago:
        EmailLog.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
    return row


class ItSuppressesRepeatedFailuresTests(TestCase):
    def test_a_clean_address_is_not_suppressed(self):
        self.assertFalse(is_suppressed("fine@example.com", "notification"))

    def test_one_failure_is_not_enough(self):
        """A single timeout is a network blip, not a dead mailbox. Suppressing here
        would silence real users during any outage of our own."""
        _log(DEAD, "failed")
        self.assertFalse(is_suppressed(DEAD, "notification"))

    def test_two_failures_are_not_enough(self):
        for _ in range(2):
            _log(DEAD, "failed")
        self.assertFalse(is_suppressed(DEAD, "notification"))

    def test_the_threshold_of_consecutive_failures_suppresses(self):
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed")
        self.assertTrue(is_suppressed(DEAD, "notification"))

    def test_a_success_in_the_run_proves_the_address_is_alive(self):
        """Otherwise an account that failed three times a month ago stays
        suppressed despite working since."""
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed")
        _log(DEAD, "sent")
        self.assertFalse(is_suppressed(DEAD, "notification"))

    def test_matching_is_case_insensitive(self):
        """Addresses are stored as typed; suppression keyed on exact case would be
        trivially bypassed by a capital letter."""
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log("Bounced@Example.com", "failed")
        self.assertTrue(is_suppressed(DEAD, "notification"))

    def test_another_address_is_unaffected(self):
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed")
        self.assertFalse(is_suppressed("someone-else@example.com", "notification"))


class SuppressionExpiresTests(TestCase):
    def test_old_failures_stop_counting(self):
        """Mailboxes come back. A permanent list quietly accumulates users who can
        never be contacted again."""
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed", days_ago=SUPPRESSION_DURATION_DAYS + 5)
        self.assertFalse(is_suppressed(DEAD, "notification"))

    def test_failures_outside_the_lookback_window_are_ignored(self):
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed", days_ago=SUPPRESSION_LOOKBACK_DAYS + 5)
        self.assertFalse(is_suppressed(DEAD, "notification"))

    def test_the_duration_is_shorter_than_the_lookback(self):
        """Otherwise an address could expire out of suppression while its failures
        still count, and immediately re-suppress — a loop with no exit."""
        self.assertLess(SUPPRESSION_DURATION_DAYS, SUPPRESSION_LOOKBACK_DAYS)


class CriticalMailIsNeverSuppressedTests(TestCase):
    """The most important behaviour here. Suppressing OTP or password reset turns a
    delivery problem into a permanent account lockout — a user whose mailbox was
    full last week must still be able to sign in today."""

    def setUp(self):
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD + 2):
            _log(DEAD, "failed")

    def test_otp_is_sent_to_a_suppressed_address(self):
        self.assertFalse(
            is_suppressed(DEAD, "otp"),
            "OTP was suppressed — the user can no longer sign in at all",
        )

    def test_password_reset_is_sent_to_a_suppressed_address(self):
        self.assertFalse(is_suppressed(DEAD, "password_reset"))

    def test_security_mail_is_sent_to_a_suppressed_address(self):
        self.assertFalse(is_suppressed(DEAD, "security"))

    def test_but_ordinary_notifications_are_still_suppressed(self):
        """Guard the guard: exempting everything would make the list decorative."""
        self.assertTrue(is_suppressed(DEAD, "notification"))
        self.assertTrue(is_suppressed(DEAD, "marketing"))


class ItFailsOpenTests(TestCase):
    """A broken suppression check must not stop mail going out. One wrongly-sent
    email costs a message; one wrongly-suppressed can cost account access."""

    def test_a_database_error_allows_the_send(self):
        from unittest import mock

        with mock.patch(
            "apps.notifications.models.EmailLog.objects.filter",
            side_effect=RuntimeError("db gone"),
        ):
            self.assertFalse(is_suppressed(DEAD, "notification"))

    def test_an_empty_address_is_not_suppressed(self):
        self.assertFalse(is_suppressed("", "notification"))
        self.assertFalse(is_suppressed(None, "notification"))


class TheQueueConsultsItTests(TestCase):
    """A suppression list nothing reads is decoration."""

    def test_queue_user_email_skips_a_suppressed_address(self):
        from apps.notifications.email_helpers import queue_user_email

        user = User.objects.create_user(
            username="sup", email=DEAD, password="Str0ng-Pass-1"
        )
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed")

        sent = queue_user_email(
            user, subject="Weekly digest", template="emails/x.html",
            context={}, email_type="notification",
        )
        self.assertFalse(
            sent, "a suppressed address was still queued — the list is not consulted"
        )

    def test_it_still_queues_for_a_healthy_address(self):
        """Guard the guard: returning False for everyone would 'fix' suppression by
        stopping all mail.

        The send itself is patched out. `CELERY_TASK_ALWAYS_EAGER` is on in the test
        settings, so without this the task runs inline, tries to render a real
        template and actually deliver — which tests Django's mail backend, not the
        suppression decision this file is about.
        """
        from unittest import mock

        from apps.notifications.email_helpers import queue_user_email

        user = User.objects.create_user(
            username="ok", email="ok@example.com", password="Str0ng-Pass-1"
        )
        with mock.patch(
            "apps.notifications.tasks.send_notification_email.apply_async"
        ) as queued:
            result = queue_user_email(
                user, subject="Weekly digest",
                template="emails/lab_expired.html",
                context={}, email_type="notification",
            )
        self.assertTrue(result)
        self.assertTrue(
            queued.called,
            "a healthy address was not queued — suppression is over-firing",
        )


class TheStatusIsExplainableTests(TestCase):
    """"Your emails stopped arriving" is a common support question; without this the
    answer means reading the log table by hand."""

    def test_it_reports_a_clean_address(self):
        status = suppression_status("fine@example.com")
        self.assertFalse(status["suppressed"])
        self.assertEqual(status["recent_failures"], 0)

    def test_it_reports_a_suppressed_address_with_an_expiry(self):
        for _ in range(SUPPRESSION_FAILURE_THRESHOLD):
            _log(DEAD, "failed")
        status = suppression_status(DEAD)
        self.assertTrue(status["suppressed"])
        self.assertEqual(status["recent_failures"], SUPPRESSION_FAILURE_THRESHOLD)
        self.assertIsNotNone(status["expires_at"])

    def test_it_states_the_critical_mail_exemption(self):
        self.assertIn("never suppressed", suppression_status(DEAD)["note"])
