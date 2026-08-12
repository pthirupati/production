"""Acceptance checklist builder (audit X7c)."""

from django.test import SimpleTestCase

from apps.labs.acceptance_checklist import build_acceptance_checklist


class AcceptanceChecklistTests(SimpleTestCase):
    def test_all_done_when_passed(self):
        items = build_acceptance_checklist(
            ["Fix nginx", "Open port 80"],
            passed=True,
        )
        self.assertEqual(len(items), 2)
        self.assertTrue(all(i["done"] for i in items))

    def test_keyword_heuristic_ticks_partial(self):
        items = build_acceptance_checklist(
            ["Restart the nginx service", "Open firewall port 443"],
            passed=False,
            output="nginx service is active and running",
        )
        self.assertTrue(items[0]["done"])
        self.assertFalse(items[1]["done"])

    def test_empty_objectives(self):
        self.assertEqual(build_acceptance_checklist(None, passed=True), [])
