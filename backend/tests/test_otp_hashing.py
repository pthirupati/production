"""Email-verification OTPs must not be readable from storage.

Audit Z4-11: the six-digit code was stored in plaintext for its whole lifetime, and
`EmailVerificationOTPAdmin` listed `code` in `readonly_fields` — so any staff user
could open the admin, read a live code for any email address, and complete that
account's verification inside the validity window. A database dump had the same
effect. The code is only ever compared, never replayed, so nothing needed it
recoverable.

Hashing a six-digit number does not stop a determined offline attacker (there are
only a million candidates). What it stops is the casual path that actually existed
here: reading it off a screen or out of a dump. Combined with the 5-attempt cap and
the short expiry, that is the meaningful part.
"""
from django.contrib.auth.hashers import identify_hasher
from django.test import TestCase

from apps.accounts.models import EmailVerificationOTP


class OTPStorageTests(TestCase):
    def setUp(self):
        self.instance, self.code, self.token = EmailVerificationOTP.generate(
            "hash@example.com"
        )

    def test_generate_returns_a_six_digit_code(self):
        self.assertRegex(self.code, r"^\d{6}$")

    def test_the_stored_value_is_not_the_code(self):
        self.instance.refresh_from_db()
        self.assertNotEqual(self.instance.code_hash, self.code)
        self.assertNotIn(self.code, self.instance.code_hash)

    def test_the_stored_value_is_a_recognised_hash(self):
        self.instance.refresh_from_db()
        identify_hasher(self.instance.code_hash)  # raises if it is not a real hash

    def test_the_plaintext_column_is_gone(self):
        """Migration 0013 drops `code` rather than renaming it, so plaintext cannot
        survive under a new name."""
        fields = {f.name for f in EmailVerificationOTP._meta.get_fields()}
        self.assertNotIn("code", fields)
        self.assertIn("code_hash", fields)


class OTPVerificationTests(TestCase):
    def setUp(self):
        self.instance, self.code, self.token = EmailVerificationOTP.generate(
            "verify@example.com"
        )

    def test_the_correct_code_still_verifies(self):
        obj, err = EmailVerificationOTP.verify(self.token, self.code)
        self.assertIsNone(err)
        self.assertIsNotNone(obj, "hashing broke the happy path")

    def test_a_wrong_code_is_refused(self):
        wrong = "000000" if self.code != "000000" else "111111"
        obj, err = EmailVerificationOTP.verify(self.token, wrong)
        self.assertIsNone(obj)
        self.assertIn("Invalid OTP", err)

    def test_the_stored_hash_cannot_be_replayed_as_the_code(self):
        """Submitting the hash itself must not authenticate."""
        self.instance.refresh_from_db()
        obj, _ = EmailVerificationOTP.verify(self.token, self.instance.code_hash)
        self.assertIsNone(obj)

    def test_attempts_still_cap_at_five(self):
        for _ in range(5):
            EmailVerificationOTP.verify(self.token, "999999")
        obj, err = EmailVerificationOTP.verify(self.token, self.code)
        self.assertIsNone(obj, "the attempt cap stopped working")

    def test_an_empty_hash_matches_nothing(self):
        """Fail closed on a malformed row — returning True on empty is the classic
        fail-open in this shape of code."""
        self.instance.code_hash = ""
        self.instance.save(update_fields=["code_hash"])
        obj, _ = EmailVerificationOTP.verify(self.token, self.code)
        self.assertIsNone(obj)
        obj2, _ = EmailVerificationOTP.verify(self.token, "")
        self.assertIsNone(obj2)

    def test_verifying_twice_fails(self):
        EmailVerificationOTP.verify(self.token, self.code)
        obj, err = EmailVerificationOTP.verify(self.token, self.code)
        self.assertIsNone(obj)
        self.assertIn("already been used", err)


class OTPAdminExposureTests(TestCase):
    """The admin was the concrete takeover path, not just the storage."""

    def test_admin_does_not_display_the_code_or_session_token(self):
        from django.contrib import admin as dj_admin

        from apps.accounts.models import EmailVerificationOTP as M

        cls = dj_admin.site._registry[M].__class__
        readonly = set(getattr(cls, "readonly_fields", ()))
        listed = set(getattr(cls, "list_display", ()))
        excluded = set(getattr(cls, "exclude", ()) or ())

        for leaky in ("code", "code_hash", "session_token"):
            self.assertNotIn(leaky, readonly, f"admin exposes {leaky} as readonly")
            self.assertNotIn(leaky, listed, f"admin lists {leaky} in list_display")
        self.assertTrue(
            {"code_hash", "session_token"} <= excluded,
            "code_hash/session_token should be explicitly excluded from the form",
        )
