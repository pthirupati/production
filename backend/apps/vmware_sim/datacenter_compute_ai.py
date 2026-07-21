"""Phase 6: hypervisor + Kubernetes / GPU-AI facades for the datacenter twin.

Lab Environment compute platforms — VMs, live migrate, snapshots, K8s GPU
operators, Slurm/Ray/CUDA/MIG — as interactive state, not real clusters.
"""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_hypervisor_platform(servers: list[dict]) -> dict:
    hosts = []
    for s in servers:
        role = s.get("role")
        if role not in ("esxi_host", "gpu_node") and s.get("hostname") not in ("web-prod-01", "web-prod-02", "gpu-node-01"):
            continue
        hv = "ESXi" if role == "esxi_host" or "web-prod" in (s.get("hostname") or "") else "KVM"
        if role == "gpu_node":
            hv = "KVM"
        hosts.append({
            "id": s["id"],
            "hostname": s.get("hostname"),
            "hypervisor": hv,
            "version": "8.0U2" if hv == "ESXi" else "QEMU 8.2 / libvirt",
            "cpu_cores": 64,
            "mem_gb": 512 if role == "gpu_node" else 256,
            "vms": [],
        })
    # Seed a few VMs on first ESXi host
    if hosts:
        h0 = hosts[0]
        h0["vms"] = [
            {"id": "vm-web-01", "name": "web-frontend-01", "cpus": 4, "mem_gb": 16, "disk_gb": 100, "power": "on", "host": h0["id"]},
            {"id": "vm-app-01", "name": "app-tier-01", "cpus": 8, "mem_gb": 32, "disk_gb": 200, "power": "on", "host": h0["id"]},
        ]
    if len(hosts) > 1:
        hosts[1]["vms"] = [
            {"id": "vm-db-01", "name": "postgres-01", "cpus": 16, "mem_gb": 64, "disk_gb": 500, "power": "on", "host": hosts[1]["id"]},
        ]
    return {
        "platforms": ["VMware ESXi", "KVM", "Proxmox", "Hyper-V", "Xen", "VirtualBox", "UTM", "QEMU"],
        "hosts": hosts,
        "snapshots": [],
        "migrations": [],
    }


def hv_action(platform: dict, op: str, **kwargs) -> tuple[bool, str]:
    hosts = platform.setdefault("hosts", [])
    if op == "create_vm":
        host_id = kwargs.get("host_id") or (hosts[0]["id"] if hosts else None)
        host = next((h for h in hosts if h["id"] == host_id), None)
        if not host:
            return False, "No hypervisor host"
        vm = {
            "id": f"vm-{int(time.time()) % 100000}",
            "name": kwargs.get("name") or "new-vm",
            "cpus": int(kwargs.get("cpus") or 2),
            "mem_gb": int(kwargs.get("mem_gb") or 4),
            "disk_gb": int(kwargs.get("disk_gb") or 40),
            "power": "off",
            "host": host["id"],
        }
        host.setdefault("vms", []).append(vm)
        return True, f"Created {vm['name']} on {host['hostname']}"
    if op == "power_vm":
        vm_id = kwargs.get("vm_id")
        mode = kwargs.get("mode") or "on"
        for h in hosts:
            for vm in h.get("vms") or []:
                if vm["id"] == vm_id:
                    vm["power"] = mode
                    return True, f"{vm['name']} powered {mode}"
        return False, f"VM {vm_id} not found"
    if op == "snapshot_vm":
        vm_id = kwargs.get("vm_id")
        for h in hosts:
            for vm in h.get("vms") or []:
                if vm["id"] == vm_id:
                    snap = {
                        "id": f"snap-{int(time.time()) % 100000}",
                        "vm_id": vm_id,
                        "name": kwargs.get("name") or f"{vm['name']}-snap",
                        "time": _now(),
                    }
                    platform.setdefault("snapshots", []).insert(0, snap)
                    return True, f"Snapshot {snap['id']}"
        return False, f"VM {vm_id} not found"
    if op == "migrate_vm":
        vm_id = kwargs.get("vm_id")
        dest = kwargs.get("dest_host")
        dest_host = next((h for h in hosts if h["id"] == dest or h.get("hostname") == dest), None)
        if not dest_host:
            return False, "Destination host not found"
        src_host = None
        vm_obj = None
        for h in hosts:
            for vm in list(h.get("vms") or []):
                if vm["id"] == vm_id:
                    src_host = h
                    vm_obj = vm
                    break
        if not vm_obj:
            return False, f"VM {vm_id} not found"
        src_host["vms"] = [v for v in src_host["vms"] if v["id"] != vm_id]
        vm_obj["host"] = dest_host["id"]
        dest_host.setdefault("vms", []).append(vm_obj)
        platform.setdefault("migrations", []).insert(0, {
            "vm_id": vm_id, "from": src_host["id"], "to": dest_host["id"],
            "type": "live" if vm_obj.get("power") == "on" else "cold", "time": _now(),
        })
        return True, f"Migrated {vm_obj['name']} → {dest_host['hostname']}"
    return False, f"Unknown hypervisor op: {op}"


def build_ai_platform(servers: list[dict]) -> dict:
    gpu_nodes = [s for s in servers if s.get("role") == "gpu_node"]
    return {
        "kubernetes": {
            "version": "1.29",
            "control_plane": ["cp-01"],
            "workers": [s.get("hostname") for s in servers if s.get("role") in ("esxi_host", "gpu_node")][:3] or ["worker-01"],
            "gpu_operator": {"installed": True, "version": "24.3.0", "status": "Ready"},
            "namespaces": ["default", "gpu-workloads", "monitoring"],
            "pods": [
                {"name": "dcgm-exporter-ds", "ns": "monitoring", "status": "Running", "node": (gpu_nodes[0].get("hostname") if gpu_nodes else "gpu-node-01")},
                {"name": "inference-llm-0", "ns": "gpu-workloads", "status": "Running", "node": (gpu_nodes[0].get("hostname") if gpu_nodes else "gpu-node-01"), "gpus": 1},
            ],
            "helm_releases": ["gpu-operator", "ingress-nginx", "prometheus"],
            "ingress": [{"host": "llm.lab.local", "service": "inference-llm"}],
            "pvcs": [{"name": "model-cache", "size_gi": 500, "status": "Bound"}],
        },
        "slurm": {
            "partition": "gpu",
            "nodes": [s.get("hostname") for s in gpu_nodes] or ["gpu-node-01"],
            "jobs": [{"id": 1042, "name": "train-llama", "state": "RUNNING", "gpus": 4}],
        },
        "ray": {"head": "ray-head.lab.local", "workers": 2, "status": "healthy"},
        "cuda": {"version": "12.4", "driver": "550.54"},
        "nccl": {"version": "2.21", "status": "ok"},
        "dcgm": {"version": "3.3", "status": "ok"},
        "mig": {"enabled": False, "profiles": ["1g.10gb", "2g.20gb", "3g.40gb"]},
        "parallelism": {"tensor": 2, "pipeline": 1},
        "inference": [{"name": "vllm-llama70b", "backend": "vLLM", "replicas": 1, "status": "Ready"}],
    }


def ai_action(ai: dict, op: str, **kwargs) -> tuple[bool, str]:
    k8s = ai.setdefault("kubernetes", {})
    if op == "deploy_pod":
        pod = {
            "name": kwargs.get("name") or "workload-pod",
            "ns": kwargs.get("ns") or "gpu-workloads",
            "status": "Running",
            "node": kwargs.get("node") or (k8s.get("workers") or ["worker-01"])[0],
            "gpus": int(kwargs.get("gpus") or 0),
        }
        k8s.setdefault("pods", []).insert(0, pod)
        return True, f"Pod {pod['name']} Running"
    if op == "helm_install":
        chart = kwargs.get("chart") or "chart"
        k8s.setdefault("helm_releases", []).append(chart)
        return True, f"Helm release {chart}"
    if op == "enable_mig":
        mig = ai.setdefault("mig", {})
        mig["enabled"] = True
        mig["active_profile"] = kwargs.get("profile") or "1g.10gb"
        return True, f"MIG enabled ({mig['active_profile']})"
    if op == "slurm_submit":
        job = {
            "id": 2000 + len((ai.get("slurm") or {}).get("jobs") or []),
            "name": kwargs.get("name") or "batch-job",
            "state": "PENDING",
            "gpus": int(kwargs.get("gpus") or 1),
        }
        ai.setdefault("slurm", {}).setdefault("jobs", []).insert(0, job)
        job["state"] = "RUNNING"
        return True, f"Slurm job {job['id']} RUNNING"
    if op == "scale_inference":
        reps = int(kwargs.get("replicas") or 2)
        for inf in ai.get("inference") or []:
            inf["replicas"] = reps
        return True, f"Inference scaled to {reps}"
    return False, f"Unknown AI op: {op}"
