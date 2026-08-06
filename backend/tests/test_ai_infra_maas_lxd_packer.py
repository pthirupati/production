"""AI Infra MAAS / LXD / Packer / VyOS baremetal command depth."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.shell import StreamedCommandResult
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


class AiInfraMaasLxdPackerTests(SimpleTestCase):
    def test_maas_machines_read_and_commission(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-001-learn-maas",
            simulation_type="baremetal",
        )
        listing = str(engine.shell.run("maas admin machines read"))
        self.assertIn("gpu-node-01", listing)
        self.assertIn("Failed commissioning", listing)
        out = str(engine.shell.run("maas admin machine commission gpu-node-03"))
        self.assertIn("Commissioning", out)
        self.assertIn("Ready", out)
        self.assertIn("PXE", out)
        deploy = str(engine.shell.run("maas admin machine deploy"))
        self.assertIn("Deploy", deploy)
        self.assertIn("Curtin", deploy)

    def test_lxc_list_and_start(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-002-build-lxd",
            simulation_type="baremetal",
        )
        listing = str(engine.shell.run("lxc list"))
        self.assertIn("gpu-worker-1", listing)
        self.assertIn("STOPPED", listing)
        started = str(engine.shell.run("lxc start k8s-node-2"))
        self.assertIn("started", started.lower())
        again = str(engine.shell.run("lxc list"))
        self.assertIn("RUNNING", again)

    def test_packer_build_streams_on_gpu_sim_type(self):
        # Packer scenarios use simulation_type=gpu — baremetal module must still load.
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-010-integration-packer",
            simulation_type="gpu",
        )
        out = engine.shell.run("packer build gpu-h100.pkr.hcl")
        self.assertIsInstance(out, StreamedCommandResult)
        blob = str(out)
        self.assertIn("CVE", blob)
        self.assertIn("PASS", blob)
        self.assertIn("h100", blob.lower())
        self.assertIn("Publishing", blob)
        boots = str(engine.shell.run("maas admin boot-resources read"))
        self.assertIn("custom/h100-jammy", boots)

    def test_packer_cve_gate_blocks_publish(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-packer-cve-fail",
            simulation_type="gpu",
        )
        out = engine.shell.run("packer build gpu-h100-cve-fail.pkr.hcl")
        self.assertIsInstance(out, StreamedCommandResult)
        blob = str(out)
        self.assertIn("FAIL", blob)
        self.assertIn("blocked publish", blob)
        self.assertNotIn("Publishing artifact", blob)
        boots = str(engine.shell.run("maas admin boot-resources read"))
        self.assertNotIn("custom/h100-jammy", boots)

    def test_vyos_interfaces_on_pxe_lab(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-007-automation-pxe",
            simulation_type="baremetal",
        )
        out = str(engine.shell.run("vyos show interfaces"))
        self.assertIn("eth1", out)
        self.assertIn("pxe", out.lower())

    def test_vyos_configure_commit_rollback(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-007-automation-pxe",
            simulation_type="baremetal",
        )
        self.assertIn("[edit]", str(engine.shell.run("configure")))
        self.assertEqual(str(engine.shell.run("set interfaces ethernet eth2 address 10.64.99.1/24")).strip(), "")
        commit = str(engine.shell.run("commit"))
        self.assertIn("Commit complete", commit)
        conf = str(engine.shell.run("show configuration"))
        self.assertIn("eth2", conf)
        rb = str(engine.shell.run("rollback 1"))
        self.assertIn("Rollback complete", rb)
        conf2 = str(engine.shell.run("show configuration"))
        self.assertNotIn("# set interfaces ethernet eth2", conf2)

    def test_maas_commission_streams_pxe_steps(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="baremetal",
        )
        out = engine.shell.run("maas admin machine commission gpu-node-04")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertGreaterEqual(len(out.lines), 5)
        self.assertTrue(any("TFTP" in ln or "DHCP" in ln for ln in out.lines))

    def test_maas_was_unreachable_before_filter_fix(self):
        """Regression: maas used to return None because only ipmitool matched."""
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="baremetal",
        )
        out = str(engine.shell.run("maas admin machines read"))
        self.assertNotEqual(out.strip(), "")
        self.assertIn("hostname", out)


class LxdGpuPassthroughIntegrationTests(SimpleTestCase):
    def test_launch_gpu_device_nvidia_smi(self):
        from apps.vmware_sim import baremetal_engine as bm
        from django.core.cache import cache
        cache.clear()
        sid = "test-lxd-gpu-e2e"
        bm.drop_session(sid)
        bm.get_state(sid, "ai-infra-lxd-gpu-passthrough")
        bm.apply_action(sid, "login", {"user": "admin"})
        res = bm.apply_action(sid, "lxd_launch", {
            "name": "gpu-burn-e2e",
            "image": "ubuntu:22.04",
            "profiles": ["default", "gpu-passthrough"],
        })
        self.assertTrue(res["ok"], res)
        add = bm.apply_action(sid, "lxd_config_device_add", {
            "name": "gpu-burn-e2e",
            "device": "gpu0",
            "type": "gpu",
            "pci": "0000:19:00.0",
        })
        self.assertTrue(add["ok"], add)
        exe = bm.apply_action(sid, "lxd_exec_echo", {
            "name": "gpu-burn-e2e",
            "command": "nvidia-smi",
        })
        self.assertTrue(exe["ok"], exe)
        self.assertIn("NVIDIA-SMI", exe["output"])
        self.assertIn("H100", exe["output"])
        disk = bm.apply_action(sid, "lxd_config_device_add", {
            "name": "gpu-burn-e2e",
            "device": "data",
            "type": "disk",
            "path": "/mnt/data",
            "size": "50GB",
        })
        self.assertTrue(disk["ok"], disk)
        lsblk = bm.apply_action(sid, "lxd_exec_echo", {
            "name": "gpu-burn-e2e",
            "command": "lsblk",
        })
        self.assertIn("data", lsblk["output"])


class PackerMaasDeployChainTests(SimpleTestCase):
    def test_factory_publish_then_maas_deploy(self):
        from unittest import mock
        from apps.vmware_sim import baremetal_engine as bm
        from django.core.cache import cache
        cache.clear()
        sid = "test-packer-maas-e2e"
        bm.drop_session(sid)
        bm.get_state(sid, "ai-infra-packer-publish")
        bm.apply_action(sid, "login", {"user": "admin"})
        start = bm.apply_action(sid, "packer_factory_start_pipeline", {
            "sku": "h100",
            "force_cve": False,
            "nvidia_marker": True,
        })
        self.assertTrue(start.get("ok"), start)
        for _ in range(20):
            run = (bm.apply_action(sid, "packer_factory_get_state", {}).get("active_run") or {})
            jobs = {j["id"]: j for j in (run.get("jobs") or [])}
            vuln = jobs.get("vuln-scan") or {}
            if vuln.get("status") == "failed":
                bm.apply_action(sid, "packer_factory_advance_job", {})  # remediate
            if run.get("publish_enabled"):
                break
            adv = bm.apply_action(sid, "packer_factory_advance_job", {})
            if not adv.get("ok") and adv.get("error"):
                break
        final = bm.apply_action(sid, "packer_factory_get_state", {})
        if not (final.get("active_run") or {}).get("publish_enabled"):
            pub = bm.apply_action(sid, "maas_publish_boot_resource", {"sku": "h100"})
        else:
            pub = bm.apply_action(sid, "packer_factory_publish_artifact", {"sku": "h100"})
        self.assertTrue(pub.get("ok"), pub)
        names = {r["name"] for r in bm.get_state(sid)["state"]["maas"]["boot_resources"]}
        self.assertIn("custom/h100-jammy", names)
        # Commission + deploy with custom image
        base = 9_000_000.0
        with mock.patch.object(bm, "_now", return_value=base):
            bm.apply_action(sid, "maas_commission", {"machine_id": 2})
        with mock.patch.object(bm, "_now", return_value=base + bm.COMMISSION_SECONDS + 1):
            self.assertEqual(
                next(m for m in bm.get_state(sid)["state"]["maas"]["machines"] if m["id"] == 2)["status"],
                "Ready",
            )
            t = base + bm.COMMISSION_SECONDS + 1
        with mock.patch.object(bm, "_now", return_value=t):
            dep = bm.apply_action(sid, "maas_deploy", {
                "machine_id": 2,
                "boot_resource": "custom/h100-jammy",
            })
            self.assertTrue(dep["ok"], dep)
        with mock.patch.object(bm, "_now", return_value=t + bm.DEPLOY_SECONDS + 1):
            m = next(x for x in bm.get_state(sid)["state"]["maas"]["machines"] if x["id"] == 2)
            self.assertEqual(m["status"], "Deployed")
            self.assertIn("h100", (m.get("os") or m.get("boot_resource") or "").lower())
