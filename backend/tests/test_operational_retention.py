"""Audit Z5-8 — the tables that only grow, and what they cost.

These are not privacy risks, which is why they were missed by the Z4-2 sweep:
they are the tables that decide backup and restore time. D3 is 2 vCPU with no
read replica, `pg_dump` duration grows linearly and restore is single-threaded,
so unbounded growth converts directly into RTO — at 50 GB, hours. `SessionRecording`
alone stores up to 5,000 I/O events per session in a JSONField.

Every period defaults to **0 = report only**, matching Z4-2. A retention job that
shipped enabled with a guessed default would delete a customer's session replays
the first night it ran, which is worse than the gap it closes. The tests that
matter most here are the ones asserting nothing is deleted by default, and the
two exclusions that would each destroy real data if they were dropped:

* a live lab's `simulation_snapshot` is the learner's work in progress — age of
  the row says nothing, `status` does;
* an **unread** notification is still pending work for the user.

`webhook_event` has a third: those rows are the durable double-fulfilment guard,
so the floor is not a preference. It must exceed the gateway's replay window.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.billing.models import ProcessedWebhookEvent
from apps.labs.models import IncidentRun, LabSession, SessionRecording
from apps.notifications.models import Notification
from apps.question_bank.models import Scenario, Technology
from celery_app.tasks import purge_expired_personal_data

User = get_user_model()

OLD = timezone.now() - timedelta(days=400)


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ops", email="ops@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )

    def _session(self, status="COMPLETED", ended=OLD, snapshot=None):
        s = LabSession.objects.create(
            user=self.user, scenario=self.scenario, status=status,
            simulation_snapshot=snapshot if snapshot is not None else {"fs": ["a"] * 50},
        )
        LabSession.objects.filter(pk=s.pk).update(started_at=OLD, ended_at=ended)
        return s

    def _age(self, model, pk, field="created_at", when=OLD):
        model.objects.filter(pk=pk).update(**{field: when})


class ReportOnlyByDefaultTests(_Base):
    """The whole safety property: an unset period must never delete."""

    def test_nothing_is_deleted_with_no_settings(self):
        rec = SessionRecording.objects.create(session=self._session(), events=[1, 2])
        self._age(SessionRecording, rec.pk)
        ev = ProcessedWebhookEvent.objects.create(event_id="evt_1")
        self._age(ProcessedWebhookEvent, ev.pk)
        n = Notification.objects.create(user=self.user, title="hi", read=True)
        self._age(Notification, n.pk)

        purge_expired_personal_data()

        self.assertTrue(SessionRecording.objects.filter(pk=rec.pk).exists())
        self.assertTrue(ProcessedWebhookEvent.objects.filter(pk=ev.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())

    def test_a_snapshot_is_not_cleared_by_default(self):
        s = self._session()
        purge_expired_personal_data()
        self.assertTrue(LabSession.objects.get(pk=s.pk).simulation_snapshot)

    def test_the_disabled_path_still_reports_a_count(self):
        """The point of report-only: pick the period from real volumes."""
        rec = SessionRecording.objects.create(session=self._session(), events=[1])
        self._age(SessionRecording, rec.pk)
        entry = purge_expired_personal_data()["session_recording"]
        self.assertFalse(entry["enabled"])
        self.assertEqual(entry["matched"], 1)
        self.assertEqual(entry["purged"], 0)

    def test_every_operational_class_is_reported(self):
        report = purge_expired_personal_data()
        for label in (
            "session_recording", "lab_snapshot", "webhook_event",
            "read_notification", "incident_run",
        ):
            self.assertIn(label, report, f"{label} is not swept at all")


class EnablingOneDoesNotEnableTheOthersTests(_Base):
    @override_settings(RETENTION_SESSION_RECORDING_DAYS=30)
    def test_recordings_go_but_webhook_events_stay(self):
        rec = SessionRecording.objects.create(session=self._session(), events=[1])
        self._age(SessionRecording, rec.pk)
        ev = ProcessedWebhookEvent.objects.create(event_id="evt_2")
        self._age(ProcessedWebhookEvent, ev.pk)

        purge_expired_personal_data()

        self.assertFalse(SessionRecording.objects.filter(pk=rec.pk).exists())
        self.assertTrue(
            ProcessedWebhookEvent.objects.filter(pk=ev.pk).exists(),
            "enabling one retention class enabled another",
        )

    @override_settings(RETENTION_SESSION_RECORDING_DAYS=30)
    def test_a_recent_recording_survives(self):
        rec = SessionRecording.objects.create(session=self._session(), events=[1])
        purge_expired_personal_data()
        self.assertTrue(SessionRecording.objects.filter(pk=rec.pk).exists())


class LiveLabsAreNeverTouchedTests(_Base):
    """The exclusion that matters most: clearing a running lab's snapshot would
    destroy the learner's work in place, mid-session."""

    @override_settings(RETENTION_LAB_SNAPSHOT_DAYS=30)
    def test_a_running_session_keeps_its_snapshot(self):
        s = self._session(status="RUNNING", ended=None)
        purge_expired_personal_data()
        self.assertTrue(
            LabSession.objects.get(pk=s.pk).simulation_snapshot,
            "a live lab's simulation state was wiped by the retention sweep",
        )

    @override_settings(RETENTION_LAB_SNAPSHOT_DAYS=30)
    def test_a_provisioning_session_keeps_its_snapshot(self):
        s = self._session(status="PROVISIONING", ended=None)
        purge_expired_personal_data()
        self.assertTrue(LabSession.objects.get(pk=s.pk).simulation_snapshot)

    @override_settings(RETENTION_LAB_SNAPSHOT_DAYS=30)
    def test_a_finished_session_has_its_snapshot_cleared(self):
        s = self._session(status="COMPLETED")
        purge_expired_personal_data()
        self.assertEqual(
            LabSession.objects.get(pk=s.pk).simulation_snapshot, {},
            "cleared to {} rather than NULL — the column is JSONField(default=dict) "
            "with no null=True, so nulling it raises IntegrityError",
        )

    @override_settings(RETENTION_LAB_SNAPSHOT_DAYS=30)
    def test_the_session_row_itself_survives(self):
        """It is the completion record that progress, grading and billing all
        reference — only the payload goes."""
        s = self._session(status="COMPLETED")
        purge_expired_personal_data()
        self.assertTrue(LabSession.objects.filter(pk=s.pk).exists())


class UnreadNotificationsSurviveTests(_Base):
    @override_settings(RETENTION_READ_NOTIFICATION_DAYS=30)
    def test_an_unread_notification_is_kept_however_old(self):
        n = Notification.objects.create(user=self.user, title="unread", read=False)
        self._age(Notification, n.pk)
        purge_expired_personal_data()
        self.assertTrue(
            Notification.objects.filter(pk=n.pk).exists(),
            "an unread notification was deleted — it is still pending work",
        )

    @override_settings(RETENTION_READ_NOTIFICATION_DAYS=30)
    def test_a_read_notification_is_removed(self):
        """Guard the guard: if nothing were ever removed the test above is vacuous."""
        n = Notification.objects.create(user=self.user, title="read", read=True)
        self._age(Notification, n.pk)
        purge_expired_personal_data()
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())


class WebhookIdempotencyFloorTests(_Base):
    @override_settings(RETENTION_WEBHOOK_EVENT_DAYS=90)
    def test_an_old_event_is_removed(self):
        ev = ProcessedWebhookEvent.objects.create(event_id="evt_old")
        self._age(ProcessedWebhookEvent, ev.pk)
        purge_expired_personal_data()
        self.assertFalse(ProcessedWebhookEvent.objects.filter(pk=ev.pk).exists())

    @override_settings(RETENTION_WEBHOOK_EVENT_DAYS=90)
    def test_a_recent_event_is_kept(self):
        """These rows are the durable double-fulfilment guard. Removing one inside
        the gateway's replay window re-opens a duplicate charge."""
        ev = ProcessedWebhookEvent.objects.create(event_id="evt_new")
        self._age(ProcessedWebhookEvent, ev.pk, when=timezone.now() - timedelta(days=2))
        purge_expired_personal_data()
        self.assertTrue(ProcessedWebhookEvent.objects.filter(pk=ev.pk).exists())

    def test_the_shipped_default_is_report_only(self):
        """A non-zero default here would be the one that could cost real money."""
        from django.conf import settings

        self.assertEqual(getattr(settings, "RETENTION_WEBHOOK_EVENT_DAYS", 0), 0)


class IncidentRunTests(_Base):
    @override_settings(RETENTION_INCIDENT_RUN_DAYS=30)
    def test_an_old_run_is_removed(self):
        run = IncidentRun.objects.create(lab_session=self._session(), template_key="t")
        self._age(IncidentRun, run.pk, field="started_at")
        purge_expired_personal_data()
        self.assertFalse(IncidentRun.objects.filter(pk=run.pk).exists())

    @override_settings(RETENTION_INCIDENT_RUN_DAYS=30)
    def test_a_recent_run_survives(self):
        run = IncidentRun.objects.create(lab_session=self._session(), template_key="t")
        purge_expired_personal_data()
        self.assertTrue(IncidentRun.objects.filter(pk=run.pk).exists())


class ThePrivacySweepStillWorksTests(_Base):
    """The operational sweeps were appended to the Z4-2 task; adding them must not
    have disturbed the privacy classes already there."""

    def test_the_original_classes_are_still_reported(self):
        report = purge_expired_personal_data()
        for label in (
            "interview_message", "async_video", "command_history", "resume",
            "account_lifecycle",
        ):
            self.assertIn(label, report, f"{label} stopped being swept")


class AccountLifecycleRetentionTests(_Base):
    """Audit Z4-12 leftover — post-deletion email has a stated TTL path."""

    def test_report_only_by_default(self):
        from apps.accounts.models import AccountLifecycleEvent

        ev = AccountLifecycleEvent.objects.create(
            user=None, email="gone@example.com", event_type="deleted",
            metadata={"user_id": 1},
        )
        self._age(AccountLifecycleEvent, ev.pk)
        report = purge_expired_personal_data()
        self.assertTrue(AccountLifecycleEvent.objects.filter(pk=ev.pk).exists())
        self.assertFalse(report["account_lifecycle"]["enabled"])
        self.assertEqual(report["account_lifecycle"]["purged"], 0)
        self.assertGreaterEqual(report["account_lifecycle"]["matched"], 1)

    @override_settings(RETENTION_ACCOUNT_LIFECYCLE_DAYS=30)
    def test_old_events_are_purged_when_enabled(self):
        from apps.accounts.models import AccountLifecycleEvent

        old = AccountLifecycleEvent.objects.create(
            user=None, email="old@example.com", event_type="deleted",
        )
        recent = AccountLifecycleEvent.objects.create(
            user=None, email="new@example.com", event_type="deleted",
        )
        self._age(AccountLifecycleEvent, old.pk)
        purge_expired_personal_data()
        self.assertFalse(AccountLifecycleEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(AccountLifecycleEvent.objects.filter(pk=recent.pk).exists())
