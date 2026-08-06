"""Log messages must not leak PII, and must stay readable.

JSONFormatter masked ONLY record.fields / record.structured — i.e. only extra={}
passed through the StructuredLogger wrapper, which is used in 4 files while plain
logging.getLogger() is used in 84. So every f-string email went to stdout in
cleartext: OTP and password-reset addresses, billing and webhook recipients, and
worst of all accounts/views.py and account_lifecycle.py logging `email=` at the
moment of account DELETION, defeating the erasure the user just asked for.

The second half of this test file matters as much as the first. Over-redaction is
its own failure mode: a log line you cannot read hides the incident entirely. An
earlier version of the token rule turned
`scenario=academy-linux-001-learn-users-groups` into `<redacted-token>`, which
would have gutted lab logging across the platform.
"""
import json
import logging

from django.test import SimpleTestCase

from common.logging_utils import JSONFormatter, _redact_message


def _fmt(msg, *args):
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=None,
    )
    return json.loads(JSONFormatter().format(record))["message"]


class RedactsPiiTests(SimpleTestCase):
    def test_email_is_masked(self):
        out = _redact_message("OTP sent to alice.smith@example.com")
        self.assertNotIn("alice.smith@example.com", out)
        self.assertIn("@example.com", out, "domain should survive for debugging")

    def test_email_masked_at_account_deletion(self):
        """The worst instance: logging the address while erasing the account."""
        out = _redact_message("Account deleted email=victim@example.com id=42")
        self.assertNotIn("victim@example.com", out)
        self.assertIn("id=42", out)

    def test_password_assignment_is_redacted(self):
        for raw in (
            "password=Sup3rS3cretValue123",
            'secret: "AbCdEf123456789012345"',
            "api_key = kXj2mNp8qRt5vWy1zAb4",
            "REFRESH=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
        ):
            with self.subTest(raw=raw):
                self.assertNotIn("<redacted", _redact_message("x"))  # sanity
                self.assertIn("redacted", _redact_message(raw))

    def test_long_opaque_tokens_are_redacted(self):
        for tok in (
            "rzp_live_AbCdEf1234567890",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdef",
            "a3f5b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f",
        ):
            with self.subTest(tok=tok):
                self.assertIn("<redacted-token>", _redact_message(tok))

    def test_redaction_applies_through_the_formatter(self):
        """Not just the helper — the actual formatter path must redact."""
        self.assertNotIn(
            "leak@example.com", _fmt("sending to %s", "leak@example.com")
        )


class KeepsLogsReadableTests(SimpleTestCase):
    """Over-redaction hides incidents. These are the false positives to avoid."""

    def test_scenario_slugs_survive(self):
        msg = "validating scenario=academy-linux-001-learn-users-groups"
        self.assertEqual(_redact_message(msg), msg)

    def test_dotted_module_paths_survive(self):
        msg = "error in apps.labs.provisioner.simulation.rhel_shell"
        self.assertEqual(_redact_message(msg), msg)

    def test_settings_names_survive(self):
        msg = "celery_worker_max_tasks_per_child=200"
        self.assertEqual(_redact_message(msg), msg)

    def test_urls_and_status_codes_survive(self):
        msg = "GET /api/labs/start/ -> 503 at capacity"
        self.assertEqual(_redact_message(msg), msg)

    def test_service_errors_survive(self):
        msg = "nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address in use)"
        self.assertEqual(_redact_message(msg), msg)

    def test_short_identifiers_survive(self):
        msg = "session_id=3f2a-11ee user_id=42 score=100"
        self.assertEqual(_redact_message(msg), msg)


class NeverBreaksLoggingTests(SimpleTestCase):
    """A dropped log line is worse than an unredacted one — it hides the event."""

    def test_empty_and_none_are_safe(self):
        self.assertEqual(_redact_message(""), "")
        self.assertIsNone(_redact_message(None))

    def test_weird_input_does_not_raise(self):
        for msg in ("%", "{unclosed", "\\x00\\x01", "a" * 5000):
            with self.subTest(msg=msg[:12]):
                _redact_message(msg)  # must not raise
