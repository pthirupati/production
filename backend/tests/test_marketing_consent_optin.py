"""Marketing consent must be opt-IN, and the opt-out must actually stop email.

Audit Z4-8: `email_marketing` defaulted to **True** — pre-ticked consent, which is
invalid under GDPR Art.4(11)/Recital 32 ("a statement or a clear affirmative
action") and inconsistent with DPDP's affirmative-action standard. A user who never
touched the setting was counted as having consented.

The second half of the file exists because the first read of `marketing_service.py`
looked far worse than it was: `run_marketing_nudges` iterates every active user and
none of the `eligible_*` helpers mention `email_marketing`, which reads like the
unsubscribe does nothing. It is actually enforced one layer down, in
`queue_user_email` -> `user_wants_email` -> `should_email("marketing")`. That is
correct but non-obvious, so it is pinned here — the next person reading the
eligibility helpers will reach the same wrong conclusion, and a "fix" that adds the
check in the loop while someone else removes it from the helper is how consent
gates get lost.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.email_helpers import user_wants_email
from apps.notifications.models import NotificationPreference

User = get_user_model()


class MarketingIsOptInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="optin", email="optin@example.com", password="Str0ng-Pass-1"
        )

    def test_new_user_has_not_consented_to_marketing(self):
        prefs = NotificationPreference.get_for_user(self.user)
        self.assertFalse(
            prefs.email_marketing,
            "marketing consent is pre-ticked — that is not consent",
        )

    def test_transactional_email_stays_on_by_default(self):
        """Service email about something the user did is not marketing, and
        switching it off by mistake would break receipts."""
        prefs = NotificationPreference.get_for_user(self.user)
        self.assertTrue(prefs.email_subscription)
        self.assertTrue(prefs.email_achievements)

    def test_model_default_is_false(self):
        field = NotificationPreference._meta.get_field("email_marketing")
        self.assertFalse(field.default)


class MarketingConsentIsEnforcedTests(TestCase):
    """Where the gate actually lives — one layer below the eligibility helpers."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="mk", email="mk@example.com", password="Str0ng-Pass-1"
        )
        self.prefs = NotificationPreference.get_for_user(self.user)

    def test_marketing_is_refused_without_consent(self):
        self.assertFalse(user_wants_email(self.user, "marketing"))

    def test_marketing_is_allowed_after_opting_in(self):
        self.prefs.email_marketing = True
        self.prefs.save(update_fields=["email_marketing"])
        self.assertTrue(user_wants_email(self.user, "marketing"))

    def test_opting_out_again_stops_it(self):
        self.prefs.email_marketing = True
        self.prefs.save(update_fields=["email_marketing"])
        self.prefs.email_marketing = False
        self.prefs.save(update_fields=["email_marketing"])
        self.assertFalse(
            user_wants_email(self.user, "marketing"),
            "unsubscribing did not stop marketing email",
        )

    def test_opting_out_of_marketing_keeps_transactional_email(self):
        """Unsubscribing from marketing must not silently kill payment receipts."""
        self.assertTrue(user_wants_email(self.user, "subscription"))

    def test_every_marketing_sender_declares_the_marketing_type(self):
        """The gate keys off email_type; a sender passing the wrong string would
        bypass consent while looking correct."""
        import inspect

        from apps.notifications import marketing_service

        src = inspect.getsource(marketing_service)
        queue_calls = src.count("queue_user_email(")
        marketing_types = src.count('email_type="marketing"')
        self.assertEqual(
            queue_calls, marketing_types,
            f"{queue_calls} queue_user_email() call(s) but only {marketing_types} "
            'declared email_type="marketing" — one would escape the consent gate',
        )
