"""Technology modules plugged into the unified RHEL simulation engine."""

from __future__ import annotations

import random
import re
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
    elif sim_type == "devops" or "devops" in slug or "ci-pipeline" in slug or "helm" in slug:
        state.hostname = "gitlab-runner"
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
    if sim_type == "devops" or "git" in slug or "ci-pipeline" in slug or "devops" in slug:
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
    if sim_type == "devops":
        return {"devops", "docker", "terraform"}
    if sim_type == "networking":
        return {"networking"}
    if sim_type == "terraform":
        return {"terraform", "docker"}
    return {sim_type, "docker"} if sim_type == "rhel" else {sim_type}


def _register_gpu(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    is_gpu_focus = engine.simulation_type == "gpu" or "gpu" in engine.scenario_slug or "nvidia" in engine.scenario_slug

    def handler(parts, line):
        low = line.strip().lower()
        # GPU-specific tools always handled here. Generic kernel tools
        # (modprobe/lspci/lsmod/modinfo) are only intercepted when they
        # reference the NVIDIA driver, or when this is a GPU-focused sim — so
        # other scenarios keep using the normal Linux handlers.
        gpu_tools = ("nvidia-smi", "dcgmi", "dcgm", "gpustat", "rocm-smi", "amd-smi", "nvcc")
        kernel_tools = ("modprobe", "rmmod", "lspci", "lsmod", "modinfo")
        if any(low.startswith(c) for c in gpu_tools):
            pass
        elif any(low.startswith(c) for c in kernel_tools) and ("nvidia" in low or is_gpu_focus):
            pass
        else:
            return None
        healthy = engine.shell.state.gpu_healthy
        if low.startswith("nvidia-smi"):
            if "-l" in parts or "--loop" in low:
                pass  # streaming flag — single snapshot is fine for the sim
            if "--query-gpu" in low:
                if not healthy:
                    return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
                return f"{GPU_NAMES[0]}, {random.randint(30, 85)}, {random.randint(2000, 38000)}, 40960"
            if healthy:
                util = random.randint(0, 95)
                mem = random.randint(1000, 38000)
                temp = random.randint(32, 78)
                return (
                    "Fri Jun 14 10:00:00 2026\n"
                    "+-----------------------------------------------------------------------------+\n"
                    "| NVIDIA-SMI 535.54.03    Driver Version: 535.54.03    CUDA Version: 12.2     |\n"
                    "|-------------------------------+----------------------+----------------------+\n"
                    "| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |\n"
                    "| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |\n"
                    "|===============================+======================+======================|\n"
                    f"|   0  {GPU_NAMES[0]:<18}  On | 00000000:01:00.0 Off |                    0 |\n"
                    f"| N/A  {temp:2d}C    P0    72W / 400W |  {mem:5d}MiB / 40960MiB |   {util:3d}%      Default |\n"
                    "+-----------------------------------------------------------------------------+"
                )
            return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running."
        if low.startswith("modprobe"):
            # `modprobe nvidia` loads the driver; `modprobe -r nvidia` unloads it.
            if "nvidia" in low:
                engine.shell.state.gpu_healthy = "-r" not in parts and "--remove" not in low
            return ""
        if low.startswith("rmmod"):
            if "nvidia" in low:
                engine.shell.state.gpu_healthy = False
            return ""
        if low.startswith("lspci"):
            out = "01:00.0 3D controller: NVIDIA Corporation GA100 [A100 SXM4 40GB] (rev a1)"
            return out
        if low.startswith("lsmod"):
            if not healthy:
                return "Module                  Size  Used by"
            return ("Module                  Size  Used by\n"
                    "nvidia              56852480  42\n"
                    "nvidia_uvm           1048576  2 nvidia\n"
                    "nvidia_drm             69632  0")
        if low.startswith("modinfo"):
            if not healthy:
                return "modinfo: ERROR: Module nvidia not found."
            return ("filename:       /lib/modules/5.14.0/kernel/drivers/video/nvidia.ko\n"
                    "version:        535.54.03\n"
                    "license:        NVIDIA\n"
                    "description:    NVIDIA Linux Open GPU Kernel Module")
        if low.startswith("nvcc"):
            return "nvcc: NVIDIA (R) Cuda compiler driver\nCuda compilation tools, release 12.2, V12.2.140"
        if low.startswith("dcgmi") or low.startswith("dcgm"):
            if not healthy:
                return "Error: Unable to connect to nv-hostengine. GPU driver not loaded."
            return ("+----+-----------+----------------------------------------------------------+\n"
                    "| GPU| Health    | Details                                                  |\n"
                    "+====+===========+==========================================================+\n"
                    "|  0 | Healthy   | All checks passed                                        |\n"
                    "+----+-----------+----------------------------------------------------------+")
        if low.startswith("gpustat"):
            if not healthy:
                return "Error: NVIDIA driver is not loaded"
            return f"[0] {GPU_NAMES[0]} | {random.randint(35, 75)}'C, {random.randint(10, 90)} % | {random.randint(2000, 38000)} / 40960 MB"
        if low.startswith("rocm-smi") or low.startswith("amd-smi"):
            return "ROCm System Management Interface\nGPU  Temp  AvgPwr  Use%\n0    45c   120W    37%"
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


def _register_baremetal(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    # IPMI power labs start with the chassis OFF so the learner has to bring it
    # up (`ipmitool power on`); otherwise the canonical power check auto-passes.
    slug = (engine.scenario_slug or "").lower()
    if slug in ("sim-baremetal-ipmi", "sim-rhel-baremetal-ipmi", "maas-ipmi-bmc-unreachable"):
        engine._power_state = "off"

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
        if low.startswith("maas"):
            if "list" in low and "machines" in low:
                return "Machine 1: ready (node-01)\nMachine 2: deployed (node-02)\nMachine 3: failed commissioning"
            if "commission" in low:
                return "Commissioning started for node-03"
            if "deploy" in low:
                return "Deploying Ubuntu 22.04 to node-02"
            return "MAAS: OK"
        if low.startswith("lxc") or low.startswith("lxd"):
            if "list" in low:
                return "gpu-worker-1 (RUNNING)\nk8s-node-2 (STOPPED)"
            if "start" in low:
                return "Instance started"
            return "LXD: OK"
        if low.startswith("virsh"):
            if "list" in low:
                return " Id   Name         State\n------------------------\n 1    vm-k8s-node  running"
            return "virsh: OK"
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
        elif low.startswith("terraform validate"):
            res = te.apply_action(sid, "terraform_validate")
        elif low.startswith("aws "):
            res = te.apply_action(sid, "aws_cli", {"command": line.strip()})
        else:
            return (
                "Usage: terraform init | plan | apply | validate | force-unlock\n"
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
