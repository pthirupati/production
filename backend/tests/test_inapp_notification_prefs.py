"""Turning off in-app notifications must actually turn them off.

Audit Z3-6. The interesting part is what the measurement showed: `should_notify_inapp`
already existed **and was already called** — by three specific tasks. But the *generic*
`create_in_app_notification` task and both direct writers
(`jira_integration/webhooks.py`, `community/views.py`) called
`Notification.objects.create` straight through. So the preference was honoured for
achievement mail and ignored for the system notifications users actually receive most.

A preference the UI offers and the backend ignores is worse than no preference: it
tells the user they are in control when they are not.

Fixed by centralising delivery in one helper rather than adding a fourth and fifth
copy of the check — scattered gates drift, which is precisely how three writers came
to bypass one that already existed. These tests pin the choke point, including a
grep-style assertion that no new writer reintroduces a direct `objects.create`.
"""
import pathlib

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.email_helpers import deliver_inapp_notification
from apps.notifications.models import Notification, NotificationPreference

User = get_user_model()


class PreferenceIsHonouredTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="inapp", email="inapp@example.com", password="Str0ng-Pass-1"
        )
        self.prefs = NotificationPreference.get_for_user(self.user)

    def _count(self):
        return Notification.objects.filter(user=self.user).count()

    def test_delivered_by_default(self):
        """Defaults are on, so existing users see no change."""
        deliver_inapp_notification(self.user, "system", "t", "m")
        self.assertEqual(self._count(), 1)

    def test_suppressed_when_the_user_opts_out(self):
        self.prefs.inapp_system = False
        self.prefs.save(update_fields=["inapp_system"])
        result = deliver_inapp_notification(self.user, "system", "t", "m")
        self.assertIsNone(result)
        self.assertEqual(self._count(), 0, "opting out did not stop the notification")

    def test_opting_out_of_one_type_leaves_others_alone(self):
        self.prefs.inapp_system = False
        self.prefs.save(update_fields=["inapp_system"])
        deliver_inapp_notification(self.user, "achievement", "t", "m")
        self.assertEqual(self._count(), 1)

    def test_force_bypasses_preferences(self):
        """Account-lifecycle and security notices must land regardless — preferences
        govern what a user finds useful, not whether we may tell them their account
        is being deleted."""
        self.prefs.inapp_system = False
        self.prefs.save(update_fields=["inapp_system"])
        deliver_inapp_notification(self.user, "system", "t", "m", force=True)
        self.assertEqual(self._count(), 1)

    def test_welcome_always_lands(self):
        """should_notify_inapp maps 'welcome' to True unconditionally."""
        self.prefs.inapp_system = False
        self.prefs.save(update_fields=["inapp_system"])
        deliver_inapp_notification(self.user, "welcome", "t", "m")
        self.assertEqual(self._count(), 1)

    def test_metadata_is_preserved(self):
        deliver_inapp_notification(self.user, "system", "t", "m", {"k": "v"})
        self.assertEqual(Notification.objects.get(user=self.user).metadata, {"k": "v"})


class WritersUseTheChokePointTests(TestCase):
    """The three writers that previously bypassed the check."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="w", email="w@example.com", password="Str0ng-Pass-1"
        )
        prefs = NotificationPreference.get_for_user(self.user)
        prefs.inapp_system = False
        prefs.save(update_fields=["inapp_system"])

    def test_generic_task_honours_preferences(self):
        from apps.notifications.tasks import create_in_app_notification

        create_in_app_notification(self.user.id, "system", "t", "m")
        self.assertEqual(
            Notification.objects.filter(user=self.user).count(), 0,
            "the generic in-app task still bypasses preferences",
        )

    def test_generic_task_delivers_when_opted_in(self):
        prefs = NotificationPreference.get_for_user(self.user)
        prefs.inapp_system = True
        prefs.save(update_fields=["inapp_system"])
        from apps.notifications.tasks import create_in_app_notification

        create_in_app_notification(self.user.id, "system", "t", "m")
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_generic_task_tolerates_a_missing_user(self):
        from apps.notifications.tasks import create_in_app_notification

        create_in_app_notification(999999, "system", "t", "m")  # must not raise

    def test_no_module_writes_notifications_directly(self):
        """A new writer calling Notification.objects.create would silently reopen
        the gap, so the choke point is asserted structurally rather than trusted."""
        from django.conf import settings

        backend = pathlib.Path(settings.BASE_DIR)
        offenders = []
        for path in backend.rglob("*.py"):
            if "migrations" in path.parts or "tests" in path.parts:
                continue
            if ".venv" in path.parts or "site-packages" in path.parts:
                continue  # third-party code is not ours to police
            if path.name == "email_helpers.py":
                continue  # the choke point itself
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # a stray non-UTF8 file is not a notification writer
            if "Notification.objects.create" in text:
                offenders.append(str(path.relative_to(backend)))
        self.assertEqual(
            offenders, [],
            "these modules write in-app notifications directly, bypassing the "
            f"preference check: {offenders}",
        )
