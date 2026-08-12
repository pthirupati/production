"""The sensitive data classes must have a retention path — and must not surprise-delete.

Audit Z4-2: interview messages (free-text candidate speech), async video, resumes
(file + parsed text) and CommandHistory had no retention and no purge. All
plaintext, kept indefinitely, stored alongside employer and current_package_lpa.

The deliberate design choice these tests pin: every RETENTION_*_DAYS defaults to
**0 = report only**. A retention job that ships enabled with a guessed default would
delete a paying customer's interview reports the first night it ran — worse than the
gap it closes. Disabled, it still COUNTS what it would remove and logs it, so the
period is chosen against real volumes and then switched on deliberately.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.interviews.models import (
    CandidateProfile,
    InterviewCampaign,
    InterviewMessage,
    InterviewRound,
)
from apps.labs.models import CommandHistory
from celery_app.tasks import purge_expired_personal_data

User = get_user_model()


def _age(model, pk_field_value, field, days):
    """Backdate an auto_now_add/auto_now column, which normal saves cannot set."""
    model.objects.filter(pk=pk_field_value).update(
        **{field: timezone.now() - timedelta(days=days)}
    )


def _make_round(user):
    """An InterviewRound needs a campaign and a round_number — same shape the
    interviews app's own tests use."""
    campaign = InterviewCampaign.objects.create(
        user=user, title="t", status="in_progress", experience_level="mid"
    )
    return InterviewRound.objects.create(
        campaign=campaign, round_number=1, round_type="technical",
        title="r", status="in_progress", duration_minutes=30,
    )


class ReportOnlyByDefaultTests(TestCase):
    """With no RETENTION_* configured, nothing may be deleted."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="ret1", email="ret1@example.com", password="Str0ng-Pass-1"
        )
        self.round = _make_round(self.user)
        self.msg = InterviewMessage.objects.create(
            round=self.round, role="candidate", content="I restarted the pod"
        )
        _age(InterviewMessage, self.msg.pk, "created_at", 4000)

    def test_default_settings_delete_nothing(self):
        report = purge_expired_personal_data()
        self.assertTrue(
            InterviewMessage.objects.filter(pk=self.msg.pk).exists(),
            "an unconfigured retention job deleted candidate speech",
        )
        self.assertFalse(report["interview_message"]["enabled"])
        self.assertEqual(report["interview_message"]["purged"], 0)

    def test_disabled_still_reports_what_it_would_remove(self):
        """The number that makes choosing a retention period an informed decision."""
        report = purge_expired_personal_data()
        self.assertGreaterEqual(report["interview_message"]["matched"], 1)

    def test_every_sensitive_class_is_covered(self):
        """Exact equality on purpose: this catches a class being *dropped*, which a
        subset assertion would miss.

        The operational sweeps (audit Z5-8) were later appended to the same task —
        different motivation (backup/restore time, not privacy) but the same
        report-only discipline — so they are listed here too. Their own behaviour
        lives in `tests/test_operational_retention.py`; what this pins is that the
        two groups both exist and neither has quietly disappeared.
        """
        report = purge_expired_personal_data()
        privacy = {
            "interview_message", "async_video", "command_history", "resume",
            "account_lifecycle",
        }
        operational = {
            "session_recording", "lab_snapshot", "webhook_event",
            "read_notification", "incident_run",
        }
        self.assertEqual(set(report), privacy | operational)


@override_settings(RETENTION_INTERVIEW_MESSAGE_DAYS=30)
class EnabledPurgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ret2", email="ret2@example.com", password="Str0ng-Pass-1"
        )
        self.round = _make_round(self.user)
        self.old = InterviewMessage.objects.create(
            round=self.round, role="candidate", content="old speech"
        )
        self.recent = InterviewMessage.objects.create(
            round=self.round, role="candidate", content="recent speech"
        )
        _age(InterviewMessage, self.old.pk, "created_at", 90)

    def test_expired_records_are_removed(self):
        report = purge_expired_personal_data()
        self.assertFalse(InterviewMessage.objects.filter(pk=self.old.pk).exists())
        self.assertTrue(report["interview_message"]["enabled"])
        self.assertEqual(report["interview_message"]["purged"], 1)

    def test_records_inside_the_window_are_kept(self):
        purge_expired_personal_data()
        self.assertTrue(
            InterviewMessage.objects.filter(pk=self.recent.pk).exists(),
            "purged a record inside the retention window",
        )

    def test_other_classes_stay_disabled(self):
        """Enabling one class must not switch on the rest."""
        report = purge_expired_personal_data()
        self.assertFalse(report["command_history"]["enabled"])
        self.assertFalse(report["resume"]["enabled"])


@override_settings(RETENTION_COMMAND_HISTORY_DAYS=30)
class CommandHistoryRetentionTests(TestCase):
    def setUp(self):
        from apps.labs.models import LabSession
        from apps.question_bank.models import Scenario, Technology

        self.user = User.objects.create_user(
            username="ret3", email="ret3@example.com", password="Str0ng-Pass-1"
        )
        tech = Technology.objects.create(name="RetTech", slug="rettech")
        scenario = Scenario.objects.create(
            title="Ret", slug="ret-scenario", technology=tech, description="d"
        )
        self.session = LabSession.objects.create(user=self.user, scenario=scenario)
        self.old = CommandHistory.objects.create(session=self.session, command="cat /etc/shadow")
        self.new = CommandHistory.objects.create(session=self.session, command="ls")
        _age(CommandHistory, self.old.pk, "timestamp", 90)

    def test_old_commands_are_purged(self):
        purge_expired_personal_data()
        self.assertFalse(CommandHistory.objects.filter(pk=self.old.pk).exists())
        self.assertTrue(CommandHistory.objects.filter(pk=self.new.pk).exists())


@override_settings(RETENTION_RESUME_DAYS=30)
class ResumeRetentionTests(TestCase):
    """Resumes are cleared field-by-field — deleting CandidateProfile would cascade
    away the whole interview history, and a bulk update() would skip the signal that
    removes the blob from disk."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="ret4", email="ret4@example.com", password="Str0ng-Pass-1"
        )
        self.profile = CandidateProfile.objects.create(
            user=self.user, resume_text="Jane Doe, staff engineer"
        )
        self.profile.resume_file.save("cv.txt", ContentFile(b"resume"), save=True)
        self.storage = self.profile.resume_file.storage
        self.name = self.profile.resume_file.name
        _age(CandidateProfile, self.profile.pk, "updated_at", 90)

    def test_resume_content_is_cleared_but_the_profile_survives(self):
        purge_expired_personal_data()
        self.profile.refresh_from_db()
        self.assertTrue(
            CandidateProfile.objects.filter(pk=self.profile.pk).exists(),
            "purging a resume destroyed the whole candidate profile",
        )
        self.assertEqual(self.profile.resume_text, "")
        self.assertFalse(self.profile.resume_file)

    def test_the_blob_leaves_the_disk_too(self):
        """Clearing the column alone would orphan the file — the exact Z4-3 leak."""
        purge_expired_personal_data()
        self.assertFalse(
            self.storage.exists(self.name),
            "the resume file survived the retention purge",
        )


class ScheduleRegistrationTests(TestCase):
    def test_task_is_on_the_beat_schedule(self):
        """A retention task nothing runs is not a retention policy."""
        from celery_app.beat_schedule import CELERY_BEAT_SCHEDULE

        tasks = {e["task"] for e in CELERY_BEAT_SCHEDULE.values()}
        self.assertIn("celery_app.tasks.purge_expired_personal_data", tasks)
