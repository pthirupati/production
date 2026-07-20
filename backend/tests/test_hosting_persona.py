"""Hosting persona + disk-full fault injection integrity."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.hosting_persona import (
    apply_hosting_persona,
    resolve_host_platform,
)
from apps.labs.provisioner.simulation.sim_types import infer_sim_type, lab_server_banner
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


class HostingPersonaTests(SimpleTestCase):
    def test_academy_aws_infers_aws_and_amazon_linux(self):
        self.assertEqual(infer_sim_type("generic", "academy-aws-022-build-waf", "aws"), "aws")
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-aws-022-build-waf",
            simulation_type="generic",
        )
        osrel = engine.shell.state.read_file("/etc/os-release") or ""
        self.assertIn("Amazon Linux", osrel)
        self.assertNotIn("Red Hat Enterprise Linux", osrel)
        dmi = engine.shell.run("dmidecode -t 1")
        self.assertIn("Amazon EC2", dmi)
        self.assertNotIn("ProLiant", dmi)
        banner = lab_server_banner("generic", "academy-aws-022-build-waf")
        self.assertIn("Amazon Linux", banner)
        self.assertNotRegex(banner, r"(?i)simulation|sandbox|mock")

    def test_linux_lab_gets_concrete_host_platform(self):
        platform = resolve_host_platform("generic", "disk-full", tech_slug="linux")
        self.assertIn(platform, ("vmware", "aws", "azure", "gcp", "baremetal"))

    def test_disk_full_shows_pressure(self):
        engine = UnifiedSimulationEngine(scenario_slug="disk-full", simulation_type="generic")
        df = engine.shell.run("df -h")
        self.assertIn("98%", df)
        procs = engine.shell.run("ps aux")
        self.assertIn("log_generator", procs)
        du = engine.shell.run("du -sh /var/log/app")
        # Should report something large (G or multi-M), not a tiny empty dir
        self.assertTrue(any(u in du for u in ("G", "M")), msg=du)


class DiskFullPresetTests(SimpleTestCase):
    def test_sim_disk_full_also_presets(self):
        engine = UnifiedSimulationEngine(scenario_slug="sim-disk-full", simulation_type="generic")
        self.assertIn("98%", engine.shell.run("df"))
