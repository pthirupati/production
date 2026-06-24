"""Tests for admin live-host interview mode."""

import unittest

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.interviews.models import InterviewAdminJoinRequest, InterviewCampaign, InterviewRound
from apps.interviews.services.admin_host import (
    admin_join_session,
    admin_post_question,
    admin_set_ai_enabled,
    ai_interviewer_active,
    host_state,
)
from apps.interviews.services.engine import submit_answer


class AdminHostModeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.candidate = User.objects.create_user(
            username="cand-host", email="cand@example.com", password="x"
        )
        self.admin = User.objects.create_user(
            username="admin-host", email="founder@fixitlab.com", password="x", is_staff=True
        )
        self.campaign = InterviewCampaign.objects.create(
            user=self.candidate, title="Host test", experience_level="mid"
        )
        self.round = InterviewRound.objects.create(
            campaign=self.campaign,
            round_number=1,
            round_type="technical",
            status="in_progress",
            persona_name="Alex",
        )
        InterviewAdminJoinRequest.objects.create(
            round=self.round,
            admin_user=self.admin,
            candidate_user=self.candidate,
            status="approved",
        )
        from apps.interviews.models import InterviewMessage

        InterviewMessage.objects.create(
            round=self.round,
            role="interviewer",
            content="How do you restart nginx?",
            message_type="question",
        )

    def test_admin_join_pauses_ai_and_welcomes(self):
        result = admin_join_session(self.round, admin_user=self.admin, display_name="Founder")
        self.assertFalse(result.get("already_joined"))
        st = host_state(self.round)
        self.assertTrue(st["joined"])
        self.assertFalse(st["ai_enabled"])
        self.assertFalse(ai_interviewer_active(self.round))
        self.assertGreaterEqual(len(result["messages"]), 2)

    def test_submit_answer_tracks_while_ai_paused(self):
        admin_join_session(self.round, admin_user=self.admin, display_name="Founder")
        admin_post_question(self.round, text="What excites you about SRE?", admin_user=self.admin)
        out = submit_answer(self.round, "I love on-call automation and reducing toil.", {})
        self.assertTrue(out.get("host_mode"))
        self.assertTrue(out.get("ai_paused"))
        self.assertIsNotNone(out.get("candidate_message"))
        mem = (self.round.metadata or {}).get("conversation", {}).get("memory", {})
        self.assertTrue(mem.get("phrases") or mem.get("topics_hit"))

    def test_resume_ai_asks_next_question(self):
        admin_join_session(self.round, admin_user=self.admin)
        admin_post_question(self.round, text="Tell me about your last project.", admin_user=self.admin)
        submit_answer(self.round, "Built a CI pipeline with GitHub Actions.", {})
        result = admin_set_ai_enabled(self.round, enabled=True, admin_user=self.admin)
        self.assertTrue(result["host_state"]["ai_enabled"])
        self.assertTrue(ai_interviewer_active(self.round))
        self.assertGreaterEqual(len(result.get("messages") or []), 1)

    def test_admin_rate_answer_like_ai(self):
        from apps.interviews.services.admin_host import admin_rate_answer, admin_rate_target

        admin_join_session(self.round, admin_user=self.admin)
        submit_answer(self.round, "I would systemctl restart nginx and check error logs.", {})
        target = admin_rate_target(self.round)
        self.assertIsNotNone(target)
        self.assertIn("ai_suggestion", target)

        result = admin_rate_answer(
            self.round,
            admin_user=self.admin,
            candidate_message_id=target["candidate_message_id"],
            quality="strong",
            use_ai=False,
        )
        self.assertGreaterEqual(result["score_result"]["score"], 80)
        self.assertTrue(result["candidate_message"].metadata.get("admin_rated"))
        self.assertIsNone(admin_rate_target(self.round))
