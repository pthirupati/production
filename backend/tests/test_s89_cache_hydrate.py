"""Session 89 — cache hydrate on get_sim_session miss."""

from django.test import SimpleTestCase
from unittest import mock

from apps.labs.provisioner.simulation import shell as sim_shell


class CacheHydrateOnMissTest(SimpleTestCase):
    def setUp(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def tearDown(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def test_miss_hydrates_from_cache(self):
        engine = mock.Mock()
        engine.simulation_type = "linux"
        with mock.patch(
            "apps.labs.provisioner.simulation.sim_persistence.cache_get_engine",
            return_value=engine,
        ):
            with mock.patch(
                "apps.labs.provisioner.simulation.sim_persistence.cache_put_engine_snapshot"
            ):
                entry = sim_shell.get_sim_session("hydrate-1")
        self.assertIsNotNone(entry)
        self.assertIs(entry["state"]["engine"], engine)
        self.assertEqual(sim_shell.sim_session_count(), 1)

    def test_hydrate_disabled(self):
        with mock.patch.dict("os.environ", {"SIM_ENGINE_CACHE_HYDRATE": "0"}):
            with mock.patch(
                "apps.labs.provisioner.simulation.sim_persistence.cache_get_engine",
                return_value=mock.Mock(),
            ) as get:
                entry = sim_shell.get_sim_session("hydrate-off")
        self.assertIsNone(entry)
        get.assert_not_called()
