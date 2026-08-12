"""Service dependency cascades and computed GPO precedence in windows_engine.

Two previously-inert models are covered:

1. Services carry DependOnService edges, so stopping a parent takes its
   dependents down and starting a child brings its dependencies up.
2. Group Policy resolves through real LSDOU precedence, including Enforced
   links and Block Inheritance, instead of sitting in state as inert data.

The last class re-checks that every shipped Windows preset is still solvable,
because the cascade changes what "stopped" means for the seeded service list.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import windows_engine as we


class WindowsBaseTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "") -> str:
        sid = f"test-win-dep-{slug or 'plain'}"
        we.drop_session(sid)
        we.get_state(sid, slug)
        return sid

    def _world(self, sid: str) -> dict:
        return we._load_session(sid)["state"]["world"]

    def _status(self, sid: str, name: str) -> str:
        return we._find_service(self._world(sid), name)["status"]


class ServiceDependencyTests(WindowsBaseTest):
    def test_stopping_rpc_cascades_to_its_dependents(self):
        sid = self._session()
        res = we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        self.assertTrue(res["ok"], res)

        # Spooler, Server, Workstation and Windows Update all depend on RPC.
        for name in ("Spooler", "LanmanServer", "LanmanWorkstation", "wuauserv"):
            self.assertEqual(self._status(sid, name), "stopped", f"{name} should have cascaded")
        self.assertIn("Spooler", res["stopped_dependents"])

    def test_cascade_is_transitive(self):
        sid = self._session()
        # DNS -> Netlogon -> LanmanWorkstation -> RpcSs, so stopping RPC must
        # reach DNS two hops away.
        we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        self.assertEqual(self._status(sid, "Netlogon"), "stopped")
        self.assertEqual(self._status(sid, "DNS"), "stopped")

    def test_stopping_a_leaf_service_cascades_to_nothing(self):
        sid = self._session()
        res = we.apply_action(sid, "stop_service", {"service": "Spooler", "session_id": sid})
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["stopped_dependents"], [])
        self.assertEqual(self._status(sid, "RpcSs"), "running")

    def test_independent_service_is_untouched_by_a_cascade(self):
        sid = self._session()
        we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        # W32Time declares no dependency on RPC in this world.
        self.assertEqual(self._status(sid, "W32Time"), "running")

    def test_starting_a_child_brings_its_dependencies_up(self):
        sid = self._session()
        we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        self.assertEqual(self._status(sid, "Spooler"), "stopped")

        res = we.apply_action(sid, "start_service", {"service": "Spooler", "session_id": sid})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._status(sid, "RpcSs"), "running")
        self.assertIn("RpcSs", res["started_dependencies"])

    def test_start_is_refused_when_a_dependency_is_disabled(self):
        sid = self._session()
        we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        we.apply_action(sid, "set_startup", {"service": "RpcSs", "startup": "disabled", "session_id": sid})

        res = we.apply_action(sid, "start_service", {"service": "Spooler", "session_id": sid})
        self.assertFalse(res["ok"])
        self.assertIn("dependency", res["error"].lower())
        self.assertEqual(self._status(sid, "Spooler"), "stopped")

    def test_transitive_start_walks_the_whole_chain(self):
        sid = self._session()
        we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        res = we.apply_action(sid, "start_service", {"service": "DNS", "session_id": sid})
        self.assertTrue(res["ok"], res)
        for name in ("RpcSs", "LanmanWorkstation", "Netlogon", "DNS"):
            self.assertEqual(self._status(sid, name), "running", f"{name} should be running")

    def test_restart_bounces_dependents_back_up(self):
        sid = self._session()
        res = we.apply_action(sid, "restart_service", {"service": "RpcSs", "session_id": sid})
        self.assertTrue(res["ok"], res)
        # A restart takes dependents down and brings them back, so the world
        # ends up where it started rather than silently orphaning them.
        self.assertEqual(self._status(sid, "Spooler"), "running")
        self.assertEqual(self._status(sid, "RpcSs"), "running")

    def test_repeated_stop_reports_no_phantom_cascade(self):
        sid = self._session()
        we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        again = we.apply_action(sid, "stop_service", {"service": "RpcSs", "session_id": sid})
        self.assertEqual(again["stopped_dependents"], [])


class GpoPrecedenceTests(WindowsBaseTest):
    DOMAIN = we.DEFAULT_DOMAIN

    def _link(self, sid: str, gpo: str, ou: str) -> dict:
        return we.apply_action(sid, "link_gpo", {"gpo": gpo, "ou": ou, "session_id": sid})

    def _rsop(self, sid: str, target: str = "") -> dict:
        res = we.apply_action(sid, "rsop", {"target": target, "session_id": sid})
        self.assertTrue(res["ok"], res)
        return res["rsop"]

    def test_unlinked_gpo_does_not_apply(self):
        sid = self._session()
        rsop = self._rsop(sid, self.DOMAIN)
        # rdp-lockdown ships with no links.
        self.assertNotIn("rdp-lockdown", [g["id"] for g in rsop["applied"]])
        self.assertIn("rdp-lockdown", [g["id"] for g in rsop["filtered"]])

    def test_disabled_gpo_does_not_apply(self):
        sid = self._session()
        we.apply_action(sid, "disable_gpo", {"gpo": "default-domain-policy", "session_id": sid})
        rsop = self._rsop(sid, self.DOMAIN)
        self.assertNotIn("default-domain-policy", [g["id"] for g in rsop["applied"]])
        reasons = {g["id"]: g["reason"] for g in rsop["filtered"]}
        self.assertIn("Disabled", reasons["default-domain-policy"])

    def test_closest_ou_wins_over_the_domain(self):
        sid = self._session()
        ou = f"{self.DOMAIN}/Servers"
        we.apply_action(sid, "create_gpo", {"name": "Servers Policy", "session_id": sid})
        we.apply_action(sid, "update_gpo_setting", {
            "gpo": "Servers Policy", "key": "Minimum password length",
            "value": "8 characters", "session_id": sid})
        self._link(sid, "Servers Policy", ou)

        rsop = self._rsop(sid, ou)
        winner = rsop["settings"]["Minimum password length"]
        self.assertEqual(winner["value"], "8 characters")
        self.assertEqual(winner["winning_gpo"], "Servers Policy")

    def test_enforced_domain_policy_beats_a_closer_ou(self):
        sid = self._session()
        ou = f"{self.DOMAIN}/Servers"
        we.apply_action(sid, "create_gpo", {"name": "Servers Policy", "session_id": sid})
        we.apply_action(sid, "update_gpo_setting", {
            "gpo": "Servers Policy", "key": "Minimum password length",
            "value": "8 characters", "session_id": sid})
        self._link(sid, "Servers Policy", ou)

        # Enforcing the domain link flips the winner back to the domain policy.
        enf = we.apply_action(sid, "set_gpo_enforced", {
            "gpo": "default-domain-policy", "enforced": True, "session_id": sid})
        self.assertTrue(enf["ok"], enf)

        rsop = self._rsop(sid, ou)
        winner = rsop["settings"]["Minimum password length"]
        self.assertEqual(winner["value"], "14 characters")
        self.assertTrue(winner["enforced"])

    def test_block_inheritance_drops_the_parent_policy(self):
        sid = self._session()
        ou = f"{self.DOMAIN}/Servers"
        we.apply_action(sid, "create_gpo", {"name": "Servers Policy", "session_id": sid})
        self._link(sid, "Servers Policy", ou)

        res = we.apply_action(sid, "set_block_inheritance", {
            "ou": ou, "blocked": True, "session_id": sid})
        self.assertTrue(res["ok"], res)

        rsop = self._rsop(sid, ou)
        self.assertNotIn("default-domain-policy", [g["id"] for g in rsop["applied"]])
        reasons = {g["id"]: g["reason"] for g in rsop["filtered"]}
        self.assertIn("inheritance blocked", reasons["default-domain-policy"])

    def test_enforced_link_survives_block_inheritance(self):
        sid = self._session()
        ou = f"{self.DOMAIN}/Servers"
        we.apply_action(sid, "create_gpo", {"name": "Servers Policy", "session_id": sid})
        self._link(sid, "Servers Policy", ou)
        we.apply_action(sid, "set_block_inheritance", {"ou": ou, "blocked": True, "session_id": sid})
        we.apply_action(sid, "set_gpo_enforced", {
            "gpo": "default-domain-policy", "enforced": True, "session_id": sid})

        rsop = self._rsop(sid, ou)
        # Enforced beats Block Inheritance — this is the rule learners get wrong.
        self.assertIn("default-domain-policy", [g["id"] for g in rsop["applied"]])

    def test_link_order_breaks_ties_within_one_container(self):
        sid = self._session()
        for name, value, order in (("Policy A", "10 characters", 2), ("Policy B", "20 characters", 1)):
            we.apply_action(sid, "create_gpo", {"name": name, "session_id": sid})
            we.apply_action(sid, "update_gpo_setting", {
                "gpo": name, "key": "Minimum password length", "value": value, "session_id": sid})
            self._link(sid, name, self.DOMAIN)
            we.apply_action(sid, "set_gpo_link_order", {
                "gpo": name, "link_order": order, "session_id": sid})

        rsop = self._rsop(sid, self.DOMAIN)
        # Link order 1 has the highest precedence in GPMC.
        self.assertEqual(rsop["settings"]["Minimum password length"]["winning_gpo"], "Policy B")

    def test_precedence_ranking_is_reported_highest_first(self):
        sid = self._session()
        rsop = self._rsop(sid, self.DOMAIN)
        self.assertTrue(rsop["applied"])
        self.assertEqual(rsop["applied"][0]["precedence"], 1)

    def test_rsop_is_exposed_on_get_state(self):
        sid = self._session()
        state = we.get_state(sid)
        self.assertIn("rsop", state)
        self.assertIn("settings", state["rsop"])

    def test_set_link_order_rejects_a_non_positive_value(self):
        sid = self._session()
        res = we.apply_action(sid, "set_gpo_link_order", {
            "gpo": "default-domain-policy", "link_order": 0, "session_id": sid})
        self.assertFalse(res["ok"])


class PresetsRemainSolvableTests(WindowsBaseTest):
    """Cascades change what 'stopped' means, so re-verify the shipped labs."""

    def test_spooler_scenario_is_still_solvable(self):
        sid = self._session("win-gui-start-critical-service")
        self.assertFalse(we.validate_windows_lab(sid, "win-gui-start-critical-service")[0])

        we.apply_action(sid, "set_startup", {"service": "Spooler", "startup": "automatic", "session_id": sid})
        res = we.apply_action(sid, "start_service", {"service": "Spooler", "session_id": sid})
        self.assertTrue(res["ok"], res)

        ok, reason = we.validate_windows_lab(sid, "win-gui-start-critical-service")
        self.assertTrue(ok, reason)

    def test_spooler_scenario_dependencies_are_running_at_seed(self):
        """The Spooler lab must not become unsolvable via a stopped dependency."""
        sid = self._session("win-gui-start-critical-service")
        world = self._world(sid)
        spooler = we._find_service(world, "Spooler")
        self.assertEqual(we._stopped_dependencies(world, spooler), [])

    def test_join_domain_scenario_is_still_solvable(self):
        slug = "win-gui-join-domain"
        sid = self._session(slug)
        self.assertFalse(we.validate_windows_lab(sid, slug)[0])

        res = we.apply_action(sid, "join_domain", {
            "domain": we.DEFAULT_DOMAIN, "user": "admin", "password": "pw", "session_id": sid})
        self.assertTrue(res["ok"], res)

        ok, reason = we.validate_windows_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_update_scenario_is_still_solvable(self):
        slug = "win-gui-retry-windows-update"
        sid = self._session(slug)
        self.assertFalse(we.validate_windows_lab(sid, slug)[0])

        res = we.apply_action(sid, "retry_update", {"kb": "KB5034123", "session_id": sid})
        self.assertTrue(res["ok"], res)
        self.assertTrue(we.validate_windows_lab(sid, slug)[0])
