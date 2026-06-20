"""In-memory Kubernetes cluster object graph for terminal kubectl simulation.

The cluster is fully mutable and self-consistent: creating, scaling, deleting,
labelling and rolling out resources updates the same object graph that
``kubectl get`` reports from. ``kubectl apply -f file.yaml`` parses a manifest
the learner wrote (via the editor or a heredoc) and materialises the resource.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class K8sNode:
    name: str
    status: str = "Ready"
    roles: list[str] = field(default_factory=lambda: ["control-plane"])
    version: str = "v1.28.2"
    schedulable: bool = True
    # Cross-tech: the node's VMware VM is hung. A hung node cannot be made Ready or
    # scheduled onto from kubectl — only a VMware reset (via the bridge) clears it.
    vm_hung: bool = False


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
    annotations: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    ip: str = "10.244.1.5"
    containers: list[str] = field(default_factory=lambda: ["app"])
    owner: str = ""  # deployment/rs that owns this pod


@dataclass
class K8sService:
    name: str
    namespace: str = "default"
    type: str = "ClusterIP"
    cluster_ip: str = "10.96.0.1"
    port: int = 80
    target_port: int = 8080
    selector: dict[str, str] = field(default_factory=lambda: {"app": "nginx"})
    endpoints: list[str] = field(default_factory=list)
    external_ip: str = ""
    node_port: int = 0


@dataclass
class K8sDeployment:
    name: str
    namespace: str = "default"
    replicas: int = 1
    ready: int = 1
    image: str = "nginx:latest"
    selector: dict[str, str] = field(default_factory=lambda: {"app": "nginx"})
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    revision: int = 1
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class K8sConfigMap:
    name: str
    namespace: str = "default"
    data: dict[str, str] = field(default_factory=dict)


@dataclass
class K8sSecret:
    name: str
    namespace: str = "default"
    type: str = "Opaque"
    data: dict[str, str] = field(default_factory=dict)


@dataclass
class K8sPVC:
    name: str
    namespace: str = "default"
    status: str = "Bound"
    capacity: str = "10Gi"
    access_modes: list[str] = field(default_factory=lambda: ["ReadWriteOnce"])
    storage_class: str = "standard"
    volume: str = "pv-001"


@dataclass
class K8sIngress:
    name: str
    namespace: str = "default"
    hosts: list[str] = field(default_factory=lambda: ["app.example.com"])
    service: str = "web"
    port: int = 80
    class_name: str = "nginx"


@dataclass
class K8sHPA:
    name: str
    namespace: str = "default"
    target: str = "Deployment/web"
    min_replicas: int = 1
    max_replicas: int = 5
    target_cpu: int = 50
    current_cpu: int = 80  # sustained load above target → wants to scale out
    current_replicas: int = 1
    desired_replicas: int = 1


@dataclass
class K8sDaemonSet:
    name: str
    namespace: str = "default"
    image: str = "fluentd:latest"
    selector: dict[str, str] = field(default_factory=lambda: {"app": "node-agent"})


class K8sCluster:
    """Mutable cluster state for kubectl simulation."""

    def __init__(self, scenario_slug: str = "", session_id: str = "") -> None:
        self.scenario_slug = scenario_slug
        # Lab session id links this cluster to the VMware simulator's bridge cache
        # (shared across workers) for cross-technology k8s-on-VMware scenarios.
        self.session_id = session_id
        self.namespaces: list[str] = ["default", "kube-system"]
        self.nodes = [
            K8sNode("master-1", roles=["control-plane"]),
            K8sNode("worker-1", roles=[]),
        ]
        self.pods: list[K8sPod] = []
        self.services: list[K8sService] = []
        self.deployments: list[K8sDeployment] = []
        self.configmaps: list[K8sConfigMap] = []
        self.secrets: list[K8sSecret] = []
        self.pvcs: list[K8sPVC] = []
        self.ingresses: list[K8sIngress] = []
        self.hpas: list[K8sHPA] = []
        self.daemonsets: list[K8sDaemonSet] = []
        self._apply_scenario(scenario_slug)
        # After seeding, fold in any cross-tech VMware node action so the very
        # first `kubectl get nodes` already reflects a node added/reset in VMware.
        self.sync_from_vmware_bridge()

    # ------------------------------------------------------------------
    # Scenario seeding
    # ------------------------------------------------------------------

    def _apply_scenario(self, slug: str) -> None:
        s = slug.lower()
        # ── Cross-technology Kubernetes-on-VMware (matched FIRST) ──
        # The cluster's worker nodes ARE VMware VMs. These start fail-closed
        # (pods Pending / a node NotReady) and only recover once the matching
        # VMware VM action is performed; sync_from_vmware_bridge() folds that in.
        if self._apply_cross_tech_k8s(s):
            return
        if "crashloop" in s:
            self.deployments = [K8sDeployment("nginx", image="nginx:broken")]
            self.pods = [
                K8sPod(
                    "nginx-7d4b8c9f-xk2m1", status="CrashLoopBackOff", ready="0/1",
                    restarts=5, image="nginx:broken", labels={"app": "nginx"}, owner="nginx",
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
                    restarts=0, image="api:missing-tag", labels={"app": "api"}, owner="api",
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
            self.pods = [K8sPod("nginx-7d4b8c9f-xk2m1", labels={"app": "nginx"}, node="worker-1", owner="nginx")]
            self.services = [K8sService("nginx", endpoints=["10.244.1.5:8080"])]
        elif "configmap" in s:
            self.deployments = [K8sDeployment("web", image="nginx:latest")]
            self.pods = [
                K8sPod(
                    "web-6d4b8c9f-xk2m1", status="CreateContainerConfigError", ready="0/1",
                    restarts=3, image="nginx:latest", labels={"app": "web"}, owner="web",
                    events=["Warning Failed: configmap \"app-config\" not found"],
                )
            ]
            self.services = [K8sService("web", selector={"app": "web"}, endpoints=[])]
        elif "rbac" in s:
            self.deployments = [K8sDeployment("nginx")]
            self.pods = [K8sPod("nginx-7d4b8c9f-xk2m1", labels={"app": "nginx"}, owner="nginx")]
            self.services = [K8sService("nginx", endpoints=["10.244.1.5:8080"])]
            self.rbac_forbidden = True
        elif "ingress" in s:
            self.deployments = [K8sDeployment("web", selector={"app": "web"})]
            self.pods = [K8sPod("web-7d4b8c9f-xk2m1", labels={"app": "web"}, owner="web")]
            self.services = [K8sService("web", selector={"app": "web"}, endpoints=["10.244.1.5:8080"])]
            self.ingresses = [K8sIngress("web", service="web", port=80)]
            self.ingress_broken = True
        elif "quota" in s:
            self.deployments = [K8sDeployment("worker")]
            self.pods = [
                K8sPod(
                    "worker-7d4b8c9f-xk2m1", status="Pending", ready="0/1",
                    restarts=0, image="busybox:latest", labels={"app": "worker"}, owner="worker",
                    events=["Warning FailedScheduling: exceeded quota: compute-resources"],
                )
            ]
            self.services = []
        elif "pvc" in s or "storageclass" in s:
            self.deployments = [K8sDeployment("db")]
            self.pods = [
                K8sPod(
                    "db-7d4b8c9f-xk2m1", status="Pending", ready="0/1",
                    restarts=0, image="postgres:15", labels={"app": "db"}, owner="db",
                    events=["Warning FailedScheduling: pod has unbound immediate PersistentVolumeClaims"],
                )
            ]
            self.pvcs = [K8sPVC("db-data", status="Pending", volume="")]
            self.services = [K8sService("db", selector={"app": "db"}, endpoints=[])]
        elif "port-fix" in s or "manifest" in s:
            self.deployments = [K8sDeployment("api", selector={"app": "api"})]
            self.pods = [K8sPod("api-5f8c7d6b-abc12", labels={"app": "api"}, image="api:v1", owner="api")]
            self.services = [
                K8sService("api", selector={"app": "api"}, port=8080, endpoints=["10.244.1.5:8080"]),
            ]
            self.service_port_wrong = True
        elif "service" in s or "endpoint" in s or "unreachable" in s:
            self.deployments = [K8sDeployment("api", selector={"app": "api"})]
            self.pods = [
                K8sPod("api-5f8c7d6b-abc12", labels={"app": "api"}, image="api:v1", owner="api"),
            ]
            self.services = [
                K8sService("api", selector={"app": "api", "version": "v2"}, endpoints=[]),
            ]
        elif "rollout" in s or "deployment-failed" in s:
            self.deployments = [K8sDeployment("web", image="web:v2", ready=0, replicas=3)]
            self.pods = [
                K8sPod("web-aaa", status="CrashLoopBackOff", ready="0/1", restarts=4, labels={"app": "web"}, image="web:v2", owner="web"),
                K8sPod("web-bbb", status="ImagePullBackOff", ready="0/1", labels={"app": "web"}, image="web:v2", owner="web"),
            ]
            self.services = [K8sService("web", selector={"app": "web"}, endpoints=[])]
            self.rollout_failed = True
        elif "loadbalancer" in s or "lb-pending" in s:
            self.deployments = [K8sDeployment("frontend", selector={"app": "frontend"})]
            self.pods = [K8sPod("frontend-xyz", labels={"app": "frontend"}, owner="frontend")]
            self.services = [K8sService("frontend", type="LoadBalancer", selector={"app": "frontend"}, endpoints=["10.244.1.5:80"])]
            self.lb_pending = True
        elif "gateway" in s:
            self.deployments = [K8sDeployment("api", selector={"app": "api"})]
            self.pods = [K8sPod("api-abc", labels={"app": "api"}, owner="api")]
            self.services = [K8sService("api", selector={"app": "api"}, endpoints=["10.244.1.5:8080"])]
            self.gateway_broken = True
        elif "network-policy" in s or "netpol" in s:
            self.deployments = [K8sDeployment("backend", selector={"app": "backend"})]
            self.pods = [K8sPod("backend-1", labels={"app": "backend"}, owner="backend")]
            self.services = [K8sService("backend", selector={"app": "backend"}, endpoints=["10.244.1.5:9090"])]
            self.netpol_blocks = True
        elif "hpa" in s or "autoscale" in s:
            self.deployments = [K8sDeployment("worker", replicas=1, ready=1)]
            self.pods = [K8sPod("worker-1", labels={"app": "worker"}, owner="worker")]
            self.services = [K8sService("worker", selector={"app": "worker"}, endpoints=["10.244.1.5:8080"])]
            self.hpa_broken = True
        else:
            self.deployments = [K8sDeployment("nginx", image="nginx:broken")]
            self.pods = [
                K8sPod(
                    "nginx-7d4b8c9f-xk2m1", status="CrashLoopBackOff", ready="0/1",
                    restarts=2, image="nginx:broken", labels={"app": "nginx"}, owner="nginx",
                )
            ]
            self.services = [K8sService("nginx", selector={"app": "nginx"}, endpoints=[])]

        # Register any seeded namespaces beyond the defaults.
        for coll in (self.pods, self.services, self.deployments, self.configmaps,
                     self.secrets, self.pvcs, self.ingresses):
            for obj in coll:
                if obj.namespace not in self.namespaces:
                    self.namespaces.append(obj.namespace)

    # ------------------------------------------------------------------
    # Cross-technology Kubernetes-on-VMware seeding
    # ------------------------------------------------------------------

    def _apply_cross_tech_k8s(self, s: str) -> bool:
        """Seed the broken state for a k8s-on-VMware cross-tech scenario.

        Returns True if `s` is one of these scenarios (so _apply_scenario stops).
        Every variant is fail-closed: capacity is short / a node is down until
        the learner performs the VMware VM action, which sync_from_vmware_bridge
        folds back in. The worker node that the missing VMware VM represents is
        recorded in self._xtech (node name + the broken condition).
        """
        self._xtech: dict | None = None

        if s == "k8s-hpa-needs-new-node-vmware":
            # A single worker is at capacity; the HPA wants 4 replicas but the
            # extra pods cannot schedule (Insufficient cpu) until worker-2 joins.
            self.nodes = [
                K8sNode("master-1", roles=["control-plane"]),
                K8sNode("worker-1", roles=[]),
            ]
            self.deployments = [K8sDeployment("web", replicas=4, ready=2)]
            self.pods = [
                K8sPod("web-aaaa1", labels={"app": "web"}, node="worker-1", owner="web"),
                K8sPod("web-aaaa2", labels={"app": "web"}, node="worker-1", owner="web"),
                K8sPod("web-aaaa3", status="Pending", ready="0/1", node="<none>",
                       labels={"app": "web"}, owner="web",
                       events=["Warning FailedScheduling: 0/2 nodes are available: "
                               "1 Insufficient cpu, 1 node(s) had untolerated taint."]),
                K8sPod("web-aaaa4", status="Pending", ready="0/1", node="<none>",
                       labels={"app": "web"}, owner="web",
                       events=["Warning FailedScheduling: 0/2 nodes are available: "
                               "1 Insufficient cpu, 1 node(s) had untolerated taint."]),
            ]
            self.services = [K8sService("web", selector={"app": "web"}, endpoints=["10.244.1.5:8080"])]
            self.hpas = [K8sHPA("web", target="Deployment/web", min_replicas=1,
                                max_replicas=6, target_cpu=50, current_cpu=85,
                                current_replicas=2, desired_replicas=4)]
            self._xtech = {"node": "worker-2", "kind": "add", "deployment": "web"}
            return True

        if s == "k8s-scale-out-add-vmware-node":
            # The learner scaled web to 4, but only worker-1 exists → 2 Pending.
            self.nodes = [
                K8sNode("master-1", roles=["control-plane"]),
                K8sNode("worker-1", roles=[]),
            ]
            self.deployments = [K8sDeployment("api", replicas=4, ready=2)]
            self.pods = [
                K8sPod("api-bbbb1", labels={"app": "api"}, node="worker-1", owner="api"),
                K8sPod("api-bbbb2", labels={"app": "api"}, node="worker-1", owner="api"),
                K8sPod("api-bbbb3", status="Pending", ready="0/1", node="<none>",
                       labels={"app": "api"}, owner="api",
                       events=["Warning FailedScheduling: 0/2 nodes are available: "
                               "1 Insufficient cpu, 1 Insufficient memory."]),
                K8sPod("api-bbbb4", status="Pending", ready="0/1", node="<none>",
                       labels={"app": "api"}, owner="api",
                       events=["Warning FailedScheduling: 0/2 nodes are available: "
                               "1 Insufficient cpu, 1 Insufficient memory."]),
            ]
            self.services = [K8sService("api", selector={"app": "api"}, endpoints=["10.244.1.5:8080"])]
            self._xtech = {"node": "worker-2", "kind": "add", "deployment": "api"}
            return True

        if s == "k8s-daemonset-needs-node-vmware":
            # A DaemonSet should run one pod per node. worker-2's VM is powered
            # off, so its DaemonSet pod is Pending until the VM is powered on.
            self.nodes = [
                K8sNode("master-1", roles=["control-plane"]),
                K8sNode("worker-1", roles=[]),
            ]
            self.daemonsets = [K8sDaemonSet("node-agent", selector={"app": "node-agent"})]
            self.deployments = []
            self.pods = [
                K8sPod("node-agent-cccc1", labels={"app": "node-agent"}, node="worker-1", owner="node-agent"),
                K8sPod("node-agent-cccc2", status="Pending", ready="0/1", node="<none>",
                       labels={"app": "node-agent"}, owner="node-agent",
                       events=["Warning FailedScheduling: 0/2 nodes are available: "
                               "1 node(s) didn't match Pod's node affinity (worker-2 NotReady/absent)."]),
            ]
            self.services = []
            self._xtech = {"node": "worker-2", "kind": "add", "daemonset": "node-agent"}
            return True

        if s == "k8s-node-notready-vmware-reset":
            # worker-1's VM is hung → the node is NotReady and its pod stranded.
            # vm_hung marks it un-recoverable from kubectl (only a VMware reset).
            self.nodes = [
                K8sNode("master-1", roles=["control-plane"]),
                K8sNode("worker-1", status="NotReady", roles=[], schedulable=True, vm_hung=True),
            ]
            self.deployments = [K8sDeployment("payments", replicas=2, ready=1)]
            self.pods = [
                K8sPod("payments-dddd1", labels={"app": "payments"}, node="master-1", owner="payments"),
                K8sPod("payments-dddd2", status="Pending", ready="0/1", node="<none>",
                       labels={"app": "payments"}, owner="payments",
                       events=["Warning FailedScheduling: 0/2 nodes are available: "
                               "1 node(s) were unschedulable, 1 node(s) had taint "
                               "{node.kubernetes.io/not-ready}."]),
            ]
            self.services = [K8sService("payments", selector={"app": "payments"}, endpoints=["10.244.1.5:8080"])]
            self._xtech = {"node": "worker-1", "kind": "reset", "deployment": "payments"}
            return True

        if s == "k8s-drain-node-poweroff-vmware":
            # Maintenance flow: worker-1 must be drained (cordoned + evicted) and
            # its VM powered off, while a NEW worker-2 VM is powered on to host the
            # rescheduled pods. Fail-closed until worker-1 is unschedulable AND
            # worker-2 is online AND no pod is left Pending.
            self.nodes = [
                K8sNode("master-1", roles=["control-plane"]),
                K8sNode("worker-1", roles=[]),
            ]
            self.deployments = [K8sDeployment("billing", replicas=3, ready=3)]
            self.pods = [
                K8sPod("billing-eeee1", labels={"app": "billing"}, node="worker-1", owner="billing"),
                K8sPod("billing-eeee2", labels={"app": "billing"}, node="worker-1", owner="billing"),
                K8sPod("billing-eeee3", labels={"app": "billing"}, node="worker-1", owner="billing"),
            ]
            self.services = [K8sService("billing", selector={"app": "billing"}, endpoints=["10.244.1.5:8080"])]
            self._xtech = {"node": "worker-2", "kind": "drain", "deployment": "billing",
                           "drain_node": "worker-1"}
            return True

        return False

    def sync_from_vmware_bridge(self) -> None:
        """Fold VMware VM node actions (from the shared bridge cache) into node state.

        This is what makes a node powered-on/created/reset in the VMware simulator
        appear Ready in this terminal's `kubectl get nodes`, and lets the stranded
        pods schedule onto it. Safe no-op for non-cross-tech clusters or when no
        VMware action has happened yet (fail-closed).
        """
        xt = getattr(self, "_xtech", None)
        if not xt or not self.session_id:
            return
        try:
            from .vmware_bridge import k8s_node_states
        except Exception:
            return
        states = k8s_node_states(self.session_id)
        node_name = xt["node"]
        online = bool(states.get("online", {}).get(node_name))
        was_reset = bool(states.get("reset", {}).get(node_name))

        if xt["kind"] == "reset":
            # The hung node's VM was reset → the existing node's kubelet recovers.
            if was_reset or online:
                node = self.find_node(node_name)
                if node:
                    node.vm_hung = False
                    node.status = "Ready"
                    node.schedulable = True
                self._schedule_pending_pods()
            return

        # add / drain kinds: a fresh worker VM was powered on / created → join it.
        if online:
            if not self.find_node(node_name):
                self.nodes.append(K8sNode(node_name, roles=[]))
            else:
                n = self.find_node(node_name)
                n.status, n.schedulable = "Ready", True

        if xt["kind"] == "drain":
            # In the drain flow the original node is taken out of service. We only
            # cordon it here if the learner already cordoned/drained it (we never
            # auto-cordon); pods land on worker-2 once it is online.
            self._schedule_pending_pods()
            return

        if online:
            self._schedule_pending_pods()

    def _schedule_pending_pods(self) -> None:
        """Place any Pending pods onto the first Ready, schedulable worker node.

        Mirrors the kube-scheduler: a Pending pod only runs once there is a node
        with capacity. We model capacity as "a Ready, schedulable node other than
        the control-plane that is not the drained node."
        """
        targets = self._worker_nodes()
        if not targets:
            return
        changed = False
        for p in self.pods:
            if p.status != "Pending":
                continue
            node = self._pick_node_for(p.owner)
            p.status = "Running"
            p.ready = "1/1"
            p.node = node
            p.events = []
            changed = True
        # Reconcile deployment ready counts + HPA observed replicas.
        for dep in self.deployments:
            dep.ready = sum(1 for p in self.pods if p.owner == dep.name and p.status == "Running")
        for hpa in self.hpas:
            running = sum(1 for p in self.pods if p.owner == hpa.target.split("/")[-1]
                          and p.status == "Running")
            hpa.current_replicas = running or hpa.current_replicas
        if changed:
            self._sync_endpoints()

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def _ns_match(self, obj: Any, namespace: str, all_ns: bool) -> bool:
        if all_ns:
            return True
        return getattr(obj, "namespace", "default") == namespace

    def find_pod(self, name: str) -> K8sPod | None:
        return next((p for p in self.pods if p.name == name), None) or \
            next((p for p in self.pods if name and name in p.name), None)

    def find_deployment(self, name: str) -> K8sDeployment | None:
        name = name.split("/")[-1]
        return next((d for d in self.deployments if d.name == name), None) or \
            next((d for d in self.deployments if name and name in d.name), None)

    def find_service(self, name: str) -> K8sService | None:
        return next((s for s in self.services if s.name == name), None)

    def find_node(self, name: str) -> K8sNode | None:
        return next((n for n in self.nodes if n.name == name), None)

    def find_hpa(self, name: str) -> K8sHPA | None:
        return next((h for h in self.hpas if h.name == name), None) or \
            (self.hpas[0] if self.hpas else None)

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    def get_pods(self, namespace: str = "default", all_ns: bool = False, wide: bool = False) -> str:
        header = "NAMESPACE   " if all_ns else ""
        cols = "NAME                     READY   STATUS             RESTARTS   AGE"
        if wide:
            cols += "     IP            NODE"
        lines = [header + cols]
        rows = [p for p in self.pods if self._ns_match(p, namespace, all_ns)]
        if not rows:
            return "No resources found in {} namespace.".format(namespace if not all_ns else "any")
        for p in rows:
            prefix = f"{p.namespace:<11} " if all_ns else ""
            row = f"{p.name:<24} {p.ready:<7} {p.status:<18} {p.restarts:<10} {p.age}"
            if wide:
                row += f"     {p.ip:<13} {p.node}"
            lines.append(prefix + row)
        return "\n".join(lines)

    def get_nodes(self, wide: bool = False) -> str:
        lines = ["NAME       STATUS                     ROLES           AGE   VERSION"]
        for n in self.nodes:
            roles = ",".join(n.roles) if n.roles else "<none>"
            status = n.status + (",SchedulingDisabled" if not n.schedulable else "")
            lines.append(f"{n.name:<10} {status:<26} {roles:<15} 30d   {n.version}")
        return "\n".join(lines)

    def get_services(self, namespace: str = "default", all_ns: bool = False) -> str:
        lines = ["NAME         TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)       AGE"]
        rows = [s for s in self.services if self._ns_match(s, namespace, all_ns)]
        for s in rows:
            ext = s.external_ip or ("<pending>" if s.type == "LoadBalancer" and not s.external_ip else "<none>")
            ports = f"{s.port}/TCP"
            if s.node_port:
                ports = f"{s.port}:{s.node_port}/TCP"
            lines.append(
                f"{s.name:<12} {s.type:<14} {s.cluster_ip:<15} {ext:<14} {ports:<13} 1h"
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

    def get_deployments(self, namespace: str = "default", all_ns: bool = False) -> str:
        lines = ["NAME       READY   UP-TO-DATE   AVAILABLE   AGE"]
        rows = [d for d in self.deployments if self._ns_match(d, namespace, all_ns)]
        for d in rows:
            ready = f"{d.ready}/{d.replicas}"
            lines.append(f"{d.name:<10} {ready:<7} {d.replicas:<12} {d.ready:<11} 1h")
        return "\n".join(lines)

    def get_replicasets(self, namespace: str = "default") -> str:
        lines = ["NAME                 DESIRED   CURRENT   READY   AGE"]
        for d in self.deployments:
            if d.namespace != namespace:
                continue
            rs = f"{d.name}-{abs(hash(d.name)) % 10000000:07d}"
            lines.append(f"{rs:<20} {d.replicas:<9} {d.replicas:<9} {d.ready:<7} 1h")
        return "\n".join(lines)

    def get_configmaps(self, namespace: str = "default") -> str:
        lines = ["NAME         DATA   AGE"]
        for cm in self.configmaps:
            if cm.namespace != namespace:
                continue
            lines.append(f"{cm.name:<12} {len(cm.data):<6} 1h")
        if len(lines) == 1:
            return f"No resources found in {namespace} namespace."
        return "\n".join(lines)

    def get_secrets(self, namespace: str = "default") -> str:
        lines = ["NAME         TYPE      DATA   AGE"]
        for sec in self.secrets:
            if sec.namespace != namespace:
                continue
            lines.append(f"{sec.name:<12} {sec.type:<9} {len(sec.data):<6} 1h")
        if len(lines) == 1:
            return f"No resources found in {namespace} namespace."
        return "\n".join(lines)

    def get_pvcs(self, namespace: str = "default") -> str:
        lines = ["NAME         STATUS    VOLUME    CAPACITY   ACCESS MODES   STORAGECLASS   AGE"]
        for pvc in self.pvcs:
            if pvc.namespace != namespace:
                continue
            vol = pvc.volume or ""
            cap = pvc.capacity if pvc.status == "Bound" else ""
            modes = ",".join(pvc.access_modes) if pvc.status == "Bound" else ""
            lines.append(
                f"{pvc.name:<12} {pvc.status:<9} {vol:<9} {cap:<10} {modes:<14} {pvc.storage_class:<14} 1h"
            )
        if len(lines) == 1:
            return f"No resources found in {namespace} namespace."
        return "\n".join(lines)

    def get_ingresses(self, namespace: str = "default") -> str:
        lines = ["NAME    CLASS   HOSTS                ADDRESS   PORTS   AGE"]
        for ing in self.ingresses:
            if ing.namespace != namespace:
                continue
            hosts = ",".join(ing.hosts)
            addr = "" if getattr(self, "ingress_broken", False) else "203.0.113.10"
            lines.append(f"{ing.name:<7} {ing.class_name:<7} {hosts:<20} {addr:<9} 80      1h")
        if len(lines) == 1:
            return f"No resources found in {namespace} namespace."
        return "\n".join(lines)

    def get_namespaces(self) -> str:
        lines = ["NAME              STATUS   AGE"]
        for ns in self.namespaces:
            lines.append(f"{ns:<17} Active   30d")
        return "\n".join(lines)

    def get_hpa(self, namespace: str = "default") -> str:
        if not self.hpas:
            return f"No resources found in {namespace} namespace."
        lines = ["NAME   REFERENCE             TARGETS         MINPODS   MAXPODS   REPLICAS   AGE"]
        for h in self.hpas:
            if h.namespace != namespace:
                continue
            targets = f"cpu: {h.current_cpu}%/{h.target_cpu}%"
            lines.append(
                f"{h.name:<6} {h.target:<21} {targets:<15} {h.min_replicas:<9} "
                f"{h.max_replicas:<9} {h.current_replicas:<10} 1h"
            )
        return "\n".join(lines)

    def get_daemonsets(self, namespace: str = "default") -> str:
        if not self.daemonsets:
            return f"No resources found in {namespace} namespace."
        lines = ["NAME         DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   AGE"]
        ready_nodes = sum(1 for n in self.nodes if n.status == "Ready" and "control-plane" not in n.roles)
        for ds in self.daemonsets:
            if ds.namespace != namespace:
                continue
            running = sum(1 for p in self.pods if p.owner == ds.name and p.status == "Running")
            lines.append(
                f"{ds.name:<12} {ready_nodes:<9} {running:<9} {running:<7} "
                f"{running:<12} {running:<11} 1h"
            )
        return "\n".join(lines)

    def describe_hpa(self, name: str) -> str:
        h = self.find_hpa(name)
        if not h:
            return f"Error from server (NotFound): horizontalpodautoscalers.autoscaling \"{name}\" not found"
        able = h.current_replicas >= h.desired_replicas
        cond = ("AbleToScale True" if able else "AbleToScale False  FailedGetScale / pods Pending")
        return (
            f"Name:                                                  {h.name}\n"
            f"Namespace:                                             {h.namespace}\n"
            f"Reference:                                             {h.target}\n"
            f"Metrics:                                               "
            f"( current / target )\n"
            f"  resource cpu on pods  (as a percentage of request):  {h.current_cpu}% / {h.target_cpu}%\n"
            f"Min replicas:                                          {h.min_replicas}\n"
            f"Max replicas:                                          {h.max_replicas}\n"
            f"Deployment pods:                                       "
            f"{h.current_replicas} current / {h.desired_replicas} desired\n"
            f"Conditions:\n  {cond}\n"
            + ("" if able else
               "Events:\n  Warning  FailedScheduling  insufficient cluster capacity — add a worker node\n")
        )

    def get_events(self, namespace: str = "default", all_ns: bool = False) -> str:
        lines = ["LAST SEEN   TYPE      REASON      OBJECT                MESSAGE"]
        any_event = False
        for p in self.pods:
            if not (all_ns or p.namespace == namespace):
                continue
            for e in p.events:
                any_event = True
                etype = "Warning" if e.startswith("Warning") else "Normal"
                msg = e.split(":", 1)[-1].strip() if ":" in e else e
                reason = e.split()[1].rstrip(":") if len(e.split()) > 1 else "Event"
                lines.append(f"2m          {etype:<9} {reason:<11} pod/{p.name:<18} {msg}")
        if not any_event:
            lines.append("2m          Normal    Scheduled   cluster               No recent warning events")
        return "\n".join(lines)

    def get_all(self, namespace: str = "default") -> str:
        out = []
        if any(p.namespace == namespace for p in self.pods):
            out.append("\n".join("pod/" + line for line in self.get_pods(namespace).splitlines()[1:]))
        if any(s.namespace == namespace for s in self.services):
            out.append(self.get_services(namespace))
        if any(d.namespace == namespace for d in self.deployments):
            out.append(self.get_deployments(namespace))
        return "\n".join(filter(None, out)) or f"No resources found in {namespace} namespace."

    # ------------------------------------------------------------------
    # -o yaml output
    # ------------------------------------------------------------------

    def pod_yaml(self, name: str) -> str:
        pod = self.find_pod(name)
        if not pod:
            return f"Error from server (NotFound): pods \"{name}\" not found"
        labels = "\n".join(f"    {k}: {v}" for k, v in pod.labels.items()) or "    {}"
        return (
            "apiVersion: v1\n"
            "kind: Pod\n"
            "metadata:\n"
            f"  name: {pod.name}\n"
            f"  namespace: {pod.namespace}\n"
            "  labels:\n"
            f"{labels}\n"
            "spec:\n"
            "  containers:\n"
            f"  - name: {pod.containers[0] if pod.containers else 'app'}\n"
            f"    image: {pod.image}\n"
            "status:\n"
            f"  phase: {pod.status}\n"
            f"  podIP: {pod.ip}\n"
        )

    def deployment_yaml(self, name: str) -> str:
        dep = self.find_deployment(name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{name}\" not found"
        sel = "\n".join(f"      {k}: {v}" for k, v in dep.selector.items())
        return (
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            f"  name: {dep.name}\n"
            f"  namespace: {dep.namespace}\n"
            "spec:\n"
            f"  replicas: {dep.replicas}\n"
            "  selector:\n"
            "    matchLabels:\n"
            f"{sel}\n"
            "  template:\n"
            "    spec:\n"
            "      containers:\n"
            f"      - name: {dep.name}\n"
            f"        image: {dep.image}\n"
            "status:\n"
            f"  replicas: {dep.replicas}\n"
            f"  readyReplicas: {dep.ready}\n"
        )

    # ------------------------------------------------------------------
    # describe
    # ------------------------------------------------------------------

    def describe_pod(self, name: str) -> str:
        pod = self.find_pod(name)
        if not pod:
            return f"Error from server (NotFound): pods \"{name}\" not found"
        events = "\n".join(f"  {e}" for e in pod.events) or "  Normal  Started  kubelet  Started container"
        labels = ",".join(f"{k}={v}" for k, v in pod.labels.items()) or "<none>"
        return (
            f"Name:         {pod.name}\n"
            f"Namespace:    {pod.namespace}\n"
            f"Node:         {pod.node}\n"
            f"Labels:       {labels}\n"
            f"Status:       {pod.status}\n"
            f"IP:           {pod.ip}\n"
            f"Containers:\n"
            f"  {pod.containers[0] if pod.containers else 'app'}:\n"
            f"    Image:    {pod.image}\n"
            f"    Restart Count:  {pod.restarts}\n"
            f"Events:\n{events}"
        )

    def describe_deployment(self, name: str) -> str:
        dep = self.find_deployment(name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{name}\" not found"
        sel = ",".join(f"{k}={v}" for k, v in dep.selector.items())
        return (
            f"Name:                   {dep.name}\n"
            f"Namespace:              {dep.namespace}\n"
            f"Selector:               {sel}\n"
            f"Replicas:               {dep.replicas} desired | {dep.replicas} updated | "
            f"{dep.replicas} total | {dep.ready} available | {dep.replicas - dep.ready} unavailable\n"
            f"StrategyType:           RollingUpdate\n"
            f"Pod Template:\n"
            f"  Containers:\n"
            f"   {dep.name}:\n"
            f"    Image:        {dep.image}\n"
        )

    def describe_node(self, name: str) -> str:
        node = self.find_node(name)
        if not node:
            return f"Error from server (NotFound): nodes \"{name}\" not found"
        roles = ",".join(node.roles) if node.roles else "<none>"
        taints = "<none>" if node.schedulable else "node.kubernetes.io/unschedulable:NoSchedule"
        pods_here = [p.name for p in self.pods if p.node == node.name]
        return (
            f"Name:               {node.name}\n"
            f"Roles:              {roles}\n"
            f"Taints:             {taints}\n"
            f"Unschedulable:      {not node.schedulable}\n"
            f"Conditions:\n"
            f"  Ready   {'True' if node.status == 'Ready' else 'False'}\n"
            f"Non-terminated Pods: ({len(pods_here)} in total)\n"
            + "\n".join(f"  default   {n}" for n in pods_here)
        )

    def describe_service(self, name: str) -> str:
        svc = self.find_service(name)
        if not svc:
            return f"Error from server (NotFound): services \"{name}\" not found"
        sel = ",".join(f"{k}={v}" for k, v in svc.selector.items())
        eps = ",".join(svc.endpoints) if svc.endpoints else "<none>"
        return (
            f"Name:              {svc.name}\n"
            f"Namespace:         {svc.namespace}\n"
            f"Type:              {svc.type}\n"
            f"Selector:          {sel}\n"
            f"IP:                {svc.cluster_ip}\n"
            f"Port:              <unset>  {svc.port}/TCP\n"
            f"TargetPort:        {svc.target_port}/TCP\n"
            f"Endpoints:         {eps}\n"
        )

    # ------------------------------------------------------------------
    # logs / exec
    # ------------------------------------------------------------------

    def logs(self, name: str, previous: bool = False) -> str:
        pod = self.find_pod(name)
        if not pod:
            return f"Error from server (NotFound): pods \"{name}\" not found"
        if pod.status in ("CrashLoopBackOff", "Error"):
            return (
                "Error from server (BadRequest): container has crashed\n"
                "panic: configuration invalid: missing required value\n"
                "  goroutine 1 [running]:\n"
                "  main.main()"
            )
        if pod.status == "ImagePullBackOff":
            return f"Error from server: failed to pull image \"{pod.image}\": not found"
        if pod.status in ("Pending", "ContainerCreating", "CreateContainerConfigError"):
            return f"Error from server (BadRequest): container \"{pod.containers[0] if pod.containers else 'app'}\" in pod \"{pod.name}\" is waiting to start"
        prefix = "(previous) " if previous else ""
        return (
            f"{prefix}[INFO] starting {pod.containers[0] if pod.containers else 'app'}\n"
            f"[INFO] listening on :8080\n"
            f"[INFO] ready to serve requests"
        )

    def exec_pod(self, name: str, cmd: str) -> str:
        pod = self.find_pod(name)
        if not pod:
            return f"Error from server (NotFound): pods \"{name}\" not found"
        if pod.status != "Running":
            return (
                "error: unable to upgrade connection: container not found "
                f"(\"{pod.containers[0] if pod.containers else 'app'}\")"
            )
        cmd_low = cmd.strip().lower()
        if not cmd_low or cmd_low in ("sh", "bash", "/bin/sh", "/bin/bash", "-it", "-ti", "-i", "-t"):
            return f"/ # (interactive shell on {pod.name}; type 'exit' to return)"
        if cmd_low.startswith("ls"):
            return "bin  dev  etc  home  proc  root  sys  tmp  usr  var"
        if cmd_low.startswith("hostname"):
            return pod.name
        if cmd_low.startswith("cat /etc/hostname"):
            return pod.name
        if cmd_low.startswith("env"):
            return "PATH=/usr/local/bin:/usr/bin\nHOSTNAME=" + pod.name
        if cmd_low.startswith("ps"):
            return "PID   USER     COMMAND\n    1 root     /app"
        if cmd_low.startswith("whoami") or cmd_low == "id":
            return "root"
        return f"(exec on {pod.name}) {cmd}"

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def delete_pod(self, name: str) -> str:
        for i, p in enumerate(self.pods):
            if p.name == name or name in p.name:
                self.pods.pop(i)
                # Recreate from owning deployment if there is one.
                dep = next((d for d in self.deployments if d.name == p.owner), None) or \
                    next((d for d in self.deployments if d.name in name), None)
                if dep:
                    if "broken" in dep.image:
                        dep.image = dep.image.replace("broken", "latest")
                    new_name = f"{dep.name}-{abs(hash(name)) % 100000:05d}"
                    healthy = "broken" not in dep.image and "missing" not in dep.image
                    self.pods.append(K8sPod(
                        new_name,
                        namespace=dep.namespace,
                        status="Running" if healthy else "CrashLoopBackOff",
                        ready="1/1" if healthy else "0/1",
                        image=dep.image,
                        labels=dict(dep.selector),
                        owner=dep.name,
                    ))
                    self._sync_endpoints()
                return f'pod "{name}" deleted'
        return f"Error from server (NotFound): pods \"{name}\" not found"

    def delete_resource(self, kind: str, name: str) -> str:
        kind = kind.lower().rstrip("s")
        if kind in ("pod", "po"):
            return self.delete_pod(name)
        mapping = {
            "deployment": self.deployments, "deploy": self.deployments,
            "service": self.services, "svc": self.services,
            "configmap": self.configmaps, "cm": self.configmaps,
            "secret": self.secrets,
            "pvc": self.pvcs, "persistentvolumeclaim": self.pvcs,
            "ingress": self.ingresses, "ing": self.ingresses,
        }
        coll = mapping.get(kind)
        if coll is None:
            return f"error: the server doesn't have a resource type \"{kind}\""
        for i, obj in enumerate(coll):
            if obj.name == name:
                coll.pop(i)
                if kind in ("deployment", "deploy"):
                    self.pods = [p for p in self.pods if p.owner != name]
                self._sync_endpoints()
                kn = {"deployment": "deployment.apps", "deploy": "deployment.apps"}.get(kind, kind)
                return f'{kn} "{name}" deleted'
        return f"Error from server (NotFound): {kind} \"{name}\" not found"

    def scale(self, dep_name: str, replicas: int) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        replicas = max(0, replicas)
        old = dep.replicas
        dep.replicas = replicas
        existing = [p for p in self.pods if p.owner == dep.name]
        healthy = "broken" not in dep.image and "missing" not in dep.image
        # Cross-tech k8s-on-VMware clusters model finite node capacity: a pod that
        # exceeds it starts Pending (FailedScheduling) until a worker VM is added in
        # VMware. Other scenarios keep the original always-schedulable behaviour.
        capacity_bound = getattr(self, "_xtech", None) is not None
        if replicas > len(existing):
            for i in range(replicas - len(existing)):
                schedulable = healthy and (not capacity_bound or self._has_free_capacity(dep.name))
                node = self._pick_node_for(dep.name) if schedulable else "<none>"
                status = ("Running" if schedulable else
                          ("Pending" if capacity_bound else "CrashLoopBackOff"))
                self.pods.append(K8sPod(
                    f"{dep.name}-{abs(hash(dep.name + str(i) + str(len(self.pods)))) % 100000:05d}",
                    namespace=dep.namespace,
                    status=status,
                    ready="1/1" if status == "Running" else "0/1",
                    image=dep.image, labels=dict(dep.selector), owner=dep.name,
                    node=node,
                    events=([] if status != "Pending" else
                            ["Warning FailedScheduling: 0/{} nodes are available: "
                             "Insufficient cpu.".format(len(self.nodes))]),
                ))
        elif replicas < len(existing):
            # Evict surplus pods; drop the Pending ones first (closest to real kube).
            existing.sort(key=lambda p: 0 if p.status == "Pending" else 1)
            remove = [p.name for p in existing[: len(existing) - replicas]]
            self.pods = [p for p in self.pods if p.name not in remove]
        dep.ready = sum(1 for p in self.pods if p.owner == dep.name and p.status == "Running")
        self._sync_endpoints()
        return f"deployment.apps/{dep.name} scaled"

    def _worker_nodes(self) -> list[K8sNode]:
        return [n for n in self.nodes
                if n.status == "Ready" and n.schedulable and not n.vm_hung
                and "control-plane" not in n.roles]

    def _has_free_capacity(self, owner: str, per_node: int = 2) -> bool:
        """True if some Ready worker node hosts fewer than per_node pods of owner."""
        for node in self._worker_nodes():
            here = sum(1 for p in self.pods
                       if p.node == node.name and p.status == "Running" and p.owner == owner)
            if here < per_node:
                return True
        return False

    def _pick_node_for(self, owner: str, per_node: int = 2) -> str:
        for node in self._worker_nodes():
            here = sum(1 for p in self.pods
                       if p.node == node.name and p.status == "Running" and p.owner == owner)
            if here < per_node:
                return node.name
        wn = self._worker_nodes()
        return wn[0].name if wn else "worker-1"

    def autoscale(self, dep_name: str, min_r: int, max_r: int, cpu: int) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        existing = self.find_hpa(dep_name)
        if existing and existing.name == dep_name:
            return f"Error from server (AlreadyExists): horizontalpodautoscalers.autoscaling \"{dep_name}\" already exists"
        running = sum(1 for p in self.pods if p.owner == dep.name and p.status == "Running")
        self.hpas.append(K8sHPA(
            dep.name, namespace=dep.namespace, target=f"Deployment/{dep.name}",
            min_replicas=max(1, min_r), max_replicas=max(min_r, max_r),
            target_cpu=cpu, current_cpu=85, current_replicas=running or 1,
            desired_replicas=min(max_r, max(min_r, dep.replicas)),
        ))
        return f"horizontalpodautoscaler.autoscaling/{dep.name} autoscaled"

    def set_image(self, dep_name: str, image: str) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        dep.history.append({"revision": dep.revision, "image": dep.image})
        dep.revision += 1
        dep.image = image
        healthy = "broken" not in image and "missing" not in image
        for p in self.pods:
            if p.owner == dep.name:
                p.image = image
                p.status = "Running" if healthy else p.status
                p.ready = "1/1" if healthy else p.ready
        dep.ready = sum(1 for p in self.pods if p.owner == dep.name and p.status == "Running")
        if healthy:
            self.service_port_wrong = getattr(self, "service_port_wrong", False)
            self.rollout_failed = False
        self._sync_endpoints()
        return f"deployment.apps/{dep.name} image updated"

    def rollout_restart(self, dep_name: str) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        if "broken" in dep.image or "v2" in dep.image or "missing" in dep.image:
            dep.image = dep.image.replace("broken", "latest").replace(":v2", ":v1").replace("missing-tag", "v1")
        dep.revision += 1
        dep.ready = dep.replicas
        self.rollout_failed = False
        # Replace owned pods with fresh running ones.
        kept = [p for p in self.pods if p.owner != dep.name]
        self.pods = kept
        for i in range(dep.replicas):
            self.pods.append(K8sPod(
                f"{dep.name}-{abs(hash(dep.name + 'restart' + str(i))) % 100000:05d}",
                namespace=dep.namespace, status="Running", ready="1/1",
                image=dep.image, labels=dict(dep.selector), owner=dep.name,
            ))
        self._sync_endpoints()
        return f"deployment.apps/{dep.name} restarted"

    def rollout_undo(self, dep_name: str) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        if dep.history:
            prev = dep.history.pop()
            dep.image = prev.get("image", dep.image)
        dep.revision += 1
        self.rollout_failed = False
        return self.rollout_restart(dep.name).replace("restarted", "rolled back")

    def rollout_status(self, dep_name: str) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        if dep.ready < dep.replicas or getattr(self, "rollout_failed", False):
            return (
                f"Waiting for deployment \"{dep.name}\" rollout to finish: "
                f"{dep.ready} of {dep.replicas} updated replicas are available..."
            )
        return f"deployment \"{dep.name}\" successfully rolled out"

    def rollout_history(self, dep_name: str) -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        lines = [f"deployment.apps/{dep.name}", "REVISION  CHANGE-CAUSE"]
        for h in dep.history:
            lines.append(f"{h['revision']:<9} <none>")
        lines.append(f"{dep.revision:<9} <none>")
        return "\n".join(lines)

    def cordon(self, node_name: str) -> str:
        node = self.find_node(node_name)
        if not node:
            return f"Error from server (NotFound): nodes \"{node_name}\" not found"
        node.schedulable = False
        return f"node/{node.name} cordoned"

    def uncordon(self, node_name: str) -> str:
        node = self.find_node(node_name)
        if not node:
            # Common scenario: uncordon the NotReady worker without naming it.
            node = next((n for n in self.nodes if n.status == "NotReady" or not n.schedulable), None)
            if not node:
                return f"Error from server (NotFound): nodes \"{node_name}\" not found"
        node.schedulable = True
        # A node whose VM is hung cannot be brought back by uncordon — its kubelet
        # is dead. Only a VMware reset (the bridge) clears vm_hung and revives it.
        if node.status == "NotReady" and not node.vm_hung:
            node.status = "Ready"
        return f"node/{node.name} uncordoned"

    def drain(self, node_name: str) -> str:
        node = self.find_node(node_name)
        if not node:
            return f"Error from server (NotFound): nodes \"{node_name}\" not found"
        node.schedulable = False
        evicted = [p.name for p in self.pods if p.node == node.name]
        # Reschedule evicted pods onto another node.
        other = next((n for n in self.nodes if n.name != node.name and n.schedulable), None)
        for p in self.pods:
            if p.node == node.name and other:
                p.node = other.name
        out = [f"node/{node.name} cordoned"]
        for e in evicted:
            out.append(f"evicting pod default/{e}")
        out.append(f"node/{node.name} drained")
        return "\n".join(out)

    def label(self, kind: str, name: str, key: str, value: str | None) -> str:
        obj = self._resource_for(kind, name)
        if obj is None:
            return f"Error from server (NotFound): {kind} \"{name}\" not found"
        labels = getattr(obj, "labels", None)
        if labels is None:
            return f"error: {kind} does not support labels"
        if value is None:
            labels.pop(key, None)
        else:
            labels[key] = value
        self._sync_endpoints()
        return f"{kind}/{name} labeled"

    def annotate(self, kind: str, name: str, key: str, value: str | None) -> str:
        obj = self._resource_for(kind, name)
        if obj is None:
            return f"Error from server (NotFound): {kind} \"{name}\" not found"
        ann = getattr(obj, "annotations", None)
        if ann is None:
            return f"error: {kind} does not support annotations"
        if value is None:
            ann.pop(key, None)
        else:
            ann[key] = value
        return f"{kind}/{name} annotated"

    def _resource_for(self, kind: str, name: str) -> Any:
        kind = kind.lower().rstrip("s")
        if kind in ("pod", "po"):
            return self.find_pod(name)
        if kind in ("deployment", "deploy"):
            return self.find_deployment(name)
        if kind in ("service", "svc"):
            return self.find_service(name)
        if kind == "node":
            return self.find_node(name)
        return None

    def patch_service_selector(self, svc_name: str, selector: dict[str, str]) -> str:
        svc = self.find_service(svc_name)
        if not svc:
            return f"Error from server (NotFound): services \"{svc_name}\" not found"
        svc.selector = selector
        self._sync_endpoints()
        return f"service/{svc_name} patched"

    def expose(self, dep_name: str, port: int, svc_type: str = "ClusterIP") -> str:
        dep = self.find_deployment(dep_name)
        if not dep:
            return f"Error from server (NotFound): deployments.apps \"{dep_name}\" not found"
        if self.find_service(dep_name):
            return f"Error from server (AlreadyExists): services \"{dep_name}\" already exists"
        svc = K8sService(
            dep_name, namespace=dep.namespace, type=svc_type, port=port,
            target_port=port, selector=dict(dep.selector),
            cluster_ip=f"10.96.0.{len(self.services) + 2}",
        )
        self.services.append(svc)
        self._sync_endpoints()
        return f"service/{dep_name} exposed"

    def run_pod(self, name: str, image: str) -> str:
        if self.find_pod(name):
            return f"Error from server (AlreadyExists): pods \"{name}\" already exists"
        self.pods.append(K8sPod(
            name, status="Running", ready="1/1", image=image,
            labels={"run": name}, owner="",
        ))
        return f"pod/{name} created"

    def create_namespace(self, name: str) -> str:
        if name in self.namespaces:
            return f"Error from server (AlreadyExists): namespaces \"{name}\" already exists"
        self.namespaces.append(name)
        return f"namespace/{name} created"

    def create_configmap(self, name: str, namespace: str, data: dict[str, str]) -> str:
        existing = next((c for c in self.configmaps if c.name == name and c.namespace == namespace), None)
        if existing:
            existing.data.update(data)
        else:
            self.configmaps.append(K8sConfigMap(name, namespace, data))
        # A configmap that pods were waiting on may unblock them.
        for p in self.pods:
            if p.status == "CreateContainerConfigError":
                p.status = "Running"
                p.ready = "1/1"
        self._sync_endpoints()
        return f"configmap/{name} created"

    def create_secret(self, name: str, namespace: str, data: dict[str, str], stype: str = "Opaque") -> str:
        existing = next((s for s in self.secrets if s.name == name and s.namespace == namespace), None)
        if existing:
            existing.data.update(data)
        else:
            self.secrets.append(K8sSecret(name, namespace, stype, data))
        return f"secret/{name} created"

    def bind_pvc(self, name: str) -> str:
        pvc = next((p for p in self.pvcs if p.name == name), None)
        if not pvc:
            return f"Error from server (NotFound): persistentvolumeclaims \"{name}\" not found"
        pvc.status = "Bound"
        pvc.volume = pvc.volume or f"pv-{abs(hash(name)) % 100000:05d}"
        for p in self.pods:
            if p.status == "Pending" and any("PersistentVolumeClaim" in e for e in p.events):
                p.status = "Running"
                p.ready = "1/1"
        self._sync_endpoints()
        return f"persistentvolumeclaim/{name} bound"

    def auth_can_i(self, verb: str, resource: str) -> str:
        if getattr(self, "rbac_forbidden", False):
            return "no"
        return "yes"

    def top_nodes(self) -> str:
        lines = ["NAME       CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%"]
        for n in self.nodes:
            if n.status == "Ready":
                lines.append(f"{n.name:<10} 250m         12%    1024Mi          25%")
            else:
                lines.append(f"{n.name:<10} <unknown>    <unknown>   <unknown>       <unknown>")
        return "\n".join(lines)

    def top_pods(self, namespace: str = "default") -> str:
        lines = ["NAME                     CPU(cores)   MEMORY(bytes)"]
        for p in self.pods:
            if p.namespace != namespace:
                continue
            if p.status == "Running":
                lines.append(f"{p.name:<24} 10m          48Mi")
            else:
                lines.append(f"{p.name:<24} 0m           0Mi")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # apply / create from YAML
    # ------------------------------------------------------------------

    def apply_yaml(self, content: str, create: bool = False) -> str:
        """Parse one or more YAML manifests and materialise the resources.

        Falls back to the legacy heuristic fixes when the manifest is too
        sparse to parse into a concrete object (keeps old scenarios working).
        """
        content = content or ""
        if not content.strip():
            return "error: no objects passed to apply"

        results: list[str] = []
        for doc in re.split(r"^---\s*$", content, flags=re.MULTILINE):
            if not doc.strip():
                continue
            res = self._apply_one_doc(doc, create)
            if res:
                results.append(res)

        if results:
            self._sync_endpoints()
            return "\n".join(results)

        # Legacy fall-through fixes (manifests that only hint at intent).
        return self._apply_legacy(content)

    def _parse_manifest(self, doc: str) -> dict[str, Any]:
        """Tiny YAML-ish parser good enough for flat k8s manifests."""
        data: dict[str, Any] = {}
        kind = re.search(r"^\s*kind:\s*(\S+)", doc, flags=re.MULTILINE)
        name = re.search(r"^\s*name:\s*(\S+)", doc, flags=re.MULTILINE)
        ns = re.search(r"^\s*namespace:\s*(\S+)", doc, flags=re.MULTILINE)
        replicas = re.search(r"^\s*replicas:\s*(\d+)", doc, flags=re.MULTILINE)
        image = re.search(r"^\s*-?\s*image:\s*(\S+)", doc, flags=re.MULTILINE)
        stype = re.search(r"^\s*type:\s*(\S+)", doc, flags=re.MULTILINE)
        port = re.search(r"^\s*(?:port|containerPort):\s*(\d+)", doc, flags=re.MULTILINE)
        target = re.search(r"^\s*targetPort:\s*(\d+)", doc, flags=re.MULTILINE)
        data["kind"] = kind.group(1) if kind else ""
        data["name"] = name.group(1).strip('"\'') if name else ""
        data["namespace"] = ns.group(1).strip('"\'') if ns else "default"
        data["replicas"] = int(replicas.group(1)) if replicas else 1
        data["image"] = image.group(1).strip('"\'') if image else ""
        data["type"] = stype.group(1) if stype else "ClusterIP"
        data["port"] = int(port.group(1)) if port else 80
        data["targetPort"] = int(target.group(1)) if target else data["port"]
        # selector / matchLabels app:
        sel = re.search(r"app:\s*(\S+)", doc)
        data["app"] = sel.group(1).strip('"\'') if sel else data["name"]
        # configmap / secret data block
        kv: dict[str, str] = {}
        in_data = False
        for raw in doc.splitlines():
            if re.match(r"^\s*data:\s*$", raw):
                in_data = True
                continue
            if in_data:
                m = re.match(r"^\s{2,}([\w.\-]+):\s*(.*)$", raw)
                if m and not raw.strip().startswith("#"):
                    kv[m.group(1)] = m.group(2).strip().strip('"\'')
                elif raw.strip() and not raw.startswith(" "):
                    in_data = False
        data["data"] = kv
        return data

    def _apply_one_doc(self, doc: str, create: bool) -> str:
        m = self._parse_manifest(doc)
        kind = (m["kind"] or "").lower()
        name = m["name"]
        if not kind or not name:
            return ""
        ns = m["namespace"]
        if ns not in self.namespaces:
            self.namespaces.append(ns)
        app = m["app"] or name

        if kind == "deployment":
            existing = next((d for d in self.deployments if d.name == name and d.namespace == ns), None)
            verb = "configured" if existing else "created"
            if create and existing:
                return f"Error from server (AlreadyExists): deployments.apps \"{name}\" already exists"
            image = m["image"] or "nginx:latest"
            dep = existing or K8sDeployment(name, namespace=ns)
            dep.image = image
            dep.replicas = m["replicas"]
            dep.selector = {"app": app}
            healthy = "broken" not in image and "missing" not in image
            if not existing:
                self.deployments.append(dep)
            # (Re)create pods to match desired replicas.
            self.pods = [p for p in self.pods if p.owner != name]
            for i in range(dep.replicas):
                self.pods.append(K8sPod(
                    f"{name}-{abs(hash(name + str(i))) % 100000:05d}",
                    namespace=ns,
                    status="Running" if healthy else "ImagePullBackOff",
                    ready="1/1" if healthy else "0/1",
                    image=image, labels={"app": app}, owner=name,
                ))
            dep.ready = dep.replicas if healthy else 0
            return f"deployment.apps/{name} {verb}"

        if kind == "pod":
            existing = self.find_pod(name)
            if create and existing:
                return f"Error from server (AlreadyExists): pods \"{name}\" already exists"
            image = m["image"] or "nginx:latest"
            healthy = "broken" not in image and "missing" not in image
            if existing:
                existing.image = image
                return f"pod/{name} configured"
            self.pods.append(K8sPod(
                name, namespace=ns,
                status="Running" if healthy else "ImagePullBackOff",
                ready="1/1" if healthy else "0/1",
                image=image, labels={"app": app}, owner="",
            ))
            return f"pod/{name} created"

        if kind == "service":
            existing = self.find_service(name)
            verb = "configured" if existing else "created"
            svc = existing or K8sService(name, namespace=ns)
            svc.type = m["type"]
            svc.port = m["port"]
            svc.target_port = m["targetPort"]
            svc.selector = {"app": app}
            if svc.type == "LoadBalancer" and not svc.external_ip:
                svc.external_ip = "203.0.113.20"
                self.lb_pending = False
            if not existing:
                self.services.append(svc)
            self.service_port_wrong = False
            return f"service/{name} {verb}"

        if kind == "configmap":
            return self.create_configmap(name, ns, m["data"])

        if kind == "secret":
            return self.create_secret(name, ns, m["data"], m["type"] if m["type"] != "ClusterIP" else "Opaque")

        if kind in ("persistentvolumeclaim",):
            existing = next((p for p in self.pvcs if p.name == name), None)
            if not existing:
                self.pvcs.append(K8sPVC(name, namespace=ns, status="Bound"))
            return f"persistentvolumeclaim/{name} created"

        if kind == "namespace":
            return self.create_namespace(name)

        if kind == "ingress":
            existing = next((i for i in self.ingresses if i.name == name), None)
            if not existing:
                self.ingresses.append(K8sIngress(name, namespace=ns, service=app, port=m["port"]))
            self.ingress_broken = False
            return f"ingress.networking.k8s.io/{name} {'configured' if existing else 'created'}"

        if kind == "networkpolicy":
            self.netpol_blocks = False
            return f"networkpolicy.networking.k8s.io/{name} created"

        if kind == "horizontalpodautoscaler":
            self.hpa_broken = False
            return f"horizontalpodautoscaler.autoscaling/{name} created"

        if kind in ("role", "rolebinding", "clusterrole", "clusterrolebinding"):
            self.rbac_forbidden = False
            return f"{kind}.rbac.authorization.k8s.io/{name} created"

        if kind == "httproute":
            self.gateway_broken = False
            return f"httproute.gateway.networking.k8s.io/{name} configured"

        return f"{kind}/{name} created"

    def _apply_legacy(self, content: str) -> str:
        """Heuristic fixes for sparse manifests used by older scenarios."""
        low = content.lower()
        if "selector:" in content and "app: api" in content:
            for s in self.services:
                if s.name == "api":
                    s.selector = {"app": "api"}
            self.service_port_wrong = False
            self._sync_endpoints()
            return "service/api configured"
        if "kind: networkpolicy" in low or "networkpolicy" in low:
            self.netpol_blocks = False
            return "networkpolicy.networking.k8s.io/allow-backend created"
        if "kind: httproute" in low or "gateway" in low:
            self.gateway_broken = False
            return "httproute.gateway.networking.k8s.io/api-route configured"
        if "type: loadbalancer" in low:
            for s in self.services:
                if s.type == "LoadBalancer":
                    s.external_ip = "203.0.113.20"
            self.lb_pending = False
            return "service/frontend configured"
        if "horizontalpodautoscaler" in low or "kind: hpa" in low:
            self.hpa_broken = False
            return "horizontalpodautoscaler.autoscaling/worker configured"
        if "kind: role" in low or "kind: rolebinding" in low:
            self.rbac_forbidden = False
            return "rolebinding.rbac.authorization.k8s.io/app-sa-binding created"
        return "configured"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sync_endpoints(self) -> None:
        for s in self.services:
            s.endpoints = []
            for p in self.pods:
                if (p.status == "Running" and p.namespace == s.namespace
                        and s.selector
                        and all(p.labels.get(k) == v for k, v in s.selector.items())):
                    s.endpoints.append(f"{p.ip}:{s.target_port}")

    def is_healthy(self) -> bool:
        if getattr(self, "rbac_forbidden", False):
            return False
        if getattr(self, "ingress_broken", False):
            return False
        if getattr(self, "service_port_wrong", False):
            return False
        if getattr(self, "rollout_failed", False):
            return False
        if getattr(self, "lb_pending", False):
            return False
        if getattr(self, "gateway_broken", False):
            return False
        if getattr(self, "netpol_blocks", False):
            return False
        if getattr(self, "hpa_broken", False):
            return False
        if any(n.status != "Ready" for n in self.nodes):
            return False
        if not self._xtech_healthy():
            return False
        return all(p.status == "Running" for p in self.pods) and all(
            s.endpoints for s in self.services if s.name != "kubernetes"
        )

    def _xtech_healthy(self) -> bool:
        """Extra fail-closed gate for cross-tech k8s-on-VMware scenarios.

        Beyond "all nodes Ready / all pods Running" this enforces the scenario's
        real success condition so the VMware action genuinely matters:
          add   : the missing worker node must now exist and be Ready
          reset : the previously-NotReady node must be Ready again (covered above)
          drain : worker-1 must be drained (unschedulable) AND a new worker added,
                  with no pod left stranded on the drained node
          hpa   : the HPA's observed replicas must meet its desired count
        """
        xt = getattr(self, "_xtech", None)
        if not xt:
            return True
        node_name = xt.get("node")
        kind = xt.get("kind")
        if kind in ("add", "drain"):
            n = self.find_node(node_name)
            if not n or n.status != "Ready":
                return False
        if kind == "drain":
            drained = self.find_node(xt.get("drain_node", "worker-1"))
            # The drained node must be cordoned (unschedulable) and emptied.
            if not drained or drained.schedulable:
                return False
            if any(p.node == drained.name for p in self.pods):
                return False
        for hpa in self.hpas:
            if hpa.current_replicas < hpa.desired_replicas:
                return False
        return True
