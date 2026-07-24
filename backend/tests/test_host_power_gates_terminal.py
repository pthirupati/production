"""When the linked host is powered off, the Lab Server terminal must refuse cmds."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.server_identity import set_power, upsert_server
from apps.labs.provisioner.simulation.vmware_bridge import set_terminal_link_state
from apps.labs.provisioner.simulation import azure_bridge


class HostPowerGatesTerminalTests(SimpleTestCase):
    def test_identity_power_off_blocks_shell(self):
        sid = "test-power-gate-1"
        upsert_server(
            sid,
            {
                "id": "srv-1",
                "hostname": "web-01",
                "power": "on",
                "tags": {"role": "primary"},
            },
            source="test",
        )
        shell = RHELShell(scenario_slug="sim-broken-nginx")
        shell.state.session_id = sid
        out = shell.run("uname -a")
        self.assertNotIn("powered off", out.lower())

        set_power(sid, "srv-1", "off", source="test")
        blocked = shell.run("uname -a")
        self.assertIn("powered off", blocked.lower())
        self.assertEqual(shell.state.last_exit_code, 255)

    def test_shell_poweroff_sticks(self):
        shell = RHELShell(scenario_slug="sim-broken-nginx")
        shell.state.session_id = "test-power-gate-2"
        shell.run("poweroff")
        blocked = shell.run("echo still-here")
        self.assertIn("powered off", blocked.lower())

    def test_azure_stop_event_not_cleared_by_stale_primary_on(self):
        """Bridge stop must win even if a different identity host is still on."""
        sid = "test-power-gate-azure"
        upsert_server(
            sid,
            {
                "id": "lab-primary",
                "hostname": "lab-01",
                "power": "on",
                "tags": {"role": "primary"},
            },
            source="test",
        )
        azure_bridge.record_vm_power(sid, "stop")
        shell = RHELShell(scenario_slug="sim-broken-nginx")
        shell.state.session_id = sid
        blocked = shell.run("hostname")
        self.assertIn("powered off", blocked.lower())

    def test_non_primary_floor_server_off_blocks_when_primary_synced(self):
        """Datacenter BMC sync also powers off the lab primary — terminal freezes."""
        sid = "test-power-gate-floor"
        upsert_server(
            sid,
            {
                "id": "lab-primary",
                "hostname": "lab-01",
                "power": "off",
                "tags": {"role": "primary"},
            },
            source="test",
        )
        upsert_server(
            sid,
            {
                "id": "rack-srv-2",
                "hostname": "esxi-02",
                "power": "off",
                "tags": {"role": "esxi_host"},
            },
            source="datacenter",
        )
        shell = RHELShell(scenario_slug="sim-broken-nginx")
        shell.state.session_id = sid
        blocked = shell.run("uptime")
        self.assertIn("powered off", blocked.lower())

    def test_unrelated_floor_server_off_does_not_block_primary_on(self):
        sid = "test-power-gate-unrelated"
        upsert_server(
            sid,
            {
                "id": "lab-primary",
                "hostname": "lab-01",
                "power": "on",
                "tags": {"role": "primary"},
            },
            source="test",
        )
        upsert_server(
            sid,
            {
                "id": "other-rack",
                "hostname": "spare-01",
                "power": "off",
                "tags": {"role": "spare"},
            },
            source="datacenter",
        )
        shell = RHELShell(scenario_slug="sim-broken-nginx")
        shell.state.session_id = sid
        shell.state.hostname = "lab-01"
        out = shell.run("uptime")
        self.assertNotIn("powered off", out.lower())

    def test_vmware_terminal_link_disconnected_blocks(self):
        sid = "test-power-gate-vmware"
        upsert_server(
            sid,
            {
                "id": "vm-1",
                "hostname": "guest-01",
                "power": "on",
                "tags": {"role": "primary"},
            },
            source="test",
        )
        set_terminal_link_state(sid, "disconnected")
        shell = RHELShell(scenario_slug="sim-broken-nginx")
        shell.state.session_id = sid
        blocked = shell.run("whoami")
        self.assertIn("powered off", blocked.lower())
