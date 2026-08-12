"""§C1 — dangling *-fundamentals refs resolve to real course_slugs."""

from django.test import SimpleTestCase

from apps.question_bank.linked_tutorial_map import (
    LINKED_TUTORIAL_MAP,
    resolve_linked_tutorial,
)


class LinkedTutorialMapTests(SimpleTestCase):
    def test_aws_fundamentals_maps(self):
        self.assertEqual(
            resolve_linked_tutorial("aws-fundamentals"),
            "aws-cloud-zero-hero",
        )

    def test_already_real_slug_passthrough(self):
        self.assertEqual(
            resolve_linked_tutorial("aws-cloud-zero-hero"),
            "aws-cloud-zero-hero",
        )

    def test_no_course_techs_blank(self):
        for dangling in ("netapp-fundamentals", "commvault-fundamentals", "dellemc-fundamentals"):
            self.assertEqual(resolve_linked_tutorial(dangling), "")

    def test_blank_stays_blank(self):
        self.assertEqual(resolve_linked_tutorial(""), "")
        self.assertEqual(resolve_linked_tutorial(None), "")

    def test_map_covers_audit_table(self):
        # Every dangling key from the audit table must be present.
        required = {
            "aws-fundamentals", "linux-fundamentals", "gpu-fundamentals",
            "netapp-fundamentals", "commvault-fundamentals", "dellemc-fundamentals",
        }
        self.assertTrue(required.issubset(LINKED_TUTORIAL_MAP))
