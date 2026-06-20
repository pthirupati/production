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
    elif sim_type == "devops" or "devops" in slug or "ci-pipeline" in slug or "helm" in slug:
        state.hostname = "gitlab-runner"
    elif sim_type == "networking" or "bgp" in slug or "ntp-drift" in slug:
        state.hostname = "core-router"

    if "unbound" in slug:
        state._mkdir("/opt/scripts")
        state._write_file(
            "/opt/scripts/deploy.sh",
            "#!/bin/bash\nset -u\necho ${MISSING_VAR}\n",
        )

    if "docker" in slug:
        # A scenario preset may have already put the docker unit (or a related
        # unit like docker-socket-proxy) into a failed state — do NOT clobber
        # that, or the fail-closed check would auto-pass.
        existing_docker = state.services.get("docker")
        preset_broke_docker = bool(existing_docker and existing_docker.active != "active")
        is_down_slug = "daemon-stopped" in slug or "stopped" in slug or "daemon-down" in slug
        if preset_broke_docker or is_down_slug:
            state.services["docker"] = SimService(
                "docker", active="failed" if preset_broke_docker else "inactive",
                enabled="enabled", description="Docker Engine",
            )
            engine._container_running = False
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


def _modules_for_type(sim_type: str) -> set[str]:
    if sim_type == "generic":
        return {"gpu", "kubernetes", "ansible", "baremetal", "database", "docker", "devops", "networking"}
    if sim_type == "devops":
        return {"devops", "docker"}
    if sim_type == "networking":
        return {"networking"}
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


def _register_k8s(engine: "UnifiedSimulationEngine", shell: RHELShell) -> None:
    sid = getattr(getattr(shell, "state", None), "session_id", "") or ""
    if not engine.cluster:
        engine.cluster = K8sCluster(engine.scenario_slug, session_id=sid)
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
    if not engine.docker:
        engine.docker = DockerState(engine.scenario_slug)
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


def _uuid() -> str:
    return "11111111-2222-3333-4444-555555555555"
