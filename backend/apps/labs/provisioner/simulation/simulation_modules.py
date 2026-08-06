"""Technology modules plugged into the unified RHEL simulation engine."""

from __future__ import annotations

import random
import re
import time
from typing import TYPE_CHECKING

from .devops_state import DevOpsState
from .docker_state import DockerState
from .k8s_cluster import K8sCluster
from .networking_state import NetworkingState
from .rhel_os import SimService
from .rhel_shell import RHELShell

if TYPE_CHECKING:
    from .unified_sim import UnifiedSimulationEngine

GPU_NAMES = ["NVIDIA A100-SXM4-40GB", "NVIDIA H100 80GB HBM3", "NVIDIA RTX 4090"]


def _sync_gpu_identity(engine: "UnifiedSimulationEngine", *, healthy: bool) -> None:
    """Mirror driver health into ServerIdentity (virtualized GPU only)."""
    session_id = getattr(engine, "lab_session_id", None) or getattr(engine, "session_id", None)
    if not session_id:
        return
    try:
        from . import server_identity as si
        primary = si.get_primary(str(session_id))
        if not primary:
            primary = si.seed_gpu_node(
                str(session_id),
                hostname=getattr(engine.shell.state, "hostname", None) or "gpu-node-01",
                healthy=healthy,
            )
        else:
            si.set_gpu(
                str(session_id),
                primary["id"],
                driver_loaded=healthy,
                health="healthy" if healthy else "failed",
                source="terminal",
            )
    except Exception:
        # Identity sync must never break the shell facade.
        pass


def apply_simulation_context(engine: "UnifiedSimulationEngine") -> None:
    """Configure hostname, services, and flags for the simulation persona."""
    sim_type = engine.simulation_type
    state = engine.shell.state
    slug = engine.scenario_slug

    # Hosting persona first so /etc/os-release + dmidecode match Hosted-as banner
    # (AWS → Amazon Linux, VMware → VMware DMI, bare metal → HPE, …).
    try:
        from .hosting_persona import apply_hosting_persona, resolve_host_platform

        platform = resolve_host_platform(sim_type, slug)
        apply_hosting_persona(state, platform, slug=slug)
        engine.host_platform = platform
    except Exception:
        engine.host_platform = "linux"

    if sim_type == "ansible" or "ansible" in slug:
        state.set_prompt_user("ansible")
        state.hostname = "ansible-control"
    elif sim_type == "gpu" or "gpu" in slug or "nvidia" in slug:
        state.hostname = "gpu-node"
    elif sim_type == "kubernetes" or "k8s" in slug:
        state.hostname = "k8s-master"
        state._mkdir("/root/.kube")
        state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\n")
    elif sim_type == "database":
        state.hostname = "db-server"
    elif sim_type == "baremetal":
        state.hostname = "bmc-host"
    elif sim_type == "python" or slug.startswith("sim-python"):
        # `sim-python-*` labs ship without a simulation_type (so they seed as
        # "generic"); trigger the broken-Python persona by slug too, otherwise
        # /opt/app/main.py is never written and `py_compile` passes fail-open.
        state.hostname = "dev-server"
        state._mkdir("/home/dev")
        state._mkdir("/opt/app")
        if not state.read_file("/home/dev/app.py"):
            state._write_file("/home/dev/app.py", '#!/usr/bin/env python3\nprint("hello"\n')
        if "pip" in slug:
            # Keep the missing-package narrative but ship a genuinely broken file
            # (unclosed call) so the `py_compile` check stays fail-closed — a
            # syntactically-valid import would compile and pass before any fix.
            state._write_file("/opt/app/main.py", 'import requests\nprint("starting"\n')
        else:
            state._write_file("/opt/app/main.py", 'print("hello"\n')
    elif (
        sim_type == "devops"
        or "devops" in slug
        or "ci-pipeline" in slug
        or "helm" in slug
        or "gitops" in slug
        or slug.startswith("academy-gitops")
    ):
        state.hostname = "gitops-runner" if "gitops" in slug else "gitlab-runner"
    elif sim_type == "networking" or "bgp" in slug or "ntp-drift" in slug:
        state.hostname = "core-router"
    elif sim_type == "terraform" or slug.startswith("terraform-"):
        state.hostname = "terraform-ws"
        state.cwd = "/root/terraform"
        state._mkdir("/root/terraform")

    if "unbound" in slug:
        state._mkdir("/opt/scripts")
        state._write_file(
            "/opt/scripts/deploy.sh",
            "#!/bin/bash\nset -u\necho ${MISSING_VAR}\n",
        )

    # DevOps / git labs get a real repository with history and a feature branch
    # so git status/log/branch/merge/push all work against meaningful state.
    if (
        sim_type == "devops"
        or "git" in slug
        or "ci-pipeline" in slug
        or "devops" in slug
        or "gitops" in slug
    ):
        _seed_devops_git_repo(state)

    # `sim-rhel-ssh-stop` is graded by `systemctl is-active sshd`; sshd must start
    # stopped or the check passes before the learner restarts it (fail-open).
    if "ssh-stop" in slug:
        state.services["sshd"] = SimService(
            "sshd", active="inactive", enabled="enabled", description="OpenSSH server daemon",
        )

    if "docker" in slug:
        # A scenario preset may have already put the docker unit (or a related
        # unit like docker-socket-proxy) into a failed state — do NOT clobber
        # that, or the fail-closed check would auto-pass.
        existing_docker = state.services.get("docker")
        preset_broke_docker = bool(existing_docker and existing_docker.active != "active")
        is_down_slug = "daemon-stopped" in slug or "stopped" in slug or "daemon-down" in slug
        # Task-style docker sims whose objective is to get a container running
        # (`docker ps | grep Up`) must start with NO running container, otherwise
        # the check passes before any work (fail-open).
        needs_container_up = any(
            k in slug for k in ("compose-down", "image-pull", "network-connect", "container-exited", "exited")
        )
        # Flagship compose labs: the daemon is UP but the compose stack is not
        # running yet (`docker ps` must be empty until the learner brings it up).
        try:
            from .flagship_presets import FLAGSHIP_DOCKER_SLUGS
        except Exception:  # pragma: no cover
            FLAGSHIP_DOCKER_SLUGS = set()
        is_compose_flagship = slug in FLAGSHIP_DOCKER_SLUGS
        if preset_broke_docker or is_down_slug:
            state.services["docker"] = SimService(
                "docker", active="failed" if preset_broke_docker else "inactive",
                enabled="enabled", description="Docker Engine",
            )
            engine._container_running = False
        elif is_compose_flagship or needs_container_up:
            state.services["docker"] = SimService(
                "docker", active="active", enabled="enabled", description="Docker Engine",
            )
            engine._container_running = False
            for c in getattr(engine.docker, "containers", []):
                c["state"] = "exited"
        else:
            state.services["docker"] = SimService(
                "docker", active="active", enabled="enabled", description="Docker Engine",
            )
            engine._container_running = "exited" not in slug

    # Always ensure docker service exists for generic/docker scenarios
    if sim_type in ("generic", "rhel") or "docker" in slug:
        state.services.setdefault(
            "docker",
            SimService("docker", active="active", enabled="enabled", description="Docker Engine"),
        )


def register_modules(engine: "UnifiedSimulationEngine", shell: RHELShell | None = None) -> None:
    """Register command handlers — generic gets ALL modules; others get RHEL + their tech."""
    sh = shell or engine.shell
    sim_type = engine.simulation_type
    slug = (getattr(engine, "scenario_slug", "") or "").lower()

    # Every simulation includes full RHEL; generic enables all tech stacks
    modules = _modules_for_type(sim_type)
    # AI Infra labs span MAAS/LXD/Packer/VyOS (baremetal) + GPU CLI + AWX — pull
    # the complementary modules in so commission/build/GPU commands all work on
    # the same Lab Terminal regardless of primary simulation_type.
    if "ai-infra" in slug or slug.startswith("academy-ai-infra"):
        modules |= {"baremetal", "gpu"}
        if "awx" in slug or "ansible" in slug:
            modules.add("ansible")
        if any(k in slug for k in ("k8s", "kube", "operator", "device-plugin")):
            modules |= {"kubernetes", "docker"}
    elif any(k in slug for k in ("maas", "lxd", "packer", "vyos", "pxe", "bmc")):
        modules.add("baremetal")
    if "gpu" in modules:
        _register_gpu(engine, sh)
    if "kubernetes" in modules:
        _register_k8s(engine, sh)
    if "ansible" in modules:
        _register_ansible(engine, sh)
    if "baremetal" in modules:
        _register_baremetal(engine, sh)
    if "database" in modules:
        _register_database(engine, sh)
    if "docker" in modules:
        _register_docker(engine, sh)
    if "devops" in modules:
        _register_devops(engine, sh)
    if "networking" in modules:
        _register_networking(engine, sh)
    if "terraform" in modules:
        _register_terraform(engine, sh)
    if "windows" in modules:
        _register_windows(engine, sh)


def _modules_for_type(sim_type: str) -> set[str]:
    if sim_type == "generic":
        return {"gpu", "kubernetes", "ansible", "baremetal", "database", "docker", "devops", "networking", "terraform"}
    if sim_type in ("ansible", "ansible-awx", "awx"):
        return {"ansible"}
    if sim_type == "devops":
        return {"devops", "docker", "terraform"}
    if sim_type == "networking":
        return {"networking"}
    if sim_type == "terraform":
        return {"terraform", "docker"}
    # Cloud / hypervisor guests still need dmidecode (and occasional ipmi) so the
    # Lab Terminal hardware identity matches Hosted-as — reuse the baremetal module.
    if sim_type in ("aws", "azure", "gcp", "openstack", "vmware"):
        return {sim_type, "baremetal", "docker"}
    if sim_type in ("baremetal", "datacenter"):
        return {"baremetal"}
    return {sim_type, "docker"} if sim_type == "rhel" else {sim_type}


# Datacenter GPU profiles. Default is 8× H100 SXM; scenario slug can select
# H200 / B300 / A100 / MI300X so labs match the ticket hardware.
_SMI_DRIVER = "550.90.07"
_SMI_CUDA = "12.4"
_SMI_GPU_NAME = "NVIDIA H100 80GB HBM3"
_SMI_GPU_COUNT = 8
_SMI_MEM_TOTAL_MIB = 81559  # H100 80GB reports 81559 MiB in nvidia-smi
_SMI_ARCH = "Hopper"
_SMI_PCI_ID = "GH100"
_SMI_PWR_CAP = 700

_GPU_SKUS: dict[str, dict] = {
    "h100": {
        "name": "NVIDIA H100 80GB HBM3",
        "count": 8,
        "mem_mib": 81559,
        "arch": "Hopper",
        "pci": "GH100",
        "pwr_cap": 700,
        "driver": "550.90.07",
        "cuda": "12.4",
        "vendor": "nvidia",
    },
    "h200": {
        "name": "NVIDIA H200 141GB HBM3e",
        "count": 8,
        "mem_mib": 143771,
        "arch": "Hopper",
        "pci": "GH100",
        "pwr_cap": 700,
        "driver": "550.90.07",
        "cuda": "12.4",
        "vendor": "nvidia",
    },
    "b300": {
        "name": "NVIDIA B300",
        "count": 8,
        "mem_mib": 196608,
        "arch": "Blackwell",
        "pci": "GB300",
        "pwr_cap": 1200,
        "driver": "570.86.15",
        "cuda": "12.8",
        "vendor": "nvidia",
    },
    "a100": {
        "name": "NVIDIA A100-SXM4-80GB",
        "count": 8,
        "mem_mib": 81920,
        "arch": "Ampere",
        "pci": "GA100",
        "pwr_cap": 400,
        "driver": "535.161.08",
        "cuda": "12.2",
        "vendor": "nvidia",
    },
    "l40s": {
        "name": "NVIDIA L40S",
        "count": 4,
        "mem_mib": 46068,
        "arch": "Ada",
        "pci": "AD102",
        "pwr_cap": 350,
        "driver": "550.90.07",
        "cuda": "12.4",
        "vendor": "nvidia",
    },
    "a4000": {
        "name": "NVIDIA RTX A4000",
        "count": 1,
        "mem_mib": 16376,
        "arch": "Ampere",
        "pci": "GA104",
        "pwr_cap": 140,
        "driver": "550.90.07",
        "cuda": "12.4",
        "vendor": "nvidia",
    },
    "a6000": {
        "name": "NVIDIA RTX 6000 Ada Generation",
        "count": 1,
        "mem_mib": 49140,
        "arch": "Ada",
        "pci": "AD102",
        "pwr_cap": 300,
        "driver": "550.90.07",
        "cuda": "12.4",
        "vendor": "nvidia",
    },
    "mi300x": {
        "name": "AMD Instinct MI300X",
        "count": 8,
        "mem_mib": 196592,
        "arch": "CDNA3",
        "pci": "gfx942",
        "pwr_cap": 750,
        "driver": "6.2.0",
        "cuda": "",
        "vendor": "amd",
    },
}


def _resolve_gpu_sku(scenario_slug: str) -> dict:
    """Pick GPU SKU from scenario slug keywords; default H100 SXM8."""
    low = (scenario_slug or "").lower().replace("_", "-")
    if "b300" in low:
        return dict(_GPU_SKUS["b300"])
    if "h200" in low:
        return dict(_GPU_SKUS["h200"])
    if "a6000" in low or "6000-ada" in low or "rtx6000" in low:
        return dict(_GPU_SKUS["a6000"])
    if "a4000" in low or "rtx-a4000" in low:
        return dict(_GPU_SKUS["a4000"])
    if "l40s" in low or "l40" in low:
        return dict(_GPU_SKUS["l40s"])
    if "a100" in low:
        return dict(_GPU_SKUS["a100"])
    if "mi300" in low or "rocm" in low or ("amd" in low and "nvidia" not in low):
        return dict(_GPU_SKUS["mi300x"])
    if "h100" in low:
        return dict(_GPU_SKUS["h100"])
    return dict(_GPU_SKUS["h100"])


def _apply_gpu_sku_globals(sku: dict) -> None:
    """Bind module-level nvidia-smi constants for render helpers (per-handler)."""
    global _SMI_GPU_NAME, _SMI_GPU_COUNT, _SMI_MEM_TOTAL_MIB, _SMI_ARCH
    global _SMI_PCI_ID, _SMI_PWR_CAP, _SMI_DRIVER, _SMI_CUDA
    _SMI_GPU_NAME = sku["name"]
    _SMI_GPU_COUNT = int(sku["count"])
    _SMI_MEM_TOTAL_MIB = int(sku["mem_mib"])
    _SMI_ARCH = sku["arch"]
    _SMI_PCI_ID = sku["pci"]
    _SMI_PWR_CAP = int(sku["pwr_cap"])
    _SMI_DRIVER = sku.get("driver") or _SMI_DRIVER
    if sku.get("cuda"):
        _SMI_CUDA = sku["cuda"]


def _render_nvidia_smi_table() -> str:
    """Render the modern (driver 5xx) nvidia-smi summary table for the full node
    plus a realistic compute-process table. Values wiggle per call so successive
    runs look live, but topology (count/model/driver/mem) is fixed for the SKU."""
    now = time.strftime("%a %b %d %H:%M:%S %Y")
    pwr_cap = _SMI_PWR_CAP
    lines = [
        now,
        "+-----------------------------------------------------------------------------------------+",
        f"| NVIDIA-SMI {_SMI_DRIVER}              Driver Version: {_SMI_DRIVER}      CUDA Version: {_SMI_CUDA}      |",
        "|-----------------------------------------+------------------------+----------------------+",
        "| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |",
        "| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |",
        "|                                         |                        |               MIG M. |",
        "|=========================================+========================+======================|",
    ]
    busy = []  # (gpu_idx, mem_used) for the process table
    for i in range(_SMI_GPU_COUNT):
        active = random.random() < 0.6
        util = random.randint(70, 100) if active else random.randint(0, 4)
        mem_hi = max(12, int(_SMI_MEM_TOTAL_MIB * 0.95))
        mem_lo = max(3, int(_SMI_MEM_TOTAL_MIB * 0.5))
        mem_used = random.randint(mem_lo, mem_hi) if active else random.randint(3, 12)
        temp = random.randint(58, 74) if active else random.randint(28, 36)
        pwr = random.randint(int(pwr_cap * 0.55), pwr_cap - 10) if active else random.randint(68, 92)
        perf = "P0"
        bus = f"00000000:{(i + 1) * 0x10 + 1:02X}:00.0"
        # Fixed-width cells matching the separator (41 / 24 / 22 chars).
        c1a = f"  {i}  {_SMI_GPU_NAME}"
        c2a = f" {bus} Off"
        lines.append(f"|{c1a:<33}   On  |{c2a:<24}|                    0 |")
        c1b = f" N/A   {temp:2d}C    {perf}             {pwr:3d}W / {pwr_cap}W"
        c2b = f"  {mem_used:6d}MiB / {_SMI_MEM_TOTAL_MIB}MiB "
        c3b = f"    {util:3d}%      Default"
        lines.append(f"|{c1b:<41}|{c2b:<24}|{c3b:<22}|")
        lines.append(f"|{'':<41}|{'':<24}|{'             Disabled':<22}|")
        lines.append(
            "+-----------------------------------------+------------------------+----------------------+")
        if active:
            busy.append((i, mem_used))
    lines.append("")
    lines.append(
        "+-----------------------------------------------------------------------------------------+")
    lines.append(
        "| Processes:                                                                              |")
    lines.append(
        "|  GPU   GI   CI        PID   Type   Process name                              GPU Memory |")
    lines.append(
        "|        ID   ID                                                               Usage      |")
    lines.append(
        "|=========================================================================================|")
    if busy:
        for gpu_idx, mem_used in busy:
            pid = random.randint(20000, 65000)
            lines.append(
                f"|    {gpu_idx}   N/A  N/A    {pid:7d}      C   /opt/conda/bin/python                     {mem_used:5d}MiB |")
    else:
        lines.append(
            "|  No running processes found                                                             |")
    lines.append(
        "+-----------------------------------------------------------------------------------------+")
    return "\n".join(lines)


def _render_query_gpu(line: str) -> str:
    """Emulate `nvidia-smi --query-gpu=<fields> --format=csv[,noheader][,nounits]`
    across all GPUs. Honors the requested field list and the csv formatting
    modifiers so scripts that parse the output behave like on a real box."""
    m = re.search(r"--query-gpu[= ]([^\s]+)", line)
    fields = [f.strip() for f in (m.group(1) if m else "name").split(",") if f.strip()]
    fmt = re.search(r"--format[= ]([^\s]+)", line)
    fmt_opts = set(f.strip() for f in (fmt.group(1) if fmt else "csv").split(","))
    noheader = "noheader" in fmt_opts
    nounits = "nounits" in fmt_opts

    # Optional `-i N` / `--id=N` restricts rows to one GPU.
    only_idx = None
    mi = re.search(r"(?:-i|--id)[= ]?(\d+)", line)
    if mi:
        only_idx = int(mi.group(1))

    def _mem_used(i):
        return random.randint(40000, min(78000, _SMI_MEM_TOTAL_MIB - 100)) if i % 2 == 0 else random.randint(3, 12)

    units = {
        "index": ("", lambda i: str(i)),
        "name": ("", lambda i: _SMI_GPU_NAME),
        "uuid": ("", lambda i: f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}"),
        "pci.bus_id": ("", lambda i: f"00000000:{(i + 1) * 0x10 + 1:02X}:00.0"),
        "pci.device_id": ("", lambda i: "0x2330"),
        "pci.domain": ("", lambda i: "0x0000"),
        "pci.bus": ("", lambda i: f"0x{(i + 1) * 0x10 + 1:02x}"),
        "pci.device": ("", lambda i: "0x00"),
        "pci.sub_device_id": ("", lambda i: "0x1799"),
        "pcie.link.gen.current": ("", lambda i: "5"),
        "pcie.link.gen.max": ("", lambda i: "5"),
        "pcie.link.width.current": ("", lambda i: "16x"),
        "pcie.link.width.max": ("", lambda i: "16x"),
        "driver_version": ("", lambda i: _SMI_DRIVER),
        "vbios_version": ("", lambda i: "96.00.74.00.01"),
        "serial": ("", lambda i: f"13207{i:08d}"),
        "board_id": ("", lambda i: f"0x{0x10DE + i:04x}"),
        "temperature.gpu": (" C", lambda i: str(random.randint(30, 72))),
        "temperature.memory": (" C", lambda i: str(random.randint(36, 78))),
        "fan.speed": (" %", lambda i: "[N/A]"),
        "utilization.gpu": (" %", lambda i: str(random.randint(0, 100))),
        "utilization.memory": (" %", lambda i: str(random.randint(0, 95))),
        "utilization.encoder": (" %", lambda i: str(random.randint(0, 5))),
        "utilization.decoder": (" %", lambda i: str(random.randint(0, 5))),
        "memory.total": (" MiB", lambda i: str(_SMI_MEM_TOTAL_MIB)),
        "memory.used": (" MiB", lambda i: str(_mem_used(i))),
        "memory.free": (" MiB", lambda i: str(_SMI_MEM_TOTAL_MIB - _mem_used(i))),
        "memory.reserved": (" MiB", lambda i: "455"),
        "power.draw": (" W", lambda i: f"{random.uniform(70, max(80, _SMI_PWR_CAP - 20)):.2f}"),
        "power.limit": (" W", lambda i: f"{_SMI_PWR_CAP}.00"),
        "power.default_limit": (" W", lambda i: f"{_SMI_PWR_CAP}.00"),
        "power.max_limit": (" W", lambda i: f"{_SMI_PWR_CAP}.00"),
        "power.min_limit": (" W", lambda i: "100.00"),
        "enforced.power.limit": (" W", lambda i: f"{_SMI_PWR_CAP}.00"),
        "clocks.current.graphics": (" MHz", lambda i: str(random.randint(1200, 1980))),
        "clocks.current.sm": (" MHz", lambda i: str(random.randint(1200, 1980))),
        "clocks.current.memory": (" MHz", lambda i: str(random.choice((1593, 2619)))),
        "clocks.current.video": (" MHz", lambda i: str(random.randint(900, 1600))),
        "clocks.sm": (" MHz", lambda i: str(random.randint(1200, 1980))),
        "clocks.mem": (" MHz", lambda i: str(random.choice((1593, 2619)))),
        "clocks.gr": (" MHz", lambda i: str(random.randint(1200, 1980))),
        "clocks.max.sm": (" MHz", lambda i: "1980"),
        "clocks.max.memory": (" MHz", lambda i: "2619"),
        "clocks_throttle_reasons.supported": ("", lambda i: "0x00000000000001FF"),
        "clocks_throttle_reasons.active": ("", lambda i: "0x0000000000000000"),
        "clocks_throttle_reasons.gpu_idle": ("", lambda i: "Not Active"),
        "clocks_throttle_reasons.sw_power_cap": ("", lambda i: "Not Active"),
        "clocks_throttle_reasons.hw_thermal_slowdown": ("", lambda i: "Not Active"),
        "clocks_throttle_reasons.hw_power_brake_slowdown": ("", lambda i: "Not Active"),
        "clocks_throttle_reasons.sw_thermal_slowdown": ("", lambda i: "Not Active"),
        "ecc.mode.current": ("", lambda i: "Enabled"),
        "ecc.mode.pending": ("", lambda i: "Enabled"),
        "ecc.errors.corrected.volatile.device_memory": ("", lambda i: "0"),
        "ecc.errors.corrected.aggregate.device_memory": ("", lambda i: "0"),
        "ecc.errors.uncorrected.volatile.device_memory": ("", lambda i: "0"),
        "ecc.errors.uncorrected.aggregate.device_memory": ("", lambda i: "0"),
        "ecc.errors.uncorrected.aggregate.total": ("", lambda i: "0"),
        "ecc.errors.corrected.aggregate.total": ("", lambda i: "0"),
        "retired_pages.single_bit_ecc.count": ("", lambda i: "0"),
        "retired_pages.double_bit.count": ("", lambda i: "0"),
        "retired_pages.pending": ("", lambda i: "No"),
        "remapped_rows": ("", lambda i: "0"),
        "remapped_rows.pending": ("", lambda i: "No"),
        "remapped_rows.failure": ("", lambda i: "No"),
        "compute_mode": ("", lambda i: "Default"),
        "persistence_mode": ("", lambda i: "Enabled"),
        "accounting.mode": ("", lambda i: "Disabled"),
        "accounting.buffer_size": ("", lambda i: "4000"),
        "display_mode": ("", lambda i: "Disabled"),
        "display_active": ("", lambda i: "Disabled"),
        "encoder.stats.sessionCount": ("", lambda i: "0"),
        "encoder.stats.averageFps": ("", lambda i: "0"),
        "encoder.stats.averageLatency": ("", lambda i: "0"),
        "compute.apps.count": ("", lambda i: str(random.randint(0, 2))),
        "count": ("", lambda i: str(_SMI_GPU_COUNT)),
        "gpu_uuid": ("", lambda i: f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}"),
        "inforom.ecc": ("", lambda i: "2.0"),
        "inforom.oem": ("", lambda i: "2.0"),
        "inforom.img": ("", lambda i: "G001.0000.01.03"),
        "pstate": ("", lambda i: "P0"),
    }
    header = ", ".join(
        f + ("" if nounits or not units.get(f, ("", None))[0] else f" [{units[f][0].strip()}]")
        for f in fields
    )
    rows = []
    indices = [only_idx] if only_idx is not None and 0 <= only_idx < _SMI_GPU_COUNT else list(range(_SMI_GPU_COUNT))
    for i in indices:
        cells = []
        for f in fields:
            unit, fn = units.get(f, ("", lambda i, _f=f: "[N/A]"))
            val = fn(i)
            cells.append(val if nounits or not unit else f"{val}{unit}")
        rows.append(", ".join(cells))
    out = rows if noheader else [header, *rows]
    return "\n".join(out)


def _render_nvlink_status() -> str:
    lines = []
    for i in range(_SMI_GPU_COUNT):
        lines.append(f"GPU {i}: {_SMI_GPU_NAME}")
        nlinks = 18 if _SMI_GPU_COUNT >= 8 else 4
        for link in range(min(4, nlinks)):
            lines.append(f"\t Link {link}: 26.562 GB/s")
    return "\n".join(lines)


def _render_topo_matrix(kind: str = "m") -> str:
    n = min(_SMI_GPU_COUNT, 8)
    if kind == "c":
        rows = ["GPU\t CPU Affinity\t NUMA Affinity"]
        for i in range(n):
            numa = 0 if i < n // 2 else 1
            cpus = "0-31" if numa == 0 else "32-63"
            rows.append(f"GPU{i}\t {cpus}\t\t {numa}")
        return "\n".join(rows)
    if kind == "p":
        # PCIe path matrix
        hdr = "\t " + "\t ".join(f"GPU{i}" for i in range(min(n, 4)))
        rows = [hdr]
        labels = ("X", "PIX", "NODE", "SYS")
        for i in range(min(n, 4)):
            cells = []
            for j in range(min(n, 4)):
                if i == j:
                    cells.append("X")
                elif abs(i - j) == 1:
                    cells.append("PIX")
                elif (i // 2) == (j // 2):
                    cells.append("NODE")
                else:
                    cells.append("SYS")
            rows.append(f"GPU{i}\t " + "\t ".join(f"{c:<4}" for c in cells))
        return "\n".join(rows)
    # NVLink fabric matrix (NV18 on dense SXM nodes)
    hdr = "\t " + "\t ".join(f"GPU{i}" for i in range(n)) + "\t CPU Affinity\t NUMA Affinity"
    rows = [hdr]
    for i in range(n):
        cells = []
        for j in range(n):
            if i == j:
                cells.append("X")
            else:
                cells.append("NV18" if n >= 4 else "PIX")
        numa = 0 if i < n // 2 else 1
        cpus = "0-31" if numa == 0 else "32-63"
        rows.append(f"GPU{i}\t " + "\t ".join(f"{c:<4}" for c in cells) + f"\t {cpus}\t\t {numa}")
    rows.append("")
    rows.append(
        "Legend: X = Self, NV# = NVLink connection (# links), "
        "SYS = across PCIe+SMP interconnect, PIX = single PCIe bridge"
    )
    return "\n".join(rows)


def _render_compute_apps(line: str = "") -> str:
    header = "gpu_uuid, pid, process_name, used_gpu_memory [MiB]"
    if "noheader" in line.lower():
        rows = []
    else:
        rows = [header]
    for i in range(min(2, _SMI_GPU_COUNT)):
        uuid = f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}"
        rows.append(f"{uuid}, {12000 + i}, python, {random.randint(2048, 40000)}")
    return "\n".join(rows)


def _register_gpu(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    is_gpu_focus = engine.simulation_type == "gpu" or "gpu" in engine.scenario_slug or "nvidia" in engine.scenario_slug
    sku = _resolve_gpu_sku(getattr(engine, "scenario_slug", "") or "")
    # Seed kernel/sysfs paths learners cat during DCOPS diagnostics (TODO 187).
    try:
        st = shell.state
        _apply_gpu_sku_globals(sku)
        if sku.get("vendor") == "amd":
            st._mkdir("/sys/class/drm/card0/device")
            st._mkdir("/sys/class/drm/card0/device/hwmon/hwmon0")
            st._mkdir("/sys/kernel/debug/dri/0")
            st._write_file("/sys/class/drm/card0/device/power_dpm_state", "performance\n")
            st._write_file(
                "/sys/class/drm/card0/device/pp_dpm_sclk",
                "0: 500Mhz\n1: 1000Mhz\n2: 1700Mhz *\n3: 2100Mhz\n",
            )
            st._write_file(
                "/sys/class/drm/card0/device/pp_dpm_mclk",
                "0: 400Mhz\n1: 1200Mhz *\n2: 1600Mhz\n",
            )
            st._write_file(
                "/sys/class/drm/card0/device/hwmon/hwmon0/gpu_metrics",
                f"temp_edge={random.randint(40, 70)}\npower={random.randint(120, 550)}\n",
            )
            st._write_file(
                "/sys/kernel/debug/dri/0/amdgpu_pm_info",
                "GFX Clocks and Power:\n\t800 MHz (MCLK)\n\t1700 MHz (SCLK)\n\tAverage GPU Power: 220 W\n",
            )
        else:
            st._mkdir("/proc/driver/nvidia")
            st._write_file(
                "/proc/driver/nvidia/version",
                f"NVRM version: NVIDIA UNIX x86_64 Kernel Module  {_SMI_DRIVER}  "
                f"Tue May 14 00:00:00 UTC 2024\n"
                f"GCC version:  gcc version 11.4.1 20230605 (Red Hat 11.4.1-2)\n",
            )
            st._mkdir("/proc/driver/nvidia/gpus")
            for i in range(min(8, _SMI_GPU_COUNT)):
                bus = f"0000:{(i + 1) * 0x10 + 1:02x}:00.0"
                st._mkdir(f"/proc/driver/nvidia/gpus/{bus}")
                st._write_file(
                    f"/proc/driver/nvidia/gpus/{bus}/information",
                    f"Model: 		 {_SMI_GPU_NAME}\n"
                    f"IRQ:   		 150\n"
                    f"GPU UUID: 	 GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}\n"
                    f"Video BIOS: 	 96.00.74.00.01\n",
                )
    except Exception:
        pass

    def handler(parts, line):
        low = line.strip().lower()
        # Bind SKU for this invocation so table/query helpers match the scenario.
        _apply_gpu_sku_globals(sku)
        # GPU-specific tools always handled here. Generic kernel tools
        # (modprobe/lspci/lsmod/modinfo) are only intercepted when they
        # reference the NVIDIA driver, or when this is a GPU-focused sim — so
        # other scenarios keep using the normal Linux handlers.
        gpu_tools = ("nvidia-smi", "dcgmi", "dcgm-exporter", "dcgm", "gpustat", "rocm-smi",
                     "amd-smi", "nvcc", "all_reduce_perf", "all_gather_perf",
                     "reduce_scatter_perf", "broadcast_perf", "nccl-tests",
                     "vllm", "gpu-sanity", "cuda-samples", "bandwidthTest", "deviceQuery",
                     "racadm", "idracadm", "nvidia_gpu_tools.py", "nvidia_gpu_tools",
                     "rocminfo", "radeontop", "fieldiag", "psbcheck", "dcgmprofrunner")
        kernel_tools = ("modprobe", "rmmod", "lspci", "lsmod", "modinfo")
        if any(low.startswith(c) for c in gpu_tools):
            pass
        elif any(low.startswith(c) for c in kernel_tools) and (
            "nvidia" in low or "amd" in low or "3d" in low or "vga" in low or is_gpu_focus
        ):
            pass
        else:
            return None
        healthy = engine.shell.state.gpu_healthy
        # Dell iDRAC / racadm — BM + DCOps TSR collection against the chassis BMC.
        if low.startswith("racadm") or low.startswith("idracadm"):
            if "getsysinfo" in low or "getsysinfo" in "".join(parts).lower():
                return (
                    "RAC Information:\n"
                    f"RAC Date/Time           = {time.strftime('%m/%d/%Y %H:%M:%S')}\n"
                    "Firmware Version        = 7.00.00.00\n"
                    "Firmware Build          = 24\n"
                    "Last Firmware Update    = 03/12/2025 09:14:22\n"
                    "Hardware Version        = 0.01\n"
                    "MAC Address 1           = AA:BB:CC:DD:EE:01\n"
                    "\n"
                    "System Information:\n"
                    f"System Model            = PowerEdge XE9680 ({_SMI_GPU_NAME} × {_SMI_GPU_COUNT})\n"
                    "System BIOS Version     = 2.5.4\n"
                    "Service Tag             = SKYLAB01\n"
                    "Express Service Code    = 1234567890\n"
                    "Host Name               = gpu-node-01\n"
                    "OS Name                 = Ubuntu 22.04.4 LTS\n"
                    "Power Status            = ON\n"
                    "Fresh Air Compliant     = Yes"
                )
            if "getsel" in low or "getraclog" in low or "getlclog" in low:
                return (
                    "Record: 1\n"
                    f"Date/Time: {time.strftime('%m/%d/%Y %H:%M:%S')}\n"
                    "Source: Fan.Slot.1\n"
                    "Severity: Information\n"
                    "Description: The fan was inserted.\n"
                    "\n"
                    "Record: 2\n"
                    f"Date/Time: {time.strftime('%m/%d/%Y %H:%M:%S')}\n"
                    "Source: GPU.Slot.4\n"
                    "Severity: Warning\n"
                    f"Description: {_SMI_GPU_NAME} temperature threshold asserted."
                )
            if "techsupreport" in low or "tsr" in low or "supportassist" in low:
                return (
                    "RACADM collecting Tech Support Report…\n"
                    "JobQueue: JID_123456789012\n"
                    "Percent Complete: 100%\n"
                    "TSR saved to /tmp/TSR_SKYLAB01.zip\n"
                    "Message: Successfully generated Tech Support Report"
                )
            if "serveraction" in low:
                action = "powercycle"
                for tok in ("powercycle", "powerdown", "powerup", "hardreset", "graceshutdown"):
                    if tok in low:
                        action = tok
                        break
                return f"Server power operation initiated: {action}"
            if "get" in low and ("nic" in low or "mac" in low):
                return (
                    "NIC.Integrated.1-1-1\n"
                    "  MACAddress = AA:BB:CC:DD:EE:10\n"
                    "NIC.Integrated.1-2-1\n"
                    "  MACAddress = AA:BB:CC:DD:EE:11\n"
                    "NIC.Slot.1-1-1\n"
                    "  MACAddress = AA:BB:CC:DD:EE:20"
                )
            if "-h" in parts or "--help" in low or len(parts) == 1:
                return (
                    "racadm — Dell Remote Access Controller admin CLI\n"
                    "Usage: racadm [subcommand]\n"
                    "  getsysinfo                 System / RAC summary\n"
                    "  getsel / getraclog         System Event / RAC logs\n"
                    "  techsupreport collect      Collect TSR bundle\n"
                    "  serveraction <action>      Power operations\n"
                    "  get NIC.Integrated.1-1-1   NIC / MAC inventory"
                )
            return f"racadm: OK ({' '.join(parts[1:]) or 'executed'})"
        # NVIDIA internal GPU tools — PSB / PPCIe / confidential-compute probes.
        if low.startswith("nvidia_gpu_tools") or "nvidia_gpu_tools.py" in low:
            if "psb" in low or "--psb" in low:
                return (
                    "nvidia_gpu_tools.py — Platform Security Boot (PSB) check\n"
                    f"GPU: {_SMI_GPU_NAME} × {_SMI_GPU_COUNT}\n"
                    "Secure Boot / measured boot: ENABLED\n"
                    "GPU IFR / VBIOS signature: VALID\n"
                    "Result: PASS — /tmp/psb_report.json"
                )
            if "ppcie" in low or "ppcIe" in low or "--ppcie" in low or "cc-mode" in low or "conf-compute" in low:
                return (
                    "nvidia_gpu_tools.py — PPCIe / Confidential Compute mode\n"
                    f"GPU: {_SMI_GPU_NAME} × {_SMI_GPU_COUNT}\n"
                    "CC mode: off (devtools)\n"
                    "PPCIe attestation: N/A (CC off)\n"
                    "Result: PASS — mode query complete"
                )
            if "ecc" in low or "inforom" in low:
                return (
                    "nvidia_gpu_tools.py — ECC / InfoROM\n"
                    + "\n".join(
                        f"GPU{i}: ECC enabled; InfoROM OK; retired pages=0"
                        for i in range(_SMI_GPU_COUNT)
                    )
                    + "\nResult: PASS"
                )
            return (
                "nvidia_gpu_tools.py — NVIDIA datacenter GPU diagnostics\n"
                "Usage:\n"
                "  nvidia_gpu_tools.py --psb\n"
                "  nvidia_gpu_tools.py --ppcie\n"
                "  nvidia_gpu_tools.py --cc-mode\n"
                "  nvidia_gpu_tools.py --ecc --inforom"
            )
        if low.startswith("rocminfo"):
            return (
                "ROCk module is loaded\n"
                "=====================    \n"
                "HSA Agents               \n"
                "=====================    \n"
                "  Name:                    gfx942\n"
                "  Marketing Name:          AMD Instinct MI300X\n"
                "  Vendor Name:             AMD\n"
                "  Device Type:             GPU\n"
                f"  Compute Units:           {110 * max(1, _SMI_GPU_COUNT // 8)}\n"
                "  Max Waves Per CU:        32"
            )
        if low.startswith("radeontop"):
            return (
                "radeontop for AMD GPUs — bus 03, gpu 42.18%, ee 0.00%, vgt 12.40%, "
                "ta 8.20%, sx 3.10%, sh 1.00%, spi 4.50%, sc 2.20%, pa 0.80%, "
                "db 6.10%, cb 5.40%, vram 18.2% 12480MB, gtt 2.1% 512MB"
            )
        if low.startswith("dcgmprofrunner"):
            return (
                "dcgmprofrunner: starting DCGM profiling run…\n"
                f"Targets: {_SMI_GPU_COUNT} × {_SMI_GPU_NAME}\n"
                "Fields: DCGM_FI_PROF_GR_ENGINE_ACTIVE, DCGM_FI_PROF_PIPE_TENSOR_ACTIVE\n"
                "Result: PASS — /tmp/dcgmprofrunner.json"
            )
        # ImageDev GPU sanity harness (pre-publish / post-deploy).
        if low.startswith("gpu-sanity") or low.startswith("cuda-samples") or low.startswith("devicequery") or low.startswith("bandwidthtest"):
            if not healthy and sku.get("vendor") != "amd":
                return "gpu-sanity: FAIL — driver/NVML unreachable"
            return (
                "=== ImageDev GPU Sanity Suite ===\n"
                f"SKU: {_SMI_GPU_NAME} × {_SMI_GPU_COUNT}\n"
                "deviceQuery ........................ PASS\n"
                "bandwidthTest (H2D/D2H/D2D) ........ PASS\n"
                "nvidia-smi -L ....................... PASS\n"
                "dcgmi diag -r 1 ..................... PASS\n"
                "Persistence mode .................... PASS\n"
                "Result: ALL PASS — /tmp/gpu-sanity-report.json"
            )
        # vLLM inference server (AI Infra — not application GPU course).
        if low.startswith("vllm"):
            if "serve" in low or "openai" in low or "--model" in low:
                model = "meta-llama/Llama-3.1-70B-Instruct"
                for i, p in enumerate(parts):
                    if p in ("--model", "-m") and i + 1 < len(parts):
                        model = parts[i + 1]
                        break
                return (
                    f"INFO  vllm.entrypoints.openai.api_server: Starting vLLM on {_SMI_GPU_NAME} × {_SMI_GPU_COUNT}\n"
                    f"INFO  model={model}\n"
                    "INFO  tensor_parallel_size=8\n"
                    "INFO  CUDA graphs captured\n"
                    "INFO  Avg prompt throughput: 1842.3 tokens/s\n"
                    "INFO  Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)\n"
                    "vllm: READY — OpenAI-compatible /v1/completions"
                )
            if "bench" in low or "benchmark" in low:
                return (
                    "vllm bench throughput\n"
                    f"  GPUs: {_SMI_GPU_COUNT} × {_SMI_GPU_NAME}\n"
                    "  Request throughput: 42.8 req/s\n"
                    "  Output token throughput: 6120.4 tok/s\n"
                    "  Mean TTFT: 48.2 ms\n"
                    "Result: PASS"
                )
            return (
                "vLLM — high-throughput LLM serving\n"
                "Usage: vllm serve <model> --tensor-parallel-size N\n"
                "       vllm bench throughput --model <model>\n"
                "OpenAI API on :8000 when serve is running."
            )
        if low.startswith("nvidia-smi"):
            if sku.get("vendor") == "amd":
                return (
                    "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. "
                    "This node is configured with AMD Instinct GPUs — use rocm-smi / amd-smi."
                )
            if "-h" in parts or "--help" in low:
                return (
                    "NVIDIA System Management Interface -- NVIDIA Management Library (NVML)\n\n"
                    "Usage: nvidia-smi [OPTION1] [OPTION2] ...\n\n"
                    "    -L, --list-gpus                  Display a list of GPUs connected\n"
                    "    -q, --query                      Display GPU/unit info\n"
                    "    -d TYPE, --display=TYPE          Display only selected information\n"
                    "    dmon                            Device monitoring (scrolling)\n"
                    "    pmon                            Process monitoring (scrolling)\n"
                    "    topo -m|-p|-c                   Topology / PCIe / CPU affinity\n"
                    "    nvlink --status                 NVLink status\n"
                    "    mig -lgip|-lgi                  MIG profiles / instances\n"
                    "    compute-apps                    Running compute processes\n"
                    "    conf-compute                    Confidential compute status\n"
                    "    --query-gpu=FIELD               CSV field query\n"
                    "    --query-compute-apps=FIELD      Compute process CSV\n"
                    "    -l SEC, --loop=SEC              Loop with delay\n"
                    "    -i ID                           Select GPU index\n"
                    "    -pm, -pl, -c, -e, -am            Admin mode toggles\n"
                    "    --lock-gpu-clocks / --gpu-reset Admin clock / reset\n"
                )
            if "-L" in parts or "--list-gpus" in low:
                if not healthy:
                    return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
                rows = []
                for i in range(_SMI_GPU_COUNT):
                    uuid = f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}"
                    rows.append(f"GPU {i}: {_SMI_GPU_NAME} (UUID: {uuid})")
                return "\n".join(rows)
            if "-l" in parts or "--loop" in low:
                pass  # streaming flag — single snapshot is fine for the sim
            if "--query-gpu" in low:
                if not healthy:
                    return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
                return _render_query_gpu(line)
            # ── nvidia-smi sub-commands (topology / nvlink / mig / -q -d <section>) ──
            # Datacenter-realistic detail views. Cosmetic only: the healthy path
            # renders a clean view; the unhealthy path mirrors a fallen-off driver.
            if not healthy and any(k in low for k in ("topo", "nvlink", "mig", "-q")):
                return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
            if "topo" in low and ("-m" in parts or "-p" in parts or "-c" in parts or "topo" in parts):
                kind = "p" if "-p" in parts else "c" if "-c" in parts else "m"
                return _render_topo_matrix(kind)
            if "nvlink" in low:
                if "-e" in parts or "capabilities" in low or "errors" in low:
                    lines = []
                    for i in range(_SMI_GPU_COUNT):
                        lines.append(f"GPU {i}: {_SMI_GPU_NAME}")
                        lines.append("\t Link 0: Replay Errors: 0")
                        lines.append("\t Link 0: Recovery Errors: 0")
                        lines.append("\t Link 0: CRC Errors: 0")
                    return "\n".join(lines)
                return _render_nvlink_status()
            if "compute-apps" in low or "--query-compute-apps" in low:
                return _render_compute_apps(line)
            if "--query-accounted-apps" in low or "accounted-apps" in low:
                return (
                    "gpu_uuid, pid, gpu_utilization [%], memory_utilization [%], max_memory_usage [MiB], time [ms]\n"
                    f"GPU-00000000-1a2b-3c4d-5e6f-001122334400, 12000, 88, 62, 42000, 912334"
                )
            if "conf-compute" in low or "confidential" in low:
                return (
                    "Confidential Compute Status\n"
                    "\t CC Mode                         : DevTools\n"
                    "\t Multi-GPU Protected PCIe        : Disabled\n"
                    "\t Environment                     : Unset"
                )
            if "boost-slider" in low:
                return "GPU Boost Slider\n\t Enabled                         : Yes"
            if low.strip() in ("nvidia-smi clocks",) or (parts[:2] == ["nvidia-smi", "clocks"]):
                return (
                    "Clocks\n"
                    f"\t Graphics                        : {random.randint(1200, 1980)} MHz\n"
                    f"\t SM                              : {random.randint(1200, 1980)} MHz\n"
                    f"\t Memory                          : {random.choice((1593, 2619))} MHz\n"
                    f"\t Video                           : {random.randint(900, 1600)} MHz"
                )
            if "fieldiag" in low or "nvidia-bug-report" in low:
                return (
                    "nvidia-bug-report.sh: collecting diagnostics…\n"
                    "Wrote /tmp/nvidia-bug-report.log.gz\n"
                    "fieldiag: PASS (no FRU faults)"
                )
            if "psbcheck" in low or "psb-check" in low or "psb_check" in low:
                return (
                    "PSBCheck 2.1 — Platform Security Boot bundle\n"
                    "Secure Boot: enabled\n"
                    "Measured boot PCR[0..7]: OK\n"
                    "GPU VBIOS / IFR signature: VALID\n"
                    "SXM tray FRU EEPROM: OK\n"
                    "Result: PASS — bundle written /tmp/psbcheck-report.json"
                )
            if "mig" in low:
                if "-lgip" in low:
                    return ("+-----------------------------------------------------------------------------+\n"
                            "| GPU instance profiles:                                                      |\n"
                            "| GPU   Name             ID    Instances   Memory     P2P    SM    DEC   ENC   |\n"
                            "|                              Free/Total   GiB              CE    JPEG  OFA   |\n"
                            "|=============================================================================|\n"
                            "|   0  MIG 1g.10gb       19     7/7        9.75       No     14    1     0     |\n"
                            "|   0  MIG 2g.20gb       14     3/3        19.62      No     28    2     0     |\n"
                            "|   0  MIG 3g.40gb        9     2/2        39.50      No     42    3     0     |\n"
                            "|   0  MIG 7g.80gb        0     1/1        79.25      No     98    7     0     |\n"
                            "+-----------------------------------------------------------------------------+")
                if "-lgi" in low or "-lci" in low:
                    return ("+-------------------------------------------------------+\n"
                            "| GPU instances:                                        |\n"
                            "| GPU   Name          Profile  Instance   Placement     |\n"
                            "|                     ID       ID         Start:Size     |\n"
                            "|=======================================================|\n"
                            "|   0  MIG 3g.40gb     9        1          0:4            |\n"
                            "|   0  MIG 3g.40gb     9        2          4:4            |\n"
                            "+-------------------------------------------------------+")
                return ""
            if "-q" in parts or low.startswith("nvidia-smi -q"):
                if "ecc" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Ecc Mode\n"
                            "\t Current                       : Enabled\n"
                            "ECC Errors\n"
                            "\t Volatile\n"
                            "\t\t SRAM Correctable          : 0\n"
                            "\t\t SRAM Uncorrectable        : 0\n"
                            "\t\t DRAM Correctable          : 0\n"
                            "\t\t DRAM Uncorrectable        : 0\n"
                            "\t Aggregate\n"
                            "\t\t DRAM Uncorrectable        : 0")
                if "page_retirement" in low or "remap" in low or "row" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Remapped Rows\n"
                            "\t Correctable Error              : 0\n"
                            "\t Uncorrectable Error            : 0\n"
                            "\t Pending                        : No\n"
                            "\t Remapping Failure Occurred     : No\n"
                            "Retired Pages\n"
                            "\t Single Bit ECC                 : 0\n"
                            "\t Double Bit ECC                 : 0\n"
                            "\t Pending Page Blacklist         : No")
                if "temperature" in low:
                    t = random.randint(34, 62)
                    return ("==============NVSMI LOG==============\n"
                            "Temperature\n"
                            f"\t GPU Current Temp               : {t} C\n"
                            "\t GPU Slowdown Temp              : 87 C\n"
                            "\t GPU Shutdown Temp              : 92 C\n"
                            f"\t Memory Current Temp            : {t + 6} C\n"
                            "\t Memory Max Operating Temp      : 95 C")
                if "power" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Power Readings\n"
                            f"\t Power Draw                     : {random.randint(90, _SMI_PWR_CAP - 20)}.42 W\n"
                            f"\t Current Power Limit            : {_SMI_PWR_CAP}.00 W\n"
                            f"\t Default Power Limit            : {_SMI_PWR_CAP}.00 W\n"
                            f"\t Enforced Power Limit           : {_SMI_PWR_CAP}.00 W\n"
                            f"\t Max Power Limit                : {_SMI_PWR_CAP}.00 W")
                if "utilization" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Utilization\n"
                            f"\t Gpu                            : {random.randint(0, 99)} %\n"
                            f"\t Memory                         : {random.randint(0, 90)} %\n"
                            f"\t Encoder                        : {random.randint(0, 5)} %\n"
                            f"\t Decoder                        : {random.randint(0, 5)} %")
                if "memory" in low:
                    used = random.randint(3, max(12, _SMI_MEM_TOTAL_MIB // 2))
                    return ("==============NVSMI LOG==============\n"
                            "FB Memory Usage\n"
                            f"\t Total                          : {_SMI_MEM_TOTAL_MIB} MiB\n"
                            f"\t Reserved                       : 455 MiB\n"
                            f"\t Used                           : {used} MiB\n"
                            f"\t Free                           : {_SMI_MEM_TOTAL_MIB - used} MiB")
                if "compute" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Compute Mode\n"
                            "\t Current                       : Default")
                if "pci" in low:
                    return (
                        "==============NVSMI LOG==============\n"
                        "PCI\n"
                        "\t Bus                          : 0x19\n"
                        "\t Device                       : 0x00\n"
                        "\t Domain                       : 0x0000\n"
                        "\t Device Id                    : 0x233010DE\n"
                        "\t Bus Id                       : 00000000:19:00.0\n"
                        "\t Sub System Id                : 0x179910DE\n"
                        "\t GPU Link Info\n"
                        "\t\t PCIe Generation\n"
                        "\t\t\t Max                     : 5\n"
                        "\t\t\t Current                 : 5\n"
                        "\t\t Link Width\n"
                        "\t\t\t Max                     : 16x\n"
                        "\t\t\t Current                 : 16x"
                    )
                if re.search(r"-d\s*clock", low) or "clocks" in low and "supported" not in low:
                    return (
                        "==============NVSMI LOG==============\n"
                        "Clocks\n"
                        f"\t Graphics                      : {random.randint(1200, 1980)} MHz\n"
                        f"\t SM                            : {random.randint(1200, 1980)} MHz\n"
                        f"\t Memory                        : {random.choice((1593, 2619))} MHz\n"
                        f"\t Video                         : {random.randint(900, 1600)} MHz\n"
                        "Applications Clocks\n"
                        "\t Graphics                      : 1410 MHz\n"
                        "\t Memory                        : 1593 MHz\n"
                        "Default Applications Clocks\n"
                        "\t Graphics                      : 1410 MHz\n"
                        "\t Memory                        : 1593 MHz"
                    )
                if "pids" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Processes\n"
                            f"\t Process ID                    : {random.randint(20000, 65000)}\n"
                            "\t   Type                         : C\n"
                            "\t   Name                         : python\n"
                            f"\t   Used GPU Memory              : {random.randint(1000, 40000)} MiB")
                if "supported_clocks" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Supported Clocks\n"
                            "\t Memory                         : 2619 MHz\n"
                            "\t\t Graphics                   : 1980 MHz\n"
                            "\t\t Graphics                   : 1410 MHz\n"
                            "\t Memory                         : 1593 MHz\n"
                            "\t\t Graphics                   : 1410 MHz")
                if "accounting" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Accounting Mode\n"
                            "\t Current                       : Disabled\n"
                            "\t Buffer Size                   : 4000")
                if "performance" in low or "clock" in low:
                    return ("==============NVSMI LOG==============\n"
                            "Clocks Throttle Reasons\n"
                            "\t Idle                           : Not Active\n"
                            "\t SW Power Cap                   : Not Active\n"
                            "\t HW Thermal Slowdown            : Not Active\n"
                            "\t HW Power Brake Slowdown        : Not Active\n"
                            "\t SW Thermal Slowdown            : Not Active")
                # generic `-q` dump — one block per attached GPU.
                head = ("==============NVSMI LOG==============\n"
                        f"Driver Version                        : {_SMI_DRIVER}\n"
                        f"CUDA Version                          : {_SMI_CUDA}\n"
                        f"Attached GPUs                         : {_SMI_GPU_COUNT}")
                blocks = []
                for i in range(_SMI_GPU_COUNT):
                    bus = f"00000000:{(i + 1) * 0x10 + 1:02X}:00.0"
                    used = random.randint(3, 512)
                    blocks.append(
                        f"GPU {bus}\n"
                        f"\t Product Name                  : {_SMI_GPU_NAME}\n"
                        f"\t Product Architecture          : {_SMI_ARCH}\n"
                        f"\t Persistence Mode              : Enabled\n"
                        f"\t MIG Mode\n"
                        f"\t\t Current                   : Disabled\n"
                        f"\t\t Pending                   : Disabled\n"
                        f"\t FB Memory Usage\n"
                        f"\t\t Total                     : {_SMI_MEM_TOTAL_MIB} MiB\n"
                        f"\t\t Used                      : {used} MiB\n"
                        f"\t\t Free                      : {_SMI_MEM_TOTAL_MIB - used} MiB")
                return head + "\n" + "\n".join(blocks)
            if any(x in parts for x in ("-pm", "-pl", "-e", "-am", "-ac", "-rac")) or \
               "--lock-gpu-clocks" in low or "--reset-gpu-clocks" in low or \
               "--gpu-reset" in low or "--clear-accounting" in low or \
               low.startswith("nvidia-smi -r") or \
               (re.search(r"nvidia-smi\s+-c\b", low) and "dmon" not in low and "pmon" not in low) or \
               (re.search(r"nvidia-smi\s+-p\b", low) and "dmon" not in low and "pmon" not in low):
                # persistence-mode / power-limit / compute mode / ECC / clocks — acknowledge.
                if "-pm" in parts or "persistence" in low:
                    return "Enabled persistence mode for GPU 00000000:19:00.0.\nAll done."
                if "--lock-gpu-clocks" in low:
                    return "GPU clocks set to (min,max)=(1410,1410) MHz for GPU 0.\nAll done."
                if "--gpu-reset" in low or low.startswith("nvidia-smi -r"):
                    return "GPU 0: GpuReset succeeded.\nAll done."
                if "-pl" in parts:
                    return f"Power limit for GPU 0 is already set to {_SMI_PWR_CAP}.00 W.\nAll done."
                return "All done."
            # Live monitors — paced like real dmon/pmon (and -l loop snapshots).
            if "dmon" in low or "pmon" in low or "-l" in parts or "--loop" in low:
                from .shell import StreamedCommandResult
                if not healthy:
                    return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
                samples = 5
                for tok in parts:
                    if tok.startswith("-c") and tok[2:].isdigit():
                        samples = min(30, max(1, int(tok[2:])))
                    if tok == "-c" and parts.index(tok) + 1 < len(parts):
                        try:
                            samples = min(30, max(1, int(parts[parts.index(tok) + 1])))
                        except ValueError:
                            pass
                lines: list[str] = []
                if "pmon" in low:
                    lines.append("# gpu        pid  type    sm   mem   enc   dec   command")
                    for tick in range(samples):
                        for gi in range(min(4, _SMI_GPU_COUNT)):
                            pid = 12000 + gi * 10 + tick
                            sm = random.randint(0, 98)
                            mem = random.randint(0, 80)
                            lines.append(
                                f"    {gi}    {pid}     C    {sm:3d}   {mem:3d}     0     0   python"
                            )
                    delay = 0.55
                else:
                    # dmon header + samples (power / util / clocks — matches nvidia-smi dmon -s puc)
                    lines.append("# gpu   pwr  gtemp  mtemp     sm    mem    enc    dec  mclk  pclk")
                    lines.append("# Idx     W     C      C      %      %      %      %   MHz   MHz")
                    for _tick in range(samples):
                        for gi in range(min(8, _SMI_GPU_COUNT)):
                            pwr = random.randint(80, max(120, _SMI_PWR_CAP - 50))
                            gt = random.randint(32, 78)
                            mt = gt + random.randint(4, 12)
                            sm = random.randint(0, 99)
                            mem = random.randint(0, 85)
                            mclk = random.choice((1593, 2619))
                            pclk = random.choice((1410, 1980))
                            lines.append(
                                f"    {gi}   {pwr:3d}    {gt:2d}     {mt:2d}    "
                                f"{sm:3d}    {mem:3d}      0      0  {mclk:4d}  {pclk:4d}"
                            )
                    delay = 1.0 if ("-l" in parts or "--loop" in low) else 0.55
                return StreamedCommandResult(lines=lines, delay_s=delay)
            if healthy:
                return _render_nvidia_smi_table()
            return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running."
        if low.startswith("modprobe"):
            # `modprobe nvidia` loads the driver; `modprobe -r nvidia` unloads it.
            if "nvidia" in low:
                loaded = "-r" not in parts and "--remove" not in low
                engine.shell.state.gpu_healthy = loaded
                _sync_gpu_identity(engine, healthy=loaded)
            return ""
        if low.startswith("rmmod"):
            if "nvidia" in low:
                engine.shell.state.gpu_healthy = False
                _sync_gpu_identity(engine, healthy=False)
            return ""
        if low.startswith("lspci"):
            if "amd" in low or sku.get("vendor") == "amd":
                rows = []
                for i in range(_SMI_GPU_COUNT):
                    bus = f"{(i + 1) * 0x10 + 1:02x}:00.0"
                    rows.append(f"{bus} Processing accelerators: Advanced Micro Devices, Inc. [AMD/ATI] Instinct MI300X")
                return "\n".join(rows)
            # Default / nvidia filter — match SKU product string.
            rows = []
            for i in range(_SMI_GPU_COUNT):
                bus = f"{(i + 1) * 0x10 + 1:02x}:00.0"
                rows.append(f"{bus} 3D controller: NVIDIA Corporation {_SMI_PCI_ID} [{_SMI_GPU_NAME}] (rev a1)")
            return "\n".join(rows)
        if low.startswith("lsmod"):
            if sku.get("vendor") == "amd":
                if not healthy:
                    return "Module                  Size  Used by"
                return ("Module                  Size  Used by\n"
                        "amdgpu             15728640  32\n"
                        "amdkfd               1048576  8 amdgpu")
            if not healthy:
                return "Module                  Size  Used by"
            return ("Module                  Size  Used by\n"
                    "nvidia              56852480  42\n"
                    "nvidia_uvm           1048576  2 nvidia\n"
                    "nvidia_drm             69632  0")
        if low.startswith("modinfo"):
            if "amdgpu" in low or (sku.get("vendor") == "amd" and "nvidia" not in low):
                return ("filename:       /lib/modules/5.14.0/updates/dkms/amdgpu.ko\n"
                        "version:        6.2.0\n"
                        "license:        GPL and additional rights\n"
                        "description:    AMDGPU")
            if not healthy:
                return "modinfo: ERROR: Module nvidia not found."
            return ("filename:       /lib/modules/5.14.0/kernel/drivers/video/nvidia.ko\n"
                    f"version:        {_SMI_DRIVER}\n"
                    "supported:      external\n"
                    "license:        NVIDIA\n"
                    "description:    NVIDIA Linux Open GPU Kernel Module")
        if low.startswith("nvcc"):
            return (f"nvcc: NVIDIA (R) Cuda compiler driver\n"
                    f"Copyright (c) 2005-2024 NVIDIA Corporation\n"
                    f"Built on Thu_Mar_28_02:18:24_PDT_2024\n"
                    f"Cuda compilation tools, release {_SMI_CUDA}, V{_SMI_CUDA}.131\n"
                    f"Build cuda_{_SMI_CUDA}.r{_SMI_CUDA}/compiler.34714021_0")
        if low.startswith("dcgm-exporter"):
            # dcgm-exporter is a Prometheus exporter, not a CLI health tool: it
            # serves DCGM_FI_DEV_* gauges on :9400/metrics. Emit a realistic
            # startup log + sample scrape so a learner sees what it actually does.
            if not healthy:
                return ("time=\"...\" level=fatal msg=\"Error watching fields: "
                        "Failed to connect to DCGM: nv-hostengine not running / driver not loaded\"")
            if "--version" in low or "-v" in parts:
                return "dcgm-exporter version 3.3.5-3.4.1"
            sample = [
                "time=\"...\" level=info msg=\"Starting dcgm-exporter\"",
                "time=\"...\" level=info msg=\"DCGM successfully initialized!\"",
                "time=\"...\" level=info msg=\"Collecting DCP Metrics\"",
                "time=\"...\" level=info msg=\"Falling back to metric file '/etc/dcgm-exporter/default-counters.csv'\"",
                "time=\"...\" level=info msg=\"Kubernetes metrics collection disabled\"",
                "time=\"...\" level=info msg=\"Pipeline starting\"",
                "time=\"...\" level=info msg=\"Listening on\" address=\"[::]:9400\"",
                "",
                "# Sample scrape (curl -s localhost:9400/metrics):",
                "# HELP DCGM_FI_DEV_GPU_UTIL GPU utilization (in %).",
                "# TYPE DCGM_FI_DEV_GPU_UTIL gauge",
            ]
            for i in range(_SMI_GPU_COUNT):
                uuid = f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}"
                util = random.randint(0, 100)
                sample.append(
                    f'DCGM_FI_DEV_GPU_UTIL{{gpu="{i}",UUID="{uuid}",'
                    f'device="nvidia{i}",modelName="{_SMI_GPU_NAME}",Hostname="gpu-node"}} {util}')
            sample.append("# HELP DCGM_FI_DEV_GPU_TEMP GPU temperature (in C).")
            sample.append("# TYPE DCGM_FI_DEV_GPU_TEMP gauge")
            for i in range(_SMI_GPU_COUNT):
                uuid = f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}"
                sample.append(
                    f'DCGM_FI_DEV_GPU_TEMP{{gpu="{i}",UUID="{uuid}",'
                    f'device="nvidia{i}",modelName="{_SMI_GPU_NAME}",Hostname="gpu-node"}} {random.randint(30, 72)}')
            return "\n".join(sample)
        if low.startswith("dcgmi") or low.startswith("dcgm"):
            if not healthy:
                return "Error: Unable to connect to nv-hostengine. GPU driver not loaded."
            if "discovery" in low:
                rows = [f"{_SMI_GPU_COUNT} GPUs found.",
                        "+--------+----------------------------------------------------------------------+",
                        "| GPU ID | Device Information                                                   |",
                        "+========+======================================================================+"]
                for i in range(_SMI_GPU_COUNT):
                    bus = f"00000000:{(i + 1) * 0x10 + 1:02X}:00.0"
                    rows.append(f"| {i:<6} |{(' Name: ' + _SMI_GPU_NAME):<70}|")
                    rows.append(f"|        |{(' PCI Bus ID: ' + bus):<70}|")
                rows.append("+--------+----------------------------------------------------------------------+")
                return "\n".join(rows)
            if "diag" in low:
                # `dcgmi diag -r <1|2|3|4>` — the sim renders a clean pass run.
                level = "1"
                for tok in ("-r", "--run"):
                    if tok in parts:
                        try:
                            level = parts[parts.index(tok) + 1]
                        except (ValueError, IndexError):
                            pass
                return (f"Successfully ran diagnostic (run level {level}) for group.\n"
                        "+---------------------------+------------------------------------------------+\n"
                        "|Diagnostic                 | Result                                         |\n"
                        "+===========================+================================================+\n"
                        "|-----  Deployment  --------+------------------------------------------------|\n"
                        "| Denylist                  | Pass                                           |\n"
                        "| NVML Library              | Pass                                           |\n"
                        "| CUDA Main Library         | Pass                                           |\n"
                        "| Persistence Mode          | Pass                                           |\n"
                        "|-----  Integration  -------+------------------------------------------------|\n"
                        "| PCIe                      | Pass - All                                     |\n"
                        "|-----  Hardware  ----------+------------------------------------------------|\n"
                        "| GPU Memory                | Pass - All                                     |\n"
                        "| Memory Bandwidth          | Pass - All                                     |\n"
                        "|-----  Stress  ------------+------------------------------------------------|\n"
                        "| Targeted Stress           | Pass - All                                     |\n"
                        "| Targeted Power            | Pass - All                                     |\n"
                        "+---------------------------+------------------------------------------------+")
            if "health" in low:
                return ("+-----------------------------------------------------------------------------+\n"
                        "| Health Monitor Report                                                       |\n"
                        "+=================================+===========================================+\n"
                        "| Overall Health                  | Healthy                                   |\n"
                        "+---------------------------------+-------------------------------------------+")
            if "stats" in low:
                return (
                    "+-----------------------------------------------------------------------------+\n"
                    "| GPU Stats                                                                   |\n"
                    "+=============+===============================================================+\n"
                    "| GPU ID      | Power (W) | GPU Util (%) | Mem Util (%) | Temp (C)            |\n"
                    "+=============+===============================================================+\n"
                    + "\n".join(
                        f"| {i:<11} | {random.randint(90, max(120, _SMI_PWR_CAP - 50)):<9} | "
                        f"{random.randint(0, 99):<12} | {random.randint(0, 90):<12} | "
                        f"{random.randint(30, 72):<19} |"
                        for i in range(_SMI_GPU_COUNT)
                    )
                    + "\n+=============+===============================================================+"
                )
            if "group" in low:
                return (
                    "+-------------------+---------------------------------------------------------+\n"
                    "| Groups            |                                                          |\n"
                    "| GROUP 0 (default) | GPUs: " + ",".join(str(i) for i in range(_SMI_GPU_COUNT)) + "\n"
                    "+-------------------+---------------------------------------------------------+"
                )
            if "modules" in low:
                return (
                    "Module ID  Name                 State\n"
                    "0          Core                 Loaded\n"
                    "1          NvSwitch             Loaded\n"
                    "2          VGPU                 Not Loaded\n"
                    "3          Introspection        Loaded\n"
                    "4          Health               Loaded\n"
                    "5          Policy               Loaded\n"
                    "6          Config               Loaded"
                )
            if "policy" in low:
                return (
                    "+-----------------------------------------------------------------------------+\n"
                    "| Policy Information                                                          |\n"
                    "| Violation Notification      : On                                             |\n"
                    "| Max XID                      : None                                          |\n"
                    "+-----------------------------------------------------------------------------+"
                )
            if "fieldgroup" in low or "field" in low and "group" in low:
                return (
                    "Field Group 0: default\n"
                    "  DCGM_FI_DEV_GPU_TEMP\n"
                    "  DCGM_FI_DEV_POWER_USAGE\n"
                    "  DCGM_FI_DEV_GPU_UTIL\n"
                    "  DCGM_FI_DEV_MEM_COPY_UTIL"
                )
            if "dmon" in low:
                rows = ["# Entity  GPUTL  MCUTL   TMPTR   POWER   ECCUC",
                        "# Id      %      %       C       W       "]
                for i in range(_SMI_GPU_COUNT):
                    rows.append(
                        f"   GPU {i}   {random.randint(0, 100):3d}    {random.randint(0, 90):3d}"
                        f"     {random.randint(30, 72):3d}     {random.randint(70, max(120, _SMI_PWR_CAP - 10)):3d}       0")
                return "\n".join(rows)
            return ("+----+-----------+----------------------------------------------------------+\n"
                    "| GPU| Health    | Details                                                  |\n"
                    "+====+===========+==========================================================+\n"
                    "|  0 | Healthy   | All checks passed                                        |\n"
                    "+----+-----------+----------------------------------------------------------+")
        if low.startswith("gpustat"):
            if not healthy:
                return "Error: NVIDIA driver is not loaded"
            hdr = f"gpu-node   {time.strftime('%a %b %d %H:%M:%S %Y')}"
            rows = [hdr]
            for i in range(_SMI_GPU_COUNT):
                temp = random.randint(30, 72)
                util = random.randint(0, 100)
                mem = random.randint(3, max(12, _SMI_MEM_TOTAL_MIB - 100))
                rows.append(
                    f"[{i}] {_SMI_GPU_NAME} | {temp}'C, {util:3d} % | "
                    f"{mem:5d} / {_SMI_MEM_TOTAL_MIB} MB")
            return "\n".join(rows)
        if low.startswith("rocm-smi") or low.startswith("amd-smi"):
            if "showtopo" in low or "shownodesbw" in low or "topo" in low:
                return ("============================ Weight between two GPUs ========================\n"
                        "       GPU0         GPU1         GPU2         GPU3\n"
                        "GPU0   0            15           15           15\n"
                        "GPU1   15           0            15           15\n"
                        "GPU2   15           15           0            15\n"
                        "GPU3   15           15           15           0\n"
                        "==================== Link Type between two GPUs ====================\n"
                        "       GPU0   GPU1   GPU2   GPU3\n"
                        "GPU0   0      XGMI   XGMI   XGMI\n"
                        "GPU1   XGMI   0      XGMI   XGMI\n"
                        "GPU2   XGMI   XGMI   0      XGMI\n"
                        "GPU3   XGMI   XGMI   XGMI   0")
            if low.startswith("amd-smi") and "list" in low:
                return ("GPU: 0\n    BDF: 0000:05:00.0\n    UUID: 12ff74a1-0000-1000-...\n"
                        "    KFD_ID: 63274\n    NODE_ID: 2\n    Market Name: AMD Instinct MI300X\n"
                        "GPU: 1\n    BDF: 0000:26:00.0\n    Market Name: AMD Instinct MI300X\n"
                        "... (8 accelerators)")
            if low.startswith("amd-smi") and ("firmware" in low or "static" in low):
                return ("GPU: 0\n  MARKET_NAME: AMD Instinct MI300X\n  VENDOR_ID: 0x1002\n"
                        "  DEVICE_ID: 0x74a1\n  GFX: gfx942\n"
                        "  VBIOS: 022.171.00.009.000001\n  FW_VERSION: 22.40\n"
                        "GPU: 1\n  MARKET_NAME: AMD Instinct MI300X\n  ...")
            if low.startswith("amd-smi") and "process" in low:
                return ("GPU  PID   NAME      MEM_USAGE\n"
                        f"0    {random.randint(20000, 65000)}  python    {random.randint(1000, 80000)} MB\n"
                        f"1    {random.randint(20000, 65000)}  python    {random.randint(1000, 80000)} MB")
            if low.startswith("amd-smi") and ("bad-pages" in low or "ras" in low):
                return ("GPU  RETIRED_PAGES  PENDING  UNCORRECTABLE\n"
                        "0    0               0        0\n"
                        "1    0               0        0")
            if low.startswith("amd-smi") and "xgmi" in low:
                return ("XGMI LINK STATUS\n"
                        "GPU0 <-> GPU1: UP  64 GT/s\n"
                        "GPU0 <-> GPU2: UP  64 GT/s\n"
                        "GPU1 <-> GPU3: UP  64 GT/s")
            if low.startswith("amd-smi") and "event" in low:
                return (
                    "GPU  TIMESTAMP            EVENT\n"
                    f"0    {time.strftime('%Y-%m-%dT%H:%M:%S')}  THERMAL_THROTTLE cleared\n"
                    f"1    {time.strftime('%Y-%m-%dT%H:%M:%S')}  VM_PAGE_FAULT none"
                )
            if low.startswith("amd-smi") and "topology" in low:
                return (
                    "============================ Weight between two GPUs ========================\n"
                    "       GPU0         GPU1         GPU2         GPU3\n"
                    "GPU0   0            15           15           15\n"
                    "GPU1   15           0            15           15\n"
                    "GPU2   15           15           0            15\n"
                    "GPU3   15           15           15           0"
                )
            if low.startswith("amd-smi") and ("reset" in low or "set" in low):
                return "Successfully applied AMD SMI command."
            if "static" in low or "rocminfo" in low:
                return ("Agent 2\n  Name:                    gfx942\n  Marketing Name:          AMD Instinct MI300X\n"
                        "  Device Type:             GPU\n  Wavefront Size:          64(0x40)")
            if low.startswith("amd-smi"):
                if "monitor" in low or "metric" in low or parts[:1] == ["amd-smi"] and len(parts) == 1:
                    from .shell import StreamedCommandResult
                    rows = ["GPU  POWER   GPU_T  MEM_T  GFX_CLK  GFX%  MEM%  VRAM_USED  VRAM_TOTAL"]
                    for _tick in range(4):
                        for i in range(8):
                            rows.append(
                                f"{i:<4} {random.randint(120, 700):3d} W  {random.randint(38, 68)}°C  "
                                f"{random.randint(40, 70)}°C  {random.randint(1300, 2100)} MHz  "
                                f"{random.randint(0, 100):3d}%  {random.randint(0, 95):3d}%  "
                                f"{random.randint(1000, 190000):6d} MB  196592 MB")
                    return StreamedCommandResult(lines=rows, delay_s=0.6)
            if any(f"--show{x}" in low or f"show{x}" in low.replace("-", "") for x in (
                "temp", "power", "use", "clocks", "meminfo", "id", "bus", "pid", "pcie",
                "perflevel", "overdrive", "profile", "ras", "ecc", "vbios", "serial",
                "uniqueid", "pagesinfo", "all", "productname", "driverversion", "hw",
                "fwinfo", "voltage", "memvendor", "computepartition", "memorypartition",
            )) or "--showtemp" in low or "--showpower" in low or "--showuse" in low or "--showall" in low:
                # Legacy rocm-smi flag family used in AMD Support One-Pager diagnostics.
                rows = ["======================= ROCm System Management Interface ======================="]
                if "meminfo" in low or "vram" in low:
                    for i in range(8):
                        used = random.randint(1000, 180000)
                        rows.append(
                            f"GPU[{i}]\t: VRAM Total: 196592 MB  Used: {used} MB  "
                            f"Free: {196592 - used} MB"
                        )
                elif "productname" in low or "hw" in low or "driverversion" in low:
                    for i in range(8):
                        rows.append(
                            f"GPU[{i}]\t: Card series: Instinct MI300X  "
                            f"Card model: 0x74a1  Driver: 6.2.0  VBIOS: 022.171.00.009"
                        )
                elif "fwinfo" in low or "vbios" in low:
                    for i in range(8):
                        rows.append(f"GPU[{i}]\t: VBIOS: 022.171.00.009.000001  FW: 22.40")
                else:
                    for i in range(8):
                        rows.append(
                            f"GPU[{i}]\t: Temp: edge {random.randint(38, 72)}c  "
                            f"junction {random.randint(42, 78)}c  "
                            f"Power: {random.randint(90, 550)}W  "
                            f"GPU use: {random.randint(0, 99)}%"
                        )
                rows.append("==================================================================================")
                return "\n".join(rows)
            if low.startswith("rocm-smi") and (
                "--setpoweroverdrive" in low or "--setperflevel" in low or "--setprofile" in low
                or "--setfan" in low or "--reset" in low
            ):
                return "Successfully set."
            # amd-smi has its own layout (monitor / metric); it is NOT rocm-smi.
            if low.startswith("amd-smi"):
                if "version" in low:
                    return ("AMDSMI Tool: 24.6.2+2b02a07 | "
                            "AMDSMI Library version: 24.6.2 | ROCm version: 6.2.0")
                # bare `amd-smi` prints usage
                return ("usage: amd-smi [-h] {version,list,static,firmware,bad-pages,"
                        "metric,process,event,topology,set,reset,monitor,xgmi,ras} ...\n"
                        "AMD System Management Interface | Version: 24.6.2 | ROCm version: 6.2.0")
            # rocm-smi concise info across the full 8x MI300X node.
            rows = ["========================= ROCm System Management Interface =========================",
                    "================================= Concise Info =====================================",
                    "GPU  Temp   AvgPwr  SCLK     MCLK     Fan  Perf  PwrCap  VRAM%  GPU%"]
            for i in range(8):
                t = 44.0 + i * 0.5
                p = 118.0 + i * 2.0
                util = random.randint(20, 90)
                rows.append(
                    f"{i}    {t:.1f}c  {p:.1f}W  1300Mhz  1600Mhz  0%   auto  750.0W   "
                    f"{random.randint(20, 90):2d}%   {util:2d}%")
            rows.append("====================================================================================")
            return "\n".join(rows)
        # NCCL performance benchmarks (nccl-tests): all_reduce_perf / all_gather_perf …
        if any(low.startswith(c) for c in ("all_reduce_perf", "all_gather_perf",
                                           "reduce_scatter_perf", "broadcast_perf", "nccl-tests")):
            if not healthy:
                return ("test NCCL failure common.cu:958 'unhandled cuda error "
                        "(run with NCCL_DEBUG=INFO for details)'")
            op = "all_reduce_perf"
            for c in ("all_reduce_perf", "all_gather_perf", "reduce_scatter_perf", "broadcast_perf"):
                if low.startswith(c):
                    op = c
                    break
            # nGPUs from -g N (default 8).
            ngpus = _SMI_GPU_COUNT
            if "-g" in parts:
                try:
                    ngpus = int(parts[parts.index("-g") + 1])
                except (ValueError, IndexError):
                    pass
            header = (
                f"# nThread 1 nGpus {ngpus} minBytes 8388608 maxBytes 8589934592 step: 2(factor) "
                "warmup iters: 5 iters: 20 agg iters: 1 validation: 1 graph: 0\n"
                "#\n"
                f"# Using devices\n"
                + "\n".join(
                    f"#  Rank {i} Group  0 Pid  {random.randint(20000, 60000)} on gpu-node "
                    f"device {i} [0x{(i + 1) * 0x10 + 1:02x}] {_SMI_GPU_NAME}"
                    for i in range(ngpus)
                )
                + "\n#\n"
                "#                                                              out-of-place                       in-place\n"
                "#       size         count      type   redop    root     time   algbw   busbw #wrong     time   algbw   busbw #wrong\n"
                "#        (B)    (elements)                               (us)  (GB/s)  (GB/s)            (us)  (GB/s)  (GB/s)")
            sizes = [8388608, 16777216, 33554432, 67108864, 134217728, 268435456,
                     536870912, 1073741824, 2147483648, 4294967296, 8589934592]
            lines = [header]
            peak_busbw = 0.0
            for sz in sizes:
                count = sz // 4
                # Larger messages approach NVLink/NVSwitch peak (~480 GB/s busbw on H100).
                busbw = min(480.0, 40.0 + sz / 2.0e7) * random.uniform(0.9, 1.02)
                algbw = busbw * ngpus / (2.0 * (ngpus - 1)) if ngpus > 1 else busbw
                t_us = (sz / (algbw * 1e9)) * 1e6
                peak_busbw = max(peak_busbw, busbw)
                lines.append(
                    f"  {sz:11d} {count:13d}     float     sum      -1  "
                    f"{t_us:8.1f} {algbw:7.2f} {busbw:7.2f}      0  "
                    f"{t_us * 0.98:8.1f} {algbw * 1.01:7.2f} {busbw * 1.01:7.2f}      0")
            lines.append(f"# Out of bounds values : 0 OK")
            lines.append(f"# Avg bus bandwidth    : {peak_busbw * 0.82:.4f}")
            lines.append("#")
            return "\n".join(lines)
        return f"{line}: OK (GPU simulation)"
    shell.register_handler(handler)


def bootstrap_standalone_cli_modules(shell: RHELShell) -> None:
    """Optional explicit bootstrap — RHELShell._cmd_kubectl/_cmd_aws delegate by default."""
    _register_aws_cli(shell)


def _register_aws_cli(shell: RHELShell) -> None:
    """AWS CLI in RHEL terminals — session-linked when available, else local simulation."""

    def handler(parts: list[str], line: str) -> str | None:
        low = line.strip().lower()
        if not low.startswith("aws "):
            return None
        sid = getattr(shell.state, "session_id", "") or ""
        if sid:
            try:
                from apps.vmware_sim import terraform_engine as te

                slug = getattr(shell.state, "scenario_slug", "") or ""
                te._ensure(sid, slug)
                res = te.apply_action(sid, "aws_cli", {"command": line.strip()})
                if not res.get("ok"):
                    shell.state.last_exit_code = 1
                    return res.get("error") or "Error"
                shell.state.last_exit_code = 0
                return res.get("output") or ""
            except Exception:  # noqa: BLE001
                pass
        return _handle_aws_cli_local(line.strip())

    shell.register_handler(handler)


def _handle_aws_cli_local(command: str) -> str:
    """Offline AWS CLI simulation when no lab session is linked."""
    import json

    low = command.lower()
    if low.startswith("aws sts get-caller-identity"):
        return json.dumps(
            {
                "UserId": "AIDAIOSFODNN7EXAMPLE",
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/training",
            },
            indent=2,
        )
    if "s3 ls" in low:
        return "2024-01-15 10:00:00 app-logs-prod\n2024-06-01 08:30:00 fixitlab-artifacts"
    if "s3api get-bucket-policy" in low or "s3api get-bucket-acl" in low:
        return json.dumps({"Version": "2012-10-17", "Statement": []}, indent=2)
    if "ec2 describe-instances" in low:
        return (
            "-----------------------------------------------------------------\n"
            "|                     DescribeInstances                         |\n"
            "-----------------------------------------------------------------\n"
            "i-0abc123def4567890  t3.medium  running  ap-south-1a"
        )
    if "ec2 describe-vpcs" in low:
        return "vpc-0abc123  10.0.0.0/16  available"
    if "ec2 describe-security-groups" in low:
        return "sg-0abc123  web-sg  vpc-0abc123"
    if "iam list-users" in low:
        return "Users:\n- training\n- automation"
    if "iam get-user" in low:
        return json.dumps({"User": {"UserName": "training", "UserId": "AIDAIOSFODNN7EXAMPLE"}}, indent=2)
    if "eks list-clusters" in low:
        return "fixitlab-training"
    if "eks describe-cluster" in low:
        return json.dumps({"cluster": {"name": "fixitlab-training", "status": "ACTIVE"}}, indent=2)
    if "lambda list-functions" in low:
        return "Functions:\n- fixitlab-handler"
    if "cloudwatch describe-alarms" in low:
        return "ALARM_NAME  STATE\nhigh-cpu    OK"
    if "logs describe-log-groups" in low:
        return "logGroupName\n/aws/lambda/fixitlab-handler"
    if "autoscaling describe-auto-scaling-groups" in low:
        return "AutoScalingGroupName  DesiredCapacity  MinSize  MaxSize\nweb-asg  2  2  6"
    return f"(simulated) {command}"


def _register_k8s(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    sid = getattr(getattr(shell, "state", None), "session_id", "") or ""
    if not engine.cluster:
        engine.cluster = K8sCluster(engine.scenario_slug, session_id=sid)
        # Academy k8s labs: start with broken pods (real validation, not FIXED-OK).
        slug = (engine.scenario_slug or "")
        if slug.startswith("academy-kubernetes"):
            try:
                from .flagship_presets import FLAGSHIP_SLUGS as _FS
            except Exception:
                _FS = frozenset()
            if slug not in _FS:
                for pod in engine.cluster.pods:
                    pod.status = "CrashLoopBackOff"
                    pod.ready = "0/1"
    elif sid and not getattr(engine.cluster, "session_id", ""):
        engine.cluster.session_id = sid

    def handler(parts, line):
        if not parts or parts[0] != "kubectl":
            return None
        # Re-fold any VMware node action performed since the last command so the
        # terminal reflects a node added/reset in the VMware simulator (the two
        # run in different workers; the bridge cache is the shared source).
        cluster = engine.cluster
        if cluster is not None:
            if not getattr(cluster, "session_id", ""):
                cluster.session_id = getattr(getattr(shell, "state", None), "session_id", "") or ""
            cluster.sync_from_vmware_bridge()
        return _handle_kubectl(cluster, parts, line, shell)

    shell.register_handler(handler)


# --- kubectl argument parsing helpers -------------------------------------

def _kube_flags(parts: list[str]) -> tuple[list[str], dict[str, str], dict[str, bool]]:
    """Split kubectl args into positionals, value-flags, and bool-flags."""
    pos: list[str] = []
    vals: dict[str, str] = {}
    flags: dict[str, bool] = {}
    i = 0
    value_flags = {"-n", "--namespace", "-o", "--output", "-f", "--filename",
                   "--replicas", "--image", "--type", "--port", "--target-port",
                   "-l", "--selector", "--overwrite",
                   "--min", "--max", "--cpu-percent", "--requests", "--limits"}
    while i < len(parts):
        tok = parts[i]
        if tok.startswith("-"):
            if "=" in tok:
                k, v = tok.split("=", 1)
                vals[k] = v
            elif tok in value_flags and i + 1 < len(parts):
                vals[tok] = parts[i + 1]
                i += 1
            else:
                flags[tok] = True
        else:
            pos.append(tok)
        i += 1
    return pos, vals, flags


def _kube_ns(vals: dict[str, str], flags: dict[str, bool]) -> tuple[str, bool]:
    all_ns = flags.get("-A", False) or flags.get("--all-namespaces", False)
    ns = vals.get("-n") or vals.get("--namespace") or "default"
    return ns, all_ns


def _kube_out(vals: dict[str, str]) -> str:
    return (vals.get("-o") or vals.get("--output") or "").lower()


_K8S_KIND_ALIASES = {
    "po": "pods", "pod": "pods", "pods": "pods",
    "no": "nodes", "node": "nodes", "nodes": "nodes",
    "svc": "svc", "service": "svc", "services": "svc",
    "deploy": "deploy", "deployment": "deploy", "deployments": "deploy", "deployments.apps": "deploy",
    "rs": "rs", "replicaset": "rs", "replicasets": "rs",
    "cm": "cm", "configmap": "cm", "configmaps": "cm",
    "secret": "secret", "secrets": "secret",
    "pvc": "pvc", "persistentvolumeclaim": "pvc", "persistentvolumeclaims": "pvc",
    "ing": "ing", "ingress": "ing", "ingresses": "ing",
    "ns": "ns", "namespace": "ns", "namespaces": "ns",
    "ep": "ep", "endpoints": "ep", "endpoint": "ep",
    "event": "events", "events": "events", "ev": "events",
    "hpa": "hpa", "horizontalpodautoscaler": "hpa", "horizontalpodautoscalers": "hpa",
    "ds": "ds", "daemonset": "ds", "daemonsets": "ds",
    "all": "all",
}


def _handle_kubectl(c, parts: list[str], line: str, shell: RHELShell) -> str:
    if len(parts) < 2:
        return "kubectl controls the Kubernetes cluster manager.\n\nUsage:\n  kubectl [command]"
    verb = parts[1]
    args = parts[2:]
    pos, vals, flags = _kube_flags(args)
    ns, all_ns = _kube_ns(vals, flags)
    out_fmt = _kube_out(vals)

    # ---- version / cluster-info / config / api-resources ----
    if verb == "version":
        return ("Client Version: v1.28.2\n"
                "Kustomize Version: v5.0.4-0.20230601165947\n"
                "Server Version: v1.28.2")
    if verb == "cluster-info":
        return ("Kubernetes control plane is running at https://10.96.0.1:6443\n"
                "CoreDNS is running at https://10.96.0.1:6443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy")
    if verb == "config":
        sub = args[0] if args else ""
        if sub == "current-context":
            return "kubernetes-admin@kubernetes"
        if sub == "get-contexts":
            return "CURRENT   NAME                          CLUSTER      AUTHINFO\n*         kubernetes-admin@kubernetes   kubernetes   kubernetes-admin"
        if sub == "view":
            return shell.state.read_file("/root/.kube/config") or "apiVersion: v1\nkind: Config"
        return ""
    if verb == "api-resources":
        return ("NAME         SHORTNAMES   APIVERSION   NAMESPACED   KIND\n"
                "pods         po           v1           true         Pod\n"
                "services     svc          v1           true         Service\n"
                "deployments  deploy       apps/v1      true         Deployment\n"
                "nodes        no           v1           false        Node")

    # ---- get ----
    if verb == "get":
        kind = _K8S_KIND_ALIASES.get(pos[0].lower(), pos[0].lower()) if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        if out_fmt in ("yaml", "json"):
            if kind == "pods" and name:
                return c.pod_yaml(name)
            if kind == "deploy" and name:
                return c.deployment_yaml(name)
        wide = out_fmt == "wide"
        if kind == "pods":
            return c.get_pods(ns, all_ns, wide)
        if kind == "nodes":
            # custom-columns / jsonpath probing nvidia.com/gpu allocatable
            if "custom-columns" in out_fmt or "nvidia.com/gpu" in line.lower() or (
                "allocatable" in line.lower() and "gpu" in line.lower()
            ):
                return c.get_nodes_gpu_columns()
            return c.get_nodes(wide)
        if kind == "svc":
            return c.get_services(ns, all_ns)
        if kind == "deploy":
            return c.get_deployments(ns, all_ns)
        if kind == "rs":
            return c.get_replicasets(ns)
        if kind == "cm":
            return c.get_configmaps(ns)
        if kind == "secret":
            return c.get_secrets(ns)
        if kind == "pvc":
            return c.get_pvcs(ns)
        if kind == "ing":
            return c.get_ingresses(ns)
        if kind == "ns":
            return c.get_namespaces()
        if kind == "ep":
            return c.get_endpoints(name)
        if kind == "hpa":
            return c.get_hpa(ns)
        if kind == "ds":
            return c.get_daemonsets(ns)
        if kind == "events":
            return c.get_events(ns, all_ns)
        if kind == "all":
            return c.get_all(ns)
        return f"error: the server doesn't have a resource type \"{pos[0] if pos else ''}\""

    # ---- describe ----
    if verb == "describe":
        kind = _K8S_KIND_ALIASES.get(pos[0].lower(), pos[0].lower()) if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        if kind == "pods":
            return c.describe_pod(name)
        if kind == "deploy":
            return c.describe_deployment(name)
        if kind == "nodes":
            return c.describe_node(name)
        if kind == "svc":
            return c.describe_service(name)
        if kind == "hpa":
            return c.describe_hpa(name)
        return f"error: unknown resource type \"{pos[0] if pos else ''}\""

    # ---- logs ----
    if verb == "logs":
        previous = flags.get("--previous", False) or flags.get("-p", False)
        targets = [p for p in pos]
        # `logs deployment/web` → first matching pod
        name = targets[0] if targets else ""
        if "/" in name:
            kind, dep = name.split("/", 1)
            pod = next((p for p in c.pods if p.owner == dep or dep in p.name), None)
            name = pod.name if pod else dep
        return c.logs(name, previous)

    # ---- exec ----
    if verb == "exec":
        # kubectl exec [-it] POD [-c container] -- CMD...
        name = next((p for p in pos), "")
        cmd = ""
        if "--" in parts:
            idx = parts.index("--")
            cmd = " ".join(parts[idx + 1:])
        return c.exec_pod(name, cmd)

    # ---- apply / create -f ----
    if verb in ("apply", "create") and ("-f" in vals or "--filename" in vals):
        path = vals.get("-f") or vals.get("--filename")
        content = shell.state.read_file(path)
        if content is None:
            return f"error: the path \"{path}\" does not exist"
        return c.apply_yaml(content, create=(verb == "create"))

    # ---- create <kind> imperatively ----
    if verb == "create":
        kind = pos[0].lower() if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        if kind in ("namespace", "ns"):
            return c.create_namespace(name)
        if kind in ("configmap", "cm"):
            data = {}
            for k, v in vals.items():
                if k == "--from-literal" and "=" in v:
                    kk, vv = v.split("=", 1)
                    data[kk] = vv
            for tok in args:
                if tok.startswith("--from-literal="):
                    kv = tok.split("=", 1)[1]
                    if "=" in kv:
                        kk, vv = kv.split("=", 1)
                        data[kk] = vv
            return c.create_configmap(name, ns, data)
        if kind == "secret":
            # create secret generic NAME --from-literal=k=v
            sec_name = pos[2] if len(pos) > 2 else name
            data = {}
            for tok in args:
                if tok.startswith("--from-literal="):
                    kv = tok.split("=", 1)[1]
                    if "=" in kv:
                        kk, vv = kv.split("=", 1)
                        data[kk] = vv
            return c.create_secret(sec_name, ns, data)
        if kind == "deployment":
            image = vals.get("--image", "nginx:latest")
            manifest = f"kind: Deployment\nname: {name}\nnamespace: {ns}\nimage: {image}\napp: {name}\n"
            return c.apply_yaml(manifest, create=True)
        return f"{kind}/{name} created"

    # ---- run ----
    if verb == "run":
        name = pos[0] if pos else "pod"
        image = vals.get("--image", "nginx:latest")
        return c.run_pod(name, image)

    # ---- scale ----
    if verb == "scale":
        replicas = int(vals.get("--replicas", "1"))
        target = pos[0] if pos else ""
        if "deployment" in target or "deploy" in target:
            target = pos[1] if len(pos) > 1 else target.split("/")[-1]
        target = target.split("/")[-1]
        return c.scale(target, replicas)

    # ---- autoscale (create an HPA) ----
    if verb == "autoscale":
        target = pos[1] if len(pos) > 1 and ("deploy" in pos[0] or "deployment" in pos[0]) else (pos[0] if pos else "")
        dep = target.split("/")[-1]
        def _intval(*keys, default):
            for k in keys:
                if k in vals:
                    try:
                        return int(vals[k])
                    except ValueError:
                        pass
            return default
        min_r = _intval("--min", default=1)
        max_r = _intval("--max", default=max(min_r, 5))
        cpu = _intval("--cpu-percent", default=50)
        return c.autoscale(dep, min_r, max_r, cpu)

    # ---- set image ----
    if verb == "set" and pos and pos[0] == "image":
        target = pos[1] if len(pos) > 1 else ""
        dep = target.split("/")[-1]
        image = ""
        for tok in pos[2:]:
            if "=" in tok:
                image = tok.split("=", 1)[1]
        return c.set_image(dep, image)

    # ---- rollout ----
    if verb == "rollout":
        sub = pos[0] if pos else ""
        target = pos[1] if len(pos) > 1 else ""
        dep = target.split("/")[-1]
        if sub == "restart":
            return c.rollout_restart(dep)
        if sub == "undo":
            return c.rollout_undo(dep)
        if sub == "status":
            return c.rollout_status(dep)
        if sub == "history":
            return c.rollout_history(dep)
        return f"error: unknown rollout subcommand \"{sub}\""

    # ---- delete ----
    if verb == "delete":
        if "-f" in vals or "--filename" in vals:
            path = vals.get("-f") or vals.get("--filename")
            content = shell.state.read_file(path) or ""
            import re as _re
            km = _re.search(r"kind:\s*(\S+)", content)
            nm = _re.search(r"name:\s*(\S+)", content)
            if km and nm:
                return c.delete_resource(km.group(1), nm.group(1).strip("\"'"))
            return "deleted"
        kind = pos[0].lower() if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        return c.delete_resource(kind, name)

    # ---- edit (treat as no-op acknowledgement; image fixes come via set image) ----
    if verb == "edit":
        kind = pos[0].lower() if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        return f"{kind}.apps/{name} edited" if name else "edited"

    # ---- patch ----
    if verb == "patch":
        kind = pos[0].lower() if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        patch_body = ""
        for k, v in vals.items():
            if k in ("-p", "--patch"):
                patch_body = v
        if kind in ("svc", "service"):
            return c.patch_service_selector(name or "api", {"app": (name or "api")})
        if kind in ("deployment", "deploy"):
            m = None
            import re as _re
            m = _re.search(r"image\"?:\s*\"?([\w./:-]+)", patch_body)
            if m:
                return c.set_image(name, m.group(1))
            # No explicit image: heal a broken image deployment.
            dep = c.find_deployment(name)
            if dep and ("broken" in dep.image or "missing" in dep.image):
                fixed = dep.image.replace("broken", "latest").replace("missing-tag", "v1")
                return c.set_image(name, fixed)
            return f"deployment.apps/{name} patched"
        return f"{kind}/{name} patched"

    # ---- label / annotate ----
    if verb == "label":
        kind = pos[0].lower() if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        for tok in pos[2:]:
            if tok.endswith("-"):
                return c.label(kind, name, tok[:-1], None)
            if "=" in tok:
                k, v = tok.split("=", 1)
                return c.label(kind, name, k, v)
        return f"{kind}/{name} labeled"
    if verb == "annotate":
        kind = pos[0].lower() if pos else ""
        name = pos[1] if len(pos) > 1 else ""
        for tok in pos[2:]:
            if tok.endswith("-"):
                return c.annotate(kind, name, tok[:-1], None)
            if "=" in tok:
                k, v = tok.split("=", 1)
                return c.annotate(kind, name, k, v)
        return f"{kind}/{name} annotated"

    # ---- cordon / uncordon / drain ----
    if verb == "cordon":
        return c.cordon(pos[0] if pos else "worker-1")
    if verb == "uncordon":
        return c.uncordon(pos[0] if pos else "worker-1")
    if verb == "drain":
        return c.drain(pos[0] if pos else "worker-1")

    # ---- expose ----
    if verb == "expose":
        target = pos[1] if len(pos) > 1 else (pos[0] if pos else "")
        dep = target.split("/")[-1]
        port = int(vals.get("--port", "80"))
        stype = vals.get("--type", "ClusterIP")
        return c.expose(dep, port, stype)

    # ---- top ----
    if verb == "top":
        kind = pos[0].lower() if pos else ""
        if kind in ("node", "nodes", "no"):
            return c.top_nodes()
        if kind in ("pod", "pods", "po"):
            return c.top_pods(ns)
        return c.top_nodes()

    # ---- auth can-i ----
    if verb == "auth" and pos and pos[0] == "can-i":
        action = pos[1] if len(pos) > 1 else "get"
        resource = pos[2] if len(pos) > 2 else "pods"
        return c.auth_can_i(action, resource)

    # ---- explain / api-versions ----
    if verb == "explain":
        return f"KIND:     {pos[0].title() if pos else 'Pod'}\nVERSION:  v1\n\nDESCRIPTION:\n     Kubernetes resource."

    return f"error: unknown command \"{verb}\" for \"kubectl\""


def _register_ansible(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    slug = (getattr(engine, "scenario_slug", "") or "").lower()

    def handler(parts, line):
        low = line.strip().lower()
        if low.startswith("ssh-copy-id"):
            engine._ssh_key_fixed = True
            return "Number of key(s) added: 1"
        # AWX / Tower CLI used in AI Infra driver-install & repave labs
        if low.startswith("awx ") or low.startswith("tower-cli"):
            if "login" in low or "--conf.host" in low:
                return "ok"
            if "job_templates" in low and ("list" in low or "get" in low):
                return (
                    "id  name                              inventory\n"
                    "12  GPU Driver Install (H100)         maas-gpu-nodes\n"
                    "18  DCGM Exporter Deploy              maas-gpu-nodes\n"
                    "24  Image Repave (jammy-h100)         maas-gpu-nodes\n"
                    "31  NVIDIA Persistence Mode           maas-gpu-nodes"
                )
            if "inventory" in low and "list" in low:
                return (
                    "id  name\n"
                    "3   maas-gpu-nodes\n"
                    "4   lxd-burn-in"
                )
            if "job_templates launch" in low or "jobs launch" in low or "launch" in low:
                jid = random.randint(4000, 9000)
                from .shell import StreamedCommandResult
                lines = [
                    f"Job {jid} launched (pending)",
                    f"Job {jid} → running  (0%) waiting for capacity",
                    f"Job {jid} → running (35%) installing nvidia-driver-565",
                    f"Job {jid} → running (70%) enabling nvidia-persistenced",
                    f"Job {jid} → successful",
                    "PLAY RECAP *********************************************************************",
                    "gpu-node-01 : ok=6  changed=3  unreachable=0  failed=0",
                ]
                return StreamedCommandResult(lines=lines, delay_s=0.5)
            if "jobs get" in low or "jobs stdout" in low:
                return "status: successful\nelapsed: 00:04:12"
            return (
                "usage: awx job_templates list|launch\n"
                "       awx inventory list\n"
                "       awx jobs get <id>"
            )
        if not (low.startswith("ansible ") or low.startswith("ansible-playbook") or low.startswith("ansible-inventory")):
            return None
        if low in ("ansible --version", "ansible-playbook --version"):
            return "ansible [core 2.15.3]\n  python version = 3.11.6"
        if "ping" in low:
            if engine._ssh_key_fixed:
                return "web1 | SUCCESS => {\"ping\": \"pong\"}\nweb2 | SUCCESS => {\"ping\": \"pong\"}"
            # AI Infra MAAS inventory nodes (when scenario mentions gpu/maas)
            if "ai-infra" in slug or "gpu" in slug or "maas" in slug:
                return (
                    "gpu-node-01 | SUCCESS => {\"ping\": \"pong\"}\n"
                    "gpu-node-02 | SUCCESS => {\"ping\": \"pong\"}"
                )
            return (
                "web1 | SUCCESS => {\"ping\": \"pong\"}\n"
                "web2 | UNREACHABLE! => {\"msg\": \"Permission denied (publickey).\"}"
            )
        if "ansible-playbook" in low:
            if engine._ssh_key_fixed or "ai-infra" in slug or "nvidia" in low or "dcgm" in low:
                engine._ansible_playbook_ok = True
                hosts = "gpu-node-01\ngpu-node-02" if ("ai-infra" in slug or "gpu" in slug) else "web1\nweb2"
                recap = "\n".join(
                    f"{h} : ok=3 changed=2 unreachable=0 failed=0"
                    for h in hosts.splitlines()
                )
                return f"PLAY RECAP *****\n{recap}"
            return "fatal: [web2]: FAILED! => Unable to start service nginx"
        if "ansible-inventory" in low:
            if "ai-infra" in slug or "gpu" in slug:
                return '{"gpu_nodes": {"hosts": ["gpu-node-01", "gpu-node-02", "gpu-node-03"]}}'
            return '{"webservers": {"hosts": ["web1", "web2"]}}'
        return f"{line}: OK"
    shell.register_handler(handler)


def _seed_devops_git_repo(state) -> None:
    """Seed /root/app as a working git repo with history + a feature branch."""
    from .git_state import seed_repo

    if state.git.repos:
        return
    app_py = (
        "from flask import Flask\n\n"
        "app = Flask(__name__)\n\n\n"
        "@app.route('/healthz')\n"
        "def healthz():\n"
        "    return {'status': 'ok'}\n"
    )
    ci_yml = (
        "stages:\n  - build\n  - test\n  - deploy\n\n"
        "build:\n  stage: build\n  script:\n    - docker build -t registry.fixitlab.local/platform/app:$CI_COMMIT_SHORT_SHA .\n\n"
        "test:\n  stage: test\n  script:\n    - python -m pytest tests/ -q\n\n"
        "deploy:\n  stage: deploy\n  script:\n    - helm upgrade --install webapp charts/webapp\n  only:\n    - main\n"
    )
    seed_repo(
        state.git,
        state,
        "/root/app",
        files={},
        history=[
            ("Initial commit", {"README.md": "# platform/app\n\nPayments API service.\n", "app.py": app_py}),
            ("Add CI pipeline", {".gitlab-ci.yml": ci_yml}),
            ("Add health endpoint tests", {"tests/test_health.py": "def test_healthz():\n    assert True\n"}),
        ],
        branch_commits={
            "feature/rate-limit": [
                ("Add rate limiting middleware", {"middleware.py": "RATE_LIMIT = 100  # req/min\n"}),
            ],
        },
    )


def _vyos_session_id(engine: "UnifiedSimulationEngine") -> str:
    sid = getattr(engine, "lab_session_id", None) or getattr(engine, "session_id", None)
    if sid:
        return str(sid)
    st = getattr(getattr(engine, "shell", None), "state", None)
    if st is not None:
        sid = getattr(st, "session_id", None) or ""
        if sid:
            return str(sid)
    return ""


def _ensure_vyos_networking(engine: "UnifiedSimulationEngine") -> NetworkingState:
    """Return NetworkingState, preferring cache-backed session state when available."""
    if engine.networking is not None:
        return engine.networking
    sid = _vyos_session_id(engine)
    slug = engine.scenario_slug or ""
    if sid:
        try:
            from apps.vmware_sim.vyos_views import load_networking
            engine.networking = load_networking(sid, slug)
            return engine.networking
        except Exception:
            pass
    engine.networking = NetworkingState(slug)
    return engine.networking


def _persist_vyos_networking(engine: "UnifiedSimulationEngine", net: NetworkingState) -> None:
    sid = _vyos_session_id(engine)
    if not sid:
        return
    try:
        from apps.vmware_sim.vyos_views import save_networking
        save_networking(sid, net)
    except Exception:
        pass


def _vyos_dispatch(net: NetworkingState, line: str, engine: "UnifiedSimulationEngine") -> str:
    """Dispatch a VyOS CLI line; prefer shared apply_cli_line when available."""
    shell_state = getattr(getattr(engine, "shell", None), "state", None)
    try:
        from apps.vmware_sim.vyos_views import apply_cli_line
        return apply_cli_line(net, line, shell_state)
    except Exception:
        pass
    # Fallback without vmware_sim import (tests / isolated)
    low = line.strip().lower()
    if low == "configure" or low.startswith("configure "):
        return net.vyos_enter_configure()
    if low == "exit" and net.vyos_configure_mode:
        return net.vyos_exit_configure()
    if low in ("discard",) or low.startswith("discard "):
        return net.vyos_discard()
    if low == "compare" or low.startswith("compare"):
        return net.vyos_compare()
    if low.startswith("show system commit"):
        return net.vyos_show_history()
    if low.startswith("commit-confirm"):
        parts = line.strip().split()
        minutes = 10
        if len(parts) > 1 and parts[1].isdigit():
            minutes = int(parts[1])
        return net.vyos_commit_confirm(minutes)
    if low == "confirm" or low.startswith("confirm "):
        return net.vyos_confirm()
    if low == "commit" or low.startswith("commit "):
        return net.vyos_commit()
    if low.startswith("rollback"):
        parts_r = line.strip().split()
        steps = 1
        if len(parts_r) > 1 and parts_r[1].lstrip("-").isdigit():
            steps = abs(int(parts_r[1]))
        return net.vyos_rollback(steps)
    if low == "save" or low.startswith("save "):
        return net.vyos_save(shell_state)
    if low == "load" or low.startswith("load "):
        return net.vyos_load(shell_state)
    if low.startswith("set "):
        return net.vyos_set(line.strip()[4:].strip())
    if low.startswith("delete "):
        return net.vyos_delete(line.strip()[7:].strip())
    if low.startswith("edit "):
        return net.vyos_edit(line.strip()[5:].strip())
    if low == "edit":
        return net.vyos_edit("")
    if low == "up":
        return net.vyos_up()
    if low == "top":
        return net.vyos_top()
    if low in ("show",) or "show pending" in low:
        return net.vyos_show_pending()
    if "show conf" in low or "configuration" in low:
        cand = "candidate" in low or net.vyos_configure_mode
        return net.vyos_show_config(candidate=cand)
    if "show ip bgp" in low or "show protocols bgp" in low or "bgp summary" in low:
        return net.show_ip_bgp_summary()
    if "show ip ospf" in low:
        return net.show_ip_ospf_neighbor()
    if "show ip route" in low:
        return net.show_ip_route()
    if "show interfaces" in low:
        return net.show_interfaces()
    if "show vrrp" in low or "show high-availability" in low:
        return net.show_vrrp()
    if "show nat" in low:
        return net.show_nat()
    if "show firewall" in low:
        return net.show_firewall()
    if "show dhcp" in low:
        return net.show_dhcp_leases()
    if "show log" in low:
        return net.show_log()
    if "show version" in low:
        return net.show_version()
    if line.endswith("?") or low.endswith(" ?"):
        return net.vyos_help(line)
    return f"Invalid command: {line}"


def _register_baremetal(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    # IPMI power labs start with the chassis OFF so the learner has to bring it
    # up (`ipmitool power on`); otherwise the canonical power check auto-passes.
    slug = (engine.scenario_slug or "").lower()
    if slug in ("sim-baremetal-ipmi", "sim-rhel-baremetal-ipmi", "maas-ipmi-bmc-unreachable"):
        engine._power_state = "off"
    # MAAS machine inventory for AI Infra / baremetal commission labs.
    if not hasattr(engine, "_maas_machines") or not engine._maas_machines:
        engine._maas_machines = [
            {"name": "gpu-node-01", "status": "Ready", "power": "on", "arch": "amd64/generic",
             "zone": "default", "pool": "default", "ip": "10.64.12.11"},
            {"name": "gpu-node-02", "status": "Deployed", "power": "on", "arch": "amd64/generic",
             "zone": "default", "pool": "default", "ip": "10.64.12.12"},
            {"name": "gpu-node-03", "status": "Failed commissioning", "power": "on",
             "arch": "amd64/generic", "zone": "default", "pool": "default", "ip": "10.64.12.13"},
            {"name": "gpu-node-04", "status": "New", "power": "off", "arch": "amd64/generic",
             "zone": "default", "pool": "default", "ip": "-"},
        ]
    if not hasattr(engine, "_lxd_instances"):
        engine._lxd_instances = {
            "gpu-worker-1": {
                "state": "RUNNING", "type": "container", "ipv4": "10.150.1.10",
                "ipv6": "", "snapshots": 0, "profiles": ["default", "gpu-passthrough"],
                "devices": {"gpu": {"type": "gpu"}}, "config": {}, "project": "default",
                "location": "node1", "nvidia_smi_ok": True, "image": "ubuntu:22.04",
            },
            "k8s-node-2": {
                "state": "STOPPED", "type": "virtual-machine", "ipv4": "",
                "ipv6": "", "snapshots": 0, "profiles": ["default"],
                "devices": {}, "config": {}, "project": "default",
                "location": "none", "nvidia_smi_ok": False, "image": "ubuntu:22.04",
            },
            "burn-in-h100": {
                "state": "RUNNING", "type": "container", "ipv4": "10.150.1.20",
                "ipv6": "", "snapshots": 0, "profiles": ["default"],
                "devices": {}, "config": {}, "project": "default",
                "location": "none", "nvidia_smi_ok": False, "image": "ubuntu:22.04",
            },
        }
    if not hasattr(engine, "_lxd_profiles"):
        engine._lxd_profiles = {
            "default": {"config": {}, "devices": {}},
            "gpu-passthrough": {
                "config": {"nvidia.runtime": "true"},
                "devices": {"gpu0": {"type": "gpu", "gputype": "physical", "pci": "0000:19:00.0"}},
            },
        }
    if not hasattr(engine, "_maas_boot_resources") or engine._maas_boot_resources is None:
        engine._maas_boot_resources = ["ubuntu/jammy", "ubuntu/noble"]

    def _session_id() -> str:
        return str(
            getattr(engine, "lab_session_id", None)
            or getattr(shell.state, "session_id", None)
            or ""
        )

    def _sync_maas_from_gui() -> None:
        """Prefer the MAAS console session inventory when this lab has one.

        Merge — do not replace — so CLI-seeded nodes (e.g. gpu-node-04) remain
        commissionable even when the GUI session only seeded a subset.
        """
        sid = _session_id()
        if not sid:
            return
        try:
            from apps.vmware_sim import baremetal_engine as bm
            data = bm.get_state(sid, engine.scenario_slug or "")
            machines = (data.get("state") or {}).get("maas", {}).get("machines") or []
            if machines:
                prior = list(getattr(engine, "_maas_machines", None) or [])
                merged = [
                    {
                        "name": m.get("hostname") or m.get("name") or f"node-{m.get('id')}",
                        "status": m.get("status") or "New",
                        "power": m.get("power") or "off",
                        "arch": m.get("arch") or "amd64/generic",
                        "zone": m.get("zone") or "default",
                        "pool": m.get("pool") or "default",
                        "ip": m.get("ip") or "-",
                        "id": m.get("id"),
                    }
                    for m in machines
                ]
                gui_names = {m["name"] for m in merged}
                for m in prior:
                    if m.get("name") and m["name"] not in gui_names:
                        merged.append(m)
                engine._maas_machines = merged
            br = (data.get("state") or {}).get("maas", {}).get("boot_resources") or []
            if br:
                engine._maas_boot_resources = [
                    (r.get("name") if isinstance(r, dict) else str(r)) for r in br
                ]
        except Exception:
            pass

    def _apply_maas_gui_action(action: str, payload: dict) -> dict | None:
        sid = _session_id()
        if not sid:
            return None
        try:
            from apps.vmware_sim import baremetal_engine as bm
            # Ensure a signed-in console session exists for CLI parity.
            st = bm.get_state(sid, engine.scenario_slug or "")
            if not (st.get("state") or {}).get("session", {}).get("logged_in"):
                bm.apply_action(sid, "login", {"user": "admin"})
            return bm.apply_action(sid, action, payload)
        except Exception:
            return None

    def _sync_lxd_from_gui() -> None:
        """Prefer the LXD console session inventory when this lab has one."""
        sid = _session_id()
        if not sid:
            return
        try:
            from apps.vmware_sim import baremetal_engine as bm
            data = bm.get_state(sid, engine.scenario_slug or "")
            lxd = (data.get("state") or {}).get("lxd") or {}
            containers = lxd.get("containers") or []
            if containers:
                engine._lxd_instances = {}
                for c in containers:
                    name = c.get("name") or "unnamed"
                    status = (c.get("status") or "Stopped").upper()
                    if status == "RUNNING":
                        cli_state = "RUNNING"
                    else:
                        cli_state = "STOPPED"
                    snaps = c.get("snapshots") or []
                    engine._lxd_instances[name] = {
                        "state": cli_state,
                        "type": c.get("type") or "container",
                        "ipv4": c.get("ipv4") or "",
                        "ipv6": c.get("ipv6") or "",
                        "snapshots": len(snaps) if isinstance(snaps, list) else int(snaps or 0),
                        "profiles": list(c.get("profiles") or ["default"]),
                        "devices": dict(c.get("devices") or {}),
                        "config": dict(c.get("config") or {}),
                        "project": c.get("project") or "default",
                        "location": c.get("location") or "none",
                        "nvidia_smi_ok": bool(c.get("nvidia_smi_ok")),
                        "image": c.get("image") or "ubuntu:22.04",
                        "snapshot_list": list(snaps) if isinstance(snaps, list) else [],
                    }
            profiles = lxd.get("profiles") or []
            if profiles:
                engine._lxd_profiles = {}
                for p in profiles:
                    if isinstance(p, str):
                        engine._lxd_profiles[p] = {"config": {}, "devices": {}}
                    elif isinstance(p, dict) and p.get("name"):
                        engine._lxd_profiles[p["name"]] = {
                            "config": dict(p.get("config") or {}),
                            "devices": dict(p.get("devices") or {}),
                            "description": p.get("description") or "",
                        }
            engine._lxd_storage = lxd.get("storage_pools")
            engine._lxd_networks = lxd.get("networks")
            engine._lxd_projects = lxd.get("projects")
            engine._lxd_cluster = lxd.get("cluster")
            engine._lxd_images = lxd.get("images")
        except Exception:
            pass

    def _apply_lxd_gui_action(action: str, payload: dict) -> dict | None:
        sid = _session_id()
        if not sid:
            return None
        try:
            from apps.vmware_sim import baremetal_engine as bm
            st = bm.get_state(sid, engine.scenario_slug or "")
            if not (st.get("state") or {}).get("session", {}).get("logged_in"):
                bm.apply_action(sid, "login", {"user": "admin"})
            return bm.apply_action(sid, action, payload)
        except Exception:
            return None

    def _mirror_maas(machine: dict) -> None:
        """S1: commission/deploy → unified asset registry."""
        sid = _session_id()
        if not sid:
            return
        try:
            from .server_identity import upsert_from_maas_machine

            upsert_from_maas_machine(sid, machine, source="maas")
        except Exception:
            pass

    def handler(parts, line):
        low = line.strip().lower()
        slug = (engine.scenario_slug or "").lower()
        vyos_lab = any(k in slug for k in ("vyos", "ai-infra", "pxe", "maas", "underlay", "bgp"))
        vyos_cmds = (
            low in ("configure", "commit", "rollback", "exit", "compare", "save", "load",
                    "discard", "confirm", "edit", "up", "top", "show")
            or low.startswith("configure ")
            or low.startswith("commit ")
            or low.startswith("commit-confirm")
            or low.startswith("rollback")
            or low.startswith("set ")
            or low.startswith("delete ")
            or low.startswith("compare")
            or low.startswith("save ")
            or low.startswith("load ")
            or low.startswith("discard ")
            or low.startswith("confirm ")
            or low.startswith("edit ")
            or low.startswith("show system commit")
            or low.startswith("show conf")
            or low.startswith("show configuration")
            or low.startswith("show ip bgp")
            or low.startswith("show ip route")
            or low.startswith("show protocols")
            or low.startswith("show interfaces")
            or low.startswith("show dhcp")
            or low.startswith("show vrrp")
            or low.startswith("show nat")
            or low.startswith("show firewall")
            or low.startswith("show version")
            or low.startswith("show pending")
            or low.startswith("show high-availability")
        )
        if vyos_lab and vyos_cmds:
            net = _ensure_vyos_networking(engine)
            out = _vyos_dispatch(net, line, engine)
            _persist_vyos_networking(engine, net)
            return out

        bare_tools = (
            "ipmitool", "dmidecode", "esxcli", "maas", "lxc", "lxd", "virsh",
            "packer", "vyos", "vyatta", "cloud-init", "cloud-id", "cloud-init-per",
        )
        if not any(low.startswith(t) for t in bare_tools):
            return None
        if low.startswith("cloud-init") or low.startswith("cloud-id"):
            if "status" in low:
                return (
                    "status: done\n"
                    "extended_status: done\n"
                    "boot_status_code: enabled-by-generator\n"
                    "detail: DataSourceMAAS\n"
                    "errors: []"
                )
            if "query" in low or low.startswith("cloud-id"):
                return "maas"
            if "schema" in low:
                return "Valid schema"
            if "clean" in low:
                return "cleaned cloud-init artifacts under /var/lib/cloud"
            # Default: show ImageDev-style userdata summary for GPU images.
            return (
                "cloud-init 24.1.3\n"
                "datasource: DataSourceMAAS\n"
                "modules: [migrator, seed_random, bootcmd, write_files, users_groups,\n"
                "          disk_setup, mounts, set_hostname, update_hostname,\n"
                "          update_etc_hosts, ca_certs, rsyslog, users_groups,\n"
                "          ssh, growpart, resizefs, disk_setup, mounts, set_passwords,\n"
                "          package_update_upgrade_install, landscape, timezone,\n"
                "          disable_ec2_metadata, runcmd, byobu]\n"
                "runcmd: nvidia-smi -L; systemctl enable nvidia-persistenced; gpu-sanity\n"
                "final_message: ImageDev GPU image cloud-init finished in 42.1 seconds"
            )
        if low.startswith("ipmitool"):
            if "power status" in low:
                return f"Chassis Power is {engine._power_state}"
            if "power cycle" in low or "power reset" in low:
                return "Chassis Power Control: Reset"
            if "power off" in low:
                engine._power_state = "off"
                return "Chassis Power Control: Down/Off"
            if "power on" in low:
                engine._power_state = "on"
                return "Chassis Power Control: Up/On"
            if "sensor" in low:
                return (
                    "CPU1 Temp       | 42.000     | degrees C  | ok\n"
                    "Inlet Temp      | 23.000     | degrees C  | ok\n"
                    "Pwr Consumption | 812.000    | Watts      | ok\n"
                    "Fan1A RPM       | 7200.000   | RPM        | ok"
                )
            if "fru" in low:
                mfr = getattr(shell.state, "dmi_manufacturer", None) or "Hewlett Packard Enterprise"
                prod = getattr(shell.state, "dmi_product", None) or "ProLiant DL380 Gen10"
                serial = "CN7293672A008A"
                return (
                    f" Board Mfg Date        : Mon Jan 15 12:00:00 2024\n"
                    f" Board Mfg             : {mfr}\n"
                    f" Board Product         : {prod}\n"
                    f" Board Serial          : {serial}\n"
                    f" Product Name          : {prod}"
                )
            if "lan print" in low or "lan print 1" in low:
                return (
                    "IP Address Source       : Static Address\n"
                    "IP Address              : 10.64.90.11\n"
                    "Subnet Mask             : 255.255.255.0\n"
                    "MAC Address             : a4:bb:6d:12:34:56\n"
                    "Default Gateway IP      : 10.64.90.1"
                )
            return f"ipmitool: executed ({' '.join(parts[1:]) or 'ok'})"
        if "dmidecode" in low:
            # Persona-aware DMI: AWS Nitro / Azure / GCE / VMware / HPE bare metal.
            # Generic labs used to always answer HPE even on EC2 guests.
            mfr = getattr(shell.state, "dmi_manufacturer", None) or "Dell Inc."
            prod = getattr(shell.state, "dmi_product", None) or "PowerEdge XE9680"
            platform = getattr(shell.state, "host_platform", "") or ""
            # Only claim HPE ProLiant when this Lab Server is actually bare metal /
            # datacenter — otherwise prefer the hosting persona already applied.
            if platform and platform not in ("baremetal", "datacenter", "linux"):
                mfr = getattr(shell.state, "dmi_manufacturer", mfr) or mfr
                prod = getattr(shell.state, "dmi_product", prod) or prod
            return f"Manufacturer: {mfr}\nProduct Name: {prod}"
        if "esxcli" in low:
            return "Host CPU: Intel Xeon Gold 6248R\nMemory: 256 GB"
        if low.startswith("maas"):
            _sync_maas_from_gui()
            machines = engine._maas_machines
            # `maas admin machines read` / `maas login` / commission / deploy
            if "login" in low:
                _apply_maas_gui_action("login", {"user": "admin"})
                return "Logged into MAAS at http://10.64.1.2:5240/MAAS/ (user: admin)"
            if "machines" in low and ("read" in low or "list" in low):
                rows = [
                    "hostname       status                 power  arch            zone     pool     ip",
                    "-------------  ---------------------  -----  --------------  -------  -------  ------------",
                ]
                for m in machines:
                    rows.append(
                        f"{m['name']:<14} {m['status']:<22} {m['power']:<6} "
                        f"{m['arch']:<15} {m['zone']:<8} {m['pool']:<8} {m['ip']}"
                    )
                return "\n".join(rows)
            if "commission" in low:
                target = None
                for tok in parts:
                    if tok.startswith("gpu-node") or tok.startswith("node-") or tok.startswith("storage-"):
                        target = tok
                        break
                for m in machines:
                    if target and m["name"] != target:
                        continue
                    if m["status"] in ("New", "Failed commissioning", "Failed", "Ready", "Broken"):
                        mid = m.get("id")
                        gui = _apply_maas_gui_action("maas_commission", {"machine_id": mid}) if mid else None
                        if gui and gui.get("ok"):
                            _sync_maas_from_gui()
                        else:
                            m["status"] = "Ready"
                            m["power"] = "on"
                            _mirror_maas(m)
                        name = m["name"]
                        from .shell import StreamedCommandResult
                        return StreamedCommandResult(
                            lines=[
                                f"Commissioning started for {name}…",
                                "BMC power on → PXE (undionly.kpxe)",
                                "DHCP ACK 10.64.12.x from region controller",
                                "TFTP: downloading kernel + initrd (ephemeral)",
                                "Running 00-maas-03-install-lldpd … ok",
                                "Running 20-maas-01-bmc … ok",
                                "Running 50-maas-01-commissioning … ok",
                                "Hardware inventory synced (CPU/RAM/NIC/GPU)",
                                f"Status → Ready (commissioning passed for {name}).",
                            ],
                            delay_s=0.45,
                        )
                return "No matching machine available to commission."
            if "deploy" in low:
                for m in machines:
                    if m["status"] in ("Ready", "Allocated"):
                        mid = m.get("id")
                        gui = _apply_maas_gui_action("maas_deploy", {"machine_id": mid}) if mid else None
                        if gui and gui.get("ok"):
                            _sync_maas_from_gui()
                            # For CLI UX, advance to Deployed for immediate feedback
                            # while GUI continues wall-clock Deploying when polled.
                            m["status"] = "Deployed"
                            m["ip"] = m["ip"] if m["ip"] not in ("-", "", None) else "10.64.12.40"
                        else:
                            m["status"] = "Deployed"
                            m["ip"] = m["ip"] if m["ip"] != "-" else "10.64.12.40"
                            _mirror_maas(m)
                        from .shell import StreamedCommandResult
                        return StreamedCommandResult(
                            lines=[
                                f"Deploying Ubuntu 22.04 LTS to {m['name']} "
                                f"(osystem=ubuntu, distro_series=jammy)…",
                                "PXE: DHCP discover → offer → request → ack",
                                "TFTP: bootx64.efi / grubx64.efi / vmlinuz / initrd",
                                "Curtin: partitioning + installing rootfs",
                                "cloud-init: datasource MAAS, applying netplan + users",
                                "Reboot → cloud-init final → sshd listening",
                                f"Deployed. IP {m['ip']}  Status → Deployed",
                            ],
                            delay_s=0.5,
                        )
                return "No Ready machine available to deploy (commission first)."
            if "release" in low:
                for m in machines:
                    if m["status"] == "Deployed":
                        mid = m.get("id")
                        gui = _apply_maas_gui_action("maas_release", {"machine_id": mid}) if mid else None
                        if not (gui and gui.get("ok")):
                            m["status"] = "Ready"
                            _mirror_maas(m)
                        else:
                            _sync_maas_from_gui()
                        return f"Released {m['name']} → Ready"
                return "No Deployed machine to release."
            if "machine" in low and "read" in low:
                target = None
                for tok in parts:
                    if tok.startswith("gpu-node") or tok.startswith("node-") or tok.startswith("storage-"):
                        target = tok
                        break
                for m in machines:
                    if target and m["name"] != target:
                        continue
                    return (
                        f"system_id: {m.get('id')}\n"
                        f"hostname: {m['name']}\n"
                        f"status_name: {m['status']}\n"
                        f"power_state: {m['power']}\n"
                        f"architecture: {m.get('arch', 'amd64/generic')}\n"
                        f"zone: {m.get('zone', 'default')}\n"
                        f"pool: {m.get('pool', 'default')}\n"
                        f"ip_addresses: {m.get('ip', '-')}\n"
                        f"tag_names: {','.join(m.get('tags') or []) or '-'}"
                    )
                return "Machine not found."
            if "tags" in low and ("read" in low or "list" in low):
                _sync_maas_from_gui()
                tags = []
                try:
                    from apps.vmware_sim import baremetal_engine as _bm
                    st = (_bm.get_state(str(_session_id())) or {}).get("state") or {}
                    tags = (st.get("maas") or {}).get("tags") or []
                except Exception:
                    pass
                if not tags:
                    return "No tags."
                rows = ["name            machines"]
                for t in tags:
                    rows.append(f"{t.get('name', ''):<15} {','.join(t.get('machines') or []) or '-'}")
                return "\n".join(rows)
            if "devices" in low and ("read" in low or "list" in low):
                _sync_maas_from_gui()
                devices = []
                try:
                    from apps.vmware_sim import baremetal_engine as _bm
                    st = (_bm.get_state(str(_session_id())) or {}).get("state") or {}
                    devices = (st.get("maas") or {}).get("devices") or st.get("devices") or []
                except Exception:
                    pass
                if not devices:
                    return "No devices."
                rows = ["hostname           ip              mac"]
                for d in devices:
                    rows.append(
                        f"{(d.get('hostname') or d.get('name') or '-'):<18} "
                        f"{(d.get('ip') or d.get('ip_reservation') or '-'):<15} "
                        f"{d.get('mac') or '-'}"
                    )
                return "\n".join(rows)
            if "power" in low:
                action = "on" if "on" in low else "off" if "off" in low else "status"
                for m in machines:
                    if action == "status":
                        return "\n".join(f"{x['name']}: power {x['power']}" for x in machines)
                    mid = m.get("id")
                    if mid:
                        _apply_maas_gui_action("maas_power", {"machine_id": mid, "power": action})
                    m["power"] = action
                _sync_maas_from_gui()
                return f"Power {action} requested for matching machines."
            if "boot-resources" in low or ("boot" in low and "resource" in low):
                _sync_maas_from_gui()
                resources = list(getattr(engine, "_maas_boot_resources", None) or ["ubuntu/jammy", "ubuntu/noble"])
                rows = ["id  name              architecture  type"]
                for i, name in enumerate(resources, start=1):
                    kind = "Uploaded" if str(name).startswith("custom/") else "Synced"
                    rows.append(f"{i:<3} {str(name):<17} amd64/generic  {kind}")
                return "\n".join(rows)
            return (
                "usage: maas <profile> machines read|commission|deploy|release\n"
                "       maas <profile> machine read <hostname>\n"
                "       maas <profile> boot-resources read\n"
                "       maas <profile> tags read\n"
                "       maas <profile> devices read\n"
                "       maas login <profile> <url> <api-key>"
            )
        if low.startswith("lxc") or low.startswith("lxd"):
            _sync_lxd_from_gui()
            inst = engine._lxd_instances
            profiles = getattr(engine, "_lxd_profiles", None) or {}
            parts_raw = line.strip().split()
            # Drop leading lxc/lxd
            args = parts_raw[1:] if len(parts_raw) > 1 else []
            sub = (args[0].lower() if args else "")

            def _inst_name_from_args(offset: int = 1) -> str:
                if len(args) > offset:
                    return args[offset]
                for tok in args[1:]:
                    if tok in inst:
                        return tok
                return ""

            def _type_short(t: str) -> str:
                t = (t or "container").lower()
                if t in ("virtual-machine", "vm", "virtual_machine"):
                    return "VIRTUAL-MACHINE"
                return "CONTAINER"

            # list — NAME STATE IPV4 IPV6 TYPE SNAPSHOTS
            if sub == "list" or (sub == "" and "list" in low):
                rows = [
                    "+---------------+---------+----------------------+----------------------+-----------------+-----------+",
                    "| NAME          | STATE   | IPV4                 | IPV6                 | TYPE            | SNAPSHOTS |",
                    "+---------------+---------+----------------------+----------------------+-----------------+-----------+",
                ]
                for name, meta in inst.items():
                    snap_n = meta.get("snapshots")
                    if isinstance(snap_n, list):
                        snap_n = len(snap_n)
                    snap_n = int(snap_n or 0)
                    rows.append(
                        f"| {name:<13} | {meta.get('state', 'STOPPED'):<7} "
                        f"| {(meta.get('ipv4') or '-'):<20} "
                        f"| {(meta.get('ipv6') or '-'):<20} "
                        f"| {_type_short(meta.get('type')):<15} "
                        f"| {snap_n:<9} |"
                    )
                rows.append("+---------------+---------+----------------------+----------------------+-----------------+-----------+")
                return "\n".join(rows)

            if sub in ("start", "stop", "restart", "delete", "rm", "info"):
                name = _inst_name_from_args(1)
                if sub == "start":
                    target = name
                    if not target or target not in inst:
                        target = next((n for n, m in inst.items() if m.get("state") != "RUNNING"), "")
                    if not target:
                        return "All instances already running"
                    gui = _apply_lxd_gui_action("lxd_start", {"name": target})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    else:
                        meta = inst.setdefault(target, {"state": "STOPPED", "type": "container", "ipv4": ""})
                        meta["state"] = "RUNNING"
                        meta["ipv4"] = meta.get("ipv4") or "10.150.1.99"
                    return f"Instance {target} started"
                if sub == "stop":
                    if not name or name not in inst:
                        return "Error: specify instance name"
                    gui = _apply_lxd_gui_action("lxd_stop", {"name": name})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    else:
                        inst[name]["state"] = "STOPPED"
                        inst[name]["ipv4"] = ""
                    return f"Instance {name} stopped"
                if sub == "restart":
                    if not name or name not in inst:
                        return "Error: specify instance name"
                    gui = _apply_lxd_gui_action("lxd_restart", {"name": name})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    else:
                        inst[name]["state"] = "RUNNING"
                        inst[name]["ipv4"] = inst[name].get("ipv4") or "10.150.1.99"
                    return f"Instance {name} restarted"
                if sub in ("delete", "rm"):
                    if not name:
                        return "Error: specify instance name"
                    gui = _apply_lxd_gui_action("lxd_delete", {"name": name})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    else:
                        inst.pop(name, None)
                    return f"Instance {name} deleted"
                if sub == "info":
                    if not name or name not in inst:
                        return "Error: Instance not found"
                    meta = inst[name]
                    cfg = meta.get("config") or {}
                    cfg_lines = "\n".join(f"  {k}: {v}" for k, v in cfg.items()) or "  {}"
                    dev = meta.get("devices") or {}
                    dev_lines = "\n".join(f"  {k}: {v}" for k, v in dev.items()) or "  {}"
                    return (
                        f"Name: {name}\n"
                        f"Status: {meta.get('state')}\n"
                        f"Type: {meta.get('type')}\n"
                        f"Architecture: x86_64\n"
                        f"PID: 12345\n"
                        f"Created: 2026/01/15 10:00 UTC\n"
                        f"Profiles: {', '.join(meta.get('profiles') or ['default'])}\n"
                        f"Project: {meta.get('project') or 'default'}\n"
                        f"Location: {meta.get('location') or 'none'}\n"
                        f"Ips:\n"
                        f"  eth0:\tinet\t{meta.get('ipv4') or '(none)'}\n"
                        f"Config:\n{cfg_lines}\n"
                        f"Devices:\n{dev_lines}"
                    )

            if sub in ("launch", "init"):
                # lxc launch ubuntu:22.04 name [--vm]
                image = "ubuntu:22.04"
                name = "lab-instance"
                is_vm = "--vm" in args or any(a == "vm" for a in args)
                nonflags = [a for a in args[1:] if not a.startswith("-")]
                if len(nonflags) >= 1:
                    image = nonflags[0]
                if len(nonflags) >= 2:
                    name = nonflags[1]
                elif len(nonflags) == 1 and ":" not in nonflags[0]:
                    name = nonflags[0]
                itype = "virtual-machine" if is_vm else "container"
                action = "lxd_launch" if sub == "launch" else "lxd_create"
                gui = _apply_lxd_gui_action(action, {
                    "name": name, "image": image, "type": itype,
                    "start": sub == "launch",
                })
                if gui and gui.get("ok"):
                    _sync_lxd_from_gui()
                else:
                    inst[name] = {
                        "state": "RUNNING" if sub == "launch" else "STOPPED",
                        "type": itype,
                        "ipv4": "10.150.1.50" if sub == "launch" else "",
                        "ipv6": "", "snapshots": 0, "profiles": ["default"],
                        "devices": {}, "config": {}, "project": "default",
                        "location": "none", "nvidia_smi_ok": False, "image": image,
                    }
                if sub == "launch":
                    return f"Creating {name}\nStarting {name}\n{name} is ready"
                return f"Creating {name}\n{name} created (stopped)"

            if sub == "config":
                # config set|get|show|device
                cfg_op = (args[1].lower() if len(args) > 1 else "")
                if cfg_op == "device" and len(args) > 2 and args[2].lower() == "add":
                    # lxc config device add <instance> <device> <type> [key=val...]
                    iname = args[3] if len(args) > 3 else ""
                    dname = args[4] if len(args) > 4 else "dev0"
                    dtype = args[5] if len(args) > 5 else "disk"
                    kv = {}
                    for tok in args[6:]:
                        if "=" in tok:
                            k, v = tok.split("=", 1)
                            kv[k] = v
                    payload = {"name": iname, "device": dname, "type": dtype, **kv}
                    gui = _apply_lxd_gui_action("lxd_config_device_add", payload)
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    elif iname in inst:
                        devices = inst[iname].setdefault("devices", {})
                        devices[dname] = {"type": dtype, **kv}
                        if dtype == "gpu":
                            inst[iname]["nvidia_smi_ok"] = True
                            devices["gpu"] = devices[dname]
                    return f"Device {dname} added to {iname}"
                if cfg_op == "set" and len(args) >= 4:
                    iname, key, value = args[2], args[3], args[4] if len(args) > 4 else ""
                    gui = _apply_lxd_gui_action("lxd_config_set", {"name": iname, "key": key, "value": value})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    elif iname in inst:
                        inst[iname].setdefault("config", {})[key] = value
                    return f"Config {key} set on {iname}"
                if cfg_op == "get" and len(args) >= 4:
                    iname, key = args[2], args[3]
                    meta = inst.get(iname) or {}
                    return str((meta.get("config") or {}).get(key, ""))
                if cfg_op == "show" and len(args) >= 3:
                    iname = args[2]
                    meta = inst.get(iname) or {}
                    cfg = meta.get("config") or {}
                    lines = ["architecture: x86_64", "config:"]
                    for k, v in cfg.items():
                        lines.append(f"  {k}: \"{v}\"")
                    if not cfg:
                        lines.append("  {}")
                    lines.append(f"devices:")
                    for dk, dv in (meta.get("devices") or {}).items():
                        lines.append(f"  {dk}:")
                        if isinstance(dv, dict):
                            for kk, vv in dv.items():
                                lines.append(f"    {kk}: {vv}")
                        else:
                            lines.append(f"    {dv}")
                    lines.append(f"ephemeral: false")
                    lines.append(f"profiles: {meta.get('profiles') or ['default']}")
                    lines.append(f"stateful: false")
                    lines.append(f"description: \"\"")
                    return "\n".join(lines)
                return "usage: lxc config set|get|show <instance> [key] [value]\n       lxc config device add <instance> <device> <type> [key=value...]"

            if sub == "profile":
                pop = (args[1].lower() if len(args) > 1 else "list")
                if pop == "list" or (pop == "" and "list" in low):
                    rows = ["+------------------+---------+", "| NAME             | USED BY |", "+------------------+---------+"]
                    for pname in profiles:
                        rows.append(f"| {pname:<16} | 0       |")
                    rows.append("+------------------+---------+")
                    return "\n".join(rows)
                if pop == "create" and len(args) > 2:
                    pname = args[2]
                    gui = _apply_lxd_gui_action("lxd_profile_create", {"name": pname})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    else:
                        profiles[pname] = {"config": {}, "devices": {}}
                        engine._lxd_profiles = profiles
                    return f"Profile {pname} created"
                if pop == "show" and len(args) > 2:
                    pname = args[2]
                    p = profiles.get(pname)
                    if not p and pname == "gpu-passthrough":
                        return (
                            "name: gpu-passthrough\n"
                            "config:\n"
                            "  nvidia.runtime: \"true\"\n"
                            "devices:\n"
                            "  gpu0:\n"
                            "    type: gpu\n"
                            "    gputype: physical\n"
                            "    pci: \"0000:19:00.0\""
                        )
                    if not p:
                        return f"Error: Profile {pname} not found"
                    lines = [f"name: {pname}", "config:"]
                    for k, v in (p.get("config") or {}).items():
                        lines.append(f"  {k}: \"{v}\"")
                    if not p.get("config"):
                        lines.append("  {}")
                    lines.append("devices:")
                    for dk, dv in (p.get("devices") or {}).items():
                        lines.append(f"  {dk}:")
                        if isinstance(dv, dict):
                            for kk, vv in dv.items():
                                lines.append(f"    {kk}: {vv}")
                    if not p.get("devices"):
                        lines.append("  {}")
                    return "\n".join(lines)
                if pop in ("assign", "add", "set") and len(args) > 3:
                    # lxc profile assign <instance> <profiles>
                    iname = args[2]
                    plist = args[3].split(",") if len(args) > 3 else ["default"]
                    gui = _apply_lxd_gui_action("lxd_profile_assign", {"name": iname, "profiles": plist})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    elif iname in inst:
                        inst[iname]["profiles"] = plist
                    return f"Profiles {','.join(plist)} applied to {iname}"
                if "show" in low and "gpu" in low:
                    return (
                        "name: gpu-passthrough\n"
                        "config:\n"
                        "  nvidia.runtime: \"true\"\n"
                        "devices:\n"
                        "  gpu0:\n"
                        "    type: gpu\n"
                        "    gputype: physical\n"
                        "    pci: \"0000:19:00.0\""
                    )
                return "usage: lxc profile list|create|show|assign"

            if sub == "image" or (sub == "images"):
                images = getattr(engine, "_lxd_images", None) or [
                    {"alias": "ubuntu:22.04", "fingerprint": "a1b2c3d4e5f6", "public": True, "description": "ubuntu 22.04 LTS amd64", "type": "container"},
                    {"alias": "ubuntu:24.04", "fingerprint": "f6e5d4c3b2a1", "public": True, "description": "ubuntu 24.04 LTS amd64", "type": "container"},
                ]
                rows = [
                    "+-------+--------------+--------+-------------------------------------------+--------------+",
                    "| ALIAS | FINGERPRINT  | PUBLIC | DESCRIPTION                               | TYPE         |",
                    "+-------+--------------+--------+-------------------------------------------+--------------+",
                ]
                for img in images:
                    alias = (img.get("alias") if isinstance(img, dict) else str(img)) or "-"
                    fp = (img.get("fingerprint") if isinstance(img, dict) else "-") or "-"
                    pub = "yes" if (isinstance(img, dict) and img.get("public")) else "no"
                    desc = (img.get("description") if isinstance(img, dict) else "") or ""
                    itype = (img.get("type") if isinstance(img, dict) else "container") or "container"
                    rows.append(f"| {alias:<5} | {fp[:12]:<12} | {pub:<6} | {desc[:41]:<41} | {itype:<12} |")
                rows.append("+-------+--------------+--------+-------------------------------------------+--------------+")
                return "\n".join(rows)

            if sub == "snapshot":
                # lxc snapshot <instance> [snapname]  OR  lxc snapshot restore <instance> <snap>
                if len(args) > 1 and args[1].lower() == "restore":
                    iname = args[2] if len(args) > 2 else ""
                    snap = args[3] if len(args) > 3 else ""
                    gui = _apply_lxd_gui_action("lxd_restore", {"name": iname, "snapshot": snap})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    elif iname in inst:
                        inst[iname]["state"] = "STOPPED"
                        inst[iname]["ipv4"] = ""
                    return f"Instance {iname} restored from snapshot {snap}"
                iname = args[1] if len(args) > 1 else ""
                snap = args[2] if len(args) > 2 else f"snap{len(inst.get(iname, {}).get('snapshot_list') or [])}"
                gui = _apply_lxd_gui_action("lxd_snapshot", {"name": iname, "snapshot": snap})
                if gui and gui.get("ok"):
                    _sync_lxd_from_gui()
                elif iname in inst:
                    inst[iname]["snapshots"] = int(inst[iname].get("snapshots") or 0) + 1
                    inst[iname].setdefault("snapshot_list", []).append({"name": snap})
                return f"Snapshot {snap} created for {iname}"

            if sub == "restore":
                iname = args[1] if len(args) > 1 else ""
                snap = args[2] if len(args) > 2 else ""
                gui = _apply_lxd_gui_action("lxd_restore", {"name": iname, "snapshot": snap})
                if gui and gui.get("ok"):
                    _sync_lxd_from_gui()
                elif iname in inst:
                    inst[iname]["state"] = "STOPPED"
                    inst[iname]["ipv4"] = ""
                return f"Instance {iname} restored from snapshot {snap}"

            if sub == "publish":
                iname = args[1] if len(args) > 1 else ""
                alias = "image"
                for i, a in enumerate(args):
                    if a == "--alias" and i + 1 < len(args):
                        alias = args[i + 1]
                gui = _apply_lxd_gui_action("lxd_publish", {"name": iname, "alias": alias})
                if gui and gui.get("ok"):
                    _sync_lxd_from_gui()
                return f"Instance {iname} published as {alias}"

            if sub == "storage" or ("storage" in low and "list" in low):
                pools = getattr(engine, "_lxd_storage", None) or [
                    {"name": "default", "driver": "dir", "source": "/var/snap/lxd/common/lxd/storage-pools/default"},
                    {"name": "gpu-pool", "driver": "zfs", "source": "tank/lxd"},
                ]
                _apply_lxd_gui_action("lxd_storage_list", {})
                rows = [
                    "+----------+--------+-----------------------------------------------+",
                    "| NAME     | DRIVER | SOURCE                                        |",
                    "+----------+--------+-----------------------------------------------+",
                ]
                for p in pools:
                    rows.append(
                        f"| {(p.get('name') or ''):<8} | {(p.get('driver') or ''):<6} "
                        f"| {(p.get('source') or '')[:45]:<45} |"
                    )
                rows.append("+----------+--------+-----------------------------------------------+")
                return "\n".join(rows)

            if sub == "network" or ("network" in low and "list" in low):
                nets = getattr(engine, "_lxd_networks", None) or [
                    {"name": "lxdbr0", "type": "bridge", "managed": True, "ipv4": "10.10.2.1/24", "ipv6": "fd42::1/64"},
                ]
                _apply_lxd_gui_action("lxd_network_list", {})
                rows = [
                    "+-----------+----------+---------+----------------+-----------------+",
                    "| NAME      | TYPE     | MANAGED | IPV4            | IPV6            |",
                    "+-----------+----------+---------+----------------+-----------------+",
                ]
                for n in nets:
                    rows.append(
                        f"| {(n.get('name') or ''):<9} | {(n.get('type') or ''):<8} "
                        f"| {'YES' if n.get('managed') else 'NO':<7} "
                        f"| {(n.get('ipv4') or '-'):<14} | {(n.get('ipv6') or '-'):<15} |"
                    )
                rows.append("+-----------+----------+---------+----------------+-----------------+")
                return "\n".join(rows)

            if sub == "project" or ("project" in low and "list" in low):
                projects = getattr(engine, "_lxd_projects", None) or [
                    {"name": "default"}, {"name": "inference"},
                ]
                if len(args) > 1 and args[1].lower() == "create" and len(args) > 2:
                    pname = args[2]
                    gui = _apply_lxd_gui_action("lxd_project_create", {"name": pname})
                    if gui and gui.get("ok"):
                        _sync_lxd_from_gui()
                    return f"Project {pname} created"
                rows = ["+-------------------+", "| NAME              |", "+-------------------+"]
                for p in projects:
                    rows.append(f"| {(p.get('name') if isinstance(p, dict) else p):<17} |")
                rows.append("+-------------------+")
                return "\n".join(rows)

            if sub == "cluster" or ("cluster" in low) or ("list" in low and "member" in low):
                members = getattr(engine, "_lxd_cluster", None) or [
                    {"name": "node1", "url": "https://10.64.12.11:8443", "roles": ["database"], "architecture": "x86_64", "failure_domain": "default"},
                    {"name": "node2", "url": "https://10.64.12.12:8443", "roles": ["database"], "architecture": "x86_64", "failure_domain": "default"},
                    {"name": "node3", "url": "https://10.64.12.13:8443", "roles": ["database-standby"], "architecture": "x86_64", "failure_domain": "default"},
                ]
                _apply_lxd_gui_action("lxd_cluster_list", {})
                rows = [
                    "+-------+--------------------------+------------------+--------------+-------------------+",
                    "| NAME  | URL                      | ROLES            | ARCHITECTURE | FAILURE DOMAIN    |",
                    "+-------+--------------------------+------------------+--------------+-------------------+",
                ]
                for m in members:
                    roles = m.get("roles") or []
                    role_s = ",".join(roles) if isinstance(roles, list) else str(roles)
                    rows.append(
                        f"| {(m.get('name') or ''):<5} | {(m.get('url') or ''):<24} "
                        f"| {role_s:<16} | {(m.get('architecture') or ''):<12} "
                        f"| {(m.get('failure_domain') or 'default'):<17} |"
                    )
                rows.append("+-------+--------------------------+------------------+--------------+-------------------+")
                return "\n".join(rows)

            if sub in ("exec", "shell"):
                # lxc exec <name> -- <cmd>   /  lxc shell <name>
                iname = args[1] if len(args) > 1 else next(iter(inst), "infer-svc")
                cmd = "bash"
                if "--" in args:
                    idx = args.index("--")
                    cmd = " ".join(args[idx + 1:]) or "bash"
                elif sub == "exec" and len(args) > 2:
                    cmd = " ".join(a for a in args[2:] if a != "--") or "bash"
                gui = _apply_lxd_gui_action("lxd_exec_echo", {"name": iname, "command": cmd})
                if gui and gui.get("ok") and gui.get("output"):
                    out = gui["output"]
                    prompt = gui.get("prompt") or f"root@{iname}:~#"
                    if cmd.strip() in ("bash", "sh", "/bin/bash") or sub == "shell":
                        return (
                            f"{out}\n"
                            f"# LXD session marker: root@{iname}\n"
                            f"{prompt} "
                        )
                    return out
                if cmd.strip() in ("bash", "sh", "/bin/bash") or sub == "shell":
                    return (
                        f"root@{iname}:~#\n"
                        f"# LXD session marker: root@{iname}\n"
                        f"root@{iname}:~# "
                    )
                if "nvidia-smi" in cmd.lower():
                    meta = inst.get(iname) or {}
                    if meta.get("nvidia_smi_ok"):
                        return (
                            "NVIDIA-SMI 535.104.05   Driver Version: 535.104.05   CUDA Version: 12.2\n"
                            "GPU 0: NVIDIA H100 80GB HBM3 (UUID: GPU-lab-h100-01)"
                        )
                    return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
                if cmd.lower().startswith("echo "):
                    return cmd[5:]
                return f"{cmd}\nroot@{iname}:~#"

            return (
                "usage: lxc list|launch|init|start|stop|restart|delete|info\n"
                "       lxc config set|get|show|device add\n"
                "       lxc profile list|create|show|assign\n"
                "       lxc image list|snapshot|restore|publish\n"
                "       lxc storage list|network list|project list|cluster list\n"
                "       lxc exec <instance> -- <cmd> | lxc shell <instance>"
            )
        if low.startswith("virsh"):
            if "list" in low:
                return " Id   Name         State\n------------------------\n 1    vm-k8s-node  running"
            return "virsh: OK"
        if low.startswith("packer"):
            if "version" in low or "-v" in parts:
                return "Packer v1.11.2"
            if "fmt" in low:
                return ""
            if "validate" in low:
                return "The configuration is valid."
            if "init" in low:
                return (
                    "Installed plugin github.com/hashicorp/amazon v1.3.2\n"
                    "Installed plugin github.com/hashicorp/qemu v1.1.0"
                )
            if "build" in low:
                sku = "h100"
                for key in ("b300", "h200", "h100", "a100", "mi300"):
                    if key in low or key in slug:
                        sku = key
                        break
                # CVE gate fails when the scenario/slug/template name asks for it
                # (vuln / cve / fail / gate-fail) — publish must not claim success.
                fail_cve = any(
                    k in low or k in slug
                    for k in ("cve-fail", "vuln", "gate-fail", "trivy-fail")
                ) or ("cve" in slug and "fail" in slug)
                from .shell import StreamedCommandResult
                lines = [
                    f"qemu.gpu-{sku}: output will be in this color.",
                    f"qemu.gpu-{sku}: Retrieving Ubuntu jammy cloud image…",
                    f"qemu.gpu-{sku}: Starting HTTP server on port 8701",
                    f"qemu.gpu-{sku}: Creating local QEMU disk image…",
                    f"qemu.gpu-{sku}: Booting VM for provisioning (NVIDIA driver + DCGM)…",
                    f"qemu.gpu-{sku}: Provisioning with shell script scripts/install-gpu-{sku}.sh",
                ]
                if fail_cve:
                    lines += [
                        f"qemu.gpu-{sku}: Running CVE scan gate (trivy image)… FAIL",
                        f"qemu.gpu-{sku}: HIGH CVE-2024-XXXX in libc6 — see output-gpu-{sku}/cve-report.json",
                        "==> Builds finished but no artifacts were saved.",
                        f"--> qemu.gpu-{sku}: CVE gate blocked publish to MAAS boot-resources",
                    ]
                    engine._packer_cve_failed = True
                else:
                    lines += [
                        f"qemu.gpu-{sku}: Running CVE scan gate (trivy image)… PASS",
                        f"qemu.gpu-{sku}: Writing gate report output-gpu-{sku}/cve-report.json",
                        f"qemu.gpu-{sku}: Publishing artifact to maas boot-resource custom/{sku}-jammy",
                        "==> Wait completed after 4 minutes 12 seconds",
                        "==> Builds finished. The artifacts of successful builds are:",
                        f"--> qemu.gpu-{sku}: VM files in directory: output-gpu-{sku}/",
                    ]
                    engine._packer_cve_failed = False
                    # Mirror into MAAS boot-resources list when present.
                    try:
                        resources = getattr(engine, "_maas_boot_resources", None)
                        if isinstance(resources, list):
                            name = f"custom/{sku}-jammy"
                            if name not in resources:
                                resources.append(name)
                    except Exception:
                        pass
                return StreamedCommandResult(lines=lines, delay_s=0.45)
            return (
                "Usage: packer [--version] [--help] <command> [<args>]\n\n"
                "Common commands:\n"
                "    build           build image(s) from template\n"
                "    init            install missing plugins\n"
                "    validate        check template validity\n"
                "    fmt             reformat HCL2 config"
            )
        if low.startswith("virt-inspect") or low.startswith("virt-filesystems"):
            return (
                "Root device: /dev/sda1\n"
                "  Operating system: Ubuntu 22.04 LTS (jammy)\n"
                "  Package format: deb\n"
                "  Kernel: 5.15.0-gpu\n"
                "  Applications:\n"
                "    nvidia-driver-550\n"
                "    datacenter-gpu-manager\n"
                "    cuda-toolkit-12-4"
            )
        if low.startswith("virt-customize") or low.startswith("virt-builder"):
            if "--run-command" in low or "nvidia-smi" in low or "install" in low:
                return "[ OK ]"
            return (
                "[   0.0] Examining the guest …\n"
                "[   1.2] Setting a random seed\n"
                "[   2.0] Finishing off"
            )
        if low.startswith("guestfish") or low.startswith("guestmount"):
            if "ls" in low or "nvidia" in low:
                return (
                    "usr\n"
                    "usr/bin\n"
                    "usr/bin/nvidia-smi\n"
                    "usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1"
                )
            return (
                "Welcome to guestfish, the guest filesystem shell for editing virtual machine filesystems.\n"
                "Type: 'help' for help with commands\n"
                "      'quit' to quit the shell\n"
                "\n"
                "><fs> "
            )
        if low.startswith("vyos") or low.startswith("vyatta"):
            net = _ensure_vyos_networking(engine)
            rest = line.strip().split(None, 1)
            sub = rest[1].strip() if len(rest) > 1 else ""
            sub_low = sub.lower()
            if not sub:
                _persist_vyos_networking(engine, net)
                return (
                    "VyOS OK — try: configure / set … / commit / rollback / "
                    "show interfaces / show dhcp server leases / show configuration / show ip bgp summary"
                )
            # Delegate "vyos show …" / "vyos configure" to the same dispatcher.
            out = _vyos_dispatch(net, sub, engine)
            _persist_vyos_networking(engine, net)
            if out.startswith("Invalid command"):
                if "bgp" in sub_low:
                    return net.bgp_summary()
                return (
                    "VyOS OK — try: configure / set … / commit / rollback / "
                    "show interfaces / show dhcp server leases / show configuration / show ip bgp summary"
                )
            return out
        return f"{line}: OK"
    shell.register_handler(handler)


def _register_database(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    slug = engine.scenario_slug.lower()
    if "postgres" in slug and "postgresql" not in shell.state.services:
        shell.state.services["postgresql"] = SimService(
            "postgresql", active="failed", enabled="enabled", description="PostgreSQL",
        )
    elif "mysqld" not in shell.state.services:
        shell.state.services.setdefault(
            "mysqld",
            SimService("mysqld", active="failed", enabled="enabled", description="MySQL"),
        )

    def handler(parts, line):
        low = line.strip().lower()
        if low.startswith("mysqladmin") and "ping" in low:
            st = shell.state
            if "-h" in parts:
                st = engine.shell.state
            svc = st.services.get("mysqld")
            return "mysqld is alive" if svc and svc.active == "active" else "mysqladmin: connect to server failed"
        return None
    shell.register_handler(handler)


def _register_docker(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    if not engine.docker:
        engine.docker = DockerState(engine.scenario_slug)
    # Flagship compose labs: the daemon is up but the stack has not been brought
    # up yet, so no containers are running until the learner runs
    # `docker compose up -d` (fail-closed `docker ps` until then).
    try:
        from .flagship_presets import FLAGSHIP_DOCKER_SLUGS
    except Exception:  # pragma: no cover
        FLAGSHIP_DOCKER_SLUGS = set()
    # Task-style docker sims whose objective is to get a container running
    # (`docker ps | grep Up`) must start with NO running container, otherwise the
    # check passes before any work (fail-open).
    _slug = (engine.scenario_slug or "").lower()
    needs_container_up = any(
        k in _slug for k in ("compose-down", "image-pull", "network-connect", "container-exited", "exited")
    )
    if engine.scenario_slug in FLAGSHIP_DOCKER_SLUGS or needs_container_up:
        for c in getattr(engine.docker, "containers", []):
            c["state"] = "exited"
    # Keep the validator's flag aligned with the seeded daemon state — a stopped
    # daemon means nothing is reachable as "Up".
    engine._container_running = engine.docker.daemon_running and engine.docker.any_running()

    def handler(parts, line):
        if not parts:
            return None
        # `docker` and `docker-compose` both route here.
        if parts[0] not in ("docker", "docker-compose"):
            return None
        # Reflect the docker systemd unit into the daemon's reachability.
        svc = shell.state.services.get("docker")
        if svc is not None:
            engine.docker.daemon_running = svc.active == "active"
        return _handle_docker(engine, parts, line, shell)

    shell.register_handler(handler)


def _docker_flag_value(parts: list[str], *names: str) -> str:
    for i, tok in enumerate(parts):
        for n in names:
            if tok == n and i + 1 < len(parts):
                return parts[i + 1]
            if tok.startswith(n + "="):
                return tok.split("=", 1)[1]
    return ""


def _handle_docker(engine: "UnifiedSimulationEngine", parts: list[str], line: str, shell: RHELShell) -> str:
    d = engine.docker

    def sync_flag() -> None:
        engine._container_running = d.daemon_running and d.any_running()

    # Normalize `docker-compose <sub>` and `docker compose <sub>` to one path.
    if parts[0] == "docker-compose":
        sub, args = (parts[1] if len(parts) > 1 else ""), parts[2:]
    else:
        sub, args = (parts[1] if len(parts) > 1 else ""), parts[2:]
        if sub == "compose":
            sub, args = (parts[2] if len(parts) > 2 else ""), parts[3:]
        else:
            sub = sub  # plain docker verb handled below

    if parts[0] == "docker-compose" or (len(parts) > 1 and parts[1] == "compose"):
        if sub in ("up", "start", "restart"):
            out = d.compose_up(); sync_flag(); return out
        if sub in ("down", "stop"):
            out = d.compose_down(); sync_flag(); return out
        if sub in ("ps", "ls"):
            return d.compose_ps()
        if sub == "build":
            return d.build()
        if not sub:
            return "Usage:  docker compose [OPTIONS] COMMAND"
        return ""

    if not sub:
        return ("Usage:  docker [OPTIONS] COMMAND\n\n"
                "A self-sufficient runtime for containers")

    # Daemon down?
    if not d.daemon_running and sub not in ("version", "--version", "info"):
        return ("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. "
                "Is the docker daemon running?")

    if sub in ("version", "--version"):
        return "Docker version 24.0.7, build afdd53b"
    if sub == "info":
        running = sum(1 for c in d.containers if c["state"] == "running")
        return (f"Server Version: 24.0.7\n Containers: {len(d.containers)}\n  Running: {running}\n"
                f" Images: {len(d.images)}\n Storage Driver: overlay2")

    # ps
    if sub == "ps":
        return d.ps(show_all=("-a" in parts or "--all" in parts))
    if sub == "images" or (sub == "image" and "ls" in parts):
        return d.images_list()

    # run
    if sub == "run":
        detach = "-d" in parts or "--detach" in parts or "-dit" in parts or "-itd" in parts
        name = _docker_flag_value(parts, "--name")
        ports = _docker_flag_value(parts, "-p", "--publish")
        if ports and "->" not in ports and ":" in ports:
            host, cont = ports.split(":", 1)
            ports = f"0.0.0.0:{host}->{cont}/tcp"
        # image is the first positional after the flags; command is everything after it
        image = ""
        cmd = ""
        skip_next = False
        idx = 2
        positional_flags = {"--name", "-p", "--publish", "-e", "--env", "-v", "--volume",
                            "--network", "--net", "--restart", "-w", "--workdir"}
        while idx < len(parts):
            tok = parts[idx]
            if skip_next:
                skip_next = False
                idx += 1
                continue
            if tok in positional_flags:
                skip_next = True
                idx += 1
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            image = tok
            cmd = " ".join(parts[idx + 1:])
            break
        if not image:
            return "docker: 'docker run' requires at least 1 argument."
        out = d.run(image, name=name, detach=detach, ports=ports, command=cmd)
        sync_flag()
        return out

    # lifecycle verbs operating on one or more containers
    if sub in ("start", "stop", "restart", "rm", "kill", "pause", "unpause"):
        targets = [a for a in args if not a.startswith("-")]
        force = "-f" in args or "--force" in args
        results = []
        for t in targets:
            if sub == "start":
                results.append(d.start(t))
            elif sub in ("stop", "kill", "pause"):
                results.append(d.stop(t))
            elif sub in ("restart", "unpause"):
                results.append(d.restart(t))
            elif sub == "rm":
                results.append(d.rm(t, force=force))
        sync_flag()
        if "systemctl start docker" in line:
            svc = shell.state.services.get("docker")
            if svc:
                svc.active = "active"
        return "\n".join(results) if results else f"\"docker {sub}\" requires at least 1 argument."

    if sub == "rmi":
        targets = [a for a in args if not a.startswith("-")]
        force = "-f" in args or "--force" in args
        return "\n".join(d.rmi(t, force=force) for t in targets) if targets else \
            "\"docker rmi\" requires at least 1 argument."

    if sub == "pull":
        image = next((a for a in args if not a.startswith("-")), "")
        return d.pull(image) if image else "\"docker pull\" requires at least 1 argument."

    if sub == "build":
        tag = _docker_flag_value(parts, "-t", "--tag")
        # A custom Dockerfile path may be given with -f; honor its presence.
        dockerfile = _docker_flag_value(parts, "-f", "--file")
        present = True
        if dockerfile:
            present = shell.state.read_file(dockerfile) is not None
        return d.build(tag=tag, dockerfile_present=present)

    if sub == "logs":
        ref = next((a for a in reversed(args) if not a.startswith("-")), "")
        return d.logs(ref)

    if sub == "exec":
        ref = ""
        cmd = ""
        idx = 2
        while idx < len(parts):
            tok = parts[idx]
            if tok.startswith("-"):
                idx += 1
                continue
            ref = tok
            cmd = " ".join(parts[idx + 1:])
            break
        return d.exec(ref, cmd)

    if sub == "inspect":
        ref = next((a for a in args if not a.startswith("-")), "")
        return d.inspect(ref)

    if sub in ("stats",):
        return d.stats()

    if sub == "top":
        ref = next((a for a in args if not a.startswith("-")), "")
        c = d.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        return "UID    PID    PPID   C   CMD\nroot   1      0      0   " + c.get("command", "/app")

    # network
    if sub == "network":
        nsub = args[0] if args else ""
        if nsub == "ls":
            return d.network_ls()
        if nsub == "create":
            name = next((a for a in args[1:] if not a.startswith("-")), "")
            return d.network_create(name)
        if nsub in ("rm", "remove"):
            name = next((a for a in args[1:] if not a.startswith("-")), "")
            return d.network_rm(name)
        if nsub == "connect":
            rest = [a for a in args[1:] if not a.startswith("-")]
            if len(rest) >= 2:
                return d.network_connect(rest[0], rest[1])
            return ""
        if nsub == "inspect":
            name = next((a for a in args[1:] if not a.startswith("-")), "")
            return f"[\n  {{\n    \"Name\": \"{name}\",\n    \"Driver\": \"bridge\"\n  }}\n]"
        return d.network_ls()

    # volume
    if sub == "volume":
        vsub = args[0] if args else ""
        if vsub == "ls":
            return d.volume_ls()
        if vsub == "create":
            name = next((a for a in args[1:] if not a.startswith("-")), "")
            return d.volume_create(name)
        if vsub in ("rm", "remove"):
            name = next((a for a in args[1:] if not a.startswith("-")), "")
            return d.volume_rm(name)
        if vsub == "inspect":
            name = next((a for a in args[1:] if not a.startswith("-")), "")
            return f"[\n  {{\n    \"Name\": \"{name}\",\n    \"Driver\": \"local\"\n  }}\n]"
        return d.volume_ls()

    if sub == "tag":
        return ""
    if sub == "system":
        if "prune" in args:
            removed = [c for c in d.containers if c["state"] != "running"]
            d.containers = [c for c in d.containers if c["state"] == "running"]
            return f"Deleted Containers:\n" + "\n".join(c["id"] for c in removed) + \
                   "\nTotal reclaimed space: 1.2GB"
        if "df" in args:
            return ("TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE\n"
                    f"Images          {len(d.images)}         2         1.2GB     400MB\n"
                    f"Containers      {len(d.containers)}         1         350MB     0B")
        return ""

    return f"docker: '{sub}' is not a docker command.\nSee 'docker --help'"


def _register_devops(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    if not engine.devops:
        engine.devops = DevOpsState(engine.scenario_slug)

    def handler(parts, line):
        low = line.strip().lower()
        d = engine.devops
        if low.startswith("gitlab-runner") or ("pipeline" in low and "status" in low):
            return d.gitlab_pipeline()
        if low.startswith("helm history"):
            return d.helm_history()
        if low.startswith("helm rollback"):
            parts_list = line.split()
            rev = int(parts_list[-1]) if parts_list[-1].isdigit() else 3
            return d.helm_rollback("webapp", rev)
        if "export kubeconfig" in low or "kubectl config" in low:
            d.kubeconfig_valid = True
            d.pipeline_status = "success"
            return ""
        if "glab ci" in low or "gitlab-ci" in low or "fix pipeline" in low:
            return d.fix_pipeline()
        if low.startswith("helm upgrade") or low.startswith("helm install"):
            d.helm_release_status = "deployed"
            return "Release webapp has been upgraded. Happy Helming!"
        if low.startswith("helm list"):
            return "NAME\tNAMESPACE\tREVISION\tSTATUS\tCHART\nwebapp\tdefault\t3\tdeployed\twebapp-1.2.0"
        if "argocd app sync" in low or "argocd app get" in low:
            if d.kubeconfig_valid:
                return "Sync Status: Synced\nHealth Status: Healthy"
            return "error: failed to sync: invalid kubeconfig"
        if "flux reconcile" in low or "flux get" in low:
            if d.kubeconfig_valid:
                return "NAME\tREADY\tSTATUS\nwebapp\tTrue\tApplied"
            return "error: kubeconfig not configured"
        if low.startswith("mvn ") or low.startswith("./mvnw"):
            if "package" in low or "install" in low:
                return "BUILD SUCCESS\nTotal time: 12.4 s"
            return "Apache Maven 3.9.6"
        if "sonar-scanner" in low or "mvn sonar:" in low:
            return "ANALYSIS SUCCESSFUL\nQuality gate status: PASSED"
        if "jenkins-cli" in low or "java -jar jenkins-cli" in low:
            return "build scheduled"
        return None
    shell.register_handler(handler)


def _register_networking(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    if not engine.networking:
        engine.networking = NetworkingState(engine.scenario_slug)

    def handler(parts, line):
        low = line.strip().lower()
        n = engine.networking
        if "bgp summary" in low or "show ip bgp" in low or "vtysh" in low:
            return n.bgp_summary()
        if "router bgp" in low or ("neighbor" in low and "remote-as" in low):
            return n.fix_bgp()
        if "chronyc tracking" in low or "ntpq" in low:
            return n.chrony_tracking()
        if "chronyc makestep" in low or "ntpdate" in low:
            return n.sync_ntp()
        if "ip link set" in low and "mtu" in low:
            n.interface_mtu = 1500
            return ""
        if parts and parts[0] == "nmcli":
            return _handle_nmcli(engine, parts, line, shell)
        return None
    shell.register_handler(handler)


def _bond_proc_text(mode: str = "active-backup", miimon: int = 100,
                     slaves: tuple[str, ...] = ("eth1", "eth2"), active: str = "eth1") -> str:
    mode_num = {"active-backup": 1, "balance-rr": 0, "802.3ad": 4, "balance-xor": 2}.get(mode, 1)
    lines = [
        "Ethernet Channel Bonding Driver: v5.14.0",
        "",
        f"Bonding Mode: fault-tolerance ({mode})" if mode == "active-backup" else f"Bonding Mode: {mode}",
        f"Primary Slave: {slaves[0]} (primary_reselect always)",
        f"Currently Active Slave: {active}",
        "MII Status: up",
        f"MII Polling Interval (ms): {miimon}",
        "Up Delay (ms): 0",
        "Down Delay (ms): 0",
        f"Mode: {mode}",
    ]
    for s in slaves:
        lines += ["", f"Slave Interface: {s}", "MII Status: up", "Speed: 1000 Mbps", "Duplex: full"]
    return "\n".join(lines) + "\n"


def _handle_nmcli(engine: "UnifiedSimulationEngine", parts: list[str], line: str, shell: RHELShell) -> str:
    """Realistic nmcli covering device/connection management and bonding.

    Bond creation/modification writes /proc/net/bonding/bond0 so scenario
    check scripts that read that file pass once the bond is correctly set up.
    """
    st = shell.state
    args = parts[1:]
    low = line.lower()

    def opt(name: str) -> str:
        for i, t in enumerate(parts):
            if t == name and i + 1 < len(parts):
                return parts[i + 1]
        return ""

    obj = args[0] if args else ""
    action = args[1] if len(args) > 1 else ""

    if obj in ("g", "general"):
        return "STATE      CONNECTIVITY  WIFI-HW  WIFI     WWAN-HW  WWAN\nconnected  full          enabled  enabled  enabled  enabled"

    if obj in ("d", "dev", "device"):
        if action in ("", "status"):
            ifs = st.network_ifs or {}
            rows = ["DEVICE  TYPE      STATE      CONNECTION"]
            rows.append("eth0    ethernet  connected  eth0")
            for name in ifs:
                if name not in ("eth0", "lo"):
                    typ = "bond" if name.startswith("bond") else "ethernet"
                    rows.append(f"{name:<7} {typ:<9} connected  {name}")
            if any(k.startswith("bond") for k in ifs):
                pass
            rows.append("lo      loopback  unmanaged  --")
            return "\n".join(rows)
        if action == "show":
            return "GENERAL.DEVICE:    eth0\nGENERAL.TYPE:      ethernet\nGENERAL.STATE:     100 (connected)"
        return ""

    if obj in ("c", "con", "connection"):
        if action in ("show", "", "s"):
            ifs = st.network_ifs or {}
            rows = ["NAME    UUID                                  TYPE      DEVICE"]
            rows.append("eth0    abc-123-eth0                          ethernet  eth0")
            for name in ifs:
                if name.startswith("bond"):
                    rows.append(f"{name:<7} bond-{name}-uuid                       bond      {name}")
            return "\n".join(rows)
        if action in ("up", "down"):
            target = args[2] if len(args) > 2 else ""
            return f"Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/1)" if action == "up" else f"Connection '{target}' successfully deactivated"
        if action in ("add",):
            con_type = opt("type")
            ifname = opt("ifname") or opt("con-name")
            con_name = opt("con-name") or ifname
            if con_type == "bond":
                # nmcli con add type bond con-name bond0 ifname bond0 mode active-backup [miimon 100]
                mode = "active-backup"
                miimon = 100
                # mode/miimon can come via bond.options "mode=active-backup,miimon=100"
                m = re.search(r"mode[=\s]+(\S+)", low)
                if m:
                    mode = m.group(1).strip(",")
                mm = re.search(r"miimon[=\s]+(\d+)", low)
                if mm:
                    miimon = int(mm.group(1))
                st.network_ifs.setdefault(ifname or "bond0", {"up": True, "addrs": []})
                st._mkdir("/proc/net/bonding")
                st._write_file(f"/proc/net/bonding/{ifname or 'bond0'}",
                               _bond_proc_text(mode=mode, miimon=miimon))
                return f"Connection '{con_name}' ({_uuid()}) successfully added."
            if con_type in ("bond-slave", "ethernet"):
                master = opt("master")
                if master:
                    return f"Connection '{con_name}' ({_uuid()}) successfully added."
                if ifname:
                    st.network_ifs.setdefault(ifname, {"up": True, "addrs": []})
                return f"Connection '{con_name}' ({_uuid()}) successfully added."
            return f"Connection '{con_name}' ({_uuid()}) successfully added."
        if action in ("mod", "modify"):
            target = args[2] if len(args) > 2 else "bond0"
            # Update miimon / mode on an existing bond proc file.
            mm = re.search(r"miimon[=\s]+(\d+)", low)
            mode_m = re.search(r"mode[=\s]+(\S+)", low)
            existing = st.read_file(f"/proc/net/bonding/{target}") or ""
            mode = mode_m.group(1).strip(",") if mode_m else (
                "active-backup" if "active-backup" in existing or not existing else "active-backup")
            miimon = int(mm.group(1)) if mm else 100
            if target.startswith("bond"):
                st._mkdir("/proc/net/bonding")
                st._write_file(f"/proc/net/bonding/{target}", _bond_proc_text(mode=mode, miimon=miimon))
            return ""
        if action in ("reload", "delete", "del"):
            return ""
        return ""

    return "nmcli: OK"


def _register_terraform(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    """Bridge terminal terraform/aws commands to terraform_engine Redis state."""

    def handler(parts: list[str], line: str) -> str | None:
        low = line.strip().lower()
        is_tf = low.startswith("terraform")
        if not (is_tf or low.startswith("aws ")):
            return None
        sid = getattr(shell.state, "session_id", "") or ""
        if not sid:
            return "iac: lab session not linked"
        from apps.vmware_sim import terraform_engine as te

        slug = engine.scenario_slug or getattr(shell.state, "scenario_slug", "") or ""
        te._ensure(sid, slug)

        if low.startswith("terraform init"):
            res = te.apply_action(sid, "terraform_init")
        elif "force-unlock" in low:
            res = te.apply_action(sid, "force_unlock")
        elif low.startswith("terraform plan"):
            res = te.apply_action(sid, "terraform_plan")
        elif low.startswith("terraform apply"):
            res = te.apply_action(sid, "terraform_apply")
        elif low.startswith("terraform destroy"):
            res = te.apply_action(sid, "terraform_destroy")
        elif low.startswith("terraform validate"):
            res = te.apply_action(sid, "terraform_validate")
        elif low.startswith("aws "):
            res = te.apply_action(sid, "aws_cli", {"command": line.strip()})
        else:
            return (
                "Usage: terraform init | plan | apply | destroy | validate | force-unlock\n"
                "       aws <service> <command> …\n"
                "(state synced with Terraform workspace simulator)"
            )

        if not res.get("ok"):
            shell.state.last_exit_code = 1
            return res.get("error") or "Error"
        shell.state.last_exit_code = 0
        ok, _msg = te.validate_terraform_lab(sid, slug)
        shell.state.terraform_fixed = ok
        return res.get("output") or res.get("message") or ""

    shell.register_handler(handler)


def _register_windows(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    """A PowerShell / cmd surface for `simulation_type: windows` terminal labs.

    Without this, Windows scenarios ran a bare Linux shell (PowerShell cmdlets
    were "command not found") and validation required `state.windows_fixed`,
    which nothing ever set — so every Windows lab failed "Check Solution" even
    after a correct fix. This handler simulates the common Windows admin verbs
    and marks the scenario fixed when the learner runs a real remediation
    command (start/enable a service, unlock/enable an account, install a role…).
    """
    st = shell.state
    # Seed a small, realistic Windows world the first time.
    if not hasattr(st, "win_services"):
        st.win_services = {
            "Spooler": {"display": "Print Spooler", "status": "Stopped", "startup": "Disabled"},
            "W3SVC": {"display": "World Wide Web Publishing Service", "status": "Stopped", "startup": "Manual"},
            "wuauserv": {"display": "Windows Update", "status": "Running", "startup": "Automatic"},
            "Netlogon": {"display": "Netlogon", "status": "Running", "startup": "Automatic"},
            "MSSQLSERVER": {"display": "SQL Server (MSSQLSERVER)", "status": "Stopped", "startup": "Manual"},
        }
    if not hasattr(st, "win_users"):
        st.win_users = {
            "Administrator": {"enabled": True, "locked": False},
            "svc_app": {"enabled": False, "locked": True},
        }
    if not hasattr(st, "win_features"):
        st.win_features = {"DHCP": False, "DNS": False, "Web-Server": False}

    def _svc_table() -> str:
        rows = ["Status   Name               DisplayName",
                "------   ----               -----------"]
        for name, s in st.win_services.items():
            rows.append(f"{s['status']:<8} {name:<18} {s['display']}")
        return "\n".join(rows)

    def handler(parts, line):  # noqa: C901 — single dispatch surface
        raw = line.strip()
        low = raw.lower()
        if not raw:
            return None

        def mark_fixed():
            st.windows_fixed = True

        # ---- Service queries ----
        if low.startswith("get-service") or low in ("sc query", "net start"):
            return _svc_table()

        # ---- Service remediation: start / restart / set startup ----
        if low.startswith(("start-service", "restart-service", "set-service")) or \
           low.startswith("net start ") or low.startswith("sc config") or low.startswith("sc start"):
            target = None
            for name in st.win_services:
                if name.lower() in low:
                    target = name
                    break
            if target:
                svc = st.win_services[target]
                if "set-service" in low or "sc config" in low:
                    if "automatic" in low or "auto" in low:
                        svc["startup"] = "Automatic"
                    if "disabled" in low:
                        svc["startup"] = "Disabled"
                    if "manual" in low or "demand" in low:
                        svc["startup"] = "Manual"
                if low.startswith(("start-service", "restart-service", "net start", "sc start")):
                    svc["status"] = "Running"
                mark_fixed()
                return f"{svc['display']} ({target}) — Status: {svc['status']}, StartupType: {svc['startup']}"
            return f"Service not found. Run Get-Service to list services."

        if low.startswith("stop-service") or low.startswith("net stop "):
            for name in st.win_services:
                if name.lower() in low:
                    st.win_services[name]["status"] = "Stopped"
                    return f"{st.win_services[name]['display']} stopped."
            return "Service not found."

        # ---- Local / AD users ----
        if low.startswith(("get-localuser", "get-aduser")) or low == "net user":
            rows = ["Name            Enabled  Locked", "----            -------  ------"]
            for name, u in st.win_users.items():
                rows.append(f"{name:<15} {str(u['enabled']):<8} {u['locked']}")
            return "\n".join(rows)

        if low.startswith(("enable-localuser", "enable-aduser", "unlock-adaccount", "set-localuser", "set-aduser")) or \
           ("net user" in low and "/active:yes" in low):
            for name in st.win_users:
                if name.lower() in low:
                    if "unlock" in low or "/active:yes" in low or "enable" in low or "-enabled $true" in low:
                        st.win_users[name]["locked"] = False
                        st.win_users[name]["enabled"] = True
                    mark_fixed()
                    return f"{name}: Enabled={st.win_users[name]['enabled']}, Locked={st.win_users[name]['locked']}"
            # Allow creating/activating an unknown account too.
            mark_fixed()
            return "User account updated."

        # ---- Roles / features ----
        if low.startswith("get-windowsfeature"):
            rows = ["Display Name                         Name          Install State",
                    "------------                         ----          -------------"]
            label = {"DHCP": "DHCP Server", "DNS": "DNS Server", "Web-Server": "Web Server (IIS)"}
            for name, installed in st.win_features.items():
                state_txt = "Installed" if installed else "Available"
                rows.append(f"{label.get(name, name):<36} {name:<13} {state_txt}")
            return "\n".join(rows)

        if low.startswith(("install-windowsfeature", "add-windowsfeature")):
            for name in st.win_features:
                if name.lower() in low:
                    st.win_features[name] = True
                    mark_fixed()
                    return (f"Success Restart Needed Exit Code      Feature Result\n"
                            f"------- -------------- ---------      --------------\n"
                            f"True    No             Success        {{{name}}}")
            return "Feature not found. Run Get-WindowsFeature to list features."

        # ---- Read-only Windows info commands ----
        if low in ("ipconfig", "ipconfig /all"):
            return ("Windows IP Configuration\n\nEthernet adapter Ethernet0:\n"
                    "   IPv4 Address. . . . . . . . . . . : 10.0.0.20\n"
                    "   Subnet Mask . . . . . . . . . . . : 255.255.255.0\n"
                    "   Default Gateway . . . . . . . . . : 10.0.0.1")
        if low == "hostname":
            return getattr(st, "hostname", "WIN-SRV-SIM")
        if low.startswith("systeminfo"):
            return ("Host Name:                 WIN-SRV-SIM\n"
                    "OS Name:                   Microsoft Windows Server 2022 Datacenter\n"
                    "OS Version:                10.0.20348 N/A Build 20348\n"
                    "System Type:               x64-based PC")
        if low.startswith("get-eventlog") or low.startswith("get-winevent"):
            return ("   Index Time          EntryType   Source                 Message\n"
                    "   ----- ----          ---------   ------                 -------\n"
                    "    9001 Jun 30 14:02  Error       Service Control Manager The service terminated unexpectedly.")
        if low.startswith("get-process"):
            return ("Handles  NPM(K)    PM(K)      WS(K)   CPU(s)     Id ProcessName\n"
                    "-------  ------    -----      -----   ------     -- -----------\n"
                    "    412      24    18240      35216     1.23   1044 svchost")

        # Not a Windows command — let the Linux dispatch handle it.
        return None

    shell.register_handler(handler)


def _uuid() -> str:
    return "11111111-2222-3333-4444-555555555555"
