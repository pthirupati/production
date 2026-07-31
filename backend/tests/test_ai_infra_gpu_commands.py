"""AI Infra GPU command matrix — dmon/pmon stream paced lines."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.shell import StreamedCommandResult
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
        self.assertTrue(any("pwr" in ln.lower() or "gtemp" in ln.lower() or ln.startswith("#") for ln in out.lines[:3]))
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
