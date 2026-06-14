"""Tests for LVM, firewalld, nano editor, and k8s cluster."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.editor_mode import EditorSession
from apps.labs.provisioner.simulation.firewall_state import FirewallState
from apps.labs.provisioner.simulation.k8s_cluster import K8sCluster
from apps.labs.provisioner.simulation.kubernetes_sim import KubernetesSimulator
from apps.labs.provisioner.simulation.lvm_state import LVMState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell


class LVMTests(SimpleTestCase):
    def test_pvcreate_and_vgextend(self):
        lvm = LVMState()
        ok, _ = lvm.pvcreate("/dev/sdc")
        self.assertTrue(ok)
        ok, msg = lvm.vgextend("rhel", "/dev/sdb")
        self.assertTrue(ok)
        self.assertIn("extended", msg.lower())

    def test_shell_lvm_commands(self):
        shell = RHELShell()
        out = shell.run("pvs")
        self.assertIn("/dev/sda2", out)
        shell.run("vgextend rhel /dev/sdb")
        out = shell.run("vgs")
        self.assertIn("rhel", out)


class FirewallTests(SimpleTestCase):
    def test_port_persistence(self):
        fw = FirewallState()
        fw.add_port("80/tcp", permanent=True)
        fw.reload()
        self.assertTrue(fw.is_port_open(80))

    def test_curl_blocked_without_firewall(self):
        shell = RHELShell(scenario_slug="sim-rhel-firewalld-port")
        out = shell.run("curl http://localhost")
        self.assertIn("Connection refused", out)
        shell.run("firewall-cmd --permanent --add-port=80/tcp")
        shell.run("firewall-cmd --reload")
        out = shell.run("curl http://localhost")
        self.assertIn("Welcome", out)


class EditorTests(SimpleTestCase):
    def test_nano_opens_editor(self):
        shell = RHELShell()
        shell.run("echo broken > /tmp/test.conf")
        out = shell.run("nano /tmp/test.conf")
        self.assertEqual(out, "__EDITOR__")
        self.assertIsNotNone(shell.state.editor)

    def test_editor_session_save(self):
        ed = EditorSession("/tmp/f", "line1")
        ed.process("fixed")
        self.assertIn("fixed", ed.content())


class K8sClusterTests(SimpleTestCase):
    def test_crashloop_fix(self):
        c = K8sCluster("sim-k8s-crashloop")
        self.assertIn("CrashLoopBackOff", c.get_pods())
        c.rollout_restart("nginx")
        self.assertIn("Running", c.get_pods())

    def test_endpoints_sync(self):
        c = K8sCluster("sim-k8s-service-not-ready")
        self.assertIn("<none>", c.get_endpoints("api"))
        c.patch_service_selector("api", {"app": "api"})
        self.assertNotIn("<none>", c.get_endpoints("api"))

    def test_kubectl_simulator(self):
        sim = KubernetesSimulator("sim-k8s-crashloop")
        out = sim.shell.run("kubectl get pods")
        self.assertIn("CrashLoopBackOff", out)
        sim.shell.run("kubectl rollout restart deployment/nginx")
        out = sim.shell.run("kubectl get pods")
        self.assertIn("Running", out)
