"""Terminal shell_ready after respawn — regression guard for reconnect loops."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class RespawnShellReadyTest(unittest.IsolatedAsyncioTestCase):
    async def test_respawn_shell_sends_shell_ready(self):
        from apps.terminal.consumers import TerminalConsumer
        from apps.labs.provisioner.simulation.shell import SimulationStreamHolder

        consumer = TerminalConsumer()
        consumer._ws_connected = True
        consumer._respawn_in_progress = False
        consumer.lab_session = MagicMock(id="sess-1")
        consumer.provider_type = "simulation"
        consumer._terminal_host = "primary"
        consumer._sim_stream_key = None

        holder = MagicMock(spec=SimulationStreamHolder)
        holder._stream_key = "sess-1:primary:abc"
        consumer.raw_socket = holder

        consumer._get_resource_id = MagicMock(return_value="sim-resource")
        consumer._open_shell = AsyncMock(return_value=True)
        consumer._safe_send = AsyncMock(return_value=True)

        with patch("apps.labs.provisioner.simulation_provisioner.evict_sim_stream"):
            ok = await consumer._respawn_shell("test")

        self.assertTrue(ok)
        calls = [str(c.args[0]) for c in consumer._safe_send.await_args_list]
        self.assertTrue(any("shell_ready" in c for c in calls))


if __name__ == "__main__":
    unittest.main()
