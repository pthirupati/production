"""The per-process simulation registry must be bounded by count, not only by age.

Audit Z5-1: `_SIM_SESSIONS` is a process-local dict holding a whole engine each
(filesystem, users, processes, LVM, git state) plus live stream handles, and there is
a copy in every one of ~5 processes (4 uvicorn workers + celery). Idle-TTL eviction
was added, but a TTL bounds nothing *inside* its own window: sessions can pile up for
two hours before anything is reclaimed, which is ample to exhaust memory on a busy
hour. The count cap makes worst-case footprint a function of a constant instead of
traffic.

Evicting a live session is safe *here specifically* — `ensure_sim_session()`
rehydrates from `LabSession.simulation_snapshot`, kept current to ~1.5s by the
trailing-edge flush — so the cost is one rebuild on next access, not lost work. That
property is what makes an LRU cap acceptable rather than destructive, and it is why
the eviction closes stream handles rather than just dropping the dict entry.
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import shell as sim_shell


class _FakeStream:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class RegistryCapTests(SimpleTestCase):
    def setUp(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()
        self.addCleanup(self._clear)

    def _clear(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def _register(self, n, prefix="s"):
        for i in range(n):
            sim_shell.register_sim_session(
                f"{prefix}{i}", f"res-{prefix}{i}", "generic", {"engine": None}
            )

    def test_registry_never_exceeds_the_cap(self):
        with mock.patch.object(sim_shell, "_SIM_MAX_SESSIONS", 5):
            self._register(20)
        self.assertLessEqual(sim_shell.sim_session_count(), 5)

    def test_the_session_just_registered_survives_its_own_registration(self):
        """The cap is enforced after insert, so a new session can never evict itself
        — which would make every start fail once the registry was full."""
        with mock.patch.object(sim_shell, "_SIM_MAX_SESSIONS", 3):
            self._register(10)
            self.assertIsNotNone(sim_shell.get_sim_session("s9"))

    def test_least_recently_used_goes_first(self):
        with mock.patch.object(sim_shell, "_SIM_MAX_SESSIONS", 3):
            self._register(3)
            # Touch s0 so s1 becomes the coldest entry.
            sim_shell.get_sim_session("s0")
            sim_shell.register_sim_session("new", "res-new", "generic", {"engine": None})
        self.assertIsNotNone(sim_shell.get_sim_session("s0"), "recently used was evicted")
        self.assertIsNone(sim_shell.get_sim_session("s1"), "coldest entry survived")

    def test_eviction_closes_stream_handles(self):
        """Dropping the dict entry alone would leak the reader thread and its socket
        — the exact resource this registry exists to bound."""
        stream = _FakeStream()
        with mock.patch.object(sim_shell, "_SIM_MAX_SESSIONS", 1):
            sim_shell.register_sim_session("old", "res-old", "generic", {"engine": None})
            with sim_shell._SIM_LOCK:
                sim_shell._SIM_SESSIONS["old"]["streams"] = {"x": stream}
            sim_shell.register_sim_session("new", "res-new", "generic", {"engine": None})
        self.assertTrue(stream.closed, "an evicted session leaked its stream")

    def test_a_broken_stream_does_not_block_eviction(self):
        class _Boom:
            def close(self):
                raise RuntimeError("socket already gone")

        with mock.patch.object(sim_shell, "_SIM_MAX_SESSIONS", 1):
            sim_shell.register_sim_session("old", "res-old", "generic", {"engine": None})
            with sim_shell._SIM_LOCK:
                sim_shell._SIM_SESSIONS["old"]["streams"] = {"x": _Boom()}
            sim_shell.register_sim_session("new", "res-new", "generic", {"engine": None})
        self.assertEqual(sim_shell.sim_session_count(), 1)

    def test_cap_of_zero_disables_the_limit(self):
        """An escape hatch for debugging must not silently mean 'evict everything'."""
        with mock.patch.object(sim_shell, "_SIM_MAX_SESSIONS", 0):
            self._register(12)
        self.assertEqual(sim_shell.sim_session_count(), 12)

    def test_normal_concurrency_is_untouched_by_the_default_cap(self):
        """MAX_CONCURRENT_LABS is 12; the default cap must not bite in normal use,
        or every busy period would churn snapshots for no reason."""
        self.assertGreaterEqual(sim_shell._SIM_MAX_SESSIONS, 24)
        self._register(12)
        self.assertEqual(sim_shell.sim_session_count(), 12)

    def test_idle_eviction_still_works_alongside_the_cap(self):
        self._register(3)
        with sim_shell._SIM_LOCK:
            for entry in sim_shell._SIM_SESSIONS.values():
                entry["last_access"] = 0  # far past the TTL
            sim_shell._evict_idle_locked()
        self.assertEqual(sim_shell.sim_session_count(), 0)
