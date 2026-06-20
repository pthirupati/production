"""End-to-end tests for the terminal Kubernetes, Docker, GPU, baremetal and
networking simulation engines.

These exercise the full path a learner takes: writing a YAML manifest, applying
it, observing mutated cluster state, scaling/rolling out, and the docker daemon
lifecycle — including a snapshot round-trip for docker state.
"""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.docker_state import DockerState
from apps.labs.provisioner.simulation.k8s_cluster import K8sCluster
from apps.labs.provisioner.simulation.sim_persistence import (
    restore_engine,
    snapshot_engine,
)
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


def _k8s_sim(slug="sim-k8s-crashloop"):
    return UnifiedSimulationEngine(scenario_slug=slug, simulation_type="kubernetes")


def _docker_sim(slug="generic"):
    return UnifiedSimulationEngine(scenario_slug=slug, simulation_type="generic")


# ---------------------------------------------------------------------------
# kubectl: get / describe / logs
# ---------------------------------------------------------------------------

class KubectlReadTests(SimpleTestCase):
    def test_get_pods_reports_state(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl get pods")
        self.assertIn("NAME", out)
        self.assertIn("CrashLoopBackOff", out)

    def test_get_pods_wide_has_ip_and_node(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl get pods -o wide")
        self.assertIn("IP", out)
        self.assertIn("NODE", out)
        self.assertIn("10.244", out)

    def test_get_nodes(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl get nodes")
        self.assertIn("master-1", out)
        self.assertIn("worker-1", out)

    def test_get_unknown_resource_errors(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl get widgets")
        self.assertIn("doesn't have a resource type", out)

    def test_describe_pod(self):
        sim = _k8s_sim()
        pod = sim.cluster.pods[0].name
        out = sim.shell.run(f"kubectl describe pod {pod}")
        self.assertIn("Name:", out)
        self.assertIn("Events:", out)

    def test_describe_deployment(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl describe deployment nginx")
        self.assertIn("Replicas:", out)
        self.assertIn("nginx", out)

    def test_logs_crashloop_shows_error(self):
        sim = _k8s_sim()
        pod = sim.cluster.pods[0].name
        out = sim.shell.run(f"kubectl logs {pod}")
        self.assertIn("crashed", out.lower())

    def test_get_pod_yaml(self):
        sim = _k8s_sim()
        pod = sim.cluster.pods[0].name
        out = sim.shell.run(f"kubectl get pod {pod} -o yaml")
        self.assertIn("kind: Pod", out)
        self.assertIn("apiVersion: v1", out)


# ---------------------------------------------------------------------------
# kubectl: apply from YAML (the headline flow)
# ---------------------------------------------------------------------------

class KubectlApplyFromYamlTests(SimpleTestCase):
    DEPLOY_YAML = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: cache
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cache
  template:
    metadata:
      labels:
        app: cache
    spec:
      containers:
      - name: cache
        image: redis:7.2
"""

    def test_apply_file_written_by_editor_creates_deployment(self):
        sim = _k8s_sim()
        # Simulate the editor saving the manifest to the VFS.
        sim.shell.state.write_file("/root/cache.yaml", self.DEPLOY_YAML)
        out = sim.shell.run("kubectl apply -f /root/cache.yaml")
        self.assertIn("deployment.apps/cache created", out)
        # It must now show up in get.
        deploys = sim.shell.run("kubectl get deployments")
        self.assertIn("cache", deploys)
        pods = sim.shell.run("kubectl get pods")
        self.assertEqual(pods.count("cache"), 3)

    def test_apply_via_heredoc_creates_resource(self):
        sim = _k8s_sim()
        block = "cat > /root/cache.yaml <<EOF\n" + self.DEPLOY_YAML + "EOF"
        sim.shell.run(block)
        self.assertIn("kind: Deployment", sim.shell.state.read_file("/root/cache.yaml") or "")
        out = sim.shell.run("kubectl apply -f /root/cache.yaml")
        self.assertIn("cache", out)
        self.assertIn("cache", sim.shell.run("kubectl get deploy"))

    def test_apply_missing_file_errors(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl apply -f /root/nope.yaml")
        self.assertIn("does not exist", out)

    def test_create_f_twice_conflicts(self):
        sim = _k8s_sim()
        sim.shell.state.write_file("/root/cache.yaml", self.DEPLOY_YAML)
        sim.shell.run("kubectl create -f /root/cache.yaml")
        out = sim.shell.run("kubectl create -f /root/cache.yaml")
        self.assertIn("AlreadyExists", out)

    def test_apply_service_yaml_creates_service_with_endpoints(self):
        sim = _k8s_sim()
        sim.shell.state.write_file("/root/cache.yaml", self.DEPLOY_YAML)
        sim.shell.run("kubectl apply -f /root/cache.yaml")
        svc_yaml = """apiVersion: v1
kind: Service
metadata:
  name: cache
  namespace: default
spec:
  selector:
    app: cache
  ports:
  - port: 6379
    targetPort: 6379
"""
        sim.shell.state.write_file("/root/svc.yaml", svc_yaml)
        out = sim.shell.run("kubectl apply -f /root/svc.yaml")
        self.assertIn("service/cache created", out)
        eps = sim.shell.run("kubectl get endpoints cache")
        self.assertNotIn("<none>", eps)


# ---------------------------------------------------------------------------
# kubectl: mutating verbs
# ---------------------------------------------------------------------------

class KubectlMutationTests(SimpleTestCase):
    def test_scale_creates_pods(self):
        sim = _k8s_sim("sim-k8s-node-notready")
        sim.shell.run("kubectl uncordon worker-1")
        out = sim.shell.run("kubectl scale deployment nginx --replicas=4")
        self.assertIn("scaled", out)
        pods = sim.shell.run("kubectl get pods")
        self.assertGreaterEqual(pods.count("nginx"), 4)

    def test_rollout_restart_heals_crashloop(self):
        sim = _k8s_sim("sim-k8s-crashloop")
        self.assertIn("CrashLoopBackOff", sim.shell.run("kubectl get pods"))
        sim.shell.run("kubectl rollout restart deployment/nginx")
        self.assertIn("Running", sim.shell.run("kubectl get pods"))
        self.assertNotIn("CrashLoopBackOff", sim.shell.run("kubectl get pods"))

    def test_rollout_status_and_history(self):
        sim = _k8s_sim()
        sim.shell.run("kubectl rollout restart deployment/nginx")
        status = sim.shell.run("kubectl rollout status deployment/nginx")
        self.assertIn("successfully rolled out", status)
        hist = sim.shell.run("kubectl rollout history deployment/nginx")
        self.assertIn("REVISION", hist)

    def test_set_image_updates_and_records_history(self):
        sim = _k8s_sim()
        sim.shell.run("kubectl set image deployment/nginx nginx=nginx:1.25")
        self.assertEqual(sim.cluster.find_deployment("nginx").image, "nginx:1.25")
        out = sim.shell.run("kubectl rollout undo deployment/nginx")
        self.assertIn("rolled back", out)

    def test_delete_pod_recreated_by_deployment(self):
        sim = _k8s_sim()
        pod = sim.cluster.pods[0].name
        out = sim.shell.run(f"kubectl delete pod {pod}")
        self.assertIn("deleted", out)
        # Deployment recreates a replacement pod.
        self.assertTrue(any(p.owner == "nginx" for p in sim.cluster.pods))

    def test_delete_deployment_removes_pods(self):
        sim = _k8s_sim()
        sim.shell.run("kubectl delete deployment nginx")
        self.assertEqual(len(sim.cluster.deployments), 0)
        self.assertNotIn("nginx", sim.shell.run("kubectl get pods"))

    def test_expose_creates_service(self):
        sim = _k8s_sim("sim-k8s-node-notready")
        # Remove the pre-existing service so expose has a clean slate.
        sim.shell.run("kubectl delete service nginx")
        out = sim.shell.run("kubectl expose deployment nginx --port=80")
        self.assertIn("exposed", out)
        self.assertIsNotNone(sim.cluster.find_service("nginx"))

    def test_run_creates_pod(self):
        sim = _k8s_sim()
        out = sim.shell.run("kubectl run debug --image=busybox")
        self.assertIn("created", out)
        self.assertIsNotNone(sim.cluster.find_pod("debug"))

    def test_label_and_annotate(self):
        sim = _k8s_sim()
        pod = sim.cluster.pods[0].name
        sim.shell.run(f"kubectl label pod {pod} tier=frontend")
        self.assertEqual(sim.cluster.find_pod(pod).labels.get("tier"), "frontend")
        sim.shell.run(f"kubectl annotate pod {pod} owner=team-a")
        self.assertEqual(sim.cluster.find_pod(pod).annotations.get("owner"), "team-a")

    def test_cordon_drain_uncordon(self):
        sim = _k8s_sim()
        self.assertIn("cordoned", sim.shell.run("kubectl cordon worker-1"))
        self.assertFalse(sim.cluster.find_node("worker-1").schedulable)
        self.assertIn("drained", sim.shell.run("kubectl drain worker-1"))
        self.assertIn("uncordoned", sim.shell.run("kubectl uncordon worker-1"))
        self.assertTrue(sim.cluster.find_node("worker-1").schedulable)

    def test_create_namespace_and_configmap(self):
        sim = _k8s_sim()
        self.assertIn("created", sim.shell.run("kubectl create namespace staging"))
        self.assertIn("staging", sim.shell.run("kubectl get namespaces"))
        sim.shell.run("kubectl create configmap app-config --from-literal=LOG_LEVEL=debug")
        self.assertIn("app-config", sim.shell.run("kubectl get configmaps"))

    def test_exec_running_pod(self):
        sim = _k8s_sim()
        sim.shell.run("kubectl run web --image=nginx:latest")
        out = sim.shell.run("kubectl exec web -- ls")
        self.assertIn("etc", out)

    def test_auth_can_i_respects_rbac(self):
        sim = _k8s_sim("sim-k8s-rbac-forbidden")
        self.assertEqual(sim.shell.run("kubectl auth can-i create pods"), "no")
        sim.cluster.rbac_forbidden = False
        self.assertEqual(sim.shell.run("kubectl auth can-i create pods"), "yes")

    def test_top_nodes_and_pods(self):
        sim = _k8s_sim()
        self.assertIn("CPU", sim.shell.run("kubectl top nodes"))
        self.assertIn("MEMORY", sim.shell.run("kubectl top pods"))


# ---------------------------------------------------------------------------
# K8sCluster unit-level backward compatibility
# ---------------------------------------------------------------------------

class K8sClusterCompatTests(SimpleTestCase):
    def test_legacy_public_api_preserved(self):
        c = K8sCluster("sim-k8s-service-not-ready")
        self.assertIn("<none>", c.get_endpoints("api"))
        c.patch_service_selector("api", {"app": "api"})
        self.assertNotIn("<none>", c.get_endpoints("api"))

    def test_apply_legacy_sparse_manifest(self):
        c = K8sCluster("sim-k8s-service-not-ready")
        # A manifest too sparse to fully parse still triggers the heuristic fix.
        c.apply_yaml("spec:\n  selector:\n    app: api\n")
        self.assertNotIn("<none>", c.get_endpoints("api"))


# ---------------------------------------------------------------------------
# docker: real-state lifecycle
# ---------------------------------------------------------------------------

class DockerLifecycleTests(SimpleTestCase):
    def test_ps_lists_seeded_running_containers(self):
        sim = _docker_sim()
        out = sim.shell.run("docker ps")
        self.assertIn("web", out)
        self.assertIn("Up", out)
        # Status reflects real container state, not a single canned string:
        # stopping a container must change what ps reports.
        sim.shell.run("docker stop web")
        self.assertNotIn("web", sim.shell.run("docker ps"))

    def test_run_detached_then_ps_shows_it(self):
        sim = _docker_sim()
        cid = sim.shell.run("docker run -d --name app1 -p 8080:80 nginx:latest")
        self.assertTrue(len(cid.strip()) >= 12)
        out = sim.shell.run("docker ps")
        self.assertIn("app1", out)
        self.assertIn("8080", out)

    def test_stop_reflects_in_ps(self):
        sim = _docker_sim()
        sim.shell.run("docker run -d --name app1 nginx:latest")
        sim.shell.run("docker stop app1")
        # Not in default ps...
        self.assertNotIn("app1", sim.shell.run("docker ps"))
        # ...but visible with -a as Exited.
        all_out = sim.shell.run("docker ps -a")
        self.assertIn("app1", all_out)
        self.assertIn("Exited", all_out)

    def test_start_brings_container_back(self):
        sim = _docker_sim()
        sim.shell.run("docker run -d --name app1 nginx:latest")
        sim.shell.run("docker stop app1")
        sim.shell.run("docker start app1")
        self.assertIn("app1", sim.shell.run("docker ps"))

    def test_cannot_remove_running_without_force(self):
        sim = _docker_sim()
        out = sim.shell.run("docker rm web")
        self.assertIn("cannot remove a running container", out.lower())
        sim.shell.run("docker stop web")
        self.assertEqual(sim.shell.run("docker rm web").strip(), "web")
        self.assertNotIn("web", sim.shell.run("docker ps -a"))

    def test_build_creates_image_in_images(self):
        sim = _docker_sim()
        out = sim.shell.run("docker build -t myapp:v1 .")
        self.assertIn("Successfully tagged myapp:v1", out)
        self.assertIn("myapp", sim.shell.run("docker images"))

    def test_run_built_image_then_appears(self):
        sim = _docker_sim()
        sim.shell.run("docker build -t myapp:v1 .")
        sim.shell.run("docker run -d --name frombuild myapp:v1")
        self.assertIn("frombuild", sim.shell.run("docker ps"))

    def test_logs_for_exited_container(self):
        sim = _docker_sim("sim-docker-container-exited")
        out = sim.shell.run("docker logs web")
        self.assertIn("fatal", out.lower())

    def test_exec_running_container(self):
        sim = _docker_sim()
        out = sim.shell.run("docker exec web ls")
        self.assertIn("etc", out)

    def test_exec_stopped_container_errors(self):
        sim = _docker_sim()
        sim.shell.run("docker stop web")
        out = sim.shell.run("docker exec web ls")
        self.assertIn("is not running", out)

    def test_inspect_returns_json(self):
        sim = _docker_sim()
        out = sim.shell.run("docker inspect web")
        self.assertIn("\"Image\"", out)
        self.assertIn("nginx", out)

    def test_network_create_and_remove(self):
        sim = _docker_sim()
        sim.shell.run("docker network create appnet")
        self.assertIn("appnet", sim.shell.run("docker network ls"))
        sim.shell.run("docker network rm appnet")
        self.assertNotIn("appnet", sim.shell.run("docker network ls"))

    def test_cannot_remove_predefined_network(self):
        sim = _docker_sim()
        out = sim.shell.run("docker network rm bridge")
        self.assertIn("pre-defined", out)

    def test_volume_create_and_remove(self):
        sim = _docker_sim()
        sim.shell.run("docker volume create data1")
        self.assertIn("data1", sim.shell.run("docker volume ls"))
        sim.shell.run("docker volume rm data1")
        self.assertNotIn("data1", sim.shell.run("docker volume ls"))

    def test_compose_up_down(self):
        sim = _docker_sim("sim-docker-container-exited")
        sim.shell.run("docker compose up -d")
        self.assertTrue(sim.docker.any_running())
        sim.shell.run("docker compose down")
        self.assertFalse(sim.docker.any_running())

    def test_daemon_stopped_blocks_commands(self):
        sim = _docker_sim("sim-docker-daemon-stopped")
        out = sim.shell.run("docker ps")
        self.assertIn("Cannot connect to the Docker daemon", out)

    def test_pull_adds_image(self):
        sim = _docker_sim()
        out = sim.shell.run("docker pull ubuntu:22.04")
        self.assertIn("Downloaded newer image", out)
        self.assertIn("ubuntu", sim.shell.run("docker images"))


class DockerStateUnitTests(SimpleTestCase):
    def test_to_from_dict_round_trip(self):
        d = DockerState("generic")
        d.run("nginx:latest", name="x", detach=True)
        data = d.to_dict()
        restored = DockerState.from_dict(data)
        self.assertIsNotNone(restored.find_container("x"))


# ---------------------------------------------------------------------------
# Snapshot round-trip: docker state persists
# ---------------------------------------------------------------------------

class SnapshotRoundTripTests(SimpleTestCase):
    def test_docker_container_survives_snapshot(self):
        sim = _docker_sim()
        sim.shell.run("docker run -d --name persistme alpine:3.19")
        snap = snapshot_engine(sim)
        restored = restore_engine(snap)
        self.assertIsNotNone(restored)
        self.assertIn("persistme", restored.shell.run("docker ps"))

    def test_docker_stop_survives_snapshot(self):
        sim = _docker_sim()
        sim.shell.run("docker stop web")
        snap = snapshot_engine(sim)
        restored = restore_engine(snap)
        self.assertNotIn("web", restored.shell.run("docker ps"))
        self.assertIn("web", restored.shell.run("docker ps -a"))


# ---------------------------------------------------------------------------
# GPU / baremetal / networking verification
# ---------------------------------------------------------------------------

class GpuSimTests(SimpleTestCase):
    def test_nvidia_smi_broken_until_driver_loaded(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-gpu-driver-fault", simulation_type="gpu")
        self.assertIn("failed", sim.shell.run("nvidia-smi").lower())
        sim.shell.run("modprobe nvidia")
        self.assertIn("NVIDIA-SMI", sim.shell.run("nvidia-smi"))

    def test_lspci_lsmod_work_for_gpu(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-gpu-driver-fault", simulation_type="gpu")
        self.assertIn("NVIDIA", sim.shell.run("lspci | grep -i nvidia"))
        # Driver not loaded -> lsmod has no nvidia row.
        self.assertNotIn("nvidia ", sim.shell.run("lsmod | grep nvidia"))
        sim.shell.run("modprobe nvidia")
        self.assertIn("nvidia", sim.shell.run("lsmod | grep nvidia"))

    def test_modprobe_remove_unloads(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-gpu-driver-fault", simulation_type="gpu")
        sim.shell.run("modprobe nvidia")
        self.assertTrue(sim.shell.state.gpu_healthy)
        sim.shell.run("modprobe -r nvidia")
        self.assertFalse(sim.shell.state.gpu_healthy)


class BaremetalSimTests(SimpleTestCase):
    def test_ipmitool_power_cycle(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-baremetal-power", simulation_type="baremetal")
        sim._power_state = "off"
        self.assertIn("off", sim.shell.run("ipmitool chassis power status").lower())
        sim.shell.run("ipmitool chassis power on")
        self.assertIn("on", sim.shell.run("ipmitool chassis power status").lower())

    def test_ipmitool_sensor_and_fru(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-baremetal-power", simulation_type="baremetal")
        self.assertIn("Temp", sim.shell.run("ipmitool sensor"))
        self.assertIn("ProLiant", sim.shell.run("ipmitool fru"))


class NetworkingNmcliTests(SimpleTestCase):
    def test_nmcli_bond_creation_writes_proc(self):
        sim = UnifiedSimulationEngine(scenario_slug="linux-bonding-configure", simulation_type="generic")
        # No bond yet.
        self.assertIn("No such file", sim.shell.run("cat /proc/net/bonding/bond0"))
        sim.shell.run("nmcli con add type bond con-name bond0 ifname bond0 mode active-backup miimon 100")
        proc = sim.shell.run("cat /proc/net/bonding/bond0")
        self.assertIn("active-backup", proc)
        self.assertIn("MII Polling Interval (ms): 100", proc)

    def test_nmcli_device_status(self):
        sim = UnifiedSimulationEngine(scenario_slug="linux-bonding-configure", simulation_type="generic")
        out = sim.shell.run("nmcli device status")
        self.assertIn("DEVICE", out)
        self.assertIn("eth0", out)

    def test_bgp_fix_via_terminal(self):
        sim = UnifiedSimulationEngine(scenario_slug="networking-bgp-session-down", simulation_type="networking")
        self.assertIn("Idle", sim.shell.run('vtysh -c "show ip bgp summary"'))
        sim.shell.run("router bgp 65001\n neighbor 10.0.0.2 remote-as 65001")
        self.assertIn("Established", sim.shell.run('vtysh -c "show ip bgp summary"'))
