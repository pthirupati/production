"""Audit Z5-1 partial — shared-cache mirror of engine snapshots (streams stay local)."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.labs.provisioner.simulation.sim_persistence import (
    SIM_ENGINE_CACHE_TTL,
    cache_drop_engine,
    cache_get_engine,
    cache_put_engine_snapshot,
    snapshot_engine,
)
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sim-engine-cache-test",
    }
}


@override_settings(CACHES=LOCMEM)
class SimEngineCacheMirrorTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_put_get_round_trips_hostname(self):
        engine = UnifiedSimulationEngine(scenario_slug="t", simulation_type="generic")
        engine.shell.state.hostname = "cache-mirror-host"
        cache_put_engine_snapshot("sid-1", engine=engine)
        restored = cache_get_engine("sid-1")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.shell.state.hostname, "cache-mirror-host")

    def test_drop_removes_blob(self):
        engine = UnifiedSimulationEngine(scenario_slug="t", simulation_type="generic")
        cache_put_engine_snapshot("sid-2", snap=snapshot_engine(engine))
        cache_drop_engine("sid-2")
        self.assertIsNone(cache_get_engine("sid-2"))

    def test_ttl_matches_vmware_sim_pattern(self):
        self.assertEqual(SIM_ENGINE_CACHE_TTL, 7200)
