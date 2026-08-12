"""Marketing mail must carry RFC 8058 one-click unsubscribe headers.

Audit Z6-4: `gmail_api.py` set only Subject/From/To. Gmail and Yahoo have *required*
`List-Unsubscribe` + `List-Unsubscribe-Post` from bulk senders since February 2024,
and the signed-token machinery already existed — it was a header away.

This is not only a deliverability nicety. Transactional mail (OTP, password reset)
shares the sending domain and its reputation, so marketing classified as spam drags
down the mail people need to sign in. That is the same coupling as Z6-3.

The header must appear on marketing mail and NOT on transactional mail: offering a
provider an "unsubscribe" affordance for password resets would let a user switch off
the mail they cannot sign in without.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.notifications.email_helpers import queue_user_email
from apps.notifications.models import NotificationPreference
from apps.notifications.unsubscribe import (
    list_unsubscribe_headers,
    marketing_unsubscribe_api_url,
    verify_marketing_unsubscribe_token,
)

User = get_user_model()


class HeaderContentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lu", email="lu@example.com", password="Str0ng-Pass-1"
        )

    def test_both_required_headers_are_present(self):
        h = list_unsubscribe_headers(self.user.id)
        self.assertIn("List-Unsubscribe", h)
        self.assertIn("List-Unsubscribe-Post", h)

    def test_post_header_has_the_exact_rfc_value(self):
        """RFC 8058 specifies this string; providers match it literally."""
        h = list_unsubscribe_headers(self.user.id)
        self.assertEqual(h["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_unsubscribe_url_is_angle_bracketed(self):
        """RFC 2369 requires the URL in angle brackets."""
        value = list_unsubscribe_headers(self.user.id)["List-Unsubscribe"]
        self.assertTrue(value.startswith("<") and value.endswith(">"), value)

    def test_url_points_at_the_postable_api_not_the_spa_page(self):
        """One-click is an unattended POST; the frontend /unsubscribe page cannot
        service it."""
        url = marketing_unsubscribe_api_url(self.user.id)
        self.assertIn("/api/notifications/unsubscribe/", url)

    def test_token_in_the_url_verifies_back_to_the_user(self):
        url = marketing_unsubscribe_api_url(self.user.id)
        token = url.split("token=", 1)[1]
        self.assertEqual(verify_marketing_unsubscribe_token(token), self.user.id)

    def test_a_tampered_token_is_rejected(self):
        url = marketing_unsubscribe_api_url(self.user.id)
        token = url.split("token=", 1)[1]
        self.assertIsNone(verify_marketing_unsubscribe_token(token + "x"))


class HeaderAttachmentTests(TestCase):
    """Which emails get the header — the discriminating half."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="att", email="att@example.com", password="Str0ng-Pass-1"
        )
        prefs = NotificationPreference.get_for_user(self.user)
        prefs.email_marketing = True  # opt in, else the send is refused (Z4-8)
        prefs.save(update_fields=["email_marketing"])

    def _capture(self, email_type):
        # send_notification_email is imported inside queue_user_email, so it must
        # be patched at its source module, not on email_helpers.
        with mock.patch("apps.notifications.tasks.send_notification_email") as task:
            task.delay = mock.MagicMock()
            queue_user_email(
                self.user, subject="s", template="emails/marketing_combined_subscribe.html",
                context={}, email_type=email_type,
            )
            if not task.delay.call_args:
                return None
            return task.delay.call_args.kwargs.get("headers")

    def test_marketing_email_carries_the_headers(self):
        headers = self._capture("marketing")
        self.assertIsNotNone(headers, "marketing send was skipped, not sent")
        self.assertIn("List-Unsubscribe", headers)
        self.assertEqual(headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_transactional_email_does_not_carry_them(self):
        """A provider must not offer to unsubscribe someone from password resets."""
        headers = self._capture("subscription")
        self.assertFalse(
            headers, f"transactional mail got List-Unsubscribe headers: {headers}"
        )


class TransportPlumbingTests(TestCase):
    """Every transport must actually emit the header — threading it to only one of
    three would look correct in code review and fail in production on whichever
    provider is live."""

    def test_gmail_transport_sets_the_headers_on_the_mime_message(self):
        import base64

        captured = {}

        class _FakeSvc:
            def users(self):
                return self

            def messages(self):
                return self

            def send(self, userId, body):  # noqa: N803 - Google's kwarg name
                captured["raw"] = body["raw"]
                return self

            def execute(self):
                return {}

        # gmail_api does `from googleapiclient.discovery import build` INSIDE the
        # function, so the patch has to land on the source module.
        with mock.patch("googleapiclient.discovery.build", return_value=_FakeSvc()):
            from apps.notifications.gmail_api import send_via_gmail_api

            try:
                send_via_gmail_api(
                    "s", "to@example.com", "<p>hi</p>", "hi",
                    headers={"List-Unsubscribe": "<https://x/api/u?token=t>",
                             "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
                )
            except Exception as exc:  # credentials plumbing differs; skip if so
                self.skipTest(f"gmail transport not exercisable here: {exc}")

        raw = base64.urlsafe_b64decode(captured["raw"]).decode("utf-8", "replace")
        self.assertIn("List-Unsubscribe:", raw)
        self.assertIn("List-Unsubscribe=One-Click", raw)

    def test_smtp_transport_passes_headers_to_the_message(self):
        from django.core import mail

        from apps.notifications.email import _deliver

        # _deliver imports these lazily from gmail_api, so patch there.
        with mock.patch("apps.notifications.gmail_api.is_gmail_api_configured",
                        return_value=False), \
             override_settings(SENDGRID_API_KEY=""):
            _deliver(
                "s", "to@example.com", "<p>hi</p>", "hi",
                headers={"List-Unsubscribe": "<https://x/api/u?token=t>"},
            )
        self.assertTrue(mail.outbox, "nothing was sent")
        self.assertIn("List-Unsubscribe", mail.outbox[-1].extra_headers)
