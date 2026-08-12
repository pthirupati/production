"""Cable topology derived from switch port maps (audit D14)."""

from django.test import SimpleTestCase

from apps.vmware_sim.datacenter_network_storage import build_cable_topology, enrich_network


class CableTopologyTests(SimpleTestCase):
    def test_up_ports_with_peers_become_links(self):
        network = {
            "switches": [{
                "id": "sw-core-01",
                "ports": [
                    {"port": 1, "status": "up", "speed": "10G", "connected_to": "srv-r01-u12"},
                    {"port": 6, "status": "down", "speed": "10G", "connected_to": None},
                    {"port": 8, "status": "up", "speed": "40G", "connected_to": "sw-agg-01"},
                ],
            }, {
                "id": "sw-agg-01",
                "ports": [],
            }],
        }
        links = build_cable_topology(network)
        ids = {l["id"] for l in links}
        self.assertTrue(any("srv-r01-u12" in i for i in ids))
        self.assertTrue(any("sw-agg-01" in i for i in ids))
        fiber = next(l for l in links if l["to"] == "sw-agg-01")
        self.assertEqual(fiber["media"], "fiber")
        access = next(l for l in links if l["to"] == "srv-r01-u12")
        self.assertEqual(access["role"], "access")

    def test_enrich_network_attaches_topology(self):
        network = {
            "switches": [{
                "id": "sw-1",
                "model": "Arista 7050",
                "ports": [{"port": 1, "status": "up", "speed": "10G", "connected_to": "host-a", "vlan": 10}],
            }],
        }
        enrich_network(network)
        self.assertTrue(network["cable_topology"])
        self.assertEqual(network["cable_topology"][0]["to"], "host-a")
