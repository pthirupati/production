"""Tests for lab infrastructure type resolution and interview practical labs."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.labs.infra import lab_infra_type


def _scenario(**kwargs):
    s = MagicMock()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


class TestLabInfraType(TestCase):
    def test_simulation_lab_mode(self):
        s = _scenario(lab_mode="simulation", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_sim_slug_fallback(self):
        s = _scenario(lab_mode="docker", slug="sim-rhel-ssh-stop", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_terraform_simulation_type(self):
        s = _scenario(lab_mode="docker", simulation_type="terraform", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_plain_docker(self):
        s = _scenario(lab_mode="docker", slug="nginx-down", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "docker")


class TestInterviewPracticalLab(TestCase):
    def test_start_uses_simulation_not_docker(self):
        from apps.interviews.models import InterviewCampaign, InterviewRound
        from apps.interviews.services import practical_lab as pl
        from apps.labs.models import LabSession
        from apps.question_bank.models import Scenario, Technology

        user = self._create_user()
        tech, _ = Technology.objects.get_or_create(slug="simulation", defaults={"name": "Simulation", "is_active": True})
        scenario, _ = Scenario.objects.get_or_create(
            slug="sim-rhel-ssh-stop",
            defaults={
                "title": "RHEL SSH Stop",
                "technology": tech,
                "category": "Fix",
                "difficulty": "easy",
                "description": "test",
                "lab_mode": "simulation",
                "simulation_type": "rhel",
                "infrastructure_type": "simulation",
                "is_active": True,
            },
        )
        scenario.lab_mode = "simulation"
        scenario.infrastructure_type = "simulation"
        scenario.save(update_fields=["lab_mode", "infrastructure_type"])

        campaign = InterviewCampaign.objects.create(user=user, title="Test", profile_snapshot={})
        round_obj = InterviewRound.objects.create(
            campaign=campaign,
            round_number=1,
            round_type="practical",
            title="Practical",
            status="in_progress",
        )
        from apps.interviews.models import InterviewMessage

        InterviewMessage.objects.create(
            round=round_obj,
            role="interviewer",
            message_type="practical",
            content="Start the lab",
            metadata={"practical_config": {"scenario_slug": "sim-rhel-ssh-stop"}},
        )

        with patch("apps.interviews.services.practical_lab.start_lab_session") as mock_start, patch(
            "apps.labs.start_gates.lab_start_block_reason",
            return_value=None,
        ):
            session = LabSession.objects.create(
                user=user,
                scenario=scenario,
                status="RUNNING",
                provider="simulation",
            )
            mock_start.return_value = session

            result = pl.start_practical_lab(user, round_obj)

        self.assertNotIn("error", result, result)
        session = LabSession.objects.get(id=result["session_id"])
        self.assertEqual(session.provider, "simulation")
        mock_start.assert_called_once()

    def _create_user(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_user(username="labuser", password="x")
