"""Technology modules plugged into the unified RHEL simulation engine."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .k8s_cluster import K8sCluster
from .rhel_os import SimService
from .rhel_shell import RHELShell

if TYPE_CHECKING:
    from .unified_sim import UnifiedSimulationEngine

GPU_NAMES = ["NVIDIA A100-SXM4-40GB", "NVIDIA H100 80GB HBM3", "NVIDIA RTX 4090"]


def apply_simulation_context(engine: "UnifiedSimulationEngine") -> None:
    """Configure hostname, services, and flags for the simulation persona."""
    sim_type = engine.simulation_type
    state = engine.shell.state
    slug = engine.scenario_slug

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
    elif sim_type == "python":
        state.hostname = "dev-server"
        state._mkdir("/home/dev")
        state._mkdir("/opt/app")
        if not state.read_file("/home/dev/app.py"):
            state._write_file("/home/dev/app.py", '#!/usr/bin/env python3\nprint("hello"\n')
        if "pip" in slug:
            state._write_file("/opt/app/main.py", 'import requests\n# missing package\n')
        else:
            state._write_file("/opt/app/main.py", 'print("hello"\n')

    if "unbound" in slug:
        state._mkdir("/opt/scripts")
        state._write_file(
            "/opt/scripts/deploy.sh",
            "#!/bin/bash\nset -u\necho ${MISSING_VAR}\n",
        )

    if "docker" in slug:
        state.services.setdefault(
            "docker",
            SimService("docker", active="active", enabled="enabled", description="Docker Engine"),
        )
        engine._container_running = False

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

    # Every simulation includes full RHEL; generic enables all tech stacks
    modules = _modules_for_type(sim_type)
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


def _modules_for_type(sim_type: str) -> set[str]:
    if sim_type == "generic":
        return {"gpu", "kubernetes", "ansible", "baremetal", "database", "docker"}
    return {sim_type, "docker"} if sim_type == "rhel" else {sim_type}


def _register_gpu(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    def handler(parts, line):
        low = line.strip().lower()
        cmds = ("nvidia-smi", "dcgm", "dcgmi", "gpustat", "rocm-smi", "amd-smi", "modprobe nvidia")
        if not any(low.startswith(c) for c in cmds):
            return None
        if low.startswith("nvidia-smi"):
            if engine.shell.state.gpu_healthy:
                util = random.randint(0, 95)
                mem = random.randint(1000, 38000)
                return f"""Fri Jun 14 10:00:00 2026
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.54.03    Driver Version: 535.54.03    CUDA Version: 12.2     |
|   0  {GPU_NAMES[0]:<18}| 00000000:01:00.0 Off |  {mem:5d}MiB / 40960MiB |  {util:3d}%"""
            return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
        if low.startswith("modprobe nvidia"):
            engine.shell.state.gpu_healthy = True
            return ""
        if low.startswith("dmesg"):
            return None  # fall through to shell dmesg
        if low.startswith("lspci"):
            return "01:00.0 3D controller: NVIDIA Corporation GA100 [A100 SXM4 40GB]"
        if low.startswith("lsmod"):
            return "nvidia              56852480  42\nnvidia_uvm           1048576  2"
        return f"{line}: OK (GPU simulation)"
    shell.register_handler(handler)


def _register_k8s(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    if not engine.cluster:
        engine.cluster = K8sCluster(engine.scenario_slug)

    def handler(parts, line):
        if not line.strip().startswith("kubectl"):
            return None
        low = line.strip().lower()
        c = engine.cluster
        if "get pods" in low:
            return c.get_pods()
        if "get nodes" in low:
            return c.get_nodes()
        if "get svc" in low or "get services" in low:
            return c.get_services()
        if "get endpoints" in low:
            name = line.split()[-1] if len(line.split()) > 2 else ""
            return c.get_endpoints(name)
        if "get deploy" in low:
            return c.get_deployments()
        if "describe pod" in low:
            return c.describe_pod(line.split()[-1])
        if "delete pod" in low:
            return c.delete_pod(line.split()[-1])
        if "rollout restart" in low:
            return c.rollout_restart(line.split()[-1])
        if "apply" in low and "-f" in low:
            return c.apply_yaml(shell.state.read_file(line.split()[-1]) or "")
        if "patch" in low and "service" in low:
            return c.patch_service_selector("api", {"app": "api"})
        if "logs" in low:
            pod = line.split()[-1]
            p = next((x for x in c.pods if pod in x.name), None)
            if p and p.status != "Running":
                return "Error from server: container not found (CrashLoopBackOff)"
            return "container started"
        return f"kubectl: OK"
    shell.register_handler(handler)


def _register_ansible(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    def handler(parts, line):
        low = line.strip().lower()
        if low.startswith("ssh-copy-id"):
            engine._ssh_key_fixed = True
            return "Number of key(s) added: 1"
        if not (low.startswith("ansible ") or low.startswith("ansible-playbook") or low.startswith("ansible-inventory")):
            return None
        if low in ("ansible --version", "ansible-playbook --version"):
            return "ansible [core 2.15.3]\n  python version = 3.11.6"
        if "ping" in low:
            if engine._ssh_key_fixed:
                return "web1 | SUCCESS => {\"ping\": \"pong\"}\nweb2 | SUCCESS => {\"ping\": \"pong\"}"
            return (
                "web1 | SUCCESS => {\"ping\": \"pong\"}\n"
                "web2 | UNREACHABLE! => {\"msg\": \"Permission denied (publickey).\"}"
            )
        if "ansible-playbook" in low:
            if engine._ssh_key_fixed:
                return "PLAY RECAP *****\nweb1 : ok=2 changed=1\nweb2 : ok=2 changed=1"
            return "fatal: [web2]: FAILED! => Unable to start service nginx"
        if "ansible-inventory" in low:
            return '{"webservers": {"hosts": ["web1", "web2"]}}'
        return f"{line}: OK"
    shell.register_handler(handler)


def _register_baremetal(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    def handler(parts, line):
        low = line.strip().lower()
        if not (low.startswith("ipmitool") or low.startswith("dmidecode") or low.startswith("esxcli")):
            return None
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
            return "CPU Temp        | 42 degrees C      | ok"
        if "fru" in low:
            return " Board Product         : ProLiant DL380 Gen10"
        if "dmidecode" in low:
            return "Manufacturer: HPE\nProduct Name: ProLiant DL380 Gen10"
        if "esxcli" in low:
            return "Host CPU: Intel Xeon Gold 6248R\nMemory: 256 GB"
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
    def handler(parts, line):
        if not line.strip().lower().startswith("docker"):
            return None
        low = line.strip().lower()
        if "docker start" in low:
            engine._container_running = True
            return "web"
        if "docker ps" in low and "-a" not in low:
            if engine._container_running:
                return "CONTAINER ID   IMAGE          STATUS         NAMES\nabc123   nginx:latest   Up 1 second   web"
            return "CONTAINER ID   IMAGE          STATUS                     NAMES\nabc123   nginx:latest   Exited (1)   web"
        return None
    shell.register_handler(handler)
