"""Scenario consoles / lab_servers survive serializers."""

from django.test import TestCase

from apps.question_bank.models import Scenario, Technology
from apps.question_bank.serializers import ScenarioListSerializer


class ScenarioConsolesSerializerTests(TestCase):
    def test_list_serializer_exposes_consoles_and_lab_servers(self):
        tech = Technology.objects.create(name="Azure", slug="azure-consoles-test")
        scenario = Scenario.objects.create(
            title="Attach disk",
            slug="azure-consoles-api-test",
            technology=tech,
            consoles=["azure", "terminal"],
            lab_servers=[
                {
                    "id": "primary",
                    "role": "primary",
                    "hostname": "vm-web01",
                    "persona": "azure",
                    "appears_in": ["azure", "terminal"],
                }
            ],
        )
        data = ScenarioListSerializer(scenario).data
        self.assertEqual(data["consoles"], ["azure", "terminal"])
        self.assertEqual(data["lab_servers"][0]["hostname"], "vm-web01")
