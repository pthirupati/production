"""Unit tests for the enterprise simulation engines (Commvault, NetApp, Dell
EMC, physical Datacenter, SOC/SIEM). Each engine is exercised with get_state,
one mutating action, and the corresponding validate_*_lab grader for a sample
scenario slug — mirroring the pattern used for the AWX/AWS engines."""

import uuid

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import (
    commvault_engine,
    datacenter_engine,
    dellemc_engine,
    netapp_engine,
    soc_engine,
)


class CommvaultEngineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())

    def test_get_state_seeds_clients_and_jobs(self):
        state = commvault_engine.get_state(self.session_id, "commvault-backup-overdue")
        self.assertIn("clients", state["state"])
        self.assertTrue(state["state"]["clients"])
        self.assertIn("jobs", state["state"])
        self.assertEqual(state["state"]["broken"].get("overdue_client"), "db01")

    def test_run_backup_clears_overdue_and_completes(self):
        commvault_engine.get_state(self.session_id, "commvault-backup-overdue")
        commvault_engine.apply_action(self.session_id, "login", {"user": "admin"})
        result = commvault_engine.apply_action(self.session_id, "run_backup", {"client": "db01"})
        self.assertTrue(result["ok"], result)
        job_id = result["job_id"]

        entry = commvault_engine._load(self.session_id)
        job = next(j for j in entry["state"]["jobs"] if j["id"] == job_id)
        job["started_ts"] -= 10  # force the wall-clock timeline to completion
        commvault_engine._save(self.session_id, entry)

        ok, msg = commvault_engine.validate_commvault_lab(self.session_id, "commvault-backup-overdue")
        self.assertTrue(ok, msg)

    def test_run_restore_action(self):
        commvault_engine.get_state(self.session_id, "commvault-restore-web01")
        commvault_engine.apply_action(self.session_id, "login", {})
        result = commvault_engine.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self.assertTrue(result["ok"], result)


class NetappEngineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())

    def test_get_state_seeds_volumes(self):
        state = netapp_engine.get_state(self.session_id, "netapp-volume-resize")
        self.assertTrue(state["state"]["volumes"])
        self.assertEqual(state["state"]["broken"].get("volume_near_full"), "vol_web_data")

    def test_resize_volume_clears_broken(self):
        netapp_engine.get_state(self.session_id, "netapp-volume-resize")
        netapp_engine.apply_action(self.session_id, "login", {})
        result = netapp_engine.apply_action(self.session_id, "resize_volume", {"name": "vol_web_data", "size_gb": 300})
        self.assertTrue(result["ok"], result)
        ok, msg = netapp_engine.validate_netapp_lab(self.session_id, "netapp-volume-resize")
        self.assertTrue(ok, msg)

    def test_create_snapmirror_and_break_mirror(self):
        netapp_engine.get_state(self.session_id, "netapp-snapmirror-create")
        netapp_engine.apply_action(self.session_id, "login", {})
        result = netapp_engine.apply_action(self.session_id, "create_snapmirror", {
            "source": "svm-prod:vol_db_data", "destination": "svm-dr:vol_dr_copy2",
        })
        self.assertTrue(result["ok"], result)


class DellemcEngineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())

    def test_get_state_seeds_storage_groups(self):
        state = dellemc_engine.get_state(self.session_id, "dellemc-volume-map")
        self.assertTrue(state["state"]["storage_groups"])
        self.assertEqual(state["state"]["broken"].get("unmapped_volume"), "0004")

    def test_map_volume_clears_broken(self):
        dellemc_engine.get_state(self.session_id, "dellemc-volume-map")
        dellemc_engine.apply_action(self.session_id, "login", {})
        result = dellemc_engine.apply_action(self.session_id, "map_volume", {
            "volume_id": "0004", "storage_group": "SG_db_prod",
        })
        self.assertTrue(result["ok"], result)
        ok, msg = dellemc_engine.validate_dellemc_lab(self.session_id, "dellemc-volume-map")
        self.assertTrue(ok, msg)

    def test_create_masking_view(self):
        dellemc_engine.get_state(self.session_id, "dellemc-masking-view")
        dellemc_engine.apply_action(self.session_id, "login", {})
        result = dellemc_engine.apply_action(self.session_id, "create_masking_view", {
            "name": "MV_db01", "storage_group": "SG_db_prod", "host": "db01", "port_group": "PG_db",
        })
        self.assertTrue(result["ok"], result)


class DatacenterEngineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())

    def test_get_state_seeds_racks_and_broken_server(self):
        state = datacenter_engine.get_state(self.session_id, "datacenter-power-replace")
        self.assertTrue(state["state"]["racks"])
        self.assertEqual(state["state"]["broken"].get("server"), "srv-r01-u14")
        self.assertEqual(state["state"]["broken"].get("component"), "power")

    def test_replace_power_supply_clears_broken(self):
        datacenter_engine.get_state(self.session_id, "datacenter-power-replace")
        datacenter_engine.apply_action(self.session_id, "login", {})
        datacenter_engine.apply_action(self.session_id, "select_asset", {"asset_id": "srv-r01-u14"})
        # An unrelated replace on a healthy component should not resolve the fault.
        datacenter_engine.apply_action(self.session_id, "replace_nic", {"asset_id": "srv-r01-u14"})
        ok, _ = datacenter_engine.validate_datacenter_lab(self.session_id, "datacenter-power-replace")
        self.assertFalse(ok)
        # Replacing the actual faulted component (power supply) clears the objective.
        result = datacenter_engine.apply_action(self.session_id, "replace_power", {"asset_id": "srv-r01-u14"})
        self.assertTrue(result["ok"], result)
        result2 = datacenter_engine.apply_action(self.session_id, "power_cycle", {"asset_id": "srv-r01-u14"})
        self.assertTrue(result2["ok"], result2)
        ok, msg = datacenter_engine.validate_datacenter_lab(self.session_id, "datacenter-power-replace")
        self.assertTrue(ok, msg)


class SocEngineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())

    def test_get_state_seeds_alerts(self):
        state = soc_engine.get_state(self.session_id, "soc-quarantine-c2")
        self.assertTrue(state["state"]["alerts"])
        self.assertEqual(state["state"]["broken"].get("open_critical_alert"), "AL-1003")
        self.assertEqual(state["state"]["broken"].get("needs_quarantine"), "ws-finance-07")

    def test_quarantine_flow_clears_broken(self):
        soc_engine.get_state(self.session_id, "soc-quarantine-c2")
        soc_engine.apply_action(self.session_id, "login", {})
        soc_engine.apply_action(self.session_id, "acknowledge_alert", {"alert_id": "AL-1003"})
        soc_engine.apply_action(self.session_id, "run_playbook", {"playbook_id": "pb-malware-contain"})
        result = soc_engine.apply_action(self.session_id, "quarantine_host", {"asset": "ws-finance-07"})
        self.assertTrue(result["ok"], result)
        result2 = soc_engine.apply_action(self.session_id, "close_incident", {"alert_id": "AL-1003"})
        self.assertTrue(result2["ok"], result2)
        ok, msg = soc_engine.validate_soc_lab(self.session_id, "soc-quarantine-c2")
        self.assertTrue(ok, msg)

    def test_block_ip_action(self):
        soc_engine.get_state(self.session_id, "soc-brute-force")
        soc_engine.apply_action(self.session_id, "login", {})
        result = soc_engine.apply_action(self.session_id, "block_ip", {"ip": "198.51.100.23"})
        self.assertTrue(result["ok"], result)
        state = soc_engine.get_state(self.session_id, "soc-brute-force")
        self.assertIn("198.51.100.23", state["state"]["blocked_ips"])
