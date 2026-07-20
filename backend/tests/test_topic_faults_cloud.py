"""Topic faults must plant cloud config for cloud academies — not host nginx/firewalld."""
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.topic_faults import apply_topic_fault
from apps.labs.provisioner.simulation.validation import validate_simulation_state

CLOUD_CHECK = "systemctl is-failed --quiet 2>/dev/null; test $? -ne 0"


class TopicFaultCloudOrderingTest(SimpleTestCase):
    def test_gcp_firewall_rules_plants_gcp_config_not_firewalld(self):
        slug = "academy-gcp-004-troubleshoot-firewall-rules"
        state = RHELOSState()
        state.scenario_slug = slug
        self.assertTrue(apply_topic_fault(slug, state))
        self.assertIn("/opt/gcp/config", state.vfs)
        fw = state.services.get("firewalld")
        self.assertTrue(fw is None or fw.active != "failed")
        ok, _ = validate_simulation_state(state, CLOUD_CHECK)
        self.assertFalse(ok)

    def test_azure_nsg_plants_azure_config(self):
        slug = "academy-azure-003-operate-nsg"
        state = RHELOSState()
        state.scenario_slug = slug
        self.assertTrue(apply_topic_fault(slug, state))
        self.assertIn("/opt/azure/config", state.vfs)
        ok, _ = validate_simulation_state(state, CLOUD_CHECK)
        self.assertFalse(ok)

    def test_openstack_nova_plants_openstack_config(self):
        slug = "academy-openstack-001-learn-nova"
        state = RHELOSState()
        state.scenario_slug = slug
        self.assertTrue(apply_topic_fault(slug, state))
        self.assertIn("/opt/openstack/clouds.yaml", state.vfs)
        ok, _ = validate_simulation_state(state, CLOUD_CHECK)
        self.assertFalse(ok)

    def test_host_firewall_lab_still_breaks_firewalld(self):
        slug = "academy-networking-003-operate-firewall"
        state = RHELOSState()
        state.scenario_slug = slug
        self.assertTrue(apply_topic_fault(slug, state))
        fw = state.services.get("firewalld")
        self.assertIsNotNone(fw)
        self.assertEqual(fw.active, "failed")
