"""Audit Z5-7 — a leak measured in file descriptors against another host.

`_active_holders` in `labs/provisioner/exec_stream.py` is process-local, but
`release_holder(session_key)` is also called from `terminate_lab_session`, which
runs in whatever process handled the termination — an HTTP request or a Celery
worker, not the uvicorn worker that registered the holder. There the pop is a
no-op, and the entry survives in the holding worker forever.

That is worse than an ordinary memory leak. Each holder deliberately pins the
docker-py client and the underlying HTTP response as GC roots, because without
them docker-py collects the connection and the exec stream drops after a second
or two. So every orphan holds **a live socket to the D4 docker daemon**: the leak
is file descriptors against a different machine, and it ends in D4 refusing
connections rather than in this process using more RAM.

The WebSocket disconnect stays the primary release. What is tested here is the
backstop for when it cannot run — worker restart, ungraceful close, or a release
issued from the wrong process.

Two properties are pinned that a naive `dict.pop` version would fail:

* eviction must **close** the holder, not merely forget it. Dropping the dict
  entry only removes the GC root; the descriptor is what needs releasing, and
  that is the entire point of the fix.
* `close()` must happen **outside** the registry lock. It touches a socket and
  can block, and holding the lock across it would stall every other terminal
  connection in the worker — trading a slow leak for a fast hang.
"""
import threading
import time
from unittest import mock

from django.test import SimpleTestCase

from apps.labs.provisioner import exec_stream
from apps.labs.provisioner.exec_stream import (
    HOLDER_TTL_SECONDS,
    MAX_HOLDERS,
    ExecStreamHolder,
    register_holder,
    release_holder,
    tracked_holder_count,
)


class _FakeSocket:
    def __init__(self):
        self.closed = False


class _ObservableHolder(ExecStreamHolder):
    """`ExecStreamHolder` uses __slots__, so `close` cannot be patched per-instance.

    Subclassing keeps every real code path (registration, keying, eviction)
    unchanged while making the close observable — patching the module-level
    `_close_quietly` instead would stop testing the thing that matters, which is
    that eviction closes the socket rather than merely forgetting it.
    """

    __slots__ = ("close",)

    def __init__(self, exec_id):
        super().__init__(_FakeSocket(), exec_id=exec_id)
        self.close = mock.Mock(
            side_effect=lambda: setattr(self.socket, "closed", True)
        )


def _fake_holder(exec_id):
    """A holder whose close() is observable and which never touches a real socket."""
    return _ObservableHolder(exec_id)


class _Base(SimpleTestCase):
    def setUp(self):
        exec_stream._active_holders.clear()
        self.addCleanup(exec_stream._active_holders.clear)


class NormalLifecycleTests(_Base):
    def test_a_registered_holder_is_tracked(self):
        register_holder("sess-1", _fake_holder("e1"))
        self.assertEqual(tracked_holder_count(), 1)

    def test_releasing_by_holder_removes_and_closes_it(self):
        h = _fake_holder("e1")
        register_holder("sess-1", h)
        release_holder("sess-1", h)
        self.assertEqual(tracked_holder_count(), 0)
        h.close.assert_called_once()

    def test_releasing_by_session_key_clears_all_its_streams(self):
        """One lab can have several terminals open."""
        for i in range(3):
            register_holder("sess-1", _fake_holder(f"e{i}"))
        register_holder("sess-2", _fake_holder("other"))
        release_holder("sess-1")
        self.assertEqual(tracked_holder_count(), 1)

    def test_one_session_release_does_not_disturb_another(self):
        keep = _fake_holder("keep")
        register_holder("sess-2", keep)
        register_holder("sess-1", _fake_holder("go"))
        release_holder("sess-1")
        self.assertEqual(tracked_holder_count(), 1)
        keep.close.assert_not_called()


class TheCeilingTests(_Base):
    def test_the_registry_cannot_grow_without_bound(self):
        """The leaking case: nothing ever releases, because the release ran in a
        different process."""
        for i in range(MAX_HOLDERS + 25):
            register_holder(f"sess-{i}", _fake_holder(f"e{i}"))
        self.assertLessEqual(tracked_holder_count(), MAX_HOLDERS)

    def test_evicted_holders_are_actually_closed(self):
        """Forgetting the entry only drops the GC root. The descriptor against D4
        is what has to be released — otherwise the fix is cosmetic."""
        first = _fake_holder("first")
        register_holder("sess-first", first)
        for i in range(MAX_HOLDERS + 5):
            register_holder(f"sess-{i}", _fake_holder(f"e{i}"))
        first.close.assert_called_once()

    def test_the_oldest_is_evicted_first(self):
        newest = None
        for i in range(MAX_HOLDERS + 3):
            newest = _fake_holder(f"e{i}")
            register_holder(f"sess-{i}", newest)
        newest.close.assert_not_called()

    def test_a_holder_that_fails_to_close_does_not_break_registration(self):
        """A socket already broken at the other end is the common case."""
        bad = _fake_holder("bad")
        bad.close = mock.Mock(side_effect=OSError("socket already gone"))
        register_holder("sess-bad", bad)
        for i in range(MAX_HOLDERS + 5):
            register_holder(f"sess-{i}", _fake_holder(f"e{i}"))
        self.assertLessEqual(tracked_holder_count(), MAX_HOLDERS)


class TheAgeLimitTests(_Base):
    def test_a_holder_older_than_any_lab_is_swept(self):
        stale = _fake_holder("stale")
        stale.registered_at = time.monotonic() - HOLDER_TTL_SECONDS - 60
        register_holder("sess-stale", stale)
        register_holder("sess-fresh", _fake_holder("fresh"))
        self.assertEqual(tracked_holder_count(), 1)
        stale.close.assert_called_once()

    def test_a_holder_inside_the_window_is_kept(self):
        """Guard the guard: a TTL that swept everything would 'fix' the leak by
        cutting live terminals out from under people."""
        live = _fake_holder("live")
        live.registered_at = time.monotonic() - 60
        register_holder("sess-live", live)
        register_holder("sess-other", _fake_holder("other"))
        self.assertEqual(tracked_holder_count(), 2)
        live.close.assert_not_called()

    def test_the_ttl_exceeds_the_longest_plausible_lab(self):
        self.assertGreaterEqual(
            HOLDER_TTL_SECONDS, 2 * 60 * 60,
            "the sweep would close terminals during long labs",
        )


class TheLockIsNotHeldDuringCloseTests(_Base):
    """`close()` touches a socket and can block. Holding the registry lock across it
    would stall every other terminal connection in the worker — a fast hang traded
    for a slow leak."""

    def test_another_thread_can_register_while_a_close_is_blocking(self):
        blocking = _fake_holder("blocking")
        blocking.registered_at = time.monotonic() - HOLDER_TTL_SECONDS - 60
        entered = threading.Event()
        allow_return = threading.Event()

        def _slow_close():
            entered.set()
            allow_return.wait(timeout=5)

        blocking.close = mock.Mock(side_effect=_slow_close)
        register_holder("sess-blocking", blocking)

        evictor = threading.Thread(
            target=register_holder, args=("sess-trigger", _fake_holder("trigger"))
        )
        evictor.start()
        self.assertTrue(entered.wait(timeout=5), "eviction never reached close()")

        # The lock must be free while the close above is still blocked.
        progressed = threading.Event()

        def _other_worker():
            register_holder("sess-other", _fake_holder("other"))
            progressed.set()

        threading.Thread(target=_other_worker).start()
        self.assertTrue(
            progressed.wait(timeout=3),
            "the registry lock is held across close() — one slow socket blocks "
            "every terminal connection in this worker",
        )

        allow_return.set()
        evictor.join(timeout=5)
