"""Simulation snapshots must be debounced without letting grading read stale state.

persist_session_snapshot used to run on EVERY command line. Measured ~15 KB of
JSONB per snapshot, and Postgres has no partial JSONB update, so each one is a
full row rewrite producing a dead tuple. At 60 concurrent labs x ~20 commands/min
that is ~20 writes/sec and roughly 1 GB/hour of write amplification on
labs_labsession — the dominant write load in the system.

The first cut of this debounce was leading-edge only, justified as "the snapshot is
just a durability backstop, so slightly stale is fine". That reasoning was WRONG,
and these tests exist to keep it from coming back:

grading is a SEPARATE HTTP request. ValidateLabView -> run_validation looks the
session up in the handling worker's process-local _SIM_SESSIONS, and with
UVICORN_WORKERS>1 that is usually not the worker holding the websocket — so it
falls back to ensure_sim_session(), which rehydrates from
LabSession.simulation_snapshot. Leading-edge-only debouncing therefore let a
learner apply the correct fix, click Check Solution, and be graded against state up
to SNAPSHOT_MIN_INTERVAL seconds old: a false failure on correct work.

Hence the trailing-edge flush. Both properties must hold simultaneously:
  * a burst of commands collapses to ~2 writes, not one per command, and
  * the snapshot is never left stale for longer than SNAPSHOT_TRAILING_DELAY.
"""
import asyncio
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from apps.terminal.consumers import TerminalConsumer


class _FakeSession:
    id = "11111111-2222-3333-4444-555555555555"


class _ConsumerMixin:
    # Keep the trailing flush fast so tests don't sleep 1.5s each.
    TRAILING = 0.02

    def _consumer(self):
        c = TerminalConsumer.__new__(TerminalConsumer)
        c.lab_session = _FakeSession()
        c.provider_type = "simulation"
        c._last_snapshot_at = 0.0
        c._snapshot_pending = False
        c._trailing_snapshot_task = None
        c.SNAPSHOT_TRAILING_DELAY = self.TRAILING
        return c

    async def _settle(self, factor=6):
        """Let any armed trailing task run."""
        await asyncio.sleep(self.TRAILING * factor)


class SnapshotDebounceTests(_ConsumerMixin, SimpleTestCase):
    async def test_first_call_writes(self):
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
            c._cancel_trailing_snapshot()
        self.assertEqual(to_thread.await_count, 1)

    async def test_rapid_calls_collapse(self):
        """20 commands in quick succession must not produce 20 JSONB rewrites."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            for _ in range(20):
                await c._maybe_snapshot_simulation()
            immediate = to_thread.await_count
            c._cancel_trailing_snapshot()
        self.assertEqual(
            immediate, 1,
            "debounce did not collapse rapid commands — write amplification remains",
        )

    async def test_write_resumes_after_the_interval(self):
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
            c._last_snapshot_at -= (c.SNAPSHOT_MIN_INTERVAL + 1)
            await c._maybe_snapshot_simulation()
            c._cancel_trailing_snapshot()
        self.assertEqual(to_thread.await_count, 2)

    async def test_force_always_writes(self):
        """The disconnect flush must ignore the debounce window."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
            await c._maybe_snapshot_simulation(force=True)
            c._cancel_trailing_snapshot()
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


class TrailingFlushTests(_ConsumerMixin, SimpleTestCase):
    """The regression that made grading read stale state."""

    async def test_suppressed_write_is_flushed_on_the_trailing_edge(self):
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()          # leading write
            await c._maybe_snapshot_simulation()          # suppressed -> arms trailing
            self.assertEqual(to_thread.await_count, 1)
            await self._settle()
            self.assertEqual(
                to_thread.await_count, 2,
                "the suppressed snapshot was never flushed — grading on another "
                "worker would rehydrate stale state and fail correct work",
            )
            self.assertFalse(c._snapshot_pending)

    async def test_burst_then_grade_sees_current_state(self):
        """The end-to-end invariant: after a burst settles, nothing is pending."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            for _ in range(20):
                await c._maybe_snapshot_simulation()
            await self._settle()
            self.assertFalse(
                c._snapshot_pending,
                "state still un-snapshotted after the burst settled",
            )
            # Cheap: 20 commands -> 2 writes, not 20.
            self.assertEqual(to_thread.await_count, 2)

    async def test_each_command_rearms_the_trailing_flush(self):
        """A steady stream must not flush mid-burst on every command."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()  # leading write
            for _ in range(5):
                await c._maybe_snapshot_simulation()
                await asyncio.sleep(self.TRAILING / 4)  # faster than the delay
            self.assertEqual(
                to_thread.await_count, 1,
                "trailing flush fired mid-burst instead of being re-armed",
            )
            await self._settle()
            self.assertEqual(to_thread.await_count, 2)

    async def test_forced_flush_cancels_pending_trailing_task(self):
        """disconnect()'s flush must not be followed by a redundant write."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
            await c._maybe_snapshot_simulation()   # arms trailing
            await c._maybe_snapshot_simulation(force=True)  # disconnect-style flush
            self.assertEqual(to_thread.await_count, 2)
            await self._settle()
            self.assertEqual(
                to_thread.await_count, 2,
                "trailing task still fired after a forced flush — extra JSONB rewrite",
            )

    async def test_trailing_task_does_nothing_when_not_pending(self):
        c = self._consumer()
        c._snapshot_pending = False
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._trailing_snapshot()
        self.assertEqual(to_thread.await_count, 0)

    async def test_trailing_flush_survives_self_cancellation(self):
        """The trailing task calls back into a path that cancels trailing tasks;
        it must not cancel itself and lose the write."""
        c = self._consumer()
        with patch("asyncio.to_thread", new=AsyncMock()) as to_thread:
            await c._maybe_snapshot_simulation()
            await c._maybe_snapshot_simulation()
            await self._settle()
        self.assertEqual(
            to_thread.await_count, 2,
            "the trailing task cancelled itself before writing",
        )
