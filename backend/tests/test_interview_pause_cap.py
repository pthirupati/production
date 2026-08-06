"""Pause/resume credit cap + proctoring counters (audit I6).

Tab-hidden time used to be refunded in full and never recorded, so leaving the
room to look something up was strictly rewarded. Credit is now capped at
MAX_CREDITED_PAUSES x MAX_CREDITED_PAUSE_SECONDS; the pause is still always
allowed and always logged.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.interviews.models import InterviewCampaign, InterviewRound
from apps.interviews.services import engine


class PauseCreditCapTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="pauser", password="x")
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

    def _pause_for(self, seconds):
        """Pause, then backdate paused_at so resume sees `seconds` of absence."""
        self.assertTrue(engine.pause_round(self.round))
        self.round.refresh_from_db()
        self.round.paused_at = timezone.now() - timedelta(seconds=seconds)
        self.round.save(update_fields=["paused_at"])
        before = self.round.ends_at
        self.assertTrue(engine.resume_round(self.round))
        self.round.refresh_from_db()
        return (self.round.ends_at - before).total_seconds()

    def test_long_absence_is_capped_at_60s(self):
        """A 10-minute absence must not buy back 10 minutes of clock."""
        credited = self._pause_for(600)
        self.assertAlmostEqual(credited, engine.MAX_CREDITED_PAUSE_SECONDS, delta=2)

    def test_short_absence_credited_in_full(self):
        credited = self._pause_for(20)
        self.assertAlmostEqual(credited, 20, delta=2)

    def test_third_pause_earns_no_credit(self):
        self._pause_for(30)
        self._pause_for(30)
        third = self._pause_for(30)
        self.assertEqual(third, 0)

    def test_pause_still_allowed_after_allowance(self):
        """Over the cap we stop paying, we do not lock the candidate out."""
        for _ in range(3):
            self._pause_for(30)
        self.assertTrue(engine.pause_round(self.round))
        self.round.refresh_from_db()
        self.assertIsNotNone(self.round.paused_at)

    def test_counters_persist_across_reload(self):
        """Regression guard: metadata must be in save(update_fields=...).

        The original resume_round saved only ["ends_at", "paused_at"], so any
        counter would look correct in memory and be silently lost on write.
        """
        self._pause_for(90)
        self._pause_for(15)
        fresh = InterviewRound.objects.get(pk=self.round.pk)
        state = engine.pause_state(fresh)
        self.assertEqual(state["count"], 2)
        self.assertEqual(state["credited_count"], 2)
        self.assertAlmostEqual(state["total_seconds"], 105, delta=3)
        self.assertAlmostEqual(state["credited_seconds"], 75, delta=3)
        # 90s absence only earned 60s, so 30s is uncredited.
        self.assertAlmostEqual(state["uncredited_seconds"], 30, delta=3)

    def test_every_pause_is_logged(self):
        self._pause_for(10)
        self._pause_for(20)
        fresh = InterviewRound.objects.get(pk=self.round.pk)
        events = engine.pause_state(fresh)["events"]
        self.assertEqual(len(events), 2)
        self.assertTrue(all("seconds" in e and "at" in e for e in events))

    def test_event_log_is_bounded(self):
        """A flapping connection must not grow metadata without limit."""
        for _ in range(25):
            self._pause_for(1)
        state = engine.pause_state(InterviewRound.objects.get(pk=self.round.pk))
        self.assertEqual(len(state["events"]), 20)
        self.assertEqual(state["count"], 25)  # aggregate stays exact

    def test_pause_count_reaches_the_report(self):
        self._pause_for(120)
        self._pause_for(10)
        result = engine.end_round(self.round, reason="completed")
        proctoring = (result["report"].confidence_analysis or {}).get("proctoring")
        self.assertIsNotNone(proctoring, "tab-switch count missing from report")
        self.assertEqual(proctoring["tab_switches"], 2)
        self.assertGreater(proctoring["uncredited_seconds"], 0)

    def test_clean_round_has_no_proctoring_block(self):
        result = engine.end_round(self.round, reason="completed")
        self.assertNotIn("proctoring", result["report"].confidence_analysis or {})
