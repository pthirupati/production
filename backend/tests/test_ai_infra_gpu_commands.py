"""AI Infra GPU command matrix — SKUs, dmon/pmon stream, amd-smi."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.shell import StreamedCommandResult
from apps.labs.provisioner.simulation.simulation_modules import _resolve_gpu_sku
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


# Table-driven coverage for the NVIDIA / AMD / DCGM depth wave (TODO 186–187).
# Each command must return a non-trivial, recognizable payload.
_NVIDIA_MATRIX = (
    ("nvidia-smi -L", ("GPU 0:", "H100")),
    ("nvidia-smi --help", ("Usage:", "query-gpu")),
    ("nvidia-smi topo -m", ("NV18", "Legend")),
    ("nvidia-smi topo -p", ("PIX", "GPU0")),
    ("nvidia-smi topo -c", ("NUMA", "Affinity")),
    ("nvidia-smi nvlink --status", ("Link 0:", "GB/s")),
    ("nvidia-smi nvlink -e", ("Replay Errors", "CRC")),
    ("nvidia-smi mig -lgip", ("MIG 1g.10gb", "profiles")),
    ("nvidia-smi mig -lgi", ("MIG 3g.40gb", "instances")),
    ("nvidia-smi compute-apps", ("gpu_uuid", "python")),
    ("nvidia-smi --query-compute-apps=pid,process_name --format=csv", ("pid",)),
    ("nvidia-smi --query-accounted-apps=gpu_uuid,pid --format=csv", ("gpu_uuid",)),
    ("nvidia-smi conf-compute -f", ("Confidential", "CC Mode")),
    ("nvidia-smi clocks", ("Graphics", "MHz")),
    ("nvidia-smi -q -d MEMORY", ("FB Memory", "MiB")),
    ("nvidia-smi -q -d TEMPERATURE", ("GPU Current Temp",)),
    ("nvidia-smi -q -d UTILIZATION", ("Gpu", "%")),
    ("nvidia-smi -q -d POWER", ("Power Draw",)),
    ("nvidia-smi -q -d ECC", ("Ecc Mode", "Enabled")),
    ("nvidia-smi -q -d CLOCK", ("Clocks", "SM")),
    ("nvidia-smi -q -d PCI", ("PCIe Generation", "Link Width")),
    ("nvidia-smi -q -d PERFORMANCE", ("Throttle",)),
    ("nvidia-smi -q -d ACCOUNTING", ("Accounting Mode",)),
    ("nvidia-smi -q -d PAGE_RETIREMENT", ("Retired Pages",)),
    (
        "nvidia-smi --query-gpu=index,name,uuid,temperature.gpu,utilization.gpu,"
        "memory.used,power.draw,clocks.sm,ecc.mode.current,pcie.link.gen.current,"
        "persistence_mode,compute_mode,serial,vbios_version "
        "--format=csv,noheader,nounits",
        ("H100",),
    ),
    (
        "nvidia-smi -i 0 --query-gpu=index,name --format=csv,noheader",
        ("0,", "H100"),
    ),
    ("nvidia-smi -pm 1", ("All done",)),
    ("nvidia-smi --lock-gpu-clocks=1410,1410", ("All done",)),
    ("nvidia-smi --gpu-reset -i 0", ("All done",)),
    ("dcgmi discovery -l", ("GPUs found", "Device Information")),
    ("dcgmi health -r", ("Overall Health", "Healthy")),
    ("dcgmi stats", ("GPU Stats", "Power")),
    ("dcgmi group -l", ("GROUP 0", "GPUs:")),
    ("dcgmi modules", ("Core", "Health")),
    ("dcgmi policy", ("Policy",)),
    ("dcgmi diag -r 1", ("Pass",)),
    ("dcgm-exporter --version", ("dcgm-exporter version",)),
    ("gpustat", ("H100",)),
    ("nvcc --version", ("Cuda compilation",)),
)

_AMD_MATRIX = (
    ("amd-smi list", ("MI300X", "BDF")),
    ("amd-smi firmware", ("VBIOS", "MARKET_NAME")),
    ("amd-smi process", ("PID", "MEM_USAGE")),
    ("amd-smi bad-pages", ("RETIRED_PAGES",)),
    ("amd-smi xgmi", ("XGMI", "UP")),
    ("amd-smi event", ("EVENT",)),
    ("amd-smi topology", ("Weight", "GPU0")),
    ("amd-smi version", ("AMDSMI", "ROCm")),
    ("rocm-smi --showtemp", ("Temp", "GPU[")),
    ("rocm-smi --showpower", ("Power", "GPU[")),
    ("rocm-smi --showmeminfo vram", ("VRAM Total",)),
    ("rocm-smi --showproductname", ("Instinct MI300X",)),
    ("rocm-smi --showdriverversion", ("Driver",)),
    ("rocm-smi --showfwinfo", ("VBIOS", "FW")),
    ("rocm-smi --showtopo", ("XGMI", "Weight")),
)


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

    def test_nvidia_command_matrix(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="gpu",
        )
        for cmd, needles in _NVIDIA_MATRIX:
            with self.subTest(cmd=cmd):
                out = str(engine.shell.run(cmd))
                self.assertGreater(len(out), 15, msg=f"empty: {cmd}")
                for needle in needles:
                    self.assertIn(needle, out, msg=f"{cmd} missing {needle!r}")

    def test_amd_command_matrix(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-005-production-rocm",
            simulation_type="gpu",
        )
        for cmd, needles in _AMD_MATRIX:
            with self.subTest(cmd=cmd):
                out = str(engine.shell.run(cmd))
                self.assertGreater(len(out), 10, msg=f"empty: {cmd}")
                for needle in needles:
                    self.assertIn(needle, out, msg=f"{cmd} missing {needle!r}")

    def test_nvlink_covers_full_gpu_count(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="gpu",
        )
        out = str(engine.shell.run("nvidia-smi nvlink --status"))
        self.assertIn("GPU 7:", out)
        topo = str(engine.shell.run("nvidia-smi topo -m"))
        self.assertIn("GPU7", topo)

    def test_nvidia_proc_driver_sysfs(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="gpu",
        )
        ver = str(engine.shell.run("cat /proc/driver/nvidia/version"))
        self.assertIn("NVRM version", ver)
        self.assertIn("550", ver)

    def test_amd_sysfs_clock_steps(self):
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-005-production-rocm",
            simulation_type="gpu",
        )
        sclk = str(engine.shell.run("cat /sys/class/drm/card0/device/pp_dpm_sclk"))
        self.assertIn("Mhz", sclk)
        self.assertIn("*", sclk)
