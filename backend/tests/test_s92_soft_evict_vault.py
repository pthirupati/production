"""Session 92 — soft-evict streamless engines to Redis (Z5-1)."""

from django.test import SimpleTestCase
from unittest import mock

from apps.labs.provisioner.simulation import shell as sim_shell


class SoftEvictStreamlessTest(SimpleTestCase):
    def setUp(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def tearDown(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def test_soft_evicts_idle_streamless(self):
        engine = object()
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS["soft-1"] = {
                "last_access": 0,
                "resource_id": "r",
                "sim_type": "linux",
                "state": {"engine": engine},
                "streams": {},
                "engine_mutated_at": 1.0,
            }
        with mock.patch.object(sim_shell, "_SIM_SOFT_IDLE_SECONDS", 60):
            with mock.patch(
                "apps.labs.provisioner.simulation.sim_persistence.cache_put_engine_snapshot"
            ) as put:
                with sim_shell._SIM_LOCK:
                    n = sim_shell._soft_evict_streamless_locked()
        self.assertEqual(n, 1)
        put.assert_called_once()
        self.assertEqual(sim_shell.sim_session_count(), 0)

    def test_keeps_entry_with_streams(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS["soft-stream"] = {
                "last_access": 0,
                "resource_id": "r",
                "sim_type": "linux",
                "state": {"engine": object()},
                "streams": {"main": object()},
                "engine_mutated_at": 1.0,
            }
        with mock.patch.object(sim_shell, "_SIM_SOFT_IDLE_SECONDS", 60):
            with mock.patch(
                "apps.labs.provisioner.simulation.sim_persistence.cache_put_engine_snapshot"
            ) as put:
                with sim_shell._SIM_LOCK:
                    n = sim_shell._soft_evict_streamless_locked()
        self.assertEqual(n, 0)
        put.assert_not_called()
        self.assertEqual(sim_shell.sim_session_count(), 1)
