"""Inventory-scoped ICMP/SSH reachability (no open-internet fake replies)."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.reachability import (
    resolve_icmp_target,
    ssh_peer_allowed,
    _same_l3_family,
)
from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.shell import StreamedCommandResult


class PlatformIsolationTests(SimpleTestCase):
    def test_same_cloud_ok_cross_cloud_denied(self):
        self.assertTrue(_same_l3_family("aws", "aws"))
        self.assertFalse(_same_l3_family("aws", "azure"))
        self.assertFalse(_same_l3_family("gcp", "aws"))
        self.assertTrue(_same_l3_family("maas", "lxd"))
        self.assertTrue(_same_l3_family("vyos", "maas"))
        self.assertFalse(_same_l3_family("aws", "maas"))


class ResolveIcmpTests(SimpleTestCase):
    def test_localhost_and_gateway(self):
        ip, err = resolve_icmp_target(
            host="127.0.0.1",
            host_ips={},
            host_names={},
            iface_addrs=["10.0.0.10/24"],
            session_id=None,
        )
        self.assertEqual(ip, "127.0.0.1")
        self.assertIsNone(err)
        ip, err = resolve_icmp_target(
            host="10.0.0.1",
            host_ips={},
            host_names={},
            iface_addrs=["10.0.0.10/24"],
            session_id=None,
        )
        self.assertEqual(ip, "10.0.0.1")
        self.assertIsNone(err)

    def test_random_public_unreachable(self):
        ip, err = resolve_icmp_target(
            host="8.8.8.8",
            host_ips={},
            host_names={},
            iface_addrs=["10.0.0.10/24"],
            session_id=None,
        )
        self.assertIsNone(ip)
        self.assertIn("Host Unreachable", err or "")

    def test_empty_subnet_host_unreachable(self):
        ip, err = resolve_icmp_target(
            host="10.0.0.77",
            host_ips={},
            host_names={},
            iface_addrs=["10.0.0.10/24"],
            session_id=None,
        )
        self.assertIsNone(ip)
        self.assertIn("Host Unreachable", err or "")


class PingStreamPacingTests(SimpleTestCase):
    def test_ping_returns_streamed_interval(self):
        sh = RHELShell()
        out = sh.run("ping -c 3 10.0.0.1")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertEqual(out.delay_s, 1.0)
        self.assertGreaterEqual(len(out.lines), 4)
        self.assertIn("3 packets transmitted, 3 received", out)


class SshPeerGateTests(SimpleTestCase):
    def test_ssh_peer_allowed_noop_without_session(self):
        row, err = ssh_peer_allowed(host="10.0.0.10", session_id=None)
        self.assertIsNone(row)
        self.assertIsNone(err)
