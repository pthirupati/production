"""In-memory Kubernetes cluster object graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class K8sNode:
    name: str
    status: str = "Ready"
    roles: list[str] = field(default_factory=lambda: ["control-plane"])
    version: str = "v1.28.2"


@dataclass
class K8sPod:
    name: str
    namespace: str = "default"
    status: str = "Running"
    ready: str = "1/1"
    restarts: int = 0
    age: str = "10m"
    node: str = "worker-1"
    image: str = "nginx:latest"
    labels: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)


@dataclass
class K8sService:
    name: str
    namespace: str = "default"
    type: str = "ClusterIP"
    cluster_ip: str = "10.96.0.1"
    port: int = 80
    selector: dict[str, str] = field(default_factory=lambda: {"app": "nginx"})
    endpoints: list[str] = field(default_factory=list)


@dataclass
class K8sDeployment:
    name: str
    namespace: str = "default"
    replicas: int = 1
    ready: int = 1
    image: str = "nginx:latest"
    selector: dict[str, str] = field(default_factory=lambda: {"app": "nginx"})


class K8sCluster:
    """Mutable cluster state for kubectl simulation."""

    def __init__(self, scenario_slug: str = "") -> None:
        self.scenario_slug = scenario_slug
        self.nodes = [
            K8sNode("master-1", roles=["control-plane"]),
            K8sNode("worker-1", roles=[]),
        ]
        self.pods: list[K8sPod] = []
        self.services: list[K8sService] = []
        self.deployments: list[K8sDeployment] = []
        self._apply_scenario(scenario_slug)

    def _apply_scenario(self, slug: str) -> None:
        s = slug.lower()
        if "crashloop" in s:
            self.deployments = [K8sDeployment("nginx", image="nginx:broken")]
            self.pods = [
                K8sPod(
                    "nginx-7d4b8c9f-xk2m1", status="CrashLoopBackOff", ready="0/1",
                    restarts=5, image="nginx:broken", labels={"app": "nginx"},
                    events=["Warning BackOff: back-off restarting failed container",
                            "Normal Pulled: Container image nginx:broken already present"],
                )
            ]
            self.services = [
                K8sService("nginx", selector={"app": "nginx"}, endpoints=[]),
            ]
        elif "imagepull" in s or "image-pull" in s:
            self.deployments = [K8sDeployment("api", image="api:missing-tag")]
            self.pods = [
                K8sPod(
                    "api-5f8c7d6b-abc12", status="ImagePullBackOff", ready="0/1",
                    restarts=0, image="api:missing-tag", labels={"app": "api"},
                    events=["Warning Failed: Error: ErrImagePull"],
                )
            ]
            self.services = [K8sService("api", selector={"app": "api"}, endpoints=[])]
        elif "node-notready" in s or ("node" in s and "notready" in s):
            self.nodes = [
                K8sNode("master-1", roles=["control-plane"]),
                K8sNode("worker-1", status="NotReady", roles=[]),
            ]
            self.deployments = [K8sDeployment("nginx")]
            self.pods = [K8sPod("nginx-7d4b8c9f-xk2m1", labels={"app": "nginx"}, node="worker-1")]
            self.services = [K8sService("nginx", endpoints=["10.244.1.5:8080"])]
        elif "configmap" in s:
            self.deployments = [K8sDeployment("web", image="nginx:latest")]
            self.pods = [
                K8sPod(
                    "web-6d4b8c9f-xk2m1", status="CreateContainerConfigError", ready="0/1",
                    restarts=3, image="nginx:latest", labels={"app": "web"},
                    events=["Warning Failed: configmap \"app-config\" not found"],
                )
            ]
            self.services = [K8sService("web", selector={"app": "web"}, endpoints=[])]
        elif "rbac" in s:
            self.deployments = [K8sDeployment("nginx")]
            self.pods = [K8sPod("nginx-7d4b8c9f-xk2m1", labels={"app": "nginx"})]
            self.services = [K8sService("nginx", endpoints=["10.244.1.5:8080"])]
            self.rbac_forbidden = True
        elif "ingress" in s:
            self.deployments = [K8sDeployment("web", selector={"app": "web"})]
            self.pods = [K8sPod("web-7d4b8c9f-xk2m1", labels={"app": "web"})]
            self.services = [K8sService("web", selector={"app": "web"}, endpoints=["10.244.1.5:8080"])]
            self.ingress_broken = True
        elif "quota" in s:
            self.deployments = [K8sDeployment("worker")]
            self.pods = [
                K8sPod(
                    "worker-7d4b8c9f-xk2m1", status="Pending", ready="0/1",
                    restarts=0, image="busybox:latest", labels={"app": "worker"},
                    events=["Warning FailedScheduling: exceeded quota: compute-resources"],
                )
            ]
            self.services = []
        elif "pvc" in s or "storageclass" in s:
            self.deployments = [K8sDeployment("db")]
            self.pods = [
                K8sPod(
                    "db-7d4b8c9f-xk2m1", status="Pending", ready="0/1",
                    restarts=0, image="postgres:15", labels={"app": "db"},
                    events=["Warning FailedScheduling: pod has unbound immediate PersistentVolumeClaims"],
                )
            ]
            self.services = [K8sService("db", selector={"app": "db"}, endpoints=[])]
        elif "port-fix" in s or "manifest" in s:
            self.deployments = [K8sDeployment("api", selector={"app": "api"})]
            self.pods = [K8sPod("api-5f8c7d6b-abc12", labels={"app": "api"}, image="api:v1")]
            self.services = [
                K8sService("api", selector={"app": "api"}, port=8080, endpoints=["10.244.1.5:8080"]),
            ]
            self.service_port_wrong = True
        elif "service" in s or "endpoint" in s or "unreachable" in s:
            self.deployments = [K8sDeployment("api", selector={"app": "api"})]
            self.pods = [
                K8sPod("api-5f8c7d6b-abc12", labels={"app": "api"}, image="api:v1"),
            ]
            self.services = [
                K8sService("api", selector={"app": "api", "version": "v2"}, endpoints=[]),
            ]
        else:
            self.deployments = [K8sDeployment("nginx", image="nginx:broken")]
            self.pods = [
                K8sPod(
                    "nginx-7d4b8c9f-xk2m1", status="CrashLoopBackOff", ready="0/1",
                    restarts=2, image="nginx:broken", labels={"app": "nginx"},
                )
            ]
            self.services = [K8sService("nginx", selector={"app": "nginx"}, endpoints=[])]

    def get_pods(self, namespace: str = "default") -> str:
        lines = ["NAME                     READY   STATUS             RESTARTS   AGE"]
        for p in self.pods:
            if p.namespace == namespace:
                lines.append(
                    f"{p.name:<24} {p.ready:<7} {p.status:<18} {p.restarts:<10} {p.age}"
                )
        return "\n".join(lines)

    def get_nodes(self) -> str:
        lines = ["NAME       STATUS   ROLES           AGE   VERSION"]
        for n in self.nodes:
            roles = ",".join(n.roles) if n.roles else "<none>"
            lines.append(f"{n.name:<10} {n.status:<8} {roles:<15} 30d   {n.version}")
        return "\n".join(lines)

    def get_services(self, namespace: str = "default") -> str:
        lines = ["NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE"]
        for s in self.services:
            if s.namespace == namespace:
                lines.append(
                    f"{s.name:<12} {s.type:<11} {s.cluster_ip:<15} <none>        {s.port}/TCP   1h"
                )
        return "\n".join(lines)

    def get_endpoints(self, name: str = "") -> str:
        lines = ["NAME         ENDPOINTS   AGE"]
        for s in self.services:
            if name and s.name != name:
                continue
            eps = ",".join(s.endpoints) if s.endpoints else "<none>"
            lines.append(f"{s.name:<12} {eps:<11} 1h")
        return "\n".join(lines)

    def get_deployments(self) -> str:
        lines = ["NAME    READY   UP-TO-DATE   AVAILABLE   AGE"]
        for d in self.deployments:
            lines.append(f"{d.name:<7} {d.ready}/{d.replicas:<7} {d.replicas:<12} {d.ready:<11} 1h")
        return "\n".join(lines)

    def describe_pod(self, name: str) -> str:
        pod = next((p for p in self.pods if p.name == name or name in p.name), None)
        if not pod:
            return f"Error from server (NotFound): pods \"{name}\" not found"
        events = "\n".join(f"  {e}" for e in pod.events) or "  Normal  Started  kubelet  Started container"
        return (
            f"Name:         {pod.name}\n"
            f"Namespace:    {pod.namespace}\n"
            f"Status:       {pod.status}\n"
            f"Image:        {pod.image}\n"
            f"Events:\n{events}"
        )

    def delete_pod(self, name: str) -> str:
        for i, p in enumerate(self.pods):
            if p.name == name or name in p.name:
                self.pods.pop(i)
                # Recreate with fixed image if deployment exists
                dep = next((d for d in self.deployments if d.name in name), None)
                if dep and "broken" in dep.image:
                    dep.image = "nginx:latest"
                    self.pods.append(K8sPod(
                        name, status="Running", ready="1/1", image="nginx:latest",
                        labels=dep.selector,
                    ))
                    self._sync_endpoints()
                return f'pod "{name}" deleted'
        return f"Error from server (NotFound): pods \"{name}\" not found"

    def rollout_restart(self, dep_name: str) -> str:
        dep_name = dep_name.split("/")[-1]
        for d in self.deployments:
            if d.name == dep_name or dep_name in d.name:
                if "broken" in d.image:
                    d.image = d.image.replace("broken", "latest")
                for p in self.pods:
                    if d.name in p.name:
                        p.status = "Running"
                        p.ready = "1/1"
                        p.restarts = 0
                        p.image = d.image
                self._sync_endpoints()
                return f"deployment.apps/{d.name} restarted"
        return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"

    def patch_service_selector(self, svc_name: str, selector: dict[str, str]) -> str:
        for s in self.services:
            if s.name == svc_name:
                s.selector = selector
                self._sync_endpoints()
                return f"service/{svc_name} patched"
        return f"Error from server (NotFound): services \"{svc_name}\" not found"

    def apply_yaml(self, content: str) -> str:
        if "selector:" in content and "app: api" in content:
            for s in self.services:
                if s.name == "api":
                    s.selector = {"app": "api"}
                    self._sync_endpoints()
            return "service/api configured"
        return "configured"

    def _sync_endpoints(self) -> None:
        for s in self.services:
            s.endpoints = []
            for p in self.pods:
                if p.status == "Running" and all(p.labels.get(k) == v for k, v in s.selector.items()):
                    s.endpoints.append("10.244.1.5:8080")

    def is_healthy(self) -> bool:
        if getattr(self, "rbac_forbidden", False):
            return False
        if getattr(self, "ingress_broken", False):
            return False
        if getattr(self, "service_port_wrong", False):
            return False
        if any(n.status != "Ready" for n in self.nodes):
            return False
        return all(p.status == "Running" for p in self.pods) and all(
            s.endpoints for s in self.services if s.name != "kubernetes"
        )
