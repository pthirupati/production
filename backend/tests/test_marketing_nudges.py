"""Tests for marketing nurture email cadence."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class MarketingNudgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="marketuser",
            email="market@example.com",
            password="testpass123",
        )
        self.user.last_login = timezone.now()
        self.user.save(update_fields=["last_login"])

    @patch("apps.notifications.email_helpers.queue_user_email", return_value=True)
    def test_technology_nudge_respects_cadence(self, mock_queue):
        from apps.notifications.marketing_service import (
            eligible_technology_subscribe_nudge,
            send_technology_subscribe_nudge,
        )
        from apps.notifications.models import MarketingEmailLog, NotificationPreference

        NotificationPreference.objects.filter(user=self.user).update(email_marketing=True)
        self.user.date_joined = timezone.now() - timedelta(days=10)
        self.user.save(update_fields=["date_joined"])

        self.assertTrue(eligible_technology_subscribe_nudge(self.user))
        self.assertTrue(send_technology_subscribe_nudge(self.user))
        self.assertFalse(eligible_technology_subscribe_nudge(self.user))

        MarketingEmailLog.objects.filter(user=self.user).update(
            sent_at=timezone.now() - timedelta(days=6)
        )
        self.assertTrue(eligible_technology_subscribe_nudge(self.user))

    @patch("apps.notifications.email_helpers.queue_user_email", return_value=True)
    def test_interview_sample_nudge_after_completion(self, mock_queue):
        from apps.interviews.models import InterviewCampaign, InterviewRound
        from apps.notifications.marketing_service import (
            eligible_interview_sample_nudge,
            send_interview_sample_nudge,
        )
        from apps.notifications.models import NotificationPreference

        NotificationPreference.objects.filter(user=self.user).update(email_marketing=True)
        completed = timezone.now() - timedelta(days=6)
        campaign = InterviewCampaign.objects.create(
            user=self.user,
            title="Sample",
            round_count=1,
            status="completed",
            is_sample=True,
            completed_at=completed,
        )
        InterviewRound.objects.create(
            campaign=campaign,
            round_number=1,
            round_type="technical",
            title="Sample",
            duration_minutes=10,
            status="completed",
        )

        self.assertTrue(eligible_interview_sample_nudge(self.user))
        self.assertTrue(send_interview_sample_nudge(self.user))
        mock_queue.assert_called_once()
