"""Session 78: multi-node fabric for torchrun --nnodes>1."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


def _engine():
    eng = UnifiedSimulationEngine(
        scenario_slug="academy-ai-infra-003-operate-dcgm",
        simulation_type="gpu",
    )
    # Clear injected driver fault so torchrun path is reachable.
    for cmd in ("sudo modprobe nvidia", "sudo systemctl restart nvidia-persistenced"):
        eng.shell.run(cmd)
    eng.shell.state.gpu_healthy = True
    for g in eng.shell.state.gpus:
        g.healthy = True
        g.oom = False
    return eng


class MultiNodeFabricTests(SimpleTestCase):
    def test_nnodes_blocked_until_fabric_up(self):
        engine = _engine()
        self.assertFalse(engine.shell.state.distributed_fabric.get("cross_node_ready"))
        blocked = str(engine.shell.run("torchrun --nnodes 2 --nproc_per_node=1 train.py"))
        self.assertIn("cross-node fabric is not ready", blocked)

        up = str(engine.shell.run("fixitlab-fabric up --nnodes 2"))
        self.assertIn("cross_node_ready=True", up)
        self.assertTrue(engine.shell.state.distributed_fabric["cross_node_ready"])

        ok = str(engine.shell.run("torchrun --nnodes 2 --nproc_per_node=1 train.py"))
        self.assertIn("Training completed successfully", ok)
        self.assertIn("fabric:", ok)

    def test_single_node_still_works(self):
        engine = _engine()
        ok = str(engine.shell.run("torchrun --nnodes 1 --nproc_per_node=1 train.py"))
        self.assertIn("Training completed successfully", ok)
