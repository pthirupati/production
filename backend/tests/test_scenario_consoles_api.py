"""Scenario consoles / lab_servers survive detail serializer; stay off list payload."""

from django.test import TestCase

from apps.question_bank.models import Scenario, Technology
from apps.question_bank.serializers import ScenarioDetailSerializer, ScenarioListSerializer


class ScenarioConsolesSerializerTests(TestCase):
    def test_detail_serializer_exposes_consoles_and_lab_servers(self):
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
        data = ScenarioDetailSerializer(scenario).data
        self.assertEqual(data["consoles"], ["azure", "terminal"])
        self.assertEqual(data["lab_servers"][0]["hostname"], "vm-web01")

    def test_list_serializer_omits_runtime_heavy_fields(self):
        tech = Technology.objects.create(name="Azure", slug="azure-consoles-list-test")
        scenario = Scenario.objects.create(
            title="Attach disk list",
            slug="azure-consoles-list-api-test",
            technology=tech,
            consoles=["azure"],
            lab_servers=[{"id": "primary", "hostname": "vm-web01"}],
            blocked_commands=["rm"],
        )
        data = ScenarioListSerializer(scenario).data
        self.assertNotIn("consoles", data)
        self.assertNotIn("lab_servers", data)
        self.assertNotIn("blocked_commands", data)
