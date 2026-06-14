"""Kubernetes troubleshooting with full object graph."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .k8s_cluster import K8sCluster
from .rhel_shell import RHELShell


class KubernetesSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-k8s-crashloop"):
        super().__init__(scenario_slug=scenario_slug, hostname="k8s-master")
        self.cluster = K8sCluster(scenario_slug)
        self.state._mkdir("/root/.kube")
        self.state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\nclusters:\n- name: fixitlab\n")

    def _register_extras(self) -> None:
        sim = self

        def k8s_handler(parts: list[str], line: str) -> str | None:
            if not line.strip().startswith("kubectl"):
                return None
            return sim._kubectl(line)

        self.shell.register_handler(k8s_handler)

    def _register_extras_on(self, shell: RHELShell) -> None:
        self._register_extras()

    def _kubectl(self, line: str) -> str:
        low = line.strip().lower()
        c = self.cluster
        if "get pods" in low:
            return c.get_pods()
        if "get nodes" in low:
            return c.get_nodes()
        if "get svc" in low or "get services" in low:
            return c.get_services()
        if "get endpoints" in low:
            name = line.split()[-1] if "endpoints" in low and len(line.split()) > 2 else ""
            return c.get_endpoints(name)
        if "get deploy" in low:
            return c.get_deployments()
        if "describe pod" in low:
            name = line.split()[-1]
            return c.describe_pod(name)
        if "delete pod" in low:
            name = line.split()[-1]
            return c.delete_pod(name)
        if "rollout restart" in low:
            dep = line.split()[-1]
            return c.rollout_restart(dep)
        if "apply" in low and "-f" in low:
            fpath = line.split()[-1]
            content = self.state.read_file(fpath) or ""
            return c.apply_yaml(content)
        if "patch" in low and "service" in low:
            return c.patch_service_selector("api", {"app": "api"})
        if "logs" in low:
            pod = line.split()[-1]
            p = next((x for x in c.pods if pod in x.name), None)
            if p and p.status != "Running":
                return f"Error from server: container not found (CrashLoopBackOff)"
            return "nginx started successfully"
        return f"kubectl: OK (simulation)"

    @property
    def k8s_healthy(self) -> bool:
        return self.cluster.is_healthy()
