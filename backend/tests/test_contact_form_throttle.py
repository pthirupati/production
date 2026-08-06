"""The public contact form must not be a remote way to take login out.

Audit Z2-6. `ContactView` is `AllowAny` and, per POST, writes a `ContactMessage` row
**and** queues mail to `SUPPORT_EMAIL` — calling `send_notification_email.delay`
directly, so it bypasses the daily-quota gate in `queue_user_email`. With no throttle
at all, a loop is not merely spam: it burns the shared ~500/day Gmail allowance
*including the reserve held back for OTP and password reset*, which is the Z6-3 auth
outage reachable by anyone with curl.

`strict_anon` (240/minute) would have been the obvious throttle and is far too loose
for something that sends email — one IP could queue 14,400 messages an hour. The
`contact` scope is deliberately tiny: nobody legitimately files six support requests
in an hour, and someone who needs to can reply to the first one.

The scope is registered in **both** settings modules. `config/test_settings.py`
REPLACES `DEFAULT_THROTTLE_RATES` wholesale, so a scope added only to
`config/settings.py` raises `ImproperlyConfigured` at request time — every contact
POST would 500 in tests while looking correct in production.
"""
import pathlib

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import ContactMessage
from common.testing import real_throttling

# `config/test_settings.py` patches `SimpleRateThrottle.allow_request` to always
# return True so the suite is never rate-limited. That made throttling a project-wide
# blind spot — a throttle could be deleted, misscoped, or lose its rate with every
# test still green. The patch now preserves the original, and `real_throttling()`
# restores it for a block, so the behaviour below is genuinely exercised rather than
# merely inspected.


class ContactThrottleTests(TestCase):
    def setUp(self):
        cache.clear()  # DRF stores throttle history in the cache
        self.client = APIClient()
        self.url = "/api/contact/"

    def _submit(self, subject="Help"):
        resp = self.client.post(
            self.url,
            {
                "name": "Jane",
                "email": "jane@example.com",
                "subject": subject,
                "message": "My lab will not start.",
            },
            format="json",
        )
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test must fail on a wrong URL rather "
            "than pass silently",
        )
        return resp

    def test_a_genuine_submission_works(self):
        resp = self._submit()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_a_burst_is_actually_cut_off(self):
        """The behaviour itself, not just the wiring.

        The helper supplies a realistic limit because the test rates are deliberately
        enormous — without it nothing trips and the test passes for the wrong reason.
        `override_settings(REST_FRAMEWORK=...)` cannot do this: DRF binds
        THROTTLE_RATES as a class attribute at import time, so the override is
        ignored and the test silently keeps the 10000/minute rate.
        """
        with real_throttling(contact="3/hour"):
            codes = [self._submit(f"Help {i}").status_code for i in range(6)]
        self.assertIn(
            429, codes,
            f"the contact form accepted 6 rapid submissions ({codes}) — unthrottled "
            "it can exhaust the shared daily email quota and stop OTP delivery",
        )

    def test_throttled_requests_write_no_row_and_send_no_mail(self):
        """A 429 must stop the side effects, not merely change the status code."""
        with real_throttling(contact="3/hour"):
            for i in range(6):
                self._submit(f"Spam {i}")
        self.assertLessEqual(
            ContactMessage.objects.count(), 3,
            "throttled requests still wrote rows and queued mail",
        )

    def test_the_production_rate_is_tight_enough_to_protect_the_quota(self):
        """The number is the protection. At `strict_anon` (240/min) one IP could
        queue 14,400 emails an hour against a ~500/day allowance.

        Read from the SOURCE of config/settings.py, not the imported module:
        `test_settings` does `from .settings import *` and then MUTATES the very same
        `REST_FRAMEWORK` dict, so `config.settings.REST_FRAMEWORK` is the
        test-mutated object. Importing it here would assert the 10000/minute test
        value and silently pass however loose production became.
        """
        import re

        from django.conf import settings as dj_settings

        src = (pathlib.Path(dj_settings.BASE_DIR) / "config" / "settings.py").read_text()
        m = re.search(r'"contact":\s*"(\d+)/(\w+)"', src)
        self.assertIsNotNone(m, "no contact rate in config/settings.py")
        count, period = int(m.group(1)), m.group(2)
        self.assertEqual(period, "hour", f"contact rate is per-{period}, expected hourly")
        self.assertLessEqual(
            count, 20,
            "the contact rate is loose enough to exhaust the daily email quota",
        )

    def test_the_scope_is_registered_in_both_settings_modules(self):
        """`test_settings` REPLACES DEFAULT_THROTTLE_RATES, so a scope added only to
        `config/settings.py` raises ImproperlyConfigured at request time — every
        contact POST 500s in tests while looking correct in production.

        Both are checked from source, since the two modules share one dict object at
        runtime and cannot be told apart by import.
        """
        from django.conf import settings as dj_settings

        root = pathlib.Path(dj_settings.BASE_DIR) / "config"
        for name in ("settings.py", "test_settings.py"):
            self.assertIn(
                '"contact":', (root / name).read_text(),
                f"the contact throttle scope is missing from {name}",
            )

    def test_the_view_does_not_use_the_loose_public_scope(self):
        """strict_anon is 240/minute — 14,400 emails an hour from one IP."""
        import inspect

        from apps.accounts import views

        src = inspect.getsource(views.ContactView)
        self.assertIn("ContactRateThrottle", src)
        self.assertNotIn("StrictAnonRateThrottle", src)

    def test_the_view_is_throttled_at_all(self):
        from apps.accounts.views import ContactView

        self.assertTrue(
            ContactView.throttle_classes,
            "ContactView has no throttle — it writes a row and sends mail per POST",
        )
