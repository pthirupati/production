"""Password reset must not answer "does this person have an account?".

Audit Z2-5. `ForgotPasswordView` is `AllowAny` and returned **404 "No active account
found with this email address"** for unknown emails and 200 for known ones — a clean
oracle anyone could query with curl.

This reverses a decision the code documented as deliberate ("give the user clear
feedback when no account matches"). That trade is genuinely arguable for a generic
SaaS. It is not arguable here: FixitLab sells interview practice, so confirming an
account exists reveals that a named individual is preparing for interviews. A
colleague or a current employer can run that check, and the answer can cost someone
their job. The usual enumeration argument is about credential-stuffing; the leak here
is the fact of membership itself.

Three paths had to be unified, not one:

* unknown / inactive email  → was 404 with a precise error
* mail dispatch failure     → was 502 "Your account was found, but ..."  (only a real
                              account can reach that line, so the *error* confirmed
                              membership just as loudly as the 404 did)
* success                   → 200

The tests below compare status **and body** across those paths, because equal status
codes with different messages leak exactly the same fact.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetToken

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="known", email="known@example.com", password="Str0ng-Pass-1"
        )
        self.inactive = User.objects.create_user(
            username="gone", email="gone@example.com", password="Str0ng-Pass-1",
            is_active=False,
        )
        self.client = APIClient()
        self.url = "/api/auth/forgot-password/"

    def _ask(self, email):
        resp = self.client.post(self.url, {"email": email}, format="json")
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test must fail on a wrong URL rather "
            "than pass silently. (A real 404 from the view would also be the bug "
            "under test, so this assertion is checked before any comparison.)",
        )
        return resp


class TheResponseIsIndistinguishableTests(_Base):
    def test_an_unknown_email_gets_the_same_status_as_a_known_one(self):
        self.assertEqual(
            self._ask("nobody@example.com").status_code,
            self._ask("known@example.com").status_code,
            "the status code reveals whether the account exists",
        )

    def test_an_unknown_email_gets_the_same_body_as_a_known_one(self):
        self.assertEqual(
            self._ask("nobody@example.com").data,
            self._ask("known@example.com").data,
            "the response body reveals whether the account exists",
        )

    def test_an_inactive_account_is_indistinguishable_from_an_active_one(self):
        """Deactivated users are still members; 'no such account' would be a lie
        that happens to be an accurate signal."""
        self.assertEqual(
            self._ask("gone@example.com").data,
            self._ask("known@example.com").data,
            "a deactivated account is distinguishable from an active one",
        )

    def test_no_response_says_the_account_was_not_found(self):
        body = str(self._ask("nobody@example.com").data).lower()
        for leak in ("no active account", "not found", "sign up for an account"):
            self.assertNotIn(leak, body, f"the response still says {leak!r}")

    def test_no_response_says_the_account_was_found(self):
        """The old 502 read 'Your account was found, but ...' — a confirmation
        dressed as an error."""
        self.assertNotIn("account was found", str(self._ask("known@example.com").data).lower())

    def test_the_copy_still_helps_someone_who_mistyped(self):
        """Anti-enumeration should cost wording, not usability."""
        body = str(self._ask("nobody@example.com").data).lower()
        self.assertIn("if an account exists", body)
        self.assertIn("check the address", body)


class TheMailFailurePathDoesNotLeakTests(_Base):
    """Reachable only for a real account, so its response must match the rest."""

    def _ask_with_broken_mail(self, email):
        with mock.patch(
            "apps.accounts.views.dispatch_notification_email",
            side_effect=RuntimeError("smtp down"),
        ):
            return self._ask(email)

    def test_a_send_failure_looks_like_every_other_outcome(self):
        broken = self._ask_with_broken_mail("known@example.com")
        baseline = self._ask("nobody@example.com")
        self.assertEqual(broken.status_code, baseline.status_code)
        self.assertEqual(
            broken.data, baseline.data,
            "a mail failure for a real account is distinguishable from an unknown "
            "address — the oracle survives in the error path",
        )

    def test_a_send_failure_is_still_recorded_for_ops(self):
        """Silence towards the caller must not mean silence in the logs."""
        from apps.accounts import views

        with self.assertLogs(views.logger, level="ERROR") as captured:
            self._ask_with_broken_mail("known@example.com")
        self.assertTrue(
            any("password reset email failed" in line.lower() for line in captured.output),
            "a failed reset send left no trace for operators",
        )


class TheFeatureStillWorksTests(_Base):
    """A generic response that also stopped sending resets would 'fix' the leak by
    breaking the feature."""

    def test_a_real_request_still_issues_a_token(self):
        self._ask("known@example.com")
        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user, used=False).exists(),
            "no reset token was issued — password reset is broken",
        )

    def test_a_real_request_still_sends_mail(self):
        with mock.patch("apps.accounts.views.dispatch_notification_email") as send:
            self._ask("known@example.com")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs["to_email"], "known@example.com")

    def test_an_unknown_email_sends_nothing(self):
        """Otherwise the endpoint becomes a way to mail arbitrary addresses."""
        with mock.patch("apps.accounts.views.dispatch_notification_email") as send:
            self._ask("nobody@example.com")
        self.assertEqual(send.call_count, 0)

    def test_an_inactive_account_gets_no_token(self):
        self._ask("gone@example.com")
        self.assertFalse(
            PasswordResetToken.objects.filter(user=self.inactive).exists(),
            "a deactivated account was issued a working reset token",
        )

    def test_requesting_again_invalidates_the_earlier_token(self):
        self._ask("known@example.com")
        self._ask("known@example.com")
        self.assertEqual(
            PasswordResetToken.objects.filter(user=self.user, used=False).count(), 1,
            "an older reset link stayed live alongside the new one",
        )

    def test_a_malformed_email_is_still_rejected(self):
        """Validation errors are fine — they say nothing about who has an account."""
        resp = self.client.post(self.url, {"email": "not-an-email"}, format="json")
        self.assertEqual(resp.status_code, 400)
