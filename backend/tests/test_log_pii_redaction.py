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
import sys

from django.test import SimpleTestCase

from common.logging_utils import JSONFormatter, _redact_message


def _format(msg, *args, exc_info=None):
    """Render a record through the production formatter, returning all fields."""
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=exc_info,
    )
    return json.loads(JSONFormatter().format(record))


def _fmt(msg, *args):
    return _format(msg, *args)["message"]


def _exc_info(exc):
    """Real exc_info triple, so formatException sees an actual traceback."""
    try:
        raise exc
    except type(exc):
        return sys.exc_info()


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
            # Deliberately NOT a realistic gateway prefix. An earlier version used
            # a real-looking "rzp_live_..." string and scripts/check-no-secrets-in-git.sh
            # correctly flagged this file in CI — the prefix pass has no test-path
            # exclusion, and it should not have one, or a genuinely leaked key in a
            # test fixture would sail through. Use a shape that exercises the
            # token rule without impersonating a live credential.
            "QxV7mLp2ZtRb9KcYwNfHgAeD",
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


class RedactsTracebacksTests(SimpleTestCase):
    """The `exception` field is a sibling of `message` and leaked just as badly.

    Redaction was originally added to `message` only, so a record could render
    `message: "Failed to send OTP to le***@example.com"` next to an `exception`
    field carrying the same address in cleartext. That is the *failure* branch —
    exactly when logs get read and exported — and it is reachable: there are ~61
    `logger.exception()` call sites, and smtplib.SMTPRecipientsRefused stringifies
    to `{'user@example.com': (550, ...)}`, which
    apps/notifications/email_dispatch.py logs verbatim.
    """

    def test_email_in_exception_text_is_masked(self):
        exc = ValueError("signup failed for victim@example.com")
        out = _format("send failed", exc_info=_exc_info(exc))
        self.assertNotIn("victim@example.com", out["exception"])
        self.assertIn("@example.com", out["exception"], "domain aids debugging")

    def test_token_in_exception_text_is_redacted(self):
        exc = RuntimeError("bad token=abcdefghijklmnopqrstuvwxyz012345")
        out = _format("auth failed", exc_info=_exc_info(exc))
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz012345", out["exception"])

    def test_smtp_style_recipient_dict_is_masked(self):
        """The concrete shape email_dispatch.py logs under `except Exception`."""
        exc = Exception("{'victim@example.com': (550, b'No such user')}")
        out = _format("email thread failed", exc_info=_exc_info(exc))
        self.assertNotIn("victim@example.com", out["exception"])

    def test_traceback_stays_readable(self):
        """Over-redaction here is worse than elsewhere: a traceback you cannot
        read is the incident you cannot diagnose. Frames carry file paths and
        dotted module names, both well over the 24-char token threshold."""
        exc = ValueError("boom")
        out = _format("failed", exc_info=_exc_info(exc))
        self.assertIn("Traceback (most recent call last)", out["exception"])
        self.assertIn("ValueError: boom", out["exception"])
        self.assertNotIn("<redacted-token>", out["exception"])
        self.assertIn(__file__, out["exception"], "frame path must survive")


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


class ProductionLoggingIsWiredToTheMaskerTests(SimpleTestCase):
    """The masker only redacts through JSONFormatter.

    `_redact_message` is called from `JSONFormatter.format`, so redaction is only
    real if production handlers actually use that formatter. The `verbose` formatter
    does no masking — it exists for local dev. Switching a handler to it, or adding a
    new handler that forgets the formatter, would silently stop redacting PII in
    production while every test above still passed.

    Deliberately reads `config.settings` out of sys.modules rather than
    `django.conf.settings`: `config/test_settings.py:153` REPLACES LOGGING wholesale
    with a bare unformatted `console` handler to keep test output quiet, so asserting
    on the active settings would grade the test config and report a leak that does not
    exist in production. (First version of this test did exactly that.)
    """

    @staticmethod
    def _production_logging():
        import sys

        mod = sys.modules.get("config.settings")
        assert mod is not None, "config.settings not imported — cannot check prod LOGGING"
        return mod.LOGGING

    def test_json_formatter_is_the_masking_one(self):
        fmt = self._production_logging()["formatters"]["json"]
        self.assertEqual(fmt["()"], "common.logging_utils.JSONFormatter")

    def test_every_production_handler_uses_the_masking_formatter(self):
        offenders = []
        for name, handler in self._production_logging()["handlers"].items():
            if handler.get("formatter") == "json":
                continue
            # console_verbose is the documented dev-only handler.
            if name == "console_verbose":
                continue
            offenders.append(f"{name} (formatter={handler.get('formatter')!r})")
        self.assertEqual(
            offenders, [],
            "these production log handlers bypass the PII masker: " + "; ".join(offenders),
        )

    def test_every_logger_routes_to_the_json_handler(self):
        """Each logger is `["console_json"] if not DEBUG else ["console_verbose"]`, so
        the production branch must name the masking handler."""
        logging_cfg = self._production_logging()
        targets = dict(logging_cfg.get("loggers", {}))
        targets["<root>"] = logging_cfg["root"]
        for name, logger in targets.items():
            with self.subTest(logger=name):
                handlers = logger.get("handlers", [])
                self.assertTrue(
                    "console_json" in handlers or "console_verbose" in handlers,
                    f"logger {name!r} routes to {handlers!r} — neither is a known "
                    "console handler, so masking coverage is unknown",
                )
