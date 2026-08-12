"""Audit Z6-16 remainder — retried sends duplicated the email.

`send_notification_email` retries on any exception, three times. The failure that
matters is the ambiguous one: the provider accepts the message and *then* the
connection times out, so the task raises and Celery sends the whole thing again. For
an OTP that means two codes arrive, one of them dead, with nothing telling the user
which.

What is being asserted is at-least-once with dedupe where delivery was proven — not
exactly-once, which is not on offer:

* a send the provider **confirmed** is never repeated;
* a send in the **ambiguous** window still is, because a missing OTP costs account
  access and a duplicate costs a moment of confusion;
* the unavoidable duplicate carries the original's `Message-ID` so clients collapse
  it.

The tests that matter most are the ones asserting we still retry, and that two
genuinely different messages never share a key. Both are ways this could "work" by
silently dropping real mail.
"""

from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.notifications.idempotency import (
    already_delivered,
    idempotency_key,
    mark_delivered,
    message_id_for,
)
from apps.notifications.tasks import send_notification_email

ARGS = ("Your code", "user@example.com", "emails/otp.html")


class TheKeyIdentifiesOneMessageTests(SimpleTestCase):
    def test_the_same_message_produces_the_same_key(self):
        """The whole mechanism rests on this — a retry must reproduce it."""
        self.assertEqual(
            idempotency_key(*ARGS, {"code": "123456"}),
            idempotency_key(*ARGS, {"code": "123456"}),
        )

    def test_dict_ordering_does_not_change_the_key(self):
        """Context survives a JSON round trip through the broker, and ordering is
        not guaranteed. An unstable key would make every retry look like a new
        message — the exact bug this prevents, and invisible if untested."""
        self.assertEqual(
            idempotency_key(*ARGS, {"code": "123456", "name": "A", "z": 1}),
            idempotency_key(*ARGS, {"z": 1, "name": "A", "code": "123456"}),
        )

    def test_a_different_code_is_a_different_message(self):
        """A user who asks for a second OTP must receive it. Collapsing these would
        turn dedupe into a lockout."""
        self.assertNotEqual(
            idempotency_key(*ARGS, {"code": "111111"}),
            idempotency_key(*ARGS, {"code": "222222"}),
        )

    def test_a_different_recipient_is_a_different_message(self):
        self.assertNotEqual(
            idempotency_key("Your code", "a@example.com", "emails/otp.html", {"c": 1}),
            idempotency_key("Your code", "b@example.com", "emails/otp.html", {"c": 1}),
        )

    def test_the_recipient_is_normalised(self):
        """Otherwise the same address in different case dedupes as two messages."""
        self.assertEqual(
            idempotency_key("s", " User@Example.com ", "t", {}),
            idempotency_key("s", "user@example.com", "t", {}),
        )

    def test_unserialisable_context_does_not_raise(self):
        """Context routinely carries dates and model instances. Raising here would
        break the send outright, in service of an optimisation."""
        import datetime

        self.assertTrue(
            idempotency_key(*ARGS, {"when": datetime.datetime(2026, 8, 9), "o": object()})
        )


class TheMessageIdIsDeterministicTests(SimpleTestCase):
    def test_it_derives_from_the_key(self):
        key = idempotency_key(*ARGS, {"code": "1"})
        self.assertEqual(message_id_for(key), message_id_for(key))

    def test_it_is_a_well_formed_rfc5322_identifier(self):
        """Malformed here means rejected or rewritten by the provider, which
        silently removes the de-duplication this buys."""
        mid = message_id_for(idempotency_key(*ARGS, {"code": "1"}))
        self.assertTrue(mid.startswith("<") and mid.endswith(">"))
        self.assertIn("@", mid)

    def test_different_messages_get_different_identifiers(self):
        self.assertNotEqual(
            message_id_for(idempotency_key(*ARGS, {"code": "1"})),
            message_id_for(idempotency_key(*ARGS, {"code": "2"})),
        )


class ConfirmedSendsAreNotRepeatedTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_an_unknown_message_is_not_marked_delivered(self):
        self.assertFalse(already_delivered("never-seen"))

    def test_marking_makes_it_known(self):
        mark_delivered("abc")
        self.assertTrue(already_delivered("abc"))

    def test_a_retry_after_a_confirmed_send_does_not_send_again(self):
        """The duplicate this module exists to stop."""
        with mock.patch("apps.notifications.tasks.send_email", return_value=True) as send:
            send_notification_email(*ARGS, {"code": "123456"})
            self.assertEqual(send.call_count, 1)
            send_notification_email(*ARGS, {"code": "123456"})
            self.assertEqual(
                send.call_count, 1,
                "the message was sent twice — a confirmed delivery was repeated",
            )

    def test_a_genuinely_new_message_still_sends(self):
        """Guard the guard: deduping everything would 'fix' duplicates by stopping
        mail, and a user waiting on a second OTP would never get it."""
        with mock.patch("apps.notifications.tasks.send_email", return_value=True) as send:
            send_notification_email(*ARGS, {"code": "111111"})
            send_notification_email(*ARGS, {"code": "222222"})
        self.assertEqual(send.call_count, 2)


class AmbiguousSendsAreStillRetriedTests(SimpleTestCase):
    """The deliberate half of the design. In the window where we cannot prove
    delivery, a missing OTP costs account access and a duplicate costs confusion —
    so we retry, and make the duplicate collapsible instead of preventing it."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_a_failed_send_is_not_marked_delivered(self):
        """Marking on attempt rather than on acceptance would turn a transient
        provider error into a permanently lost email."""
        with mock.patch("apps.notifications.tasks.send_email", return_value=False):
            with self.assertRaises(RuntimeError):
                send_notification_email(*ARGS, {"code": "123456"})
        self.assertFalse(already_delivered(idempotency_key(*ARGS, {"code": "123456"})))

    def test_the_next_attempt_actually_sends(self):
        with mock.patch("apps.notifications.tasks.send_email", return_value=False):
            with self.assertRaises(RuntimeError):
                send_notification_email(*ARGS, {"code": "123456"})
        with mock.patch("apps.notifications.tasks.send_email", return_value=True) as send:
            send_notification_email(*ARGS, {"code": "123456"})
        self.assertTrue(
            send.called,
            "a failed send was never retried — the email is lost for good",
        )

    def test_a_raising_send_is_not_marked_delivered(self):
        with mock.patch(
            "apps.notifications.tasks.send_email", side_effect=RuntimeError("timeout")
        ):
            with self.assertRaises(RuntimeError):
                send_notification_email(*ARGS, {"code": "123456"})
        self.assertFalse(already_delivered(idempotency_key(*ARGS, {"code": "123456"})))

    def test_the_retry_reuses_the_original_message_id(self):
        """What makes the unavoidable duplicate collapse in the client."""
        seen = []
        with mock.patch(
            "apps.notifications.tasks.send_email",
            side_effect=lambda **kw: seen.append(kw["headers"]["Message-ID"]) or False,
        ):
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    send_notification_email(*ARGS, {"code": "123456"})
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])


class ItDoesNotBreakExistingCallersTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_a_caller_supplied_message_id_wins(self):
        """Threading headers (`In-Reply-To`/`References`) depend on the caller's own
        identifier; overwriting it would break conversation grouping."""
        with mock.patch("apps.notifications.tasks.send_email", return_value=True) as send:
            send_notification_email(*ARGS, {"c": 1}, headers={"Message-ID": "<mine@x>"})
        self.assertEqual(send.call_args.kwargs["headers"]["Message-ID"], "<mine@x>")

    def test_other_headers_are_preserved(self):
        with mock.patch("apps.notifications.tasks.send_email", return_value=True) as send:
            send_notification_email(*ARGS, {"c": 1}, headers={"List-Unsubscribe": "<u>"})
        self.assertEqual(send.call_args.kwargs["headers"]["List-Unsubscribe"], "<u>")

    def test_no_headers_at_all_still_works(self):
        with mock.patch("apps.notifications.tasks.send_email", return_value=True) as send:
            send_notification_email(*ARGS, {"c": 1})
        self.assertIn("Message-ID", send.call_args.kwargs["headers"])

    def test_the_callers_header_dict_is_not_mutated(self):
        """A shared or reused dict picking up a stale Message-ID would attach one
        message's identifier to a different message — dedupe that deletes real mail."""
        headers = {"List-Unsubscribe": "<u>"}
        with mock.patch("apps.notifications.tasks.send_email", return_value=True):
            send_notification_email(*ARGS, {"c": 1}, headers=headers)
        self.assertNotIn("Message-ID", headers)


class TheHeaderSurvivesTheMailStackTests(SimpleTestCase):
    """`Message-ID` is not an ordinary custom header — Django generates one of its
    own, and `email.message.Message.__setitem__` *appends* rather than replaces. Two
    Message-ID headers on one message is malformed, and the de-duplication this
    buys would quietly stop working."""

    def test_django_emits_exactly_one_message_id(self):
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            "s", "b", "f@x.com", ["t@x.com"],
            headers={"Message-ID": "<abc@fixitlab.in>"},
        ).message()
        self.assertEqual(msg.get_all("Message-ID"), ["<abc@fixitlab.in>"])

    def test_it_does_not_leak_the_sending_hostname(self):
        """Django's generated identifier ends in the machine's hostname, which then
        ships in the headers of every outbound email. Ours ends in the public
        domain, so supplying it also closes that disclosure."""
        import socket

        from django.core.mail import EmailMultiAlternatives

        key = idempotency_key(*ARGS, {"code": "1"})
        msg = EmailMultiAlternatives(
            "s", "b", "f@x.com", ["t@x.com"],
            headers={"Message-ID": message_id_for(key)},
        ).message()
        self.assertNotIn(socket.gethostname(), msg["Message-ID"])
        self.assertIn("@fixitlab.in", msg["Message-ID"])


class ItFailsOpenTests(SimpleTestCase):
    """A broken cache must not stop mail. One duplicate costs a message; one wrongly
    suppressed send can cost account access."""

    def test_a_cache_error_on_lookup_allows_the_send(self):
        with mock.patch(
            "apps.notifications.idempotency.cache.get", side_effect=RuntimeError("down")
        ):
            self.assertFalse(already_delivered("k"))

    def test_a_cache_error_on_write_does_not_fail_the_task(self):
        with mock.patch(
            "apps.notifications.idempotency.cache.set", side_effect=RuntimeError("down")
        ), mock.patch("apps.notifications.tasks.send_email", return_value=True):
            self.assertTrue(send_notification_email(*ARGS, {"c": 1}))
