"""Regression tests for interview robustness + the free AI hint/bot service.

These lock in fixes for production-down bugs:
- A question with malformed ``expected_keywords`` (non-string entries) used to
  500 the live answer endpoint ("interviewer not working").
- Double-ending a round (race / double-click) used to KeyError into a 500.
- The lab "Ask AI" button used to 400 for any non-interview scenario.
All interview/hint logic is FREE and rule-based (no paid/OpenAI APIs).
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.interviews.models import (
    InterviewCampaign,
    InterviewEntitlement,
    InterviewMessage,
    InterviewQuestion,
    InterviewRound,
)
from apps.interviews.services.entitlements import ensure_interview_defaults

User = get_user_model()


class InterviewMessageRobustnessTest(TestCase):
    def setUp(self):
        ensure_interview_defaults()
        self.user = User.objects.create_user(
            username="iv_robust", email="iv_robust@example.com", password="x"
        )
        ent, _ = InterviewEntitlement.objects.get_or_create(user=self.user)
        ent.is_complimentary = True
        ent.is_active = True
        ent.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _running_round(self) -> InterviewRound:
        camp = InterviewCampaign.objects.create(
            user=self.user, title="t", status="in_progress", experience_level="mid"
        )
        return InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="in_progress", duration_minutes=30,
        )

    def test_malformed_keywords_do_not_500(self):
        question = InterviewQuestion.objects.create(
            slug="malformed-kw", question_text="Explain TCP.", category="technical",
            expected_keywords=[None, 123, "tcp"],  # corrupt JSON data
        )
        rnd = self._running_round()
        InterviewMessage.objects.create(
            round=rnd, role="interviewer", content="Explain TCP.",
            message_type="question", question=question,
        )
        resp = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/message/",
            {"answer": "TCP uses a 3-way handshake and is reliable.", "input_type": "text"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("interviewer_reply", resp.data)
        self.assertTrue(resp.data["interviewer_reply"]["content"])

    def test_double_end_does_not_500(self):
        rnd = self._running_round()
        first = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/end/", {"reason": "completed"}, format="json"
        )
        second = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/end/", {"reason": "completed"}, format="json"
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertLess(second.status_code, 500, second.content)


class SharedAiHintServiceTest(TestCase):
    """The free hint service must serve ANY scenario, not just interview mode."""

    def setUp(self):
        from apps.question_bank.models import Technology, Scenario
        from apps.labs.models import LabSession, CommandHistory

        self.user = User.objects.create_user(
            username="hint_u", email="hint_u@example.com", password="x"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=tech, slug="nginx-502", title="Nginx 502 under load",
            category="Web Server", difficulty="medium", description="nginx upstream timing out",
            objectives=["Restore 200 responses"], interview_mode=False, coding_mode=False,
        )
        self.session = LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="RUNNING"
        )
        CommandHistory.objects.create(
            session=self.session, command="systemctl status nginx", output="active"
        )

    def test_ai_hint_for_non_interview_scenario(self):
        resp = self.client.post(f"/api/labs/{self.session.id}/ai-hint/", {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["hint"]["content"])
        self.assertTrue(resp.data["hint"]["ai_generated"])

    def test_ai_hint_question_mode(self):
        resp = self.client.post(
            f"/api/labs/{self.session.id}/ai-hint/",
            {"question": "where do I even start?"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["answer"])
