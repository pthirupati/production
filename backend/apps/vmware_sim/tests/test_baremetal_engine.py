"""Tests for the MAAS / LXD / KVM bare-metal engine lifecycle + grading.

The commissioning/deploy lifecycle advances on wall-clock time.  Tests drive
time by patching ``time.time`` (via the engine's ``_now`` helper) so they run
instantly and deterministically rather than sleeping.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import baremetal_engine as bm


class BaremetalLifecycleTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "maas-commission") -> str:
        sid = f"test-bm-{slug}"
        bm.drop_session(sid)
        bm.get_state(sid, slug)
        bm.apply_action(sid, "login", {"user": "admin"})
        return sid

    def _machine(self, sid, mid):
        state = bm.get_state(sid)["state"]
        return next(m for m in state["maas"]["machines"] if m["id"] == mid)

    # ── grading contract ──────────────────────────────────────────────────
    def test_starts_broken_and_fails_validation(self):
        sid = self._session("maas-commission")
        ok, _ = bm.validate_baremetal_lab(sid, "maas-commission")
        self.assertFalse(ok)

    def test_commission_action_clears_broken_and_passes(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        self.assertTrue(res["ok"], res)
        ok, msg = bm.validate_baremetal_lab(sid, "maas-commission")
        self.assertTrue(ok, msg)

    def test_no_session_does_not_pass(self):
        ok, _ = bm.validate_baremetal_lab("nonexistent-session", "maas-commission")
        self.assertFalse(ok)

    def test_lxd_scenario_grading(self):
        sid = self._session("lxd-container-stopped")
        ok, _ = bm.validate_baremetal_lab(sid, "lxd-container-stopped")
        self.assertFalse(ok)
        bm.apply_action(sid, "lxd_start", {"name": "batch-job"})
        ok, msg = bm.validate_baremetal_lab(sid, "lxd-container-stopped")
        self.assertTrue(ok, msg)

    def test_kvm_scenario_grading(self):
        sid = self._session("kvm-vm-stopped")
        ok, _ = bm.validate_baremetal_lab(sid, "kvm-vm-stopped")
        self.assertFalse(ok)
        bm.apply_action(sid, "kvm_start", {"name": "train-vm-2"})
        ok, msg = bm.validate_baremetal_lab(sid, "kvm-vm-stopped")
        self.assertTrue(ok, msg)

    # ── wall-clock commissioning lifecycle ─────────────────────────────────
    def test_commission_advances_over_wall_clock_not_per_request(self):
        sid = self._session("maas-commission")
        base = 1_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Commissioning")
            self.assertEqual(m["progress"], 0)

        # Halfway through with no additional action — pure wall-clock advance.
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS / 2):
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Commissioning")
            self.assertGreaterEqual(m["progress"], 40)
            self.assertLess(m["progress"], 100)

        # Past the full duration — machine should be Ready.
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Ready")
            self.assertEqual(m["progress"], 100)
            self.assertTrue(m["ip"])

    def test_multiple_reads_do_not_double_advance(self):
        """Progress is a function of wall-clock, so repeated reads at the same
        instant must be idempotent (advance is not per-request)."""
        sid = self._session("maas-commission")
        base = 2_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + 5):
            first = self._machine(sid, 2)["progress"]
            second = self._machine(sid, 2)["progress"]
            third = self._machine(sid, 2)["progress"]
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_full_commission_then_deploy_lifecycle(self):
        sid = self._session("maas-commission")
        base = 3_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        # Finish commissioning.
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(self._machine(sid, 2)["status"], "Ready")
            t_deploy = base + bm.COMMISSION_SECONDS + 1
        # Kick off deploy.
        with mock.patch.object(bm, "_now", return_value=t_deploy):
            res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2})
            self.assertTrue(res["ok"], res)
            self.assertEqual(self._machine(sid, 2)["status"], "Deploying")
        # Complete deploy over wall-clock.
        with mock.patch.object(bm, "_now", return_value=t_deploy + bm.DEPLOY_SECONDS + 1):
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Deployed")
            self.assertEqual(m["os"], "Ubuntu 22.04 LTS")

    def test_deploy_rejected_before_ready(self):
        sid = self._session("maas-commission")
        # Machine 2 starts Failed — cannot deploy directly.
        res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2})
        self.assertFalse(res["ok"])

    def test_commission_log_populated(self):
        sid = self._session("maas-commission")
        base = 4_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            m = self._machine(sid, 2)
        messages = " ".join(e["message"] for e in m["log"])
        self.assertIn("Commissioning started", messages)
        self.assertIn("Ready", messages)

    # ── node detail fields ─────────────────────────────────────────────────
    def test_machines_have_detail_fields(self):
        sid = self._session("maas-commission")
        m = self._machine(sid, 1)
        self.assertIn("interfaces", m)
        self.assertIn("storage", m)
        self.assertTrue(m["interfaces"])
        self.assertTrue(m["storage"])
        self.assertIn("log", m)

    # ── KVM / LXD start-stop lifecycle ─────────────────────────────────────
    def test_kvm_start_stop_cycle(self):
        sid = self._session("kvm-vm-stopped")
        bm.apply_action(sid, "kvm_start", {"name": "train-vm-1"})
        state = bm.get_state(sid)["state"]
        vm = next(v for v in state["kvm"]["vms"] if v["name"] == "train-vm-1")
        self.assertEqual(vm["state"], "running")
        bm.apply_action(sid, "kvm_stop", {"name": "train-vm-1"})
        state = bm.get_state(sid)["state"]
        vm = next(v for v in state["kvm"]["vms"] if v["name"] == "train-vm-1")
        self.assertEqual(vm["state"], "shut off")
        self.assertEqual(vm["ip"], "")

    def test_lxd_start_stop_cycle(self):
        sid = self._session("lxd-container-stopped")
        bm.apply_action(sid, "lxd_stop", {"name": "infer-svc"})
        state = bm.get_state(sid)["state"]
        c = next(c for c in state["lxd"]["containers"] if c["name"] == "infer-svc")
        self.assertEqual(c["status"], "Stopped")
        bm.apply_action(sid, "lxd_start", {"name": "infer-svc"})
        state = bm.get_state(sid)["state"]
        c = next(c for c in state["lxd"]["containers"] if c["name"] == "infer-svc")
        self.assertEqual(c["status"], "Running")

    def test_power_toggle(self):
        sid = self._session("maas-commission")
        bm.apply_action(sid, "maas_power", {"machine_id": 1, "power": "off"})
        self.assertEqual(self._machine(sid, 1)["power"], "off")
        bm.apply_action(sid, "maas_power", {"machine_id": 1, "power": "on"})
        self.assertEqual(self._machine(sid, 1)["power"], "on")

    def test_requires_login(self):
        sid = f"test-bm-nologin"
        bm.drop_session(sid)
        bm.get_state(sid, "maas-commission")
        res = bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        self.assertFalse(res["ok"])

    # ── IPMI power verbs (on/off/cycle/status) ─────────────────────────────
    def test_ipmi_power_status(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "ipmi_power", {"machine_id": 1, "verb": "status"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["power"], self._machine(sid, 1)["power"])

    def test_ipmi_power_off_then_on(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "ipmi_power", {"machine_id": 1, "verb": "off"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._machine(sid, 1)["power"], "off")
        res = bm.apply_action(sid, "ipmi_power", {"machine_id": 1, "verb": "on"})
        self.assertEqual(self._machine(sid, 1)["power"], "on")

    def test_ipmi_power_cycle_logs_pxe_boot(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "ipmi_power", {"machine_id": 1, "verb": "cycle"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._machine(sid, 1)["power"], "on")
        log = " ".join(e["message"] for e in self._machine(sid, 1)["log"])
        self.assertIn("power cycle", log.lower())
        self.assertIn("PXE", log)

    def test_ipmi_power_fails_when_bmc_unreachable(self):
        sid = self._session("maas-commission")
        # gpu-node-02's BMC is unreachable at the start of the maas scenario.
        res = bm.apply_action(sid, "ipmi_power", {"machine_id": 2, "verb": "on"})
        self.assertFalse(res["ok"])

    # ── MAAS enlist (PXE) — start of the lifecycle ─────────────────────────
    def test_enlist_adds_new_machine(self):
        sid = self._session("maas-commission")
        before = len(bm.get_state(sid)["state"]["maas"]["machines"])
        res = bm.apply_action(sid, "maas_enlist", {"hostname": "node-99"})
        self.assertTrue(res["ok"], res)
        machines = bm.get_state(sid)["state"]["maas"]["machines"]
        self.assertEqual(len(machines), before + 1)
        new = next(m for m in machines if m["hostname"] == "node-99")
        self.assertEqual(new["status"], "New")
        log = " ".join(e["message"] for e in new["log"])
        self.assertIn("PXE", log)

    def test_enlisted_machine_can_commission_to_ready(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_enlist", {"hostname": "node-77"})
        mid = res["machine_id"]
        base = 9_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": mid})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            m = next(m for m in bm.get_state(sid)["state"]["maas"]["machines"] if m["id"] == mid)
            self.assertEqual(m["status"], "Ready")

    def test_boot_resources_seeded_and_packer_publish(self):
        sid = self._session("maas-commission")
        resources = bm.get_state(sid)["state"]["maas"]["boot_resources"]
        names = {r["name"] for r in resources}
        self.assertIn("ubuntu/jammy", names)
        self.assertIn("ubuntu/noble", names)
        res = bm.apply_action(sid, "maas_publish_boot_resource", {"sku": "h200"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["boot_resource"]["name"], "custom/h200-jammy")
        updated = {r["name"] for r in bm.get_state(sid)["state"]["maas"]["boot_resources"]}
        self.assertIn("custom/h200-jammy", updated)

    def test_packer_publish_clears_missing_boot_resource_flag(self):
        sid = self._session("packer-gpu")
        entry_state = bm.get_state(sid)["state"]
        entry_state["broken"] = {"packer_image_unpublished": True, "missing_boot_resource": "custom/h100-jammy"}
        # Persist broken flags via commission path: re-save through enlist noop then publish.
        from django.core.cache import cache
        import json
        key = f"baremetal_session:{sid}"
        raw = cache.get(key)
        data = json.loads(raw) if isinstance(raw, str) else raw
        data["state"]["broken"] = {"packer_image_unpublished": True, "missing_boot_resource": "custom/h100-jammy"}
        cache.set(key, json.dumps(data), 7200)
        res = bm.apply_action(sid, "packer_publish_maas", {"sku": "h100"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(bm.get_state(sid)["state"].get("broken") or {}, {})

    def test_maas_deploy_uses_custom_boot_resource(self):
        sid = self._session("maas-custom-deploy")
        base = 5_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(self._machine(sid, 2)["status"], "Ready")
            t_deploy = base + bm.COMMISSION_SECONDS + 1
        pub = bm.apply_action(sid, "maas_publish_boot_resource", {"sku": "h100"})
        self.assertTrue(pub["ok"], pub)
        with mock.patch.object(bm, "_now", return_value=t_deploy):
            res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2, "boot_resource": "custom/h100-jammy"})
            self.assertTrue(res["ok"], res)
            self.assertEqual(res.get("boot_resource"), "custom/h100-jammy")
            deploying = self._machine(sid, 2)
            self.assertEqual(deploying["status"], "Deploying")
            self.assertEqual(deploying["boot_resource"], "custom/h100-jammy")
            self.assertIn("h100", (deploying.get("pending_os") or "").lower())
        with mock.patch.object(bm, "_now", return_value=t_deploy + bm.DEPLOY_SECONDS + 1):
            done = self._machine(sid, 2)
            self.assertEqual(done["status"], "Deployed")
            self.assertIn("custom/h100-jammy", done.get("os") or "")

    def test_maas_deploy_rejects_unknown_boot_resource(self):
        sid = self._session("maas-bad-image")
        base = 6_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(self._machine(sid, 2)["status"], "Ready")
            t_deploy = base + bm.COMMISSION_SECONDS + 1
        with mock.patch.object(bm, "_now", return_value=t_deploy):
            res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2, "boot_resource": "custom/missing-jammy"})
            self.assertFalse(res["ok"])
            self.assertIn("not found", (res.get("error") or "").lower())

    # ── Canonical-like MAAS fields + infra ─────────────────────────────────
    def test_machines_have_canonical_detail_fields(self):
        sid = self._session("maas-commission")
        m = self._machine(sid, 1)
        for key in (
            "owner", "pool", "zone", "locked", "tags", "fabric", "domain",
            "power_type", "bmc_address", "bmc_user", "disk_count", "storage_gb",
            "pci_devices", "usb_devices", "events", "commissioning_results",
            "test_results", "storage_layout",
        ):
            self.assertIn(key, m)
        self.assertEqual(m["pool"], "default")
        self.assertEqual(m["zone"], "default")
        self.assertFalse(m["locked"])
        self.assertEqual(m["storage_layout"], "flat")
        iface = m["interfaces"][0]
        self.assertIn("fabric", iface)
        self.assertIn("subnet", iface)
        self.assertIn("ip_mode", iface)
        self.assertIn("link_speed", iface)
        # Ready GPU node should already have PCI GPUs from seed.
        gpus = [p for p in m["pci_devices"] if p.get("type") == "gpu"]
        self.assertEqual(len(gpus), 8)

    def test_infra_seeded_on_get_state(self):
        sid = self._session("maas-commission")
        maas = bm.get_state(sid)["state"]["maas"]
        for key in (
            "controllers", "domains", "zones", "resource_pools",
            "devices", "dhcp", "settings", "users",
        ):
            self.assertIn(key, maas)
            self.assertTrue(maas[key])
        self.assertTrue(any(c.get("type") == "region" for c in maas["controllers"]))
        self.assertTrue(any(c.get("type") == "rack" for c in maas["controllers"]))
        self.assertIn("regiond", maas["controllers"][0]["services"])
        self.assertEqual(maas["settings"]["maas_name"], "fixitlab")

    def test_commission_fills_gpu_pci_and_results(self):
        sid = self._session("maas-commission")
        base = 7_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
            mid_commission = self._machine(sid, 2)
            self.assertEqual(mid_commission["pci_devices"], [])
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            m = self._machine(sid, 2)
        self.assertEqual(m["status"], "Ready")
        gpus = [p for p in m["pci_devices"] if p.get("type") == "gpu"]
        self.assertEqual(len(gpus), 8)
        self.assertTrue(m["commissioning_results"])
        self.assertTrue(all(r["status"] == "passed" for r in m["commissioning_results"]))
        events = " ".join(e["message"] for e in m["events"])
        self.assertIn("Ready", events)

    def test_deploy_logs_allocated_then_deploying(self):
        sid = self._session("maas-commission")
        base = 8_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(self._machine(sid, 2)["status"], "Ready")
            t_deploy = base + bm.COMMISSION_SECONDS + 1
        with mock.patch.object(bm, "_now", return_value=t_deploy):
            res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2})
            self.assertTrue(res["ok"], res)
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Deploying")
            log = " ".join(e["message"] for e in m["log"])
            self.assertIn("allocated", log.lower())
            events = " ".join(e["message"] for e in m["events"])
            self.assertIn("Allocated", events)
            self.assertIn("Deploying", events)
        # Deploy steps include DHCP / TFTP / Curtin.
        with mock.patch.object(bm, "_now", return_value=t_deploy + bm.DEPLOY_SECONDS + 1):
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Deployed")
            log = " ".join(e["message"] for e in m["log"])
            self.assertIn("DHCP", log)
            self.assertIn("TFTP", log)
            self.assertIn("Curtin", log)

    def test_release_deployed_to_ready(self):
        sid = self._session("maas-commission")
        # Machine 3 starts Deployed.
        base = 10_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            res = bm.apply_action(sid, "maas_release", {"machine_id": 3})
            self.assertTrue(res["ok"], res)
            m = self._machine(sid, 3)
            self.assertEqual(m["status"], "Releasing")
        with mock.patch.object(bm, "_now", return_value=base + bm.RELEASE_SECONDS + 1):
            m = self._machine(sid, 3)
            self.assertEqual(m["status"], "Ready")
            self.assertEqual(m.get("os") or "", "")

    def test_abort_commissioning_to_failed(self):
        sid = self._session("maas-commission")
        base = 11_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
            res = bm.apply_action(sid, "maas_abort", {"machine_id": 2})
            self.assertTrue(res["ok"], res)
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Failed commissioning")
            self.assertIsNone(m.get("phase_started_at"))

    def test_lock_blocks_deploy(self):
        sid = self._session("maas-commission")
        base = 12_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(self._machine(sid, 2)["status"], "Ready")
            t_deploy = base + bm.COMMISSION_SECONDS + 1
        with mock.patch.object(bm, "_now", return_value=t_deploy):
            lock = bm.apply_action(sid, "maas_lock", {"machine_id": 2})
            self.assertTrue(lock["ok"], lock)
            self.assertTrue(self._machine(sid, 2)["locked"])
            res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2})
            self.assertFalse(res["ok"])
            unlock = bm.apply_action(sid, "maas_unlock", {"machine_id": 2})
            self.assertTrue(unlock["ok"], unlock)
            self.assertFalse(self._machine(sid, 2)["locked"])
            res2 = bm.apply_action(sid, "maas_deploy", {"machine_id": 2})
            self.assertTrue(res2["ok"], res2)

    def test_apply_storage_layout_lvm_and_raid10(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_apply_storage_layout", {"machine_id": 1, "layout": "lvm"})
        self.assertTrue(res["ok"], res)
        m = self._machine(sid, 1)
        self.assertEqual(m["storage_layout"], "lvm")
        self.assertTrue(all(d.get("role") == "lvm-pv" for d in m["storage"]))
        res = bm.apply_action(sid, "maas_apply_storage_layout", {"machine_id": 1, "layout": "raid10"})
        self.assertTrue(res["ok"], res)
        m = self._machine(sid, 1)
        self.assertEqual(m["storage_layout"], "raid10")
        self.assertGreaterEqual(len(m["storage"]), 4)
        self.assertTrue(all(d.get("raid") == "raid10" for d in m["storage"]))

    def test_lifecycle_includes_extended_statuses(self):
        for status in (
            "Releasing", "Broken", "Testing", "Rescue mode",
            "Failed commissioning", "Failed deployment",
        ):
            self.assertIn(status, bm.LIFECYCLE)