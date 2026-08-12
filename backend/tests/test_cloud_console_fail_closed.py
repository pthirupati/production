"""Regression: azure/gcp console graders must fail CLOSED on an unseeded world.

Both `_apply_preset` matchers are keyword-driven (resize/nsg|firewall/disk/power).
Replaying them over the scenarios that actually ship leaves 117 of 147
academy-azure-* and 117 of 147 academy-gcp-* slugs with no `broken` key at all —
slugs like "academy-azure-001-learn-virtual-machines" match none of the keywords.

Before this guard, `validate_*_lab` treated "no broken markers" as success, so
those 234 labs returned (True, "... validation passed") on the first Check with
zero learner actions — completion XP for pressing a button. The console has no
objective to grade for an unmapped slug, so it must defer to the terminal
sentinel path instead of passing.
"""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.labs.models import LabSession
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
from apps.vmware_sim import azure_engine, gcp_engine
from tests import AuthMixin, ScenarioMixin

CHECK_SH = (
    "#!/bin/bash\n"
    "systemctl is-failed --quiet 2>/dev/null; test $? -ne 0\n"
    "exit 0\n"
)

# Slugs that match no _apply_preset keyword — the 117+117 majority case.
UNSEEDED = [
    ("academy-azure-001-learn-virtual-machines", "azure"),
    ("academy-azure-004-troubleshoot-vnet", "azure"),
    ("academy-gcp-001-learn-compute-engine", "gcp"),
    ("academy-gcp-005-production-iam", "gcp"),
]


class CloudConsoleFailClosedTests(TestCase, AuthMixin, ScenarioMixin):
    def _provision(self, slug: str, sim_type: str):
        tech = self.create_tech(name=f"Tech {sim_type} {slug[-8:]}")
        scenario = self.create_scenario(
            tech=tech,
            slug=slug,
            simulation_type=sim_type,
            lab_mode="simulation",
            validation_script=CHECK_SH,
        )
        lab = LabSession.objects.create(
            user=self.user, scenario=scenario, status="RUNNING"
        )
        session = MagicMock()
        session.id = lab.id
        session.scenario = scenario
        prov = SimulationProvisioner()
        resource_id, _ = prov.provision(session)
        LabSession.objects.filter(pk=lab.pk).update(container_id=resource_id)
        return prov, resource_id

    def setUp(self):
        self.user = self.create_user()

    def test_unseeded_slug_does_not_auto_pass(self):
        """A freshly provisioned lab with no learner action must never pass."""
        for slug, sim_type in UNSEEDED:
            with self.subTest(slug=slug):
                prov, resource_id = self._provision(slug, sim_type)
                try:
                    passed, msg = prov.run_validation(resource_id, CHECK_SH, slug)
                    self.assertFalse(passed, f"{slug} auto-passed with no work: {msg}")
                    # And the learner gets a pointer to the real objective, not a
                    # dead-end NO_VALIDATION_SCRIPT.
                    self.assertIn("broken configuration", msg)
                finally:
                    prov.terminate(resource_id)

    def test_seeded_slug_still_fails_then_passes(self):
        """The 30 keyword-matched slugs per provider must remain gradeable."""
        cases = [
            (azure_engine, "academy-azure-002-troubleshoot-nsg-ssh",
             azure_engine.validate_azure_lab, "Azure validation passed"),
            (gcp_engine, "academy-gcp-002-troubleshoot-firewall-ssh",
             gcp_engine.validate_gcp_lab, "GCP validation passed"),
        ]
        for engine, slug, validate, ok_msg in cases:
            with self.subTest(slug=slug):
                session_id = f"failclosed-{slug}"
                engine.drop_session(session_id)
                engine._ensure(session_id, slug)

                passed, msg = validate(session_id, slug)
                self.assertFalse(passed, f"{slug} passed before any fix: {msg}")

                # Resolving the seeded objective must still award the pass.
                entry = engine._load(session_id)
                entry["state"]["broken"] = {}
                engine._save(session_id, entry)

                passed, msg = validate(session_id, slug)
                self.assertTrue(passed, f"{slug} unpassable after fix: {msg}")
                self.assertEqual(msg, ok_msg)
                engine.drop_session(session_id)
