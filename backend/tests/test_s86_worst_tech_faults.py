"""G3: 9 worst academy techs get topic-native faults, not nginx."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.scenario_presets import (
    apply_scenario_preset,
    _topic_fault_wins_over_academy_preset,
)
from apps.labs.provisioner.simulation.topic_faults import apply_topic_fault


class WorstTechFaultsTest(SimpleTestCase):
    def test_topic_wins_prefixes(self):
        self.assertTrue(_topic_fault_wins_over_academy_preset("academy-netapp-001-learn-svm"))
        self.assertTrue(_topic_fault_wins_over_academy_preset("academy-datacenter-002-build-pdu"))
        self.assertFalse(_topic_fault_wins_over_academy_preset("academy-linux-001-learn-users-groups"))

    def test_netapp_fault_not_nginx(self):
        state = RHELOSState()
        self.assertTrue(apply_topic_fault("academy-netapp-001-learn-svm", state))
        self.assertIn("netapp-ontap", state.services)
        self.assertEqual(state.services["netapp-ontap"].active, "failed")
        self.assertNotIn("nginx", state.services)

    def test_academy_preset_skips_nginx_for_netapp(self):
        state = RHELOSState()
        apply_scenario_preset("academy-netapp-001-learn-svm", state)
        self.assertNotEqual(
            getattr(state.services.get("nginx"), "active", None),
            "failed",
            "nginx must not be the planted break for NetApp academy labs",
        )
        self.assertIn("netapp-ontap", state.services)

    def test_soc_and_otel_and_mesh(self):
        for slug, unit in (
            ("academy-soc-001-learn-siem", "wazuh-agent"),
            ("academy-opentelemetry-001-learn-traces", "otelcol"),
            ("academy-service-mesh-001-learn-sidecar", "istiod"),
        ):
            state = RHELOSState()
            self.assertTrue(apply_topic_fault(slug, state), slug)
            self.assertIn(unit, state.services, slug)
            self.assertEqual(state.services[unit].active, "failed", slug)

    def test_datacenter_and_dellemc(self):
        state = RHELOSState()
        self.assertTrue(apply_topic_fault("academy-datacenter-002-build-pdu", state))
        self.assertIn("pdu-monitor", state.services)

        state = RHELOSState()
        self.assertTrue(apply_topic_fault("academy-dellemc-001-learn-storage-pools", state))
        self.assertIn("unisphere", state.services)

    def test_commvault_and_ai_infra(self):
        state = RHELOSState()
        self.assertTrue(apply_topic_fault("academy-commvault-001-learn-backup", state))
        self.assertIn("commvault", state.services)
        self.assertNotIn("nginx", state.services)

        state = RHELOSState()
        self.assertTrue(apply_topic_fault("academy-ai-infra-001-learn-gpu-nodes", state))
        self.assertFalse(state.gpu_healthy)
        self.assertTrue(any("Xid" in line or "NVRM" in line for line in (state.dmesg_extra or [])))

        state = RHELOSState()
        self.assertTrue(apply_topic_fault("academy-ai-infra-010-operate-cluster", state))
        self.assertIn("nvidia-device-plugin", state.services)
