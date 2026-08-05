"""VyOS NetworkingState depth — configure/commit/firewall/BGP/dashboard."""

from django.test import TestCase

from apps.labs.provisioner.simulation.networking_state import NetworkingState
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


class VyosNetworkingDepthTests(TestCase):
    def test_firewall_set_commit_show(self):
        n = NetworkingState("ai-infra-vyos-firewall")
        n.vyos_enter_configure()
        n.vyos_set("firewall name PXE default-action drop")
        n.vyos_set("firewall name PXE rule 10 action accept")
        n.vyos_set("firewall name PXE rule 10 protocol udp")
        out = n.vyos_commit()
        self.assertIn("Commit complete", out)
        fw = n.show_firewall()
        self.assertIn("PXE", fw)
        self.assertIn("accept", fw)
        self.assertIn("udp", fw)

    def test_commit_rejects_bgp_neighbor_without_remote_as(self):
        n = NetworkingState("ai-infra-vyos-bgp")
        n.vyos_enter_configure()
        n.vyos_set("protocols bgp 65001 neighbor 10.64.1.50")
        err = n.vyos_commit()
        self.assertIn("Commit failed", err)
        self.assertIn("remote-as", err.lower())
        # With remote-as it should succeed
        n.vyos_set("protocols bgp 65001 neighbor 10.64.1.50 remote-as 65050")
        ok = n.vyos_commit()
        self.assertIn("Commit complete", ok)

    def test_rollback_restores(self):
        n = NetworkingState("ai-infra-vyos-bgp")
        n.vyos_enter_configure()
        before_tree = n.vyos_running_tree
        before = n.vyos_running
        n.vyos_set("interfaces ethernet eth2 address 10.64.99.1/24")
        self.assertIn("Commit complete", n.vyos_commit())
        self.assertIn("eth2", n.show_interfaces())
        rb = n.vyos_rollback(1)
        self.assertIn("Rollback complete", rb)
        self.assertEqual(n.vyos_running, before)
        self.assertNotIn("eth2", n.show_interfaces())
        # Tree should no longer list eth2
        eth = (n.vyos_running_tree.get("interfaces") or {}).get("ethernet") or {}
        self.assertNotIn("eth2", eth)
        self.assertEqual(
            set((before_tree.get("interfaces") or {}).get("ethernet", {}).keys()),
            set(eth.keys()),
        )

    def test_to_dashboard_keys(self):
        n = NetworkingState("ai-infra-vyos")
        dash = n.to_dashboard()
        for key in (
            "interfaces", "routes", "bgp", "ospf", "firewall",
            "nat", "vrrp", "dhcp_leases", "revisions", "uncommitted",
        ):
            self.assertIn(key, dash, msg=f"missing dashboard key: {key}")
        self.assertTrue(isinstance(dash["interfaces"], list))
        self.assertTrue(len(dash["interfaces"]) >= 2)
        self.assertTrue(isinstance(dash["dhcp_leases"], list))

    def test_discard_resets_candidate(self):
        n = NetworkingState("ai-infra-vyos")
        n.vyos_enter_configure()
        n.vyos_set("interfaces ethernet eth9 description scratch")
        self.assertTrue(n.to_dashboard()["uncommitted"] or n.vyos_candidate != n.vyos_running)
        n.vyos_discard()
        self.assertEqual(n.vyos_candidate, n.vyos_running)
        self.assertFalse(n.to_dashboard()["uncommitted"])

    def test_commit_confirm_and_confirm(self):
        n = NetworkingState("ai-infra-vyos")
        n.vyos_enter_configure()
        n.vyos_set("interfaces ethernet eth3 description confirm-me")
        out = n.vyos_commit_confirm(5)
        self.assertIn("Commit complete", out)
        self.assertIsNotNone(n.commit_confirm_deadline)
        conf = n.vyos_confirm()
        self.assertIn("completed", conf.lower())
        self.assertIsNone(n.commit_confirm_deadline)

    def test_save_load_config_boot(self):
        n = NetworkingState("ai-infra-vyos")
        st = RHELOSState("ai-infra-vyos")
        n.bind_shell(st)
        n.vyos_enter_configure()
        n.vyos_set("interfaces ethernet eth4 description saved")
        n.vyos_commit()
        save_out = n.vyos_save(st)
        self.assertIn("Done", save_out)
        boot = st.read_file("/config/config.boot")
        self.assertIsNotNone(boot)
        self.assertIn("eth4", boot)

    def test_show_commands_from_tree(self):
        n = NetworkingState("ai-infra-vyos")
        n.vyos_enter_configure()
        n.vyos_set("protocols static route 10.99.0.0/16 next-hop 10.64.1.2")
        n.vyos_set("high-availability vrrp group pxe-ha interface eth1")
        n.vyos_set("high-availability vrrp group pxe-ha virtual-address 10.64.12.254")
        n.vyos_set("nat source rule 10 outbound-interface eth1")
        n.vyos_set("nat source rule 10 translation masquerade")
        n.vyos_commit()
        self.assertIn("10.99.0.0/16", n.show_ip_route())
        self.assertIn("MASTER", n.show_vrrp())
        self.assertIn("source", n.show_nat())
        self.assertIn("VyOS", n.show_version())

    def test_edit_up_top(self):
        n = NetworkingState("ai-infra-vyos")
        n.vyos_enter_configure()
        self.assertIn("[edit interfaces ethernet eth0]", n.vyos_edit("interfaces ethernet eth0"))
        self.assertIn("[edit interfaces ethernet]", n.vyos_up())
        self.assertEqual(n.vyos_top(), "[edit]")

    def test_shell_wire_new_verbs(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-007-automation-pxe",
            simulation_type="baremetal",
        )
        self.assertIn("[edit]", str(engine.shell.run("configure")))
        engine.shell.run("set firewall name LAB default-action accept")
        self.assertIn("Commit complete", str(engine.shell.run("commit")))
        fw = str(engine.shell.run("show firewall"))
        self.assertIn("LAB", fw)
        route = str(engine.shell.run("show ip route"))
        self.assertTrue("connected" in route.lower() or "C>*" in route)
        self.assertIn("VyOS", str(engine.shell.run("show version")))
        self.assertIn("Done", str(engine.shell.run("save")))
