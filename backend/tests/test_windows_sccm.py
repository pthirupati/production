"""Windows simulator Microsoft Endpoint Configuration Manager (SCCM/MECM) actions."""

from django.test import SimpleTestCase, override_settings

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fixitlab-windows-sccm-test",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class WindowsSccmStateTest(SimpleTestCase):
    def test_get_state_includes_sccm(self):
        from apps.vmware_sim.windows_engine import drop_session, get_state

        session_id = "test-win-sccm-state"
        drop_session(session_id)
        state = get_state(session_id, "win-gui-unlock-ad-user")
        self.assertIn("sccm", state)
        sccm = state["sccm"]
        self.assertEqual(sccm["site_code"], "FIX")
        self.assertTrue(sccm["client_installed"])
        self.assertIn(sccm["client_status"], ("active", "inactive", "unknown"))
        self.assertIsInstance(sccm.get("collections"), list)
        self.assertTrue(len(sccm["collections"]) >= 1)
        self.assertIsInstance(sccm.get("deployments"), list)
        drop_session(session_id)


@override_settings(CACHES=LOCMEM_CACHE)
class WindowsSccmPatchFailedTest(SimpleTestCase):
    def test_preset_shows_required_deployment_failed(self):
        from apps.vmware_sim.windows_engine import drop_session, get_state

        session_id = "test-win-sccm-patch-failed-preset"
        drop_session(session_id)
        state = get_state(session_id, "win-sccm-patch-failed")
        deployments = state["sccm"]["deployments"]
        failed = [d for d in deployments if d["status"] == "Failed"]
        self.assertTrue(failed, deployments)
        dep = failed[0]
        self.assertTrue(dep["error"])
        self.assertEqual(state["goal"]["kind"], "sccm_deployment_installed")
        # The matching Windows Update entry should also be failed.
        upd = next((u for u in state["updates"] if u["kb"] == dep["kb"]), None)
        self.assertIsNotNone(upd)
        self.assertEqual(upd["status"], "failed")
        drop_session(session_id)

    def test_retry_deployment_installs_and_validates(self):
        from apps.vmware_sim.windows_engine import (
            apply_action,
            drop_session,
            get_state,
            validate_windows_lab,
        )

        session_id = "test-win-sccm-patch-failed-retry"
        drop_session(session_id)
        state = get_state(session_id, "win-sccm-patch-failed")

        # A fresh session always fails validation.
        ok, msg = validate_windows_lab(session_id, "win-sccm-patch-failed")
        self.assertFalse(ok, msg)

        failed_dep = next(d for d in state["sccm"]["deployments"] if d["status"] == "Failed")
        result = apply_action(session_id, "sccm_retry_deployment", {"deployment_id": failed_dep["id"]})
        self.assertTrue(result["ok"], result)

        state = get_state(session_id, "win-sccm-patch-failed")
        dep = next(d for d in state["sccm"]["deployments"] if d["id"] == failed_dep["id"])
        self.assertEqual(dep["status"], "Installed")
        self.assertEqual(dep["error"], "")
        upd = next(u for u in state["updates"] if u["kb"] == dep["kb"])
        self.assertEqual(upd["status"], "installed")

        ok, msg = validate_windows_lab(session_id, "win-sccm-patch-failed")
        self.assertTrue(ok, msg)
        drop_session(session_id)

    def test_install_deployment_action_is_alias_of_retry(self):
        from apps.vmware_sim.windows_engine import apply_action, drop_session, get_state

        session_id = "test-win-sccm-install-alias"
        drop_session(session_id)
        state = get_state(session_id, "win-sccm-patch-failed")
        failed_dep = next(d for d in state["sccm"]["deployments"] if d["status"] == "Failed")

        result = apply_action(session_id, "sccm_install_deployment", {"deployment_id": failed_dep["id"]})
        self.assertTrue(result["ok"], result)

        state = get_state(session_id, "win-sccm-patch-failed")
        dep = next(d for d in state["sccm"]["deployments"] if d["id"] == failed_dep["id"])
        self.assertEqual(dep["status"], "Installed")
        drop_session(session_id)

    def test_sccm_sync_updates_and_machine_policy_cycle(self):
        from apps.vmware_sim.windows_engine import apply_action, drop_session, get_state

        session_id = "test-win-sccm-sync-and-cycle"
        drop_session(session_id)
        get_state(session_id, "win-sccm-patch-failed")

        sync = apply_action(session_id, "sccm_sync_updates", {})
        self.assertTrue(sync["ok"], sync)
        state = get_state(session_id, "win-sccm-patch-failed")
        self.assertTrue(len(state["sccm"]["software_updates"]) >= 1)

        cycle = apply_action(session_id, "sccm_machine_policy_cycle", {})
        self.assertTrue(cycle["ok"], cycle)
        state = get_state(session_id, "win-sccm-patch-failed")
        self.assertEqual(state["sccm"]["client_status"], "active")
        drop_session(session_id)

    def test_open_software_center_is_noop_ok(self):
        from apps.vmware_sim.windows_engine import apply_action, drop_session, get_state

        session_id = "test-win-sccm-open-software-center"
        drop_session(session_id)
        get_state(session_id, "win-sccm-patch-failed")
        result = apply_action(session_id, "sccm_open_software_center", {})
        self.assertTrue(result["ok"], result)
        drop_session(session_id)

    def test_unknown_deployment_id_returns_error_not_raise(self):
        from apps.vmware_sim.windows_engine import apply_action, drop_session, get_state

        session_id = "test-win-sccm-unknown-deployment"
        drop_session(session_id)
        get_state(session_id, "win-sccm-patch-failed")
        result = apply_action(session_id, "sccm_retry_deployment", {"deployment_id": "NOPE"})
        self.assertFalse(result["ok"])
        drop_session(session_id)
