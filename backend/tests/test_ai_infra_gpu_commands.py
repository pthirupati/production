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


def _healthy_gpu_engine(slug):
    """Engine for `slug` with the driver brought up, as a learner would.

    GPU-track slugs now carry a deliberate driver fault (`topic_faults.GPU_KEYWORDS`),
    so `nvidia-smi` reports "couldn't communicate with the NVIDIA driver" on a fresh
    session. That is correct lab behaviour — it is the break the learner is there to
    fix — but the tests below are about the *command implementations*, which need
    working hardware to exercise.

    The fault is asserted before repairing it rather than stepped around, so this
    covers both halves: the lab really is broken at the start, and it really does
    come back. A test that merely picked a fault-free slug would have hidden the
    day the injection stopped firing.
    """
    engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type="gpu")
    assert "couldn't communicate" in str(engine.shell.run("nvidia-smi -L")), (
        f"{slug} was expected to start with an injected GPU driver fault; "
        "if the injection was narrowed, this test's premise changed"
    )
    for cmd in ("sudo modprobe nvidia", "sudo systemctl restart nvidia-persistenced"):
        engine.shell.run(cmd)
    assert "couldn't communicate" not in str(engine.shell.run("nvidia-smi -L")), (
        f"{slug} is NOT repairable by the documented driver steps — the lab is "
        "unsolvable, which is far worse than this test failing"
    )
    return engine


class AiInfraGpuCommandsTests(SimpleTestCase):
    def test_nvidia_smi_dmon_streams_lines(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        out = engine.shell.run("nvidia-smi dmon -c 3")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertGreaterEqual(len(out.lines), 4)
        self.assertTrue(
            any("pwr" in ln.lower() or "gtemp" in ln.lower() or ln.startswith("#") for ln in out.lines[:3])
        )
        blob = str(out)
        self.assertIn("gpu", blob.lower())

    def test_nvidia_smi_pmon_streams(self):
        engine = _healthy_gpu_engine("ai-infra-esc-dcgm-exporter-blank")
        out = engine.shell.run("nvidia-smi pmon -c 2")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertTrue(any("pid" in ln.lower() for ln in out.lines[:2]))

    def test_sku_h100_thermal_hero(self):
        sku = _resolve_gpu_sku("ai-infra-dcops-h100-gpu4-thermal")
        self.assertIn("H100", sku["name"])
        engine = _healthy_gpu_engine("ai-infra-dcops-h100-gpu4-thermal")
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
        engine = _healthy_gpu_engine("ai-infra-maas-commission-h100")
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
        engine = _healthy_gpu_engine("ai-infra-maas-commission-h100")
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
        engine = _healthy_gpu_engine("ai-infra-maas-commission-h100")
        out = str(engine.shell.run("nvidia-smi nvlink --status"))
        self.assertIn("GPU 7:", out)
        topo = str(engine.shell.run("nvidia-smi topo -m"))
        self.assertIn("GPU7", topo)

    def test_nvidia_proc_driver_sysfs(self):
        engine = _healthy_gpu_engine("ai-infra-maas-commission-h100")
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

    def test_dcgmi_diag_fails_from_ecc_state(self):
        """Audit §A1 — planted ECC counters must fail GPU Memory, not always Pass."""
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        gpus = engine.shell.state.gpus
        self.assertTrue(gpus)
        gpus[0].ecc_aggregate_uncorrected = 3
        gpus[0].remap_pending = True
        gpus[0].diag_memory_fail = True
        out = str(engine.shell.run("dcgmi diag -r 1"))
        self.assertIn("GPU Memory", out)
        self.assertIn("Fail", out)
        self.assertRegex(out, r"GPU Memory\s+\|\s+Fail")

    def test_dcgmi_stats_stable_across_calls(self):
        """Audit §A1 — dcgmi stats must not use random.randint (diagnosable)."""
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        g = engine.shell.state.gpus[0]
        g.power_w = 412.0
        g.util_gpu = 77
        g.util_mem = 41
        g.temp_c = 63
        a = str(engine.shell.run("dcgmi stats"))
        b = str(engine.shell.run("dcgmi stats"))
        self.assertEqual(a, b)
        self.assertIn("412", a)
        self.assertIn("77", a)
        self.assertIn("63", a)

    def test_nvlink_degraded_width_from_state(self):
        engine = _healthy_gpu_engine("ai-infra-dcops-h100-nvlink-degraded")
        g = engine.shell.state.gpus[0]
        g.ensure_default_nvlink(dense=True)
        g.nvlink_links[0] = {
            **g.nvlink_links[0],
            "width_gbps": 13.281,
            "active": False,
            "replay_errors": 42,
        }
        status = str(engine.shell.run("nvidia-smi nvlink --status"))
        self.assertIn("13.281", status)
        self.assertIn("Inactive", status)
        errors = str(engine.shell.run("nvidia-smi nvlink -e"))
        self.assertIn("Replay Errors: 42", errors)

    def test_query_gpu_reads_planted_temp(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        engine.shell.state.gpus[0].temp_c = 71
        out = str(
            engine.shell.run(
                "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits"
            )
        )
        self.assertTrue(out.strip().startswith("71"), msg=out)

    def test_vllm_respects_tensor_parallel_and_oom(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        # Inventory is SKU-sized; ask for more TP than GPUs → hard error.
        out = str(engine.shell.run(
            "vllm serve meta-llama/Llama-3 --tensor-parallel-size 99"
        ))
        self.assertIn("tensor_parallel_size", out)
        self.assertIn("larger than", out.lower())
        # Honour a valid TP in the ready banner.
        n = len(engine.shell.state.gpus)
        out = str(engine.shell.run(
            f"vllm serve meta-llama/Llama-3 --tensor-parallel-size {min(2, n)}"
        ))
        self.assertIn(f"tensor_parallel_size={min(2, n)}", out)
        self.assertIn("READY", out)
        self.assertIn("KV cache", out)
        # Planted OOM fails with a real CUDA message.
        engine.shell.state.gpus[0].oom = True
        engine.shell.state.gpus[0].memory_used_mib = engine.shell.state.gpus[0].memory_total_mib
        oom = str(engine.shell.run("vllm serve meta-llama/Llama-3 --tensor-parallel-size 1"))
        self.assertIn("CUDA out of memory", oom)
        self.assertIn("OutOfMemoryError", oom)

    def test_vllm_kv_cache_exhausted_by_max_model_len(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        # Fill most of GPU 0 so a huge max_model_len cannot reserve KV pages.
        g0 = engine.shell.state.gpus[0]
        g0.memory_used_mib = max(0, int(g0.memory_total_mib) - 512)
        out = str(engine.shell.run(
            "vllm serve meta-llama/Llama-3 --tensor-parallel-size 1 "
            "--gpu-memory-utilization 0.9 --max-model-len 200000"
        ))
        self.assertIn("KV cache", out)
        self.assertIn("max_model_len", out)
        self.assertNotIn("READY", out)

    def test_vllm_tp_must_divide_attention_heads(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        # 8B → 32 heads; TP=3 does not divide.
        out = str(engine.shell.run(
            "vllm serve meta-llama/Llama-3.1-8B-Instruct --tensor-parallel-size 3"
        ))
        self.assertIn("attention heads", out)
        self.assertIn("divisible", out.lower())
        self.assertNotIn("READY", out)

    def test_torchrun_nccl_hang_clears_with_ib_disable(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        engine.shell.state.nccl_hang = True
        hung = str(engine.shell.run("torchrun --nproc_per_node=2 train.py"))
        self.assertIn("allreduce timed out", hung)
        self.assertIn("NCCL_IB_DISABLE", hung)
        engine.shell.state.env["NCCL_IB_DISABLE"] = "1"
        ok = str(engine.shell.run("torchrun --nproc_per_node=2 train.py"))
        self.assertIn("Training completed successfully", ok)

    def test_torchrun_fsdp_oom_suggests_activation_checkpointing(self):
        engine = _healthy_gpu_engine("academy-ai-infra-003-operate-dcgm")
        engine.shell.state.gpus[0].oom = True
        out = str(engine.shell.run(
            "torchrun --nproc_per_node=1 --fsdp train.py"
        ))
        self.assertIn("FSDP", out)
        self.assertIn("activation checkpointing", out.lower())
        self.assertIn("OutOfMemoryError", out)
