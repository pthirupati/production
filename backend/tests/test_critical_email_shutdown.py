"""Audit Z6-16 remainder — a deploy mid-send silently dropped an OTP.

Critical mail (OTP, password reset) is sent from the web process in a thread rather
than via Celery, so that sign-in does not depend on the queue being up. That part is
a reasonable trade. The problem was `daemon=True`: daemon threads are killed when
the interpreter exits, so a rolling deploy landing between "we told the user their
code was sent" and "the SMTP call returned" **dropped the message** — no queue, no
retry, and nothing in any log saying it had happened. The user saw a success screen
and waited for an email that no longer existed anywhere.

The fix deliberately does **not** make the threads non-daemon. That would let one
hung SMTP connection block interpreter exit indefinitely, converting a dropped email
into a stuck deploy — a worse failure, and a much harder one to diagnose at 2am.
Instead the threads are tracked and given a *bounded* window to finish at exit.

So there are two properties here, and both matter:

* the common case now completes instead of being killed;
* the pathological case still exits, but says who did not get their mail.

The second is what these tests mostly guard, because a silent drop was the original
bug and "fixed it by hiding it better" is the obvious way to regress.
"""

import threading
import time
from unittest import mock

from django.test import SimpleTestCase

from apps.notifications import email_dispatch


class _Barrier:
    """A send that blocks until released, so a 'still in flight' state is real
    rather than simulated by patching `is_alive`."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self, *args, **kwargs):
        self.started.set()
        self.release.wait(timeout=10)
        return True


class InFlightSendsAreTrackedTests(SimpleTestCase):
    """The registry is the whole mechanism. If sends are not tracked, the drain has
    nothing to wait for and the fix is decorative."""

    def setUp(self):
        email_dispatch._inflight.clear()
        self.addCleanup(email_dispatch._inflight.clear)

    def test_a_critical_send_is_registered_while_it_runs(self):
        barrier = _Barrier()
        with mock.patch.object(email_dispatch, "send_email_now", barrier):
            email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
            self.assertTrue(barrier.started.wait(timeout=5))
            with email_dispatch._inflight_lock:
                tracked = {addr for _, addr in email_dispatch._inflight}
            self.assertIn(
                "user@example.com", tracked,
                "the send is not tracked, so shutdown cannot wait for it",
            )
            barrier.release.set()

    def test_it_is_deregistered_once_delivered(self):
        """Otherwise the set grows for the process lifetime and every shutdown waits
        on threads that finished hours ago."""
        with mock.patch.object(email_dispatch, "send_email_now", return_value=True):
            email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with email_dispatch._inflight_lock:
                if not email_dispatch._inflight:
                    break
            time.sleep(0.01)
        with email_dispatch._inflight_lock:
            self.assertEqual(email_dispatch._inflight, set())

    def test_it_is_deregistered_even_when_the_send_raises(self):
        """A leak on the error path is the one that matters — those are the sends
        most likely to be in flight when something is going wrong enough to trigger
        a restart."""
        with mock.patch.object(
            email_dispatch, "send_email_now", side_effect=RuntimeError("smtp down")
        ):
            email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with email_dispatch._inflight_lock:
                if not email_dispatch._inflight:
                    break
            time.sleep(0.01)
        with email_dispatch._inflight_lock:
            self.assertEqual(email_dispatch._inflight, set())

    def test_non_critical_mail_is_not_tracked(self):
        """Guard the guard: queued mail is Celery's problem and already durable.
        Tracking it would make every shutdown wait on the wrong things."""
        with mock.patch("apps.notifications.tasks.send_notification_email.apply_async"):
            email_dispatch.dispatch_notification_email(
                "Weekly digest", "user@example.com", "emails/x.html", critical=False
            )
        with email_dispatch._inflight_lock:
            self.assertEqual(email_dispatch._inflight, set())


class TheDrainWaitsForDeliveryTests(SimpleTestCase):
    def setUp(self):
        email_dispatch._inflight.clear()
        self.addCleanup(email_dispatch._inflight.clear)

    def test_the_drain_waits_for_an_in_flight_send_to_finish(self):
        """The point of the whole change: at exit, a send that is nearly done gets
        to finish instead of being killed."""
        delivered = threading.Event()

        def slow_send(*args, **kwargs):
            time.sleep(0.2)
            delivered.set()
            return True

        with mock.patch.object(email_dispatch, "send_email_now", slow_send):
            email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
            self.assertFalse(delivered.is_set(), "test is not exercising the wait")
            email_dispatch._drain_inflight_sends()
            self.assertTrue(
                delivered.is_set(),
                "the drain returned before the send completed — the OTP would have "
                "been killed at interpreter exit, which is the original bug",
            )

    def test_the_drain_is_a_no_op_when_nothing_is_in_flight(self):
        """The overwhelmingly common shutdown. It must not add latency."""
        started = time.monotonic()
        email_dispatch._drain_inflight_sends()
        self.assertLess(time.monotonic() - started, 0.5)


class AHungSendNeverBlocksShutdownTests(SimpleTestCase):
    """The reason the threads stay daemons. A stuck SMTP connection must not be able
    to hold a deploy open, or one dropped email becomes an outage."""

    def setUp(self):
        email_dispatch._inflight.clear()
        self.addCleanup(email_dispatch._inflight.clear)

    def test_the_drain_gives_up_after_the_timeout(self):
        barrier = _Barrier()
        with mock.patch.object(email_dispatch, "send_email_now", barrier), \
                mock.patch.object(email_dispatch, "CRITICAL_DRAIN_TIMEOUT_SECONDS", 0.3):
            email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
            self.assertTrue(barrier.started.wait(timeout=5))
            started = time.monotonic()
            email_dispatch._drain_inflight_sends()
            elapsed = time.monotonic() - started
            barrier.release.set()

        self.assertLess(
            elapsed, 3,
            "the drain blocked on a hung send — a stuck mail server would now hang "
            "every deploy, which is worse than the bug being fixed",
        )

    def test_the_threads_remain_daemons(self):
        """Stated as a test because 'just make it non-daemon' is the obvious-looking
        simplification, and it reintroduces the hang above."""
        barrier = _Barrier()
        with mock.patch.object(email_dispatch, "send_email_now", barrier):
            email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
            self.assertTrue(barrier.started.wait(timeout=5))
            with email_dispatch._inflight_lock:
                threads = [t for t, _ in email_dispatch._inflight]
            self.assertTrue(all(t.daemon for t in threads))
            barrier.release.set()

    def test_an_abandoned_send_is_logged_with_its_recipient(self):
        """The single most important line in the change. A dropped OTP is
        unavoidable in the limit; a *silent* dropped OTP is the actual defect —
        support cannot act on what was never recorded."""
        barrier = _Barrier()
        with mock.patch.object(email_dispatch, "send_email_now", barrier), \
                mock.patch.object(email_dispatch, "CRITICAL_DRAIN_TIMEOUT_SECONDS", 0.2), \
                self.assertLogs("apps.notifications.email_dispatch", "ERROR") as logs:
            email_dispatch.dispatch_notification_email(
                "Your code", "dropped@example.com", "emails/otp.html", critical=True
            )
            self.assertTrue(barrier.started.wait(timeout=5))
            email_dispatch._drain_inflight_sends()
            barrier.release.set()

        blob = "\n".join(logs.output)
        self.assertIn("dropped@example.com", blob)
        self.assertIn("undelivered", blob)

    def test_a_completed_send_is_not_reported_as_abandoned(self):
        """Guard the guard: crying wolf on every clean shutdown would train everyone
        to ignore the line that matters."""
        with mock.patch.object(email_dispatch, "send_email_now", return_value=True):
            email_dispatch.dispatch_notification_email(
                "Your code", "fine@example.com", "emails/otp.html", critical=True
            )
            with self.assertNoLogs("apps.notifications.email_dispatch", "ERROR"):
                email_dispatch._drain_inflight_sends()


class TheDrainIsRegisteredAtExitTests(SimpleTestCase):
    """A drain nobody calls is decoration — this is the wiring the fix depends on."""

    def test_the_drain_is_registered_at_import(self):
        """`atexit` exposes no public registry to introspect, so this asserts on the
        module source. That is weaker than calling it, but the alternative is no
        coverage at all on the line that makes the whole mechanism run — deleting
        the `atexit.register` call would otherwise leave every other test in this
        file passing while the drain never fires in production."""
        import inspect

        source = inspect.getsource(email_dispatch)
        self.assertIn("atexit.register(_drain_inflight_sends)", source)


class CriticalMailStillReturnsImmediatelyTests(SimpleTestCase):
    """The reason this path exists at all. If tracking made dispatch synchronous, the
    login request would now block on SMTP."""

    def setUp(self):
        email_dispatch._inflight.clear()
        self.addCleanup(email_dispatch._inflight.clear)

    def test_dispatch_does_not_block_on_the_send(self):
        barrier = _Barrier()
        with mock.patch.object(email_dispatch, "send_email_now", barrier):
            started = time.monotonic()
            result = email_dispatch.dispatch_notification_email(
                "Your code", "user@example.com", "emails/otp.html", critical=True
            )
            elapsed = time.monotonic() - started
            barrier.release.set()

        self.assertTrue(result)
        self.assertLess(
            elapsed, 1,
            "dispatch now blocks on delivery — every OTP request pays the SMTP "
            "round trip",
        )
