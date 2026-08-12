"""``linked_tutorial`` is a real Scenario field, not a dropped YAML key (audit L1071).

Before this field existed the scenario catalog carried ``linked_tutorial`` in YAML,
the validator even fabricated a placeholder for it, but nothing persisted it — so the
"read the theory first" link could never be rendered. These tests pin both the model
field and its serializer exposure so the value cannot silently go dead again.
"""

from django.test import TestCase

from apps.question_bank.models import Scenario, Technology
from apps.question_bank.serializers import (
    ScenarioAdminSerializer,
    ScenarioDetailSerializer,
)


class ScenarioLinkedTutorialTests(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="AWS", slug="aws-linked-tutorial-test")

    def _scenario(self, **kwargs):
        return Scenario.objects.create(
            title="Recover the EBS volume",
            slug=kwargs.pop("slug", "aws-linked-tutorial-test-1"),
            technology=self.tech,
            **kwargs,
        )

    def test_field_persists_a_course_slug(self):
        self._scenario(linked_tutorial="aws-cloud-zero-hero")
        stored = Scenario.objects.get(slug="aws-linked-tutorial-test-1")
        self.assertEqual(stored.linked_tutorial, "aws-cloud-zero-hero")

    def test_defaults_to_blank_not_null(self):
        # Blank means "no tutorial linked yet". It must never be None, because
        # callers render it straight into a URL.
        stored = self._scenario(slug="aws-linked-tutorial-test-2")
        stored.refresh_from_db()
        self.assertEqual(stored.linked_tutorial, "")

    def test_detail_serializer_exposes_linked_tutorial(self):
        scenario = self._scenario(
            slug="aws-linked-tutorial-test-3", linked_tutorial="aws-cloud-zero-hero"
        )
        data = ScenarioDetailSerializer(scenario).data
        self.assertEqual(data["linked_tutorial"], "aws-cloud-zero-hero")

    def test_admin_serializer_can_write_linked_tutorial(self):
        # Admin CRUD is the only surface that edits the link, so it must accept
        # the field on write, not merely echo it back.
        scenario = self._scenario(slug="aws-linked-tutorial-test-4")
        serializer = ScenarioAdminSerializer(
            scenario, data={"linked_tutorial": "linux-sysadmin-zero-hero"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        scenario.refresh_from_db()
        self.assertEqual(scenario.linked_tutorial, "linux-sysadmin-zero-hero")
