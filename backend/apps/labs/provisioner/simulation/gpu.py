"""GPU troubleshooting on full RHEL OS + NVIDIA/DCGM commands."""

from __future__ import annotations

import random

from .base_sim import BaseRHELSimulator
from .rhel_shell import RHELShell

GPU_NAMES = ["NVIDIA A100-SXM4-40GB", "NVIDIA H100 80GB HBM3", "NVIDIA RTX 4090"]


class GPUSimulator(BaseRHELSimulator):
    """Full RHEL shell plus GPU-specific tooling."""

    def __init__(self, scenario_slug: str = "gpu-nvidia-fallen-off-bus"):
        super().__init__(scenario_slug=scenario_slug, hostname="gpu-node")
        self.state.gpu_healthy = False

    def _register_extras(self) -> None:
        sim = self

        def gpu_handler(parts: list[str], line: str) -> str | None:
            low = line.strip().lower()
            if not low:
                return None
            gpu_cmds = (
                "nvidia-smi", "dcgm", "dcgmi", "gpustat", "rocm-smi", "amd-smi",
                "lspci", "lsmod", "modprobe",
            )
            if not any(low.startswith(c) for c in gpu_cmds):
                return None
            return sim._gpu_command(line)

        self.shell.register_handler(gpu_handler)

    def _register_extras_on(self, shell: RHELShell) -> None:
        sim = self

        def gpu_handler(parts: list[str], line: str) -> str | None:
            low = line.strip().lower()
            gpu_cmds = ("nvidia-smi", "dcgm", "dcgmi", "gpustat", "rocm-smi", "amd-smi", "lspci", "lsmod", "modprobe")
            if not any(low.startswith(c) for c in gpu_cmds):
                return None
            return sim._gpu_command(line)

        shell.register_handler(gpu_handler)

    def _gpu_command(self, line: str) -> str:
        low = line.strip().lower()
        if low.startswith("nvidia-smi"):
            if self.state.gpu_healthy:
                return self._nvidia_smi()
            return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
        if low.startswith("dcgmi discovery"):
            return (
                "3 GPUs found.\n+--------+--------------------------------+\n"
                "| GPU ID | Device Name                    |\n"
                "+--------+--------------------------------+\n"
                "| 0      | NVIDIA A100-SXM4-40GB          |\n"
                "| 1      | NVIDIA A100-SXM4-40GB          |\n"
                "| 2      | NVIDIA H100 80GB HBM3          |\n"
                "+--------+--------------------------------+"
            )
        if low.startswith("dcgmi") or low.startswith("dcgm"):
            return "dcgmi: command executed (simulation). Use 'dcgmi discovery -l' for GPU list."
        if low.startswith("rocm-smi") or low.startswith("amd-smi"):
            return "======================= ROCm System Management Interface =======================\nGPU  Temp   AvgPwr  SCLK    MCLK     Fan  Perf  PwrCap  VRAM%  GPU%\n0    45.0c  32.0W   800Mhz  1600Mhz  0%   auto  300.0W   12%   0%"
        if low.startswith("lspci"):
            return "01:00.0 3D controller: NVIDIA Corporation GA100 [A100 SXM4 40GB]"
        if low.startswith("lsmod"):
            return "nvidia_uvm           1048576  2\nnvidia_drm             77824  0\nnvidia              56852480  42"
        if low.startswith("modprobe nvidia"):
            self.state.gpu_healthy = True
            return ""
        return f"{line}: OK (simulation)"

    def _nvidia_smi(self) -> str:
        util = random.randint(0, 95)
        mem_used = random.randint(1000, 38000)
        return f"""Fri Jun 14 10:00:00 2026
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.54.03    Driver Version: 535.54.03    CUDA Version: 12.2     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  {GPU_NAMES[0]:<18}| 00000000:01:00.0 Off |                    0 |
| N/A   42C    P0    68W / 400W |  {mem_used:5d}MiB / 40960MiB |     {util:3d}%      Default |
+-------------------------------+----------------------+----------------------+
"""
