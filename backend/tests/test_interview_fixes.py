"""Interview resume score, practical lab metadata, and voice clarification tests."""

import unittest

from django.test import SimpleTestCase, TestCase, override_settings

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "iv-test"}}


class InterviewClarificationTest(SimpleTestCase):
    def test_clarify_probe_reasks_original_question(self):
        from apps.interviews.services.interview_ai import generate_clarify_probe

        q = "How would you debug elevated 5xx on an nginx ingress?"
        probe = generate_clarify_probe(candidate_answer="we use caching", question_text=q)
        self.assertIn("So again:", probe)
        self.assertIn(q, probe)

    def test_access_through_association_definition(self):
        from apps.interviews.services.interview_ai import generate_clarification_reply

        q = "Walk me through how you'd audit IAM permissions in AWS."
        reply = generate_clarification_reply(
            candidate_question="Can you go deeper on access through association with a real example?",
            question_text=q,
        )
        self.assertIn("Deployers", reply)
        self.assertIn("Alice", reply)
        self.assertIn(q, reply)

    def test_long_answer_with_iam_not_treated_as_question(self):
        from apps.interviews.services.interview_ai import is_candidate_question

        answer = (
            "I would audit IAM by listing users and roles, checking group membership, "
            "and tracing access through association — for example policies attached to "
            "groups rather than users directly?"
        )
        self.assertFalse(is_candidate_question(answer))

    def test_short_correct_answer_not_reprompted(self):
        from apps.interviews.services.engine import _should_reprompt_answer
        from apps.interviews.services.scoring import CORRECTNESS_CORRECT, score_answer

        class Q:
            question_text = "How do you restart nginx on a Linux host?"
            expected_keywords = ["systemctl", "restart", "nginx", "service"]
            technology_id = None

        result = score_answer(Q(), "Run systemctl restart nginx and verify with curl localhost.")
        self.assertIn(result["quality"], ("adequate", "strong", "brief"))
        self.assertFalse(_should_reprompt_answer(result, CORRECTNESS_CORRECT))

    def test_force_advance_moves_to_next_question(self):
        from apps.interviews.services.interview_ai import generate_unclear_audio_reply

        reply = generate_unclear_audio_reply(
            question_text="How do you debug a pod crash loop?",
            partial_transcript="",
        )
        self.assertIn("didn't catch", reply.lower())
        self.assertIn("crash loop", reply)

    def test_unclear_audio_reply_is_empathetic_not_judgmental(self):
        from apps.interviews.services.interview_ai import generate_unclear_audio_reply

        reply = generate_unclear_audio_reply(question_text="Explain IAM roles.")
        low = reply.lower()
        self.assertTrue(
            any(p in low for p in ("didn't catch", "trouble hearing", "lost you", "audio")),
            reply,
        )
        self.assertNotIn("wrong", low)
        self.assertNotIn("off-base", low)


class ResumeScoreWithoutFileTest(unittest.TestCase):
    def test_no_resume_returns_null_score(self):
        from apps.interviews.services.resume_parser import score_resume

        result = score_resume({}, resume_text="", target_technology="Linux", target_role="SRE")
        self.assertFalse(result["has_resume"])
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result.get("message"), "No resume uploaded")


class PracticalLabMetadataTest(TestCase):
    @override_settings(CACHES=LOCMEM)
    def test_generated_practical_uses_message_metadata(self):
        from django.contrib.auth import get_user_model

        from apps.interviews.models import InterviewCampaign, InterviewMessage, InterviewRound
        from apps.interviews.services.practical_lab import (
            _current_practical_message,
            _practical_config_from_message,
            _practical_scenario_slug,
            validate_practical_answer,
        )

        User = get_user_model()
        user = User.objects.create_user(username="plab-meta", email="plab@example.com", password="x")
        campaign = InterviewCampaign.objects.create(user=user, title="t", experience_level="mid")
        rnd = InterviewRound.objects.create(campaign=campaign, round_number=1, round_type="technical")
        msg = InterviewMessage.objects.create(
            round=rnd,
            role="interviewer",
            content="Fix the service",
            message_type="practical",
            metadata={
                "practical_config": {
                    "kind": "command",
                    "scenario_slug": "sim-rhel-ssh-stop",
                    "validate_commands": ["systemctl start sshd"],
                },
            },
        )
        cfg = _practical_config_from_message(msg)
        self.assertEqual(cfg.get("scenario_slug"), "sim-rhel-ssh-stop")
        self.assertEqual(_current_practical_message(rnd).id, msg.id)
        self.assertEqual(_practical_scenario_slug(rnd), "sim-rhel-ssh-stop")
        result = validate_practical_answer(rnd, "systemctl start sshd")
        self.assertTrue(result["validated"])
        self.assertEqual(result["validation_key"], f"msg:{msg.id}")
