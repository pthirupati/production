"""Simulation snapshots must be debounced without losing work.

persist_session_snapshot used to run on EVERY command line. Measured ~15 KB of
JSONB per snapshot, and Postgres has no partial JSONB update, so each one is a
full row rewrite producing a dead tuple. At 60 concurrent labs x ~20 commands/min
that is ~20 writes/sec and roughly 1 GB/hour of write amplification on
labs_labsession — the dominant write load in the system.

The snapshot is a durability BACKSTOP (the authoritative engine is in memory), so
a slightly stale one is acceptable. Losing a learner's session is not — hence the
forced flush on disconnect, which these tests pin down.
"""
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from apps.terminal.consumers import TerminalConsumer


class _FakeSession:
    id = "11111111-2222-3333-4444-555555555555"


class SnapshotDebounceTests(SimpleTestCase):
    def _consumer(self):
        c = TerminalConsumer.__new__(TerminalConsumer)
        c.lab_session = _FakeSession()
        c.provider_type = "simulation"
        c._last_snapshot_at = 0.0
        c._snapshot_pending = False
        return c

    async def test_first_call_writes(self):
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
        self.assertEqual(to_thread.await_count, 1)

    async def test_rapid_calls_collapse_to_one_write(self):
        """20 commands in quick succession must not produce 20 JSONB rewrites."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            for _ in range(20):
                await c._maybe_snapshot_simulation()
        self.assertEqual(
            to_thread.await_count, 1,
            "debounce did not collapse rapid commands — write amplification remains",
        )
        self.assertTrue(
            c._snapshot_pending,
            "suppressed writes must be marked pending so the flush knows to run",
        )

    async def test_write_resumes_after_the_interval(self):
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
            # Pretend the interval has elapsed.
            c._last_snapshot_at -= (c.SNAPSHOT_MIN_INTERVAL + 1)
            await c._maybe_snapshot_simulation()
        self.assertEqual(to_thread.await_count, 2)

    async def test_force_always_writes(self):
        """The disconnect flush must ignore the debounce window."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()          # consumes the window
            await c._maybe_snapshot_simulation(force=True)  # must still write
        self.assertEqual(
            to_thread.await_count, 2,
            "forced flush was swallowed by the debounce — work could be lost",
        )

    async def test_no_write_without_a_session(self):
        c = self._consumer()
        c.lab_session = None
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation(force=True)
        self.assertEqual(to_thread.await_count, 0)

    async def test_no_write_for_non_simulation_providers(self):
        """Docker-backed labs have no engine to snapshot."""
        c = self._consumer()
        c.provider_type = "docker"
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation(force=True)
        self.assertEqual(to_thread.await_count, 0)

    async def test_persist_failure_is_swallowed_not_raised(self):
        """A best-effort backstop must never break the terminal session."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("db gone"))):
            await c._maybe_snapshot_simulation(force=True)  # must not raise
