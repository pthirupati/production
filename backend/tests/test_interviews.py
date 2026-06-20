"""Tests for AI Interview Studio."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.interviews.models import (
    InterviewAdminJoinRequest,
    InterviewCampaign,
    InterviewPlanTier,
    InterviewQuestion,
    InterviewVoiceOption,
)
from apps.interviews.services.campaign_builder import create_campaign_rounds
from apps.interviews.services.engine import ask_next_question, start_round, submit_answer
from apps.interviews.services.entitlements import get_entitlement_payload, user_has_interview_access
from apps.interviews.services.interview_settings import ensure_staff_entitlement, get_platform_settings
from apps.question_bank.models import Technology

User = get_user_model()


class InterviewStudioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="candidate", email="c@t.com", password="pass12345")
        self.admin = User.objects.create_user(
            username="admin", email="admin@t.com", password="pass12345", is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        InterviewPlanTier.objects.create(
            code="free", name="Free", price_inr=0, interviews_per_month=1, max_rounds=3,
        )
        InterviewPlanTier.objects.create(
            code="pro", name="Pro", price_inr=999, interviews_per_month=3, max_rounds=5,
            voice_enabled=True, practical_enabled=True, certificate_enabled=True,
        )
        InterviewPlanTier.objects.create(
            code="premium", name="Premium", price_inr=2499, interviews_per_month=5, max_rounds=5,
            voice_enabled=True, practical_enabled=True, certificate_enabled=True,
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        InterviewQuestion.objects.create(
            slug="test-linux-q",
            category="technical",
            round_types=["technical"],
            experience_levels=["mid"],
            difficulty=2,
            question_text="Explain how you troubleshoot high CPU on a Linux server.",
            expected_keywords=["top", "ps", "load"],
        )
        InterviewVoiceOption.objects.create(
            code="indian-female",
            label="Indian Female",
            locale="en-IN",
            gender="female",
            region="india",
            browser_voice_hint="Neerja",
            is_default=True,
        )

    def test_create_campaign_and_rounds(self):
        campaign = InterviewCampaign.objects.create(
            user=self.user,
            title="Test campaign",
            round_count=3,
            status="scheduled",
            profile_snapshot={"experience_level": "mid"},
            primary_technology=self.tech,
            experience_level="mid",
        )
        rounds = create_campaign_rounds(campaign)
        self.assertEqual(len(rounds), 3)
        self.assertEqual(rounds[0].round_type, "technical")
        self.assertEqual(rounds[0].duration_minutes, 45)

    def test_api_create_campaign(self):
        res = self.client.post("/api/interviews/campaigns/", {"round_count": 3}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["round_count"], 3)

    def test_interview_engine_flow(self):
        campaign = InterviewCampaign.objects.create(
            user=self.user,
            title="Engine test",
            round_count=3,
            status="scheduled",
            profile_snapshot={"experience_level": "mid"},
            experience_level="mid",
        )
        create_campaign_rounds(campaign)
        r1 = campaign.rounds.get(round_number=1)
        start_round(r1)
        q = ask_next_question(r1)
        self.assertIsNotNone(q)
        result = submit_answer(r1, "I would run top and ps to find the process, then check load average and recent deploys.")
        self.assertIn("score", result)
        self.assertGreater(result["score"]["score"], 0)

    def test_start_round_returns_200_without_api_key_or_profile(self):
        """Starting a round must succeed (not 500) with the free engine, no
        ANTHROPIC_API_KEY, and no pre-existing CandidateProfile.

        Regression for the production 'Server error. Please try again later.' on
        start: round 1 is created with status 'schedulable', the view permitted
        that status but engine.start_round() rejected it and returned a payload
        with no 'message' key, so the view 500'd with KeyError. The start path is
        now robust and the first-question fetch is optional (it raises on the
        SQLite test DB's JSON contains lookup but the room still opens with the
        intro — on CI Postgres a question is also returned).
        """
        import os
        from unittest import mock

        # Explicitly create a campaign with NO profile and a snapshot whose
        # experience_level is None (the value that used to crash intro rendering).
        campaign = InterviewCampaign.objects.create(
            user=self.user,
            title="No-profile start",
            round_count=3,
            status="scheduled",
            profile_snapshot={"experience_level": None, "target_role": ""},
            experience_level="mid",
        )
        create_campaign_rounds(campaign)
        r1 = campaign.rounds.get(round_number=1)
        self.assertEqual(r1.status, "schedulable")

        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            res = self.client.post(f"/api/interviews/rounds/{r1.id}/start/", {}, format="json")

        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertEqual(body["status"], "in_progress")
        # The interviewer intro must be present and non-empty.
        self.assertIn("intro", body)
        self.assertTrue(body["intro"]["content"].strip())

    def test_start_returns_200_and_engine_produces_question_no_api(self):
        """End-to-end guarantee for the FREE interview path:

        1. The start endpoint returns 200 (never a 500 "Server error") with NO
           ANTHROPIC_API_KEY and NO pre-existing CandidateProfile.
        2. The LLM engine falls back to the rule-based free engine (no client)
           and still produces a non-empty interviewer reply — i.e. the live
           interview NEVER depends on a paid API.
        3. The question engine produces a question. The adaptive selector uses a
           JSON ``contains`` lookup that SQLite cannot run locally; on CI/Postgres
           it works, so we assert a question is produced there and only tolerate
           the documented SQLite ``NotSupportedError`` on the local backend.
        """
        import os
        from unittest import mock

        from django.db.utils import NotSupportedError

        from apps.interviews.services import llm_engine

        campaign = InterviewCampaign.objects.create(
            user=self.user,
            title="Free engine start",
            round_count=3,
            status="scheduled",
            primary_technology=self.tech,
            profile_snapshot={},  # no profile at all
            experience_level="mid",
        )
        create_campaign_rounds(campaign)
        r1 = campaign.rounds.get(round_number=1)

        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            # Drop any cached Anthropic client so the no-key state is observed.
            llm_engine._get_client.cache_clear()
            # (1) start endpoint must be 200, not 500.
            res = self.client.post(f"/api/interviews/rounds/{r1.id}/start/", {}, format="json")
            self.assertEqual(res.status_code, 200, res.content)

            # (2) No paid client, yet the engine still replies (free fallback).
            self.assertIsNone(llm_engine._get_client(), "must have no paid LLM client without a key")
            reply = llm_engine.generate_interviewer_reply(
                persona_name="Alex",
                round_type="technical",
                question_text="How do you debug high CPU?",
                candidate_answer="I'd run top, then ps, then check recent deploys.",
                score_hint={"quality": "strong", "score": 80},
                profile_snapshot={},
                conversation_tail=[],
                strong_streak=1,
            )
            self.assertTrue(reply and reply.strip(), "free engine must produce a reply")

            # (3) Question engine produces a question (Postgres/CI); the SQLite
            #     JSON-contains limitation is documented and tolerated locally.
            r1.refresh_from_db()
            try:
                q = ask_next_question(r1)
            except NotSupportedError:
                self.skipTest("JSON contains lookup unsupported on local SQLite (works on CI Postgres)")
            else:
                self.assertIsNotNone(q, "free engine must select a question")
                self.assertTrue(q.content.strip())
        # Restore the client cache state for subsequent tests.
        llm_engine._get_client.cache_clear()

    def test_voice_config_free_browser(self):
        res = self.client.get("/api/interviews/voice/config/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["tts_provider"], "browser")
        self.assertFalse(data["uses_paid_apis"])
        self.assertTrue(len(data["voices"]) >= 1)

    def test_staff_free_entitlement(self):
        ensure_staff_entitlement(self.admin)
        self.assertTrue(user_has_interview_access(self.admin))
        payload = get_entitlement_payload(self.admin)
        self.assertTrue(payload["is_admin_granted_free"])
        self.assertFalse(payload["uses_paid_apis"])

    def test_platform_settings_singleton(self):
        row = get_platform_settings()
        self.assertEqual(row.pk, 1)
        self.assertTrue(row.staff_free_by_default)

    def test_admin_join_request_flow(self):
        campaign = InterviewCampaign.objects.create(
            user=self.user,
            title="Join test",
            round_count=1,
            status="in_progress",
            experience_level="mid",
        )
        create_campaign_rounds(campaign)
        r1 = campaign.rounds.get(round_number=1)
        r1.status = "in_progress"
        r1.save()
        req = InterviewAdminJoinRequest.objects.create(
            round=r1,
            admin_user=self.admin,
            candidate_user=self.user,
            message="Observe please",
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            f"/api/interviews/join-requests/{req.id}/respond/",
            {"approve": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, "approved")
        self.assertIsNotNone(res.json()["request"]["observer_token"])

    def test_demo_activate_staff(self):
        self.user.is_staff = True
        self.user.save()
        res = self.client.post("/api/interviews/billing/demo-activate/", {"plan_code": "pro"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["entitlement"]["is_active"])

    def test_plans_public(self):
        res = self.client.get("/api/interviews/plans/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.json()["plans"]) >= 1)

    def test_admin_settings_api(self):
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin)
        res = admin_client.get("/api/admin/interviews/settings/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("enabled", res.json())
