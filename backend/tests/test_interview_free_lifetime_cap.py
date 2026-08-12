"""Z1-12: lifetime free-campaign cap (per account, not just monthly)."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.interviews.models import (
    InterviewCampaign,
    InterviewPlanTier,
    InterviewPlatformSettings,
)
from apps.interviews.services.entitlements import consume_interview_credit, ensure_interview_defaults

User = get_user_model()


@override_settings(INTERVIEW_FREE_CAMPAIGNS_LIFETIME=2)
class FreeCampaignLifetimeCapTests(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        InterviewPlanTier.objects.filter(code="free").update(is_active=True)
        row, _ = InterviewPlatformSettings.objects.get_or_create(pk=1)
        row.enabled = True
        row.free_campaigns_per_month = 5
        row.save(update_fields=["enabled", "free_campaigns_per_month"])
        self.user = User.objects.create_user(
            username="freelifer",
            email="freelifer@example.com",
            password="Str0ng-Pass-1",
        )

    def test_lifetime_cap_blocks_after_n_free_campaigns(self):
        for i in range(2):
            InterviewCampaign.objects.create(
                user=self.user,
                title=f"free-{i}",
                status="completed",
            )
        # Monthly quota would still allow (limit=5), lifetime=2 must refuse.
        self.assertFalse(consume_interview_credit(self.user))

    def test_cancelled_campaigns_do_not_count(self):
        InterviewCampaign.objects.create(
            user=self.user, title="cancelled", status="cancelled"
        )
        InterviewCampaign.objects.create(
            user=self.user, title="one", status="completed"
        )
        self.assertTrue(consume_interview_credit(self.user))
