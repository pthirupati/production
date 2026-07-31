"""AI Infra GPU command matrix — SKUs, dmon/pmon stream, amd-smi."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.shell import StreamedCommandResult
from apps.labs.provisioner.simulation.simulation_modules import _resolve_gpu_sku
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


class AiInfraGpuCommandsTests(SimpleTestCase):
    def test_nvidia_smi_dmon_streams_lines(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-003-operate-dcgm",
            simulation_type="gpu",
        )
        out = engine.shell.run("nvidia-smi dmon -c 3")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertGreaterEqual(len(out.lines), 4)
        self.assertTrue(
            any("pwr" in ln.lower() or "gtemp" in ln.lower() or ln.startswith("#") for ln in out.lines[:3])
        )
        blob = str(out)
        self.assertIn("gpu", blob.lower())

    def test_nvidia_smi_pmon_streams(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-esc-dcgm-exporter-blank",
            simulation_type="gpu",
        )
        out = engine.shell.run("nvidia-smi pmon -c 2")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertTrue(any("pid" in ln.lower() for ln in out.lines[:2]))

    def test_sku_h100_thermal_hero(self):
        sku = _resolve_gpu_sku("ai-infra-dcops-h100-gpu4-thermal")
        self.assertIn("H100", sku["name"])
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-dcops-h100-gpu4-thermal",
            simulation_type="gpu",
        )
        out = str(engine.shell.run("nvidia-smi -L"))
        self.assertIn("H100", out)
        self.assertIn("GPU 0:", out)

    def test_sku_h200_from_slug(self):
        sku = _resolve_gpu_sku("academy-ai-infra-099-operate-nvidia-smi-h200")
        self.assertIn("H200", sku["name"])
        self.assertEqual(sku["mem_mib"], 143771)

    def test_sku_b300_from_slug(self):
        sku = _resolve_gpu_sku("ai-infra-packer-b300-image")
        self.assertIn("B300", sku["name"])
        self.assertEqual(sku["arch"], "Blackwell")

    def test_sku_rocm_uses_mi300x(self):
        sku = _resolve_gpu_sku("academy-ai-infra-005-production-rocm")
        self.assertEqual(sku["vendor"], "amd")
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-005-production-rocm",
            simulation_type="gpu",
        )
        out = str(engine.shell.run("nvidia-smi"))
        self.assertIn("AMD", out)
        rocm = str(engine.shell.run("rocm-smi --showtemp"))
        self.assertIn("GPU", rocm)

    def test_nvidia_smi_query_sections(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="gpu",
        )
        for cmd in (
            "nvidia-smi -q -d MEMORY",
            "nvidia-smi -q -d TEMPERATURE",
            "nvidia-smi -q -d UTILIZATION",
            "nvidia-smi topo -m",
            "nvidia-smi --help",
        ):
            out = str(engine.shell.run(cmd))
            self.assertTrue(len(out) > 20, msg=cmd)

    def test_amd_smi_extras(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-015-production-rocm-2",
            simulation_type="gpu",
        )
        for cmd in (
            "amd-smi list",
            "amd-smi firmware",
            "amd-smi process",
            "amd-smi bad-pages",
            "amd-smi xgmi",
        ):
            out = str(engine.shell.run(cmd))
            self.assertTrue(len(out) > 10, msg=cmd)
