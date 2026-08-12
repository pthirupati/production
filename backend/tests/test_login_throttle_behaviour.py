"""`LoginRateThrottle` makes two claims that had never been executed.

Its docstring says it (a) keys on **IP + email**, so failures against one account from
one source do not rate-limit everyone behind a shared egress IP, and (b) counts only
**failed** attempts, so a correct password never consumes quota.

Neither had ever run: `config/test_settings.py` patches
`SimpleRateThrottle.allow_request` to always return True, so every throttle in this
codebase was untestable until `common.testing.real_throttling()` was added. Both
claims are load-bearing and fail in opposite, user-visible directions:

* If (a) is wrong, one person fat-fingering their password locks out an entire
  office behind a NAT — the exact scenario the custom key exists to prevent.
* If (b) is wrong, an active user is throttled out of their own account by logging
  in successfully, which is worse than having no brute-force protection at all.

The bucket is deliberately small here so it actually trips; the real rate is
10/minute.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from common.testing import real_throttling

User = get_user_model()

PASSWORD = "Str0ng-Pass-1"


class LoginThrottleBehaviourTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password=PASSWORD
        )
        self.client = APIClient()
        self.url = "/api/auth/login/"

    def _login(self, email, password):
        resp = self.client.post(
            self.url, {"email": email, "password": password}, format="json"
        )
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test must fail on a wrong URL rather "
            "than pass silently",
        )
        return resp

    # ── claim (b): successes never consume the bucket ────────────────────────
    def test_repeated_successful_logins_are_never_throttled(self):
        """Being throttled out of your own account by signing in correctly would be
        worse than having no brute-force protection."""
        with real_throttling(login="3/minute"):
            codes = [self._login("alice@example.com", PASSWORD).status_code
                     for _ in range(8)]
        self.assertNotIn(
            429, codes,
            f"a correct password consumed throttle quota ({codes}) — active users "
            "would be locked out of their own accounts",
        )

    def test_a_success_after_failures_still_works(self):
        """Failures below the limit must not block the legitimate attempt."""
        with real_throttling(login="5/minute"):
            for _ in range(3):
                self._login("alice@example.com", "wrong-password")
            resp = self._login("alice@example.com", PASSWORD)
        self.assertNotEqual(
            resp.status_code, 429,
            "a valid login was refused after a few typos, below the limit",
        )

    # ── the protection itself ────────────────────────────────────────────────
    def test_repeated_failures_are_eventually_blocked(self):
        with real_throttling(login="3/minute"):
            codes = [self._login("alice@example.com", "wrong-password").status_code
                     for _ in range(8)]
        self.assertIn(
            429, codes,
            f"brute-force attempts were never throttled ({codes})",
        )

    # ── claim (a): the key is per (IP + email) ───────────────────────────────
    def test_failures_against_one_account_do_not_lock_out_another(self):
        """Shared egress IPs are the norm — corporate NAT, VPN, CI. Keying on IP
        alone would let one user's typos lock out their whole office."""
        with real_throttling(login="3/minute"):
            for _ in range(8):
                self._login("alice@example.com", "wrong-password")
            resp = self._login("bob@example.com", PASSWORD)
        self.assertNotEqual(
            resp.status_code, 429,
            "failures against alice throttled bob from the same IP — the throttle is "
            "keying on IP alone, not (IP + email)",
        )

    def test_an_unknown_email_does_not_throttle_a_real_account(self):
        """Otherwise anyone could lock out any address they can guess."""
        with real_throttling(login="3/minute"):
            for _ in range(8):
                self._login("nobody@example.com", "wrong-password")
            resp = self._login("alice@example.com", PASSWORD)
        self.assertNotEqual(
            resp.status_code, 429,
            "guessing at an unrelated address throttled a real account",
        )


class ThrottleHelperIsHonestTests(TestCase):
    """If the helper silently failed to restore real throttling, every test above
    would pass while asserting nothing — the failure mode this session keeps hitting."""

    def test_throttling_is_genuinely_active_inside_the_helper(self):
        from rest_framework.throttling import SimpleRateThrottle

        patched = SimpleRateThrottle.allow_request
        with real_throttling(login="1/minute"):
            self.assertIsNot(
                SimpleRateThrottle.allow_request, patched,
                "real_throttling did not restore the genuine implementation",
            )
        self.assertIs(
            SimpleRateThrottle.allow_request, patched,
            "real_throttling leaked live throttling into the rest of the suite",
        )

    def test_rates_are_restored_afterwards(self):
        from rest_framework.throttling import SimpleRateThrottle

        before = SimpleRateThrottle.THROTTLE_RATES
        with real_throttling(login="1/minute"):
            pass
        self.assertIs(SimpleRateThrottle.THROTTLE_RATES, before)
