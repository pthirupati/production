"""Audit Z5-16 (backpressure half) — a firehose command could pin a worker.

`_read_output` forwarded every 4 KB chunk as its own JSON frame with no
server-side bound, so `yes`, `cat /dev/urandom` or a runaway log tail was limited
only by the client's TCP window. A fast client therefore costs a thread hop, a
`json.dumps` and a WebSocket frame per 4 KB indefinitely — on a box that also has
to serve every other lab.

The design choices worth pinning:

* the budget is **bytes per second**, not a total. The goal is to stop one session
  monopolising a worker, not to truncate legitimate output — a lab printing a
  large file should still finish, just not faster than anyone can read it;
* it **sleeps rather than drops**. Discarding output would corrupt the terminal
  stream, which is a worse failure than slowing it, and the sleep is the actual
  mechanism: it yields the event loop so other sessions get scheduled;
* the threshold sits far above interactive use, so ordinary work never reaches
  this code path at all. A test pins that, because a limiter that engages during
  normal typing would be a regression dressed as a fix.
"""
import asyncio
import time
from unittest import mock

from django.test import SimpleTestCase

from apps.terminal.consumers import (
    OUTPUT_BYTES_PER_SECOND,
    OUTPUT_THROTTLE_SLEEP,
    TerminalConsumer,
)


def _consumer():
    """A consumer with only the fields the limiter touches.

    Constructing the real object would open sockets; the method under test is pure
    accounting over four attributes.
    """
    c = TerminalConsumer.__new__(TerminalConsumer)
    c._out_window_start = 0.0
    c._out_bytes_in_window = 0
    c._throttle_notified = False
    c.lab_session = mock.Mock(id="test-session")
    return c


class TheLimiterEngagesOnlyUnderFirehoseTests(SimpleTestCase):
    def test_interactive_output_is_never_throttled(self):
        """A full 200x50 screen redraw is ~40 KB. If this path engaged during normal
        typing it would be a regression dressed as a fix."""
        c = _consumer()
        slept = []
        with mock.patch("asyncio.sleep", side_effect=lambda d: slept.append(d) or asyncio.sleep(0)):
            for _ in range(50):
                asyncio.run(c._apply_output_backpressure(40 * 1024))
        self.assertEqual(slept, [], "normal terminal output was throttled")

    def test_a_firehose_is_throttled(self):
        c = _consumer()
        slept = []

        async def _fake_sleep(d):
            slept.append(d)

        with mock.patch("asyncio.sleep", _fake_sleep):
            asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND + 1))
        self.assertEqual(
            slept, [OUTPUT_THROTTLE_SLEEP],
            "output past the per-second budget was forwarded without pausing",
        )

    def test_the_budget_refills_each_second(self):
        """Otherwise the first big burst throttles the session permanently."""
        c = _consumer()
        slept = []

        async def _fake_sleep(d):
            slept.append(d)

        with mock.patch("asyncio.sleep", _fake_sleep):
            asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND + 1))
            self.assertEqual(len(slept), 1)
            # Move the window on.
            c._out_window_start = time.monotonic() - 2.0
            asyncio.run(c._apply_output_backpressure(1024))
        self.assertEqual(
            len(slept), 1, "the session stayed throttled after its window reset"
        )

    def test_sustained_output_keeps_being_throttled(self):
        """Guard the guard: if the window reset on every call the limiter would
        never engage twice, and a sustained firehose would run unbounded."""
        c = _consumer()
        slept = []

        async def _fake_sleep(d):
            slept.append(d)

        with mock.patch("asyncio.sleep", _fake_sleep):
            for _ in range(4):
                asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND))
        self.assertGreaterEqual(len(slept), 3)


class ItSlowsRatherThanTruncatesTests(SimpleTestCase):
    def test_no_output_is_discarded(self):
        """Dropping bytes would corrupt the terminal stream — a worse failure than
        slowing it. The method returns None and never signals a skip."""
        c = _consumer()

        async def _noop(_):
            return None

        with mock.patch("asyncio.sleep", _noop):
            result = asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND * 10))
        self.assertIsNone(result)

    def test_the_read_loop_still_sends_after_throttling(self):
        """The call site must not treat throttling as a reason to stop streaming."""
        import inspect

        src = inspect.getsource(TerminalConsumer._read_output)
        idx = src.index("_apply_output_backpressure")
        after = src[idx:]
        self.assertIn(
            "_safe_send", after,
            "backpressure is applied but the chunk is no longer sent — output would "
            "be silently dropped",
        )


class TheNoticeIsNotItselfAFirehoseTests(SimpleTestCase):
    def test_it_logs_once_per_window_not_per_chunk(self):
        c = _consumer()

        async def _noop(_):
            return None

        with mock.patch("asyncio.sleep", _noop), \
                mock.patch("apps.terminal.consumers.logger") as log:
            for _ in range(20):
                asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND))
        self.assertEqual(
            log.info.call_count, 1,
            "a throttle notice printed at firehose rate is itself a firehose",
        )

    def test_it_logs_again_in_a_new_window(self):
        c = _consumer()

        async def _noop(_):
            return None

        with mock.patch("asyncio.sleep", _noop), \
                mock.patch("apps.terminal.consumers.logger") as log:
            asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND))
            c._out_window_start = time.monotonic() - 2.0
            asyncio.run(c._apply_output_backpressure(OUTPUT_BYTES_PER_SECOND))
        self.assertEqual(log.info.call_count, 2)


class TheThresholdIsSaneTests(SimpleTestCase):
    def test_it_is_well_above_a_screen_redraw(self):
        self.assertGreater(
            OUTPUT_BYTES_PER_SECOND, 512 * 1024,
            "the cap is low enough to interfere with ordinary terminal use",
        )

    def test_it_is_low_enough_to_bound_a_firehose(self):
        self.assertLessEqual(
            OUTPUT_BYTES_PER_SECOND, 16 * 1024 * 1024,
            "the cap is so high it never engages, which is the bug it fixes",
        )

    def test_the_pause_yields_but_does_not_stall(self):
        self.assertGreater(OUTPUT_THROTTLE_SLEEP, 0)
        self.assertLessEqual(
            OUTPUT_THROTTLE_SLEEP, 0.5,
            "a long pause makes legitimate large output feel broken",
        )
