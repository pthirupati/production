"""Learner-facing terminal labels must never say Simulation."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.shell import SimulationStreamHolder
from apps.labs.provisioner.simulation.sim_types import lab_server_banner
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


class LabServerBannerTests(SimpleTestCase):
    def test_banner_never_contains_simulation(self):
        samples = [
            ("aws", "academy-aws-001-learn-ec2"),
            ("azure", "azure-attach-managed-disk"),
            ("gcp", "gcp-attach-persistent-disk"),
            ("openstack", "openstack-attach-cinder-volume"),
            ("vmware", "vmware-add-disk"),
            ("generic", "academy-linux-001-learn-users"),
            ("rhel", "boot-fail"),
        ]
        for sim_type, slug in samples:
            banner = lab_server_banner(sim_type, slug)
            self.assertNotRegex(banner, r"(?i)simulation|simulator|sandbox|mock|demo")

    def test_stream_banner_uses_lab_server_persona(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-aws-001-learn-ec2",
            simulation_type="aws",
        )
        holder = engine.create_stream()
        holder._timeout = 0.05
        chunks = []
        for _ in range(8):
            try:
                data = holder.recv(4096)
            except TimeoutError:
                break
            if not data:
                break
            chunks.append(data.decode("utf-8", errors="replace"))
        text = "".join(chunks)
        self.assertIn("AWS EC2 Lab Server", text)
        self.assertNotRegex(text, r"(?i)FixitLab Simulation|Simulation —")

    def test_default_stream_holder_banner(self):
        holder = SimulationStreamHolder(lambda _line: "")
        chunk = holder.recv(4096).decode("utf-8", errors="replace")
        self.assertIn("Lab Server — RHEL 9", chunk)
        self.assertNotIn("Simulation", chunk)
