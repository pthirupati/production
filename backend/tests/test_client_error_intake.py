"""Audit Z6-6 — a white screen in production had no way of reaching anyone.

`ErrorBoundary.jsx` and `SimErrorBoundary.jsx` caught React crashes and wrote them
to `console.error`. Nothing read that console, so "did that deploy break checkout?"
could only be answered by waiting for a support email.

`@sentry/react` is the obvious fix and would give source maps and replay this does
not. It also puts a browser-side third-party processor in the path of user data,
which needs a DPDP consent decision and a privacy-policy change — an owner call.
`SENTRY_DSN` is already wired server-side and already env-gated, so posting to our
own origin reaches the same dashboard with no new vendor and no new dependency.

The endpoint is public and unauthenticated, so the tests below are mostly about
what it refuses to do:

* it never trusts a `user_id` from the payload — otherwise anyone could file
  crashes against someone else's account;
* it stores the **route**, not the full URL. Query strings on this platform carry
  password-reset and payment tokens, and a crash report is not a place for either;
* everything is length-capped, because an unauthenticated endpoint that logs its
  input is otherwise a way to write arbitrary volume into the log pipeline — and
  on a metered Sentry plan, to burn the error budget so real crashes are dropped.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.client_errors import MAX_FIELD_CHARS, MAX_MESSAGE_CHARS
from common.testing import real_throttling

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/client-errors/"

    def _post(self, **payload):
        body = {"message": "Cannot read properties of undefined"}
        body.update(payload)
        resp = self.client.post(self.url, body, format="json")
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test must fail on a wrong URL rather "
            "than pass silently",
        )
        return resp


class ItAcceptsReportsTests(_Base):
    def test_an_anonymous_report_is_accepted(self):
        """Most crashes happen before or without a login."""
        self.assertEqual(self._post().status_code, 204)

    def test_the_error_reaches_the_log_pipeline(self):
        with self.assertLogs("fixitlab.client", level="ERROR") as captured:
            self._post(message="Boom in checkout")
        self.assertTrue(any("Boom in checkout" in line for line in captured.output))

    def test_the_structured_context_is_attached(self):
        """A message alone is not diagnosable — the route and kind are what make a
        report actionable."""
        import logging

        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("fixitlab.client")
        handler = _Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

        self._post(route="/checkout", kind="sim_error:aws", stack="at foo()")
        ctx = records[0].client_error
        self.assertEqual(ctx["route"], "/checkout")
        self.assertEqual(ctx["kind"], "sim_error:aws")
        self.assertEqual(ctx["stack"], "at foo()")

    def test_an_authenticated_report_records_the_user(self):
        user = User.objects.create_user(
            username="crash", email="crash@example.com", password="Str0ng-Pass-1"
        )
        self.client.force_authenticate(user=user)
        import logging

        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("fixitlab.client")
        handler = _Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

        self._post()
        self.assertEqual(records[0].client_error["user_id"], user.id)


class ItRefusesToBeAbusedTests(_Base):
    def test_a_payload_user_id_is_ignored(self):
        """Otherwise any anonymous caller can file crashes against someone else."""
        import logging

        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("fixitlab.client")
        handler = _Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

        self._post(user_id=99999)
        self.assertIsNone(
            records[0].client_error["user_id"],
            "the endpoint trusted a user id supplied by the caller",
        )

    def test_an_oversized_message_is_truncated_not_rejected(self):
        """Truncating keeps the report; rejecting loses the crash entirely."""
        import logging

        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("fixitlab.client")
        handler = _Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

        resp = self._post(message="x" * 50_000, stack="y" * 50_000)
        self.assertEqual(resp.status_code, 204)
        ctx = records[0].client_error
        self.assertLessEqual(len(ctx["message"]), MAX_MESSAGE_CHARS)
        self.assertLessEqual(len(ctx["stack"]), MAX_FIELD_CHARS)

    def test_an_empty_message_is_accepted_but_not_logged(self):
        """Nothing actionable; a 4xx would only teach the client to retry."""
        with self.assertNoLogs("fixitlab.client", level="ERROR"):
            resp = self._post(message="")
        self.assertEqual(resp.status_code, 204)

    def test_a_non_dict_payload_does_not_crash_the_endpoint(self):
        resp = self.client.post(self.url, ["not", "a", "dict"], format="json")
        self.assertIn(resp.status_code, (204, 400))

    def test_a_burst_from_one_source_is_throttled(self):
        """A render loop can fire hundreds of times a second. Unthrottled, one tab
        floods the log pipeline — and on a metered plan, drops real crashes."""
        with real_throttling(client_error="3/hour"):
            codes = [self._post(message=f"crash {i}").status_code for i in range(6)]
        self.assertIn(429, codes, f"the intake accepted 6 rapid reports ({codes})")

    def test_the_scope_is_registered_in_both_settings_modules(self):
        """`test_settings` REPLACES DEFAULT_THROTTLE_RATES, so a scope added only to
        `config/settings.py` raises ImproperlyConfigured at request time."""
        import pathlib

        from django.conf import settings as dj_settings

        root = pathlib.Path(dj_settings.BASE_DIR) / "config"
        for name in ("settings.py", "test_settings.py"):
            self.assertIn(
                '"client_error":', (root / name).read_text(),
                f"the client_error throttle scope is missing from {name}",
            )

    def test_the_production_rate_is_not_tight_enough_to_hide_an_incident(self):
        """The opposite failure: one broken deploy legitimately produces a burst from
        many browsers, and a tight per-IP cap would silence exactly the signal this
        endpoint exists to capture. Read from source — test_settings mutates the same
        REST_FRAMEWORK dict, so the imported value is the test one.
        """
        import pathlib
        import re

        from django.conf import settings as dj_settings

        src = (pathlib.Path(dj_settings.BASE_DIR) / "config" / "settings.py").read_text()
        m = re.search(r'"client_error":\s*"(\d+)/(\w+)"', src)
        self.assertIsNotNone(m, "no client_error rate in config/settings.py")
        self.assertGreaterEqual(
            int(m.group(1)), 20,
            "the client-error rate is tight enough to drop reports during an incident",
        )
