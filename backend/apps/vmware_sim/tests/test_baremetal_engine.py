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

    # ── Packer Image Factory pipeline ──────────────────────────────────────
    def test_packer_factory_pipeline_publish_boot_resource(self):
        sid = self._session("ai-infra-packer-gpu-image-factory")
        st = bm.get_state(sid)["state"]
        self.assertIn("needs_custom_image_deploy", st.get("broken") or {})

        template = (
            'provisioner "shell" { script = "scripts/install-gpu-h100.sh" }\n'
            'runcmd: [systemctl enable --now nvidia-persistenced]\n'
        )
        start = bm.apply_action(sid, "packer_factory_start_pipeline", {
            "sku": "h100",
            "files": {"gpu-h100.pkr.hcl": template},
            "template": template,
        })
        self.assertTrue(start["ok"], start)
        self.assertEqual(start["run"]["sku"], "h100")

        # Drive all jobs: init/validate/build/libguestfs complete in one advance each;
        # vuln-scan needs fail then remediate; gpu-sanity + publish need two steps each.
        max_steps = 40
        for _ in range(max_steps):
            run = bm.apply_action(sid, "packer_factory_get_state", {}).get("active_run") or {}
            if run.get("status") == "success":
                break
            if run.get("status") == "failure":
                failed = next((j for j in run["jobs"] if j["status"] == "failure"), None)
                self.assertIsNotNone(failed)
                if failed["id"] == "vuln-scan+remediate":
                    # Advance again remediates CVE, or explicit re-run
                    adv = bm.apply_action(sid, "packer_factory_advance_job", {})
                    self.assertTrue(adv["ok"], adv)
                    continue
                rerun = bm.apply_action(sid, "packer_factory_rerun_job", {
                    "job_id": failed["id"],
                    "files": {"gpu-h100.pkr.hcl": template},
                })
                self.assertTrue(rerun["ok"], rerun)
                continue
            adv = bm.apply_action(sid, "packer_factory_advance_job", {})
            self.assertTrue(adv["ok"], adv)
        else:
            self.fail("Pipeline did not complete within step budget")

        final = bm.apply_action(sid, "packer_factory_get_state", {})
        self.assertTrue(final.get("artifact_ready") or (final.get("active_run") or {}).get("artifact_ready"))
        names = {r["name"] for r in bm.get_state(sid)["state"]["maas"]["boot_resources"]}
        self.assertIn("custom/h100-jammy", names)
        broken = bm.get_state(sid)["state"].get("broken") or {}
        self.assertNotIn("packer_image_unpublished", broken)
        self.assertNotIn("missing_boot_resource", broken)

    def test_packer_factory_gpu_sanity_requires_nvidia_marker(self):
        sid = self._session("packer-gpu-sanity")
        start = bm.apply_action(sid, "packer_factory_start_pipeline", {
            "sku": "h200",
            "files": {"gpu-h200.pkr.hcl": 'source "qemu" "gpu" {}\n# no driver markers\n'},
            "template": "plain packer without drivers",
        })
        self.assertTrue(start["ok"], start)
        self.assertFalse(start["run"]["has_nvidia_marker"])

        # Advance through jobs until gpu-sanity fails
        for _ in range(30):
            run = (bm.apply_action(sid, "packer_factory_get_state", {}).get("active_run") or {})
            jobs = {j["id"]: j for j in run.get("jobs") or []}
            if jobs.get("gpu-sanity", {}).get("status") == "failure":
                break
            if run.get("status") == "failure" and jobs.get("vuln-scan+remediate", {}).get("status") == "failure":
                bm.apply_action(sid, "packer_factory_advance_job", {})  # remediate
                continue
            bm.apply_action(sid, "packer_factory_advance_job", {})
        else:
            self.fail("gpu-sanity did not fail")

        gpu = next(j for j in bm.apply_action(sid, "packer_factory_get_state", {})["active_run"]["jobs"] if j["id"] == "gpu-sanity")
        self.assertEqual(gpu["status"], "failure")
        names = {r["name"] for r in bm.get_state(sid)["state"]["maas"]["boot_resources"]}
        self.assertNotIn("custom/h200-jammy", names)

    def test_needs_custom_image_deploy_cleared_on_deploy(self):
        sid = self._session("ai-infra-packer-custom-deploy")
        # Seed broken flag (preset already sets it for packer slugs)
        broken = bm.get_state(sid)["state"].get("broken") or {}
        self.assertTrue(broken.get("needs_custom_image_deploy"))

        base = 7_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            # Clear publish-related flags via publish
            pub = bm.apply_action(sid, "maas_publish_boot_resource", {"sku": "h100"})
            self.assertTrue(pub["ok"], pub)
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(self._machine(sid, 2)["status"], "Ready")
            t_deploy = base + bm.COMMISSION_SECONDS + 1
        with mock.patch.object(bm, "_now", return_value=t_deploy):
            # Re-set needs_custom_image_deploy after publish cleared other flags
            from django.core.cache import cache as _cache
            import json as _json
            key = f"baremetal_session:{sid}"
            raw = _cache.get(key)
            data = _json.loads(raw) if isinstance(raw, str) else raw
            data["state"].setdefault("broken", {})["needs_custom_image_deploy"] = True
            _cache.set(key, _json.dumps(data), 7200)
            res = bm.apply_action(sid, "maas_deploy", {"machine_id": 2, "boot_resource": "custom/h100-jammy"})
            self.assertTrue(res["ok"], res)
        with mock.patch.object(bm, "_now", return_value=t_deploy + bm.DEPLOY_SECONDS + 1):
            done = self._machine(sid, 2)
            self.assertEqual(done["status"], "Deployed")
            self.assertTrue(str(done.get("boot_resource") or "").startswith("custom/"))
            ok, msg = bm.validate_baremetal_lab(sid, "ai-infra-packer-custom-deploy")
            self.assertTrue(ok, msg)
            self.assertNotIn("needs_custom_image_deploy", bm.get_state(sid)["state"].get("broken") or {})

    # ── LXD inventory / lifecycle ─────────────────────────────────────────
    def test_lxd_launch_creates_running_instance(self):
        sid = self._session("lxd-container-stopped")
        res = bm.apply_action(sid, "lxd_launch", {
            "name": "lab-infer",
            "image": "ubuntu:22.04",
            "type": "container",
        })
        self.assertTrue(res["ok"], res)
        containers = bm.get_state(sid)["state"]["lxd"]["containers"]
        row = next(c for c in containers if c["name"] == "lab-infer")
        self.assertEqual(row["status"], "Running")
        self.assertEqual(row["type"], "container")
        self.assertTrue(row.get("ipv4"))
        self.assertIn("default", row.get("profiles") or [])
        self.assertIsInstance(row.get("snapshots"), list)
        self.assertIsInstance(row.get("devices"), dict)
        self.assertEqual(row.get("project"), "default")

    def test_lxd_snapshot_and_restore(self):
        sid = self._session("lxd-container-stopped")
        bm.apply_action(sid, "lxd_start", {"name": "batch-job"})
        res = bm.apply_action(sid, "lxd_snapshot", {"name": "batch-job", "snapshot": "pre-change"})
        self.assertTrue(res["ok"], res)
        c = next(x for x in bm.get_state(sid)["state"]["lxd"]["containers"] if x["name"] == "batch-job")
        self.assertTrue(any(s.get("name") == "pre-change" for s in c["snapshots"]))
        res = bm.apply_action(sid, "lxd_restore", {"name": "batch-job", "snapshot": "pre-change"})
        self.assertTrue(res["ok"], res)
        c = next(x for x in bm.get_state(sid)["state"]["lxd"]["containers"] if x["name"] == "batch-job")
        self.assertEqual(c["status"], "Stopped")
        self.assertEqual(c.get("ipv4") or "", "")

    def test_lxd_gpu_device_sets_nvidia_smi_ok(self):
        sid = self._session("lxd-container-stopped")
        res = bm.apply_action(sid, "lxd_config_device_add", {
            "name": "infer-svc",
            "device": "gpu",
            "type": "gpu",
            "pci": "0000:19:00.0",
        })
        self.assertTrue(res["ok"], res)
        c = next(x for x in bm.get_state(sid)["state"]["lxd"]["containers"] if x["name"] == "infer-svc")
        self.assertTrue(c.get("nvidia_smi_ok"))
        self.assertIn("gpu", c.get("devices") or {})
        self.assertEqual(c["devices"]["gpu"]["type"], "gpu")
        exec_res = bm.apply_action(sid, "lxd_exec_echo", {"name": "infer-svc", "command": "nvidia-smi"})
        self.assertTrue(exec_res["ok"], exec_res)
        self.assertIn("NVIDIA", exec_res.get("output") or "")

    def test_lxd_seed_has_storage_networks_cluster(self):
        sid = self._session("lxd-container-stopped")
        lxd = bm.get_state(sid)["state"]["lxd"]
        self.assertGreaterEqual(len(lxd.get("storage_pools") or []), 1)
        self.assertGreaterEqual(len(lxd.get("networks") or []), 1)
        self.assertGreaterEqual(len(lxd.get("cluster") or []), 1)
        self.assertGreaterEqual(len(lxd.get("projects") or []), 1)
        for c in lxd["containers"]:
            self.assertIn("type", c)
            self.assertIn("profiles", c)
            self.assertIn("snapshots", c)
            self.assertIn("devices", c)
            self.assertIn("config", c)
            self.assertIn("project", c)
            self.assertIn("location", c)

    # ── Rescue mode (Entering/Exiting) ─────────────────────────────────────
    def test_enter_rescue_then_exit_rescue_lifecycle(self):
        sid = self._session("maas-rescue")
        state = bm.get_state(sid)["state"]
        self.assertIn("needs_rescue_enter", state.get("broken") or {})
        m3_start = next(m for m in state["maas"]["machines"] if m["id"] == 2)
        self.assertEqual(m3_start["status"], "Deployed")

        base = 13_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            res = bm.apply_action(sid, "maas_enter_rescue", {"machine_id": 2})
            self.assertTrue(res["ok"], res)
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Entering rescue mode")
        self.assertNotIn("needs_rescue_enter", bm.get_state(sid)["state"].get("broken") or {})

        with mock.patch.object(bm, "_now", return_value=base + bm.RESCUE_SECONDS + 1):
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Rescue mode")
            t_exit = base + bm.RESCUE_SECONDS + 1

        with mock.patch.object(bm, "_now", return_value=t_exit):
            res = bm.apply_action(sid, "maas_exit_rescue", {"machine_id": 2})
            self.assertTrue(res["ok"], res)
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Exiting rescue mode")

        with mock.patch.object(bm, "_now", return_value=t_exit + bm.RESCUE_SECONDS + 1):
            m = self._machine(sid, 2)
            self.assertEqual(m["status"], "Deployed")

    def test_exit_rescue_requires_rescue_mode(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_exit_rescue", {"machine_id": 1})
        self.assertFalse(res["ok"])

    # ── Action aliases ──────────────────────────────────────────────────────
    def test_dhcp_configure_alias_enables_and_clears_broken(self):
        sid = self._session("maas-dhcp")
        state = bm.get_state(sid)["state"]
        self.assertFalse(state["maas"]["dhcp"]["enabled"])
        self.assertIn("dhcp_disabled", state.get("broken") or {})
        res = bm.apply_action(sid, "maas_dhcp_configure", {"enabled": True})
        self.assertTrue(res["ok"], res)
        state = bm.get_state(sid)["state"]
        self.assertTrue(state["maas"]["dhcp"]["enabled"])
        self.assertNotIn("dhcp_disabled", state.get("broken") or {})

    def test_add_zone_alias_creates_zone(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_add_zone", {"name": "az-c"})
        self.assertTrue(res["ok"], res)
        zones = bm.get_state(sid)["state"]["maas"]["zones"]
        self.assertTrue(any(z["name"] == "az-c" for z in zones))

    def test_add_pool_alias_creates_pool(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_add_pool", {"name": "inference"})
        self.assertTrue(res["ok"], res)
        pools = bm.get_state(sid)["state"]["maas"]["resource_pools"]
        self.assertTrue(any(p["name"] == "inference" for p in pools))

    # ── DNS records / users ──────────────────────────────────────────────────
    def test_add_dns_record(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_add_dns_record", {"name": "new-host", "data": "10.10.1.99"})
        self.assertTrue(res["ok"], res)
        domains = bm.get_state(sid)["state"]["maas"]["domains"]
        domain = next(d for d in domains if d["name"] == "maas")
        self.assertTrue(any(
            r["name"] == "new-host" and r["data"] == "10.10.1.99" for r in domain["records"]
        ))

    def test_create_and_delete_user(self):
        sid = self._session("maas-commission")
        res = bm.apply_action(sid, "maas_create_user", {"username": "lab-user", "email": "lab@maas.local"})
        self.assertTrue(res["ok"], res)
        users = bm.get_state(sid)["state"]["maas"]["users"]
        self.assertTrue(any(u["username"] == "lab-user" for u in users))
        res = bm.apply_action(sid, "maas_delete_user", {"username": "lab-user"})
        self.assertTrue(res["ok"], res)
        users = bm.get_state(sid)["state"]["maas"]["users"]
        self.assertFalse(any(u["username"] == "lab-user" for u in users))

    # ── Settings leaves clear scenario blockers ───────────────────────────
    def test_settings_update_clears_ntp_and_commissioning_flags(self):
        sid = self._session("maas-settings")
        state = bm.get_state(sid)["state"]
        self.assertIn("settings_ntp_wrong", state.get("broken") or {})
        self.assertIn("settings_commissioning_incomplete", state.get("broken") or {})
        res = bm.apply_action(sid, "maas_update_settings", {
            "ntp_servers": "ntp.ubuntu.com",
            "commissioning_distro_series": "jammy",
        })
        self.assertTrue(res["ok"], res)
        state = bm.get_state(sid)["state"]
        self.assertNotIn("settings_ntp_wrong", state.get("broken") or {})
        self.assertNotIn("settings_commissioning_incomplete", state.get("broken") or {})

    # ── Commissioning script attach clears scripts_unattached ─────────────
    def test_attach_script_clears_scripts_unattached(self):
        sid = self._session("ai-infra-maas-scripts-users")
        state = bm.get_state(sid)["state"]
        self.assertIn("scripts_unattached", state.get("broken") or {})
        self.assertIn("needs_operator_user", state.get("broken") or {})
        self.assertFalse(any(u.get("username") == "operator" for u in state["maas"]["users"]))
        res = bm.apply_action(sid, "maas_attach_script", {"name": "60-fixitlab-custom-check"})
        self.assertTrue(res["ok"], res)
        state = bm.get_state(sid)["state"]
        self.assertNotIn("scripts_unattached", state.get("broken") or {})
        res = bm.apply_action(sid, "maas_create_user", {"username": "operator", "email": "ops@maas.local"})
        self.assertTrue(res["ok"], res)
        state = bm.get_state(sid)["state"]
        self.assertNotIn("needs_operator_user", state.get("broken") or {})
