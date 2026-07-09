"""Tests for lab infrastructure type resolution and interview practical labs."""

import pytest
from unittest.mock import MagicMock, patch

from apps.labs.infra import lab_infra_type


def _scenario(**kwargs):
    s = MagicMock()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


class TestLabInfraType:
    def test_simulation_lab_mode(self):
        s = _scenario(lab_mode="simulation", infrastructure_type="docker")
        assert lab_infra_type(s) == "simulation"

    def test_sim_slug_fallback(self):
        s = _scenario(lab_mode="docker", slug="sim-rhel-ssh-stop", infrastructure_type="docker")
        assert lab_infra_type(s) == "simulation"

    def test_terraform_simulation_type(self):
        s = _scenario(lab_mode="docker", simulation_type="terraform", infrastructure_type="docker")
        assert lab_infra_type(s) == "simulation"

    def test_plain_docker(self):
        s = _scenario(lab_mode="docker", slug="nginx-down", infrastructure_type="docker")
        assert lab_infra_type(s) == "docker"


@pytest.mark.django_db
class TestInterviewPracticalLab:
    def test_start_uses_simulation_not_docker(self, django_user_model):
        from apps.interviews.models import InterviewCampaign, InterviewRound
        from apps.interviews.services import practical_lab as pl
        from apps.labs.models import LabSession
        from apps.question_bank.models import Scenario, Technology

        user = django_user_model.objects.create_user(username="labuser", password="x")
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
            title="Practical",
            status="in_progress",
        )

        with patch("apps.labs.sessions.get_provisioner") as mock_gp:
            prov = MagicMock()
            prov.provision.return_value = ("sim-abc123", "sim-rhel-ssh-stop")
            mock_gp.return_value = prov

            result = pl.start_practical_lab(user, round_obj)

        assert result.get("session_id")
        session = LabSession.objects.get(id=result["session_id"])
        assert session.provider == "simulation"
        mock_gp.assert_called_with("simulation")
