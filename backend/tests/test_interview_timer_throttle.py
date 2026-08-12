"""Timer endpoints are throttled, but not out of the answering budget (audit L358).

The audit asked for a throttle on extend/pause/resume, which were unbounded while
start/message/practical were not. Adding plain `InterviewRateThrottle` closes that,
but `interview` is **200/day per user** and `UserRateThrottle` keys one bucket per
user per scope — so timer calls and *answer* calls would draw down the same finite
daily allowance.

That matters because pause/resume is not user-initiated. `InterviewRoom.jsx` fires
pause on every `visibilitychange` to hidden and resume on every return, debounced
only 400ms. Alt-tabbing to read documentation would spend the quota that answering
questions needs, and DRF raises the 429 on `message` — ending the interview
mid-answer. `InterviewTimerRateThrottle` re-keys to a separate bucket at the same
configured rate.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.interviews.models import InterviewCampaign, InterviewRound
from common.testing import real_throttling


class InterviewTimerThrottleTests(TestCase):
    def setUp(self):
        cache.clear()  # DRF keeps throttle history in the cache
        User = get_user_model()
        self.user = User.objects.create_user(username="timer", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.campaign = InterviewCampaign.objects.create(
            user=self.user, title="SRE", status="in_progress",
        )
        self.round = InterviewRound.objects.create(
            campaign=self.campaign,
            round_number=1,
            round_type="technical",
            title="Technical",
            status="in_progress",
            ends_at=timezone.now() + timedelta(minutes=30),
        )
        self.pause_url = f"/api/interviews/rounds/{self.round.id}/pause/"
        self.resume_url = f"/api/interviews/rounds/{self.round.id}/resume/"
        self.message_url = f"/api/interviews/rounds/{self.round.id}/message/"

    def test_timer_endpoints_are_throttled(self):
        """The original audit item: pause/resume must not be unbounded."""
        with real_throttling(interview="4/hour"):
            codes = [
                self.client.post(self.pause_url if i % 2 == 0 else self.resume_url).status_code
                for i in range(8)
            ]
        self.assertIn(429, codes, f"timer endpoints never throttled: {codes}")

    def test_tab_switching_does_not_consume_the_answer_budget(self):
        """Regression: pause/resume must not 429 the next answer.

        With a shared bucket this is exactly what happened — the timer calls
        exhausted the quota and `message` was refused.
        """
        with real_throttling(interview="6/hour"):
            # Simulate a candidate alt-tabbing away and back a few times. This
            # alone would spend the whole 6/hour on a shared bucket.
            for _ in range(5):
                self.client.post(self.pause_url)
                self.client.post(self.resume_url)

            resp = self.client.post(self.message_url, {"message": "my answer"}, format="json")

        self.assertNotEqual(
            resp.status_code, 429,
            "answering was rate-limited by background tab-switching",
        )
