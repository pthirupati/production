"""Interview resume score + practical lab metadata unit tests."""

import unittest

from django.test import SimpleTestCase, TestCase, override_settings

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "iv-test"}}


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
