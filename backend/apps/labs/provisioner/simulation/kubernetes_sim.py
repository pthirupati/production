"""Kubernetes troubleshooting simulation."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator


class KubernetesSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-k8s-crashloop"):
        super().__init__(scenario_slug=scenario_slug, hostname="k8s-master")
        self.state._mkdir("/root/.kube")
        self.state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\nclusters:\n- name: fixitlab\n")
        self._pod_fixed = False

    def _register_extras(self) -> None:
        sim = self

        def k8s_handler(parts: list[str], line: str) -> str | None:
            if not line.strip().startswith("kubectl"):
                return None
            low = line.strip().lower()
            if "kubectl get pods" in low and not sim._pod_fixed:
                return "NAME                     READY   STATUS             RESTARTS   AGE\nnginx-7d4b8c9f-xk2m1      0/1     CrashLoopBackOff   5          10m"
            if "kubectl get pods" in low and sim._pod_fixed:
                return "NAME                     READY   STATUS    RESTARTS   AGE\nnginx-7d4b8c9f-xk2m1      1/1     Running   0          12m"
            if "kubectl rollout restart" in low or "kubectl delete pod" in low:
                sim._pod_fixed = True
                return "pod \"nginx-7d4b8c9f-xk2m1\" deleted"
            if "kubectl describe pod" in low:
                return "Events:\n  Warning  BackOff    kubelet  Back-off restarting failed container\n  Normal   Pulled     kubelet  Container image \"nginx:broken\" already present"
            return None

        self.shell.register_handler(k8s_handler)
