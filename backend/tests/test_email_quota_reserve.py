"""A marketing blast must never starve OTP and password-reset delivery.

Audit Z6-3: marketing and transactional mail share one consumer Gmail account
(~500 recipients/day) and the same `_deliver` chain. Exhausting the quota with a
nurture campaign therefore does not merely fail to market — it stops OTP and
password reset, so nobody can sign in or recover an account until the quota resets.
An auth outage caused by a marketing campaign is the worst trade in the system.

The real fix is a separate sending identity for bulk mail (owner task). This
reserves the tail of the daily quota instead: marketing stops at `cap - reserve`
while transactional keeps sending. The asymmetry is the whole point, so the test
that matters is the one asserting transactional still goes out *after* marketing has
been cut off.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.notifications.email_helpers import marketing_send_allowed, queue_user_email
from apps.notifications.models import EmailLog, NotificationPreference

User = get_user_model()


def _log_sends(n, status="sent"):
    EmailLog.objects.bulk_create([
        EmailLog(subject="s", to_email=f"u{i}@example.com", template="t", status=status)
        for i in range(n)
    ])
    cache.delete("email:sent_today")  # the 60s cache would mask the new rows


@override_settings(EMAIL_DAILY_SEND_CAP=100, EMAIL_TRANSACTIONAL_RESERVE=30)
class QuotaGateTests(TestCase):
    def setUp(self):
        # Own the count absolutely. Clearing only the cache was not enough: the
        # budget is computed from EmailLog rows, and other tests in the suite write
        # them, so `_log_sends(69)` landed on top of an existing tally and blew the
        # 70-row budget. This passed in isolation and failed in the full run — the
        # test was wrong, not the guard.
        EmailLog.objects.all().delete()
        cache.delete("email:sent_today")

    def test_allowed_when_the_day_is_quiet(self):
        allowed, _ = marketing_send_allowed()
        self.assertTrue(allowed)

    def test_allowed_just_below_the_marketing_budget(self):
        _log_sends(69)  # budget is 100 - 30 = 70
        self.assertTrue(marketing_send_allowed()[0])

    def test_refused_once_the_marketing_budget_is_reached(self):
        _log_sends(70)
        allowed, reason = marketing_send_allowed()
        self.assertFalse(allowed)
        self.assertIn("reserved", reason)

    def test_the_reserve_is_never_consumed_by_marketing(self):
        """The defining property: between budget and cap, marketing is off."""
        _log_sends(85)  # past the 70 budget, still under the 100 cap
        self.assertFalse(marketing_send_allowed()[0])

    def test_failed_sends_do_not_count_against_the_quota(self):
        """A bounce did not consume a recipient slot."""
        _log_sends(90, status="failed")
        self.assertTrue(marketing_send_allowed()[0])

    def test_no_cap_configured_means_no_gate(self):
        """Moving to a real ESP should not leave a phantom limit in place."""
        _log_sends(5000)
        with override_settings(EMAIL_DAILY_SEND_CAP=0):
            self.assertTrue(marketing_send_allowed()[0])

    def test_the_count_survives_a_cache_flush(self):
        """Counted from EmailLog, not a cache counter — losing it to a Redis flush
        would silently restore the behaviour this guard exists to prevent."""
        _log_sends(80)
        cache.clear()
        self.assertFalse(marketing_send_allowed()[0])


@override_settings(EMAIL_DAILY_SEND_CAP=100, EMAIL_TRANSACTIONAL_RESERVE=30)
class TransactionalKeepsFlowingTests(TestCase):
    """Marketing being cut off must not touch OTP or password reset."""

    def setUp(self):
        EmailLog.objects.all().delete()   # see QuotaGateTests.setUp
        cache.delete("email:sent_today")
        self.user = User.objects.create_user(
            username="q", email="q@example.com", password="Str0ng-Pass-1"
        )
        prefs = NotificationPreference.get_for_user(self.user)
        prefs.email_marketing = True
        prefs.save(update_fields=["email_marketing"])
        _log_sends(80)  # past the marketing budget, inside the reserve

    def _queue(self, email_type):
        with mock.patch("apps.notifications.tasks.send_notification_email") as task:
            task.delay = mock.MagicMock()
            sent = queue_user_email(
                self.user, subject="s",
                template="emails/marketing_combined_subscribe.html",
                context={}, email_type=email_type,
            )
            return sent, task.delay.called

    def test_marketing_is_refused_inside_the_reserve(self):
        sent, called = self._queue("marketing")
        self.assertFalse(sent)
        self.assertFalse(called, "a marketing email was queued inside the reserve")

    def test_transactional_still_sends_inside_the_reserve(self):
        sent, called = self._queue("subscription")
        self.assertTrue(
            sent and called,
            "transactional mail was blocked by the marketing quota — this guard "
            "exists to prevent exactly that",
        )

    def test_achievement_mail_also_still_sends(self):
        sent, called = self._queue("achievements")
        self.assertTrue(sent and called)
