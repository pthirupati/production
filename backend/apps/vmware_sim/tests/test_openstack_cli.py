"""Tests for the `openstack` CLI surface over the OpenStack engine.

The CLI must be a true alias for the Horizon click actions: solving a lab by
typing the command has to clear the same `broken` flag the dashboard clears,
and an unrecognized command has to fail loudly rather than no-op.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import openstack_engine as oe


class OpenStackCliBaseTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "", *, login: bool = True) -> str:
        sid = f"test-os-cli-{slug or 'plain'}"
        oe.drop_session(sid)
        oe.get_state(sid, slug)
        if login:
            oe.apply_action(sid, "login", {"user": "admin"})
        return sid


class CliParsingTests(OpenStackCliBaseTest):
    def test_unknown_object_is_a_nonzero_error(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack frobnicate list")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)
        self.assertIn("frobnicate", res["stderr"])

    def test_unknown_subcommand_is_a_nonzero_error(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack server frobnicate web-01")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_requires_authentication(self):
        sid = self._session(login=False)
        res = oe.run_command(sid, "openstack server list")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_leading_binary_name_is_optional(self):
        sid = self._session()
        with_prefix = oe.run_command(sid, "openstack server list")
        without_prefix = oe.run_command(sid, "server list")
        self.assertTrue(with_prefix["ok"])
        self.assertEqual(with_prefix["stdout"], without_prefix["stdout"])

    def test_flag_forms_are_equivalent(self):
        positionals, opts = oe._parse_cli_opts(["create", "app-1", "--flavor=m1.large", "--image", "rhel-9"])
        self.assertEqual(positionals, ["create", "app-1"])
        self.assertEqual(opts["flavor"], "m1.large")
        self.assertEqual(opts["image"], "rhel-9")

    def test_dashed_flags_normalize_to_payload_keys(self):
        _, opts = oe._parse_cli_opts(["--dst-port", "8080", "--remote-ip", "10.0.0.0/8"])
        self.assertEqual(opts["dst_port"], "8080")
        self.assertEqual(opts["remote_ip"], "10.0.0.0/8")


class CliReadCommandTests(OpenStackCliBaseTest):
    def test_server_list_reflects_engine_state_not_a_static_table(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack server list")
        self.assertTrue(res["ok"])
        self.assertIn("web-01", res["stdout"])

        # A server created through the CLI must show up in the next listing.
        oe.run_command(sid, "openstack server create app-02 --flavor m1.small")
        res2 = oe.run_command(sid, "openstack server list")
        self.assertIn("app-02", res2["stdout"])

    def test_server_show_unknown_server_errors(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack server show nope-99")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_volume_and_network_and_flavor_listings(self):
        sid = self._session()
        self.assertIn("vol-web-data", oe.run_command(sid, "openstack volume list")["stdout"])
        self.assertIn("private", oe.run_command(sid, "openstack network list")["stdout"])
        self.assertIn("m1.medium", oe.run_command(sid, "openstack flavor list")["stdout"])
        self.assertIn("cirros-0.6.2", oe.run_command(sid, "openstack image list")["stdout"])


class CliClearsBrokenFlagTests(OpenStackCliBaseTest):
    """The whole point of the CLI: it must be gradeable, not decorative."""

    def test_start_instance_via_cli_clears_stopped_flag(self):
        sid = self._session("openstack-power-restore")
        state = oe.get_state(sid, "openstack-power-restore")["state"]
        self.assertTrue(state["broken"].get("instance_stopped"))
        ok, msg = oe.validate_openstack_lab(sid, "openstack-power-restore")
        self.assertFalse(ok)
        self.assertIn("instance_stopped", msg)

        res = oe.run_command(sid, "openstack server start web-01")
        self.assertTrue(res["ok"], res)

        after = oe.get_state(sid)["state"]
        self.assertEqual(after["instances"][0]["status"], "ACTIVE")
        self.assertFalse(after.get("broken", {}).get("instance_stopped"))
        ok2, msg2 = oe.validate_openstack_lab(sid, "openstack-power-restore")
        self.assertTrue(ok2, msg2)

    def test_attach_volume_via_cli_matches_click_action(self):
        sid = self._session("openstack-volume-attach")
        self.assertTrue(
            oe.get_state(sid, "openstack-volume-attach")["state"]["broken"].get("volume_unattached")
        )
        res = oe.run_command(sid, "openstack server add volume web-01 vol-web-data --device /dev/vdc")
        self.assertTrue(res["ok"], res)

        after = oe.get_state(sid)["state"]
        vol = after["volumes"][0]
        self.assertEqual(vol["status"], "in-use")
        self.assertEqual(vol["device"], "/dev/vdc")
        self.assertFalse(after.get("broken", {}).get("volume_unattached"))
        ok, msg = oe.validate_openstack_lab(sid, "openstack-volume-attach")
        self.assertTrue(ok, msg)

    def test_detach_volume_via_cli(self):
        sid = self._session("openstack-volume-attach")
        oe.run_command(sid, "openstack server add volume web-01 vol-web-data")
        oe.run_command(sid, "openstack server remove volume web-01 vol-web-data")
        vol = oe.get_state(sid)["state"]["volumes"][0]
        self.assertEqual(vol["status"], "available")
        self.assertIsNone(vol["attached_to"])

    def test_create_instance_via_cli_uses_requested_flavor(self):
        sid = self._session("openstack-launch")
        self.assertTrue(
            oe.get_state(sid, "openstack-launch")["state"]["broken"].get("needs_instance")
        )
        res = oe.run_command(sid, "openstack server create app-02 --flavor m1.large --image rhel-9")
        self.assertTrue(res["ok"], res)
        state = oe.get_state(sid)["state"]
        inst = next(i for i in state["instances"] if i["name"] == "app-02")
        self.assertEqual(inst["flavor"], "m1.large")
        self.assertEqual(inst["image"], "rhel-9")
        self.assertFalse(state.get("broken", {}).get("needs_instance"))
        # BUILD→ACTIVE transition still in flight — grader must wait, not pass early.
        ok_busy, msg_busy = oe.validate_openstack_lab(sid, "openstack-launch")
        self.assertFalse(ok_busy)
        self.assertIn("transition", msg_busy.lower())

    def test_create_instance_rejects_unknown_flavor(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack server create app-03 --flavor m1.enormous")
        self.assertFalse(res["ok"])

    def test_resize_requires_flavor_flag(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack server resize web-01")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_security_group_rule_create_adds_rule(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack security group rule create web --protocol tcp --dst-port 8080")
        self.assertTrue(res["ok"], res)
        sg = next(s for s in oe.get_state(sid)["state"]["security_groups"] if s["name"] == "web")
        self.assertTrue(any(r.get("port_min") == 8080 for r in sg["rules"]))

    def test_floating_ip_associate_via_cli(self):
        sid = self._session()
        res = oe.run_command(sid, "openstack floating ip set 172.24.4.100 --port web-01")
        self.assertTrue(res["ok"], res)
        inst = oe.get_state(sid)["state"]["instances"][0]
        self.assertEqual(inst.get("floating_ip"), "172.24.4.100")
