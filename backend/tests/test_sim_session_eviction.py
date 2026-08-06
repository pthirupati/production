"""_SIM_SESSIONS must be bounded, and must not evict live work.

The registry holds live UnifiedSimulationEngine objects (full VFS, users, services,
processes) plus live stream handles, with no TTL, no maxsize and no eviction — and
there are five independent copies (4 uvicorn workers + celery_provisioning).

The leak is structural: provisioning populates the Celery process's dict, the
terminal connects to an arbitrary uvicorn worker whose dict is empty so a second
engine is built there, and teardown drops it in ONE process. Celery children
recycle and self-heal; uvicorn workers never do.

Eviction is keyed on IDLE TIME rather than count pressure on purpose. Evicting an
ACTIVE session forces a rebuild from LabSession.simulation_snapshot, which is now
debounced to 15s and could therefore lose recent work. These tests pin that
distinction down — it is the whole safety argument for the change.
"""
import time
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import shell as sim_shell


class SimSessionEvictionTests(SimpleTestCase):
    def setUp(self):
        sim_shell._SIM_SESSIONS.clear()

    def tearDown(self):
        sim_shell._SIM_SESSIONS.clear()

    def _register(self, sid, idle_seconds=0.0):
        sim_shell.register_sim_session(sid, f"res-{sid}", "generic", {"engine": object()})
        if idle_seconds:
            sim_shell._SIM_SESSIONS[sid]["last_access"] = time.time() - idle_seconds
        return sim_shell._SIM_SESSIONS[sid]

    # ── observability ────────────────────────────────────────────────────────
    def test_count_is_exposed(self):
        """Without this, an OOM from the leak looks like a random restart."""
        self.assertEqual(sim_shell.sim_session_count(), 0)
        self._register("a")
        self._register("b")
        self.assertEqual(sim_shell.sim_session_count(), 2)

    # ── the leak is bounded ──────────────────────────────────────────────────
    def test_registering_evicts_entries_idle_past_the_ttl(self):
        self._register("stale", idle_seconds=sim_shell._SIM_IDLE_TTL_SECONDS + 60)
        self.assertEqual(sim_shell.sim_session_count(), 1)
        self._register("fresh")
        self.assertNotIn("stale", sim_shell._SIM_SESSIONS)
        self.assertIn("fresh", sim_shell._SIM_SESSIONS)

    def test_eviction_closes_live_streams(self):
        """Orphaned stream handles hold sockets, not just memory."""
        entry = self._register("stale", idle_seconds=sim_shell._SIM_IDLE_TTL_SECONDS + 60)
        stream = MagicMock()
        entry["streams"] = {"main": stream}
        self._register("trigger")
        stream.close.assert_called_once()

    def test_many_stale_entries_are_all_reclaimed(self):
        # Register all 50 fresh FIRST, then backdate them together. Backdating as
        # we go would have each register() evict the previous one — which is
        # correct behaviour, but it means the registry never actually holds 50 and
        # the test would not be exercising bulk reclaim.
        for i in range(50):
            self._register(f"old-{i}")
        self.assertEqual(sim_shell.sim_session_count(), 50)
        stale_at = time.time() - (sim_shell._SIM_IDLE_TTL_SECONDS + 10)
        for i in range(50):
            sim_shell._SIM_SESSIONS[f"old-{i}"]["last_access"] = stale_at
        self._register("new")
        self.assertEqual(
            sim_shell.sim_session_count(), 1,
            "stale entries survived — the registry is still unbounded",
        )

    # ── active work is never touched ─────────────────────────────────────────
    def test_active_session_is_not_evicted(self):
        """The safety argument: evicting a live session could lose up to 15s of work."""
        self._register("active")
        for i in range(20):
            self._register(f"other-{i}")
        self.assertIn(
            "active", sim_shell._SIM_SESSIONS,
            "an active session was evicted — a learner could lose work",
        )

    def test_recently_idle_session_is_not_evicted(self):
        """Just under the TTL must survive — no off-by-one eviction."""
        self._register("recent", idle_seconds=sim_shell._SIM_IDLE_TTL_SECONDS - 60)
        self._register("trigger")
        self.assertIn("recent", sim_shell._SIM_SESSIONS)

    def test_reads_refresh_the_idle_clock(self):
        """A session being actively used must not age out mid-lab."""
        self._register("busy", idle_seconds=sim_shell._SIM_IDLE_TTL_SECONDS - 30)
        sim_shell.get_sim_session("busy")          # a command arrives
        self._register("trigger")
        self.assertIn(
            "busy", sim_shell._SIM_SESSIONS,
            "reading a session did not refresh its clock — long labs would be evicted",
        )

    def test_resource_lookup_also_refreshes(self):
        self._register("byres", idle_seconds=sim_shell._SIM_IDLE_TTL_SECONDS - 30)
        found = sim_shell.get_sim_session_by_resource("res-byres")
        self.assertIsNotNone(found)
        self._register("trigger")
        self.assertIn("byres", sim_shell._SIM_SESSIONS)

    def test_get_missing_session_returns_none(self):
        self.assertIsNone(sim_shell.get_sim_session("nope"))
