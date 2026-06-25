"""Tests for the AI-interview PARITY features added on top of the existing
generation-first engine. All exercise the FREE, deterministic path — no paid
OpenAI/Anthropic/cloud API anywhere.

Covers:
  * structured scorecard — recommendation + per-competency ratings,
  * heuristic confidence/communication analysis (filler words, length, pace),
  * real-time coaching tips after an answer (practice mode),
  * performance analytics — candidate trend/radar + recruiter comparison,
  * interview templates / job-role library + one-click launch,
  * candidate invitation flow (shareable token -> provisioned campaign),
  * one-way async video round (prompts -> recorded answer -> finalize report).
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.interviews.models import (
    AsyncVideoResponse,
    InterviewCampaign,
    InterviewEntitlement,
    InterviewInvitation,
    InterviewMessage,
    InterviewReport,
    InterviewRound,
    InterviewTemplate,
)
from apps.interviews.services import engine
from apps.interviews.services.entitlements import ensure_interview_defaults

User = get_user_model()


def _grant(user):
    ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
    ent.is_active = True
    ent.is_complimentary = True
    ent.interviews_remaining = 50
    ent.period_end = timezone.now() + timedelta(days=365)
    ent.save()
    return ent


SNAP = {
    "experience_level": "mid",
    "years_experience": 4,
    "target_role": "SRE",
    "current_company": "Acme",
    "primary_technology_name": "Kubernetes",
    "secondary_technologies": ["Prometheus"],
    "resume_parsed": {
        "skills_detected": ["kubernetes", "prometheus", "linux"],
        "years_experience_hint": 4,
        "has_resume": True,
    },
}

STRONG_ANSWER = (
    "When our cluster had an OOMKill incident I was responsible for the fix. I rolled "
    "back the deploy, added a cache size limit, and as a result we cut the error rate to "
    "zero and shipped a postmortem. I watched p99 latency and memory to confirm the fix "
    "held with zero downtime."
)


# ---------------------------------------------------------------------------
# Scorecard: recommendation + competency ratings + confidence analysis.
# ---------------------------------------------------------------------------

class ScorecardTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user("sc", "sc@example.com", "x")

    def _run_round(self, answers):
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="in_progress",
            experience_level="mid", profile_snapshot=SNAP,
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="schedulable", duration_minutes=30,
        )
        engine.start_round(rnd)
        engine.ask_next_question(rnd)
        for a in answers:
            engine.submit_answer(rnd, a, {"input_type": "text"})
        return rnd, engine.end_round(rnd, reason="completed")

    def test_report_has_recommendation_and_competencies(self):
        rnd, out = self._run_round([STRONG_ANSWER] * 6)
        report = out["report"]
        self.assertIn(
            report.recommendation,
            ("strong_hire", "hire", "maybe", "no_hire"),
        )
        self.assertTrue(report.competency_ratings, "scorecard must include per-competency rows")
        names = {row["name"] for row in report.competency_ratings}
        self.assertIn("Technical depth", names)
        for row in report.competency_ratings:
            self.assertIn("score", row)
            self.assertIn("rating", row)

    def test_confidence_analysis_present_and_heuristic(self):
        rnd, out = self._run_round([STRONG_ANSWER] * 4)
        conf = out["report"].confidence_analysis
        self.assertTrue(conf)
        self.assertIs(conf.get("is_heuristic"), True)
        self.assertIn("confidence_score", conf)
        self.assertGreaterEqual(conf["confidence_score"], 0)
        self.assertLessEqual(conf["confidence_score"], 100)

    def test_filler_words_lower_confidence(self):
        from apps.interviews.services.scorecard import analyze_confidence

        clean = [InterviewMessage(role="candidate", content=STRONG_ANSWER, message_type="text")]
        filler_text = "um like uh you know basically i mean um like sort of i guess maybe stuff " * 3
        noisy = [InterviewMessage(role="candidate", content=filler_text, message_type="text")]
        self.assertGreater(
            analyze_confidence(clean)["confidence_score"],
            analyze_confidence(noisy)["confidence_score"],
        )

    def test_no_hire_recommendation_on_av_timeout(self):
        from apps.interviews.services.scorecard import recommend

        self.assertEqual(recommend(95, True, reason="av_timeout"), "no_hire")
        self.assertEqual(recommend(90, True), "strong_hire")
        self.assertEqual(recommend(40, False), "no_hire")


# ---------------------------------------------------------------------------
# Real-time coaching (practice mode).
# ---------------------------------------------------------------------------

class CoachingTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user("co", "co@example.com", "x")
        _grant(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_message_endpoint_returns_coaching_in_practice_mode(self):
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="in_progress",
            experience_level="mid", profile_snapshot=SNAP,
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="in_progress", duration_minutes=30,
        )
        engine.ask_next_question(rnd)
        resp = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/message/",
            {"answer": "ok", "input_type": "text", "practice": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNotNone(resp.data.get("coaching"))
        self.assertIn("tip", resp.data["coaching"])

    def test_no_coaching_without_practice_flag(self):
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="in_progress",
            experience_level="mid", profile_snapshot=SNAP,
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="in_progress", duration_minutes=30,
        )
        engine.ask_next_question(rnd)
        resp = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/message/",
            {"answer": STRONG_ANSWER, "input_type": "text"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data.get("coaching"))


# ---------------------------------------------------------------------------
# Analytics: candidate dashboard + recruiter comparison.
# ---------------------------------------------------------------------------

class AnalyticsTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user("an", "an@example.com", "x")
        _grant(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _completed_campaign(self, score=80.0):
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="completed",
            experience_level="mid", profile_snapshot=SNAP, overall_score=score,
            completed_at=timezone.now(),
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="passed", duration_minutes=30, overall_score=score,
        )
        InterviewReport.objects.create(
            round=rnd, passed=True, overall_score=score,
            technical_score=score, communication_score=score - 5,
            problem_solving_score=score, practical_score=score,
            presence_score=70, resume_alignment_score=68,
            recommendation="hire",
        )
        return camp

    def test_candidate_analytics_endpoint(self):
        self._completed_campaign(70)
        self._completed_campaign(85)
        resp = self.client.get("/api/interviews/analytics/me/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["attempts"], 2)
        self.assertEqual(len(resp.data["radar"]), 6)
        self.assertGreater(resp.data["best_score"], 0)
        # Improvement = latest - first = 85 - 70 = 15.
        self.assertAlmostEqual(resp.data["improvement"], 15.0, places=1)

    def test_recruiter_comparison_requires_recruiter(self):
        # No invitations -> not a recruiter -> 403.
        resp = self.client.get("/api/interviews/analytics/compare/")
        self.assertEqual(resp.status_code, 403)

    def test_recruiter_comparison_ranks_candidates(self):
        # Become a recruiter by creating an invitation, then compare.
        InterviewInvitation.objects.create(created_by=self.user, role_title="SRE")
        self._completed_campaign(60)
        self._completed_campaign(90)
        resp = self.client.get("/api/interviews/analytics/compare/")
        self.assertEqual(resp.status_code, 200, resp.content)
        cands = resp.data["candidates"]
        self.assertGreaterEqual(len(cands), 2)
        # Ranked by overall_score desc.
        self.assertEqual(cands[0]["rank"], 1)
        self.assertGreaterEqual(cands[0]["overall_score"], cands[1]["overall_score"])


# ---------------------------------------------------------------------------
# Templates / job-role library.
# ---------------------------------------------------------------------------

class TemplateTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user("tm", "tm@example.com", "x")
        _grant(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_default_templates_seeded_and_listed(self):
        resp = self.client.get("/api/interviews/templates/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertGreaterEqual(len(resp.data["templates"]), 4)
        slugs = {t["slug"] for t in resp.data["templates"]}
        self.assertIn("sre-senior", slugs)

    def test_launch_from_template_builds_campaign(self):
        from apps.interviews.services.templates import ensure_default_templates

        ensure_default_templates()
        tmpl = InterviewTemplate.objects.get(slug="sre-senior")
        resp = self.client.post(f"/api/interviews/templates/{tmpl.id}/launch/", {}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(resp.data["rounds"]), tmpl.round_count)
        camp = InterviewCampaign.objects.get(id=resp.data["id"])
        self.assertEqual(camp.template_id, tmpl.id)
        self.assertEqual(camp.experience_level, "senior")

    def test_non_admin_cannot_create_template(self):
        resp = self.client.post(
            "/api/interviews/templates/",
            {"name": "Hacker role", "experience_level": "mid"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Invitation flow.
# ---------------------------------------------------------------------------

class InvitationTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.recruiter = User.objects.create_user("rec", "rec@example.com", "x")
        self.candidate = User.objects.create_user("cand", "cand@example.com", "x")
        _grant(self.candidate)

    def test_create_invitation_and_public_lookup(self):
        c = APIClient()
        c.force_authenticate(self.recruiter)
        resp = c.post(
            "/api/interviews/invitations/",
            {"candidate_email": "cand@example.com", "role_title": "SRE", "send_email": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        token = resp.data["token"]
        self.assertIn("/interviews/invite/", resp.data["invite_url"])

        # Public lookup (no auth) marks it opened and returns the role.
        pub = APIClient().get(f"/api/interviews/invite/{token}/")
        self.assertEqual(pub.status_code, 200, pub.content)
        self.assertTrue(pub.data["valid"])
        self.assertEqual(pub.data["role_title"], "SRE")
        InterviewInvitation.objects.get(token=token)
        self.assertEqual(InterviewInvitation.objects.get(token=token).status, "opened")

    def test_candidate_accepts_and_gets_campaign(self):
        inv = InterviewInvitation.objects.create(
            created_by=self.recruiter, candidate_email="cand@example.com", role_title="SRE"
        )
        c = APIClient()
        c.force_authenticate(self.candidate)
        resp = c.post(f"/api/interviews/invite/{inv.token}/accept/", {}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data["rounds"])
        inv.refresh_from_db()
        self.assertEqual(inv.status, "accepted")
        self.assertEqual(inv.accepted_by_id, self.candidate.id)
        self.assertIsNotNone(inv.campaign_id)

    def test_revoked_invitation_cannot_be_accepted(self):
        inv = InterviewInvitation.objects.create(
            created_by=self.recruiter, role_title="SRE", status="revoked"
        )
        c = APIClient()
        c.force_authenticate(self.candidate)
        resp = c.post(f"/api/interviews/invite/{inv.token}/accept/", {}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# One-way async video round.
# ---------------------------------------------------------------------------

class AsyncVideoTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user("av", "av@example.com", "x")
        _grant(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _async_round(self):
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="scheduled",
            experience_level="mid", profile_snapshot=SNAP, mode="async_video",
        )
        return InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="scheduled", duration_minutes=20, mode="async_video",
        )

    def test_prompts_generated_and_recorded_answer_scored(self):
        rnd = self._async_round()
        # Start the async round.
        start = self.client.post(f"/api/interviews/rounds/{rnd.id}/async/prompts/")
        self.assertEqual(start.status_code, 200, start.content)
        self.assertGreaterEqual(len(start.data["prompts"]), 3)

        # Submit a recorded answer (transcript only — clip is optional in tests).
        resp = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/async/response/",
            {"question_index": 0, "transcript": STRONG_ANSWER, "duration_seconds": 45},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNotNone(resp.data["score"])
        self.assertIn("confidence", resp.data["analysis"])
        self.assertEqual(AsyncVideoResponse.objects.filter(round=rnd).count(), 1)

    def test_finalize_async_round_produces_report(self):
        rnd = self._async_round()
        self.client.post(f"/api/interviews/rounds/{rnd.id}/async/prompts/")
        for i in range(3):
            self.client.post(
                f"/api/interviews/rounds/{rnd.id}/async/response/",
                {"question_index": i, "transcript": STRONG_ANSWER, "duration_seconds": 40},
                format="multipart",
            )
        fin = self.client.post(f"/api/interviews/rounds/{rnd.id}/async/finalize/")
        self.assertEqual(fin.status_code, 200, fin.content)
        self.assertIsNotNone(fin.data["report"])
        rnd.refresh_from_db()
        self.assertIn(rnd.status, ("passed", "failed"))

    def test_review_playback_returns_responses(self):
        rnd = self._async_round()
        self.client.post(f"/api/interviews/rounds/{rnd.id}/async/prompts/")
        self.client.post(
            f"/api/interviews/rounds/{rnd.id}/async/response/",
            {"question_index": 0, "transcript": STRONG_ANSWER, "duration_seconds": 30},
            format="multipart",
        )
        rev = self.client.get(f"/api/interviews/rounds/{rnd.id}/async/review/")
        self.assertEqual(rev.status_code, 200, rev.content)
        self.assertEqual(len(rev.data["responses"]), 1)


# ---------------------------------------------------------------------------
# Transcript + résumé highlights mapping.
# ---------------------------------------------------------------------------

class TranscriptMappingTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user("tr", "tr@example.com", "x")
        _grant(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_transcript_has_timestamps_and_resume_highlights(self):
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="in_progress",
            experience_level="mid", profile_snapshot=SNAP,
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="in_progress", duration_minutes=30,
        )
        engine.start_round(rnd)
        engine.ask_next_question(rnd)
        engine.submit_answer(rnd, STRONG_ANSWER, {"input_type": "text"})

        resp = self.client.get(f"/api/interviews/rounds/{rnd.id}/transcript/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["transcript"])
        for row in resp.data["transcript"]:
            self.assertIn("offset_seconds", row)
            self.assertIn("timestamp", row)
        # Resume skills (kubernetes/prometheus/linux) appear in the highlights.
        skills = {h["skill"] for h in resp.data["resume_highlights"]}
        self.assertTrue({"kubernetes", "linux"} & skills)


# ---------------------------------------------------------------------------
# No paid API in the new services.
# ---------------------------------------------------------------------------

class NoPaidApiTest(TestCase):
    def test_interviews_app_has_no_paid_api(self):
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        forbidden = (
            "import anthropic", "from anthropic",
            "import openai", "from openai",
            "import elevenlabs", "from elevenlabs",
            "elevenlabs.api",
        )
        for path in root.rglob("*.py"):
            if path.name.startswith("test_"):
                continue
            src = path.read_text(encoding="utf-8", errors="ignore")
            code = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
            code = "\n".join(line.split("#", 1)[0] for line in code.splitlines()).lower()
            for token in forbidden:
                self.assertNotIn(token, code, f"{path.name}: paid-API usage {token!r}")
