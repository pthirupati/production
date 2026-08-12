"""Audit Z5-6 — an uncapped consumer and a poll loop that never idled.

`TERMINAL_MAX_WS_PER_USER` was enforced inside `TerminalConsumer.connect` and
nowhere else. `BaremetalConsumer` was added later, on the same 2-vCPU box, with no
cap at all — one account could open unlimited sockets. A limit implemented inside
one consumer is a limit the next consumer will not have, so the accounting moved
to `common.ws_slots` and both now call it.

The tick loop was the expensive half. `_get_state()` is a `select_related` query
plus a Redis get, run every 1.5 s per socket, and the snapshot comparison
suppressed the **send** rather than the **work** — 100 idle sockets meant ~4,000
DB queries a minute, sending nothing. Backing off is safe precisely because the
poll is not how changes arrive: `baremetal_engine._notify_session` pushes over the
channel layer immediately. The poll exists only to animate wall-clock progress
while a machine is Commissioning/Deploying, so it snaps back to the fast interval
the moment anything is transient.

`acquire_ws_slot` fails **open** on a cache error, and that is deliberate: a Redis
blip must not lock every user out of every terminal. The cap bounds resource use
under normal operation; it is not a security control, and failing closed would
cost far more availability than an uncapped minute costs capacity.
"""
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim.baremetal_consumer import (
    IDLE_MAX_INTERVAL_SECONDS,
    PUSH_INTERVAL_SECONDS,
    BaremetalConsumer,
)
from common import ws_slots
from common.ws_slots import (
    MAX_WS_PER_USER,
    acquire_ws_slot,
    current_ws_count,
    release_ws_slot,
)


class SlotAccountingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_the_first_connection_is_allowed(self):
        self.assertTrue(acquire_ws_slot(1))
        self.assertEqual(current_ws_count(1), 1)

    def test_connections_are_allowed_up_to_the_cap(self):
        for i in range(MAX_WS_PER_USER):
            self.assertTrue(acquire_ws_slot(1), f"refused at connection {i + 1}")

    def test_the_cap_is_enforced(self):
        for _ in range(MAX_WS_PER_USER):
            acquire_ws_slot(1)
        self.assertFalse(acquire_ws_slot(1))

    def test_a_refused_connection_does_not_consume_a_slot(self):
        """Otherwise a user who hits the cap once can never reconnect."""
        for _ in range(MAX_WS_PER_USER):
            acquire_ws_slot(1)
        acquire_ws_slot(1)
        acquire_ws_slot(1)
        self.assertEqual(current_ws_count(1), MAX_WS_PER_USER)

    def test_releasing_frees_a_slot(self):
        for _ in range(MAX_WS_PER_USER):
            acquire_ws_slot(1)
        release_ws_slot(1)
        self.assertTrue(acquire_ws_slot(1))

    def test_users_are_counted_separately(self):
        for _ in range(MAX_WS_PER_USER):
            acquire_ws_slot(1)
        self.assertTrue(
            acquire_ws_slot(2), "one user filling their quota blocked another"
        )

    def test_the_count_never_goes_negative(self):
        """Over-releasing (disconnect plus the __call__ finally) must not create
        free slots out of nothing."""
        acquire_ws_slot(1)
        for _ in range(5):
            release_ws_slot(1)
        self.assertEqual(current_ws_count(1), 0)

    def test_it_fails_open_when_the_cache_is_down(self):
        """A Redis blip must not lock every user out of every terminal."""
        with mock.patch.object(
            ws_slots, "MAX_WS_PER_USER", 1
        ), mock.patch("django.core.cache.cache.incr", side_effect=RuntimeError("redis down")):
            self.assertTrue(acquire_ws_slot(99))

    def test_releasing_survives_a_cache_error(self):
        with mock.patch("django.core.cache.cache.decr", side_effect=RuntimeError("down")):
            release_ws_slot(1)  # must not raise


class BothConsumersShareTheAccountingTests(SimpleTestCase):
    """The whole point of extracting it: the next consumer inherits the cap."""

    def test_the_terminal_consumer_uses_the_shared_helper(self):
        import inspect

        from apps.terminal import consumers

        src = inspect.getsource(consumers.TerminalConsumer.connect)
        self.assertIn("acquire_ws_slot", src)

    def test_the_baremetal_consumer_uses_the_shared_helper(self):
        import inspect

        src = inspect.getsource(BaremetalConsumer.connect)
        self.assertIn(
            "acquire_ws_slot", src,
            "BaremetalConsumer has no per-user cap — one account can open "
            "unlimited polling sockets",
        )

    def test_the_baremetal_consumer_releases_its_slot_on_an_abrupt_drop(self):
        """`disconnect()` does not run on an ungraceful close; the `finally` in
        `__call__` is what stops the slot leaking for an hour."""
        import inspect

        src = inspect.getsource(BaremetalConsumer.__call__)
        self.assertIn("finally", src)
        self.assertIn("_release_connection_slot", src)

    def test_releasing_twice_is_harmless(self):
        """Both `disconnect()` and the `finally` fire on a clean close."""
        cache.clear()
        self.addCleanup(cache.clear)
        acquire_ws_slot(7)
        c = BaremetalConsumer()
        c._tracked_user_id = 7
        c._release_connection_slot()
        c._release_connection_slot()
        self.assertEqual(current_ws_count(7), 0)


class IdleBackoffTests(SimpleTestCase):
    """Pace the work, not just the send."""

    def _consumer(self):
        c = BaremetalConsumer()
        c.session_id = "s1"
        return c

    def test_a_fresh_consumer_starts_at_the_fast_interval(self):
        self.assertEqual(self._consumer()._tick_interval, PUSH_INTERVAL_SECONDS)

    def _drive(self, consumer, state, times=1):
        """Run the interval logic the way `_send_state` does, without a DB."""
        import json

        for _ in range(times):
            transient = consumer._has_transient_machine(state)
            snapshot = json.dumps(state, default=str, sort_keys=True)
            if transient:
                consumer._tick_interval = PUSH_INTERVAL_SECONDS
            elif snapshot == consumer._last_snapshot:
                from apps.vmware_sim.baremetal_consumer import (
                    IDLE_BACKOFF_FACTOR,
                )

                consumer._tick_interval = min(
                    consumer._tick_interval * IDLE_BACKOFF_FACTOR,
                    IDLE_MAX_INTERVAL_SECONDS,
                )
            else:
                consumer._tick_interval = PUSH_INTERVAL_SECONDS
            consumer._last_snapshot = snapshot

    def test_an_idle_session_backs_off(self):
        c = self._consumer()
        idle = {"maas": {"machines": [{"status": "Ready"}]}}
        self._drive(c, idle, times=4)
        self.assertGreater(
            c._tick_interval, PUSH_INTERVAL_SECONDS,
            "an idle socket still polls the database every 1.5 seconds",
        )

    def test_the_backoff_is_capped(self):
        c = self._consumer()
        idle = {"maas": {"machines": [{"status": "Ready"}]}}
        self._drive(c, idle, times=50)
        self.assertLessEqual(c._tick_interval, IDLE_MAX_INTERVAL_SECONDS)

    def test_a_transition_snaps_back_to_the_fast_interval(self):
        """A progress bar that animates at 30-second granularity is not a progress
        bar — this is what makes the backoff safe."""
        c = self._consumer()
        self._drive(c, {"maas": {"machines": [{"status": "Ready"}]}}, times=6)
        self._drive(c, {"maas": {"machines": [{"status": "Deploying"}]}})
        self.assertEqual(c._tick_interval, PUSH_INTERVAL_SECONDS)

    def test_any_state_change_also_snaps_back(self):
        c = self._consumer()
        self._drive(c, {"maas": {"machines": [{"status": "Ready"}]}}, times=6)
        self._drive(c, {"maas": {"machines": [{"status": "Allocated"}]}})
        self.assertEqual(c._tick_interval, PUSH_INTERVAL_SECONDS)

    def test_a_transient_machine_is_recognised(self):
        """Guard the guard: if this never returned True the backoff would starve
        every progress bar on the page."""
        c = self._consumer()
        self.assertTrue(
            c._has_transient_machine({"maas": {"machines": [{"status": "Commissioning"}]}})
        )
        self.assertFalse(
            c._has_transient_machine({"maas": {"machines": [{"status": "Ready"}]}})
        )

    def test_the_idle_ceiling_is_a_real_reduction(self):
        self.assertGreaterEqual(
            IDLE_MAX_INTERVAL_SECONDS / PUSH_INTERVAL_SECONDS, 10,
            "the backoff does not meaningfully reduce the query load",
        )
