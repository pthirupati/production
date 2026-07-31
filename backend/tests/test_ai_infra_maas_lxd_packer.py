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
        self.assertIn("h100", blob.lower())

    def test_vyos_interfaces_on_pxe_lab(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-007-automation-pxe",
            simulation_type="baremetal",
        )
        out = str(engine.shell.run("vyos show interfaces"))
        self.assertIn("eth1", out)
        self.assertIn("pxe", out.lower())

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
