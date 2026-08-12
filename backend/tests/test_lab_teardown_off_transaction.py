"""Audit Z5-9 — SSH to another host, inside a lock every lab start waits on.

`StartLabView` terminated the user's previous labs by calling
`terminate_lab_session` inline, inside the `transaction.atomic()` block that holds
both the session row lock and the **global capacity advisory lock**. That call is
network I/O — SSH to D4, or a round trip to the docker daemon — so one slow D4
response serialised lab starts for every user on the platform, not just the one
swapping labs.

The split is the whole fix, and it is not "move it all to Celery":

* the **DB half stays inside** the transaction. Capacity accounting has to be
  atomic with the INSERT, or two concurrent starts both see room under the cap.
* only the **resource teardown** is deferred, and via `transaction.on_commit`
  rather than a bare `.delay()`. A start that rolls back after this point must not
  destroy a lab the user still has running — that is the failure a naive `.delay()`
  introduces, and it is worse than the problem being fixed.

The old inline version also swallowed every failure into a `logger.warning`. On a
box with a hard capacity cap, a teardown that quietly fails is a container that
runs until the reaper notices, so the task retries.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, TransactionTestCase

from apps.labs.models import LabSession
from apps.public_api.views import _schedule_lab_teardown
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lab", email="lab@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )

    def _session(self, container_id="c123"):
        return LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="RUNNING",
            provider="docker", container_id=container_id,
        )


class TeardownIsDeferredTests(TransactionTestCase):
    """`on_commit` only fires for real on a committed transaction, so these need
    TransactionTestCase — under plain TestCase every test is inside a rollback and
    the callback would never run, which would make the assertions vacuous."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="lab2", email="lab2@example.com", password="Str0ng-Pass-1"
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )

    def _session(self):
        return LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="RUNNING",
            provider="docker", container_id="c123",
        )

    def test_nothing_happens_until_the_transaction_commits(self):
        session = self._session()
        with mock.patch("celery_app.tasks.teardown_lab_resource.apply_async") as queued:
            with transaction.atomic():
                _schedule_lab_teardown(session)
                queued.assert_not_called()   # still inside the lock
            queued.assert_called_once()

    def test_a_rolled_back_start_does_not_destroy_the_users_lab(self):
        """The bug a bare `.delay()` would introduce: the start fails, and the lab
        the user still has running is torn down anyway."""
        session = self._session()
        with mock.patch("celery_app.tasks.teardown_lab_resource.apply_async") as queued:
            try:
                with transaction.atomic():
                    _schedule_lab_teardown(session)
                    raise RuntimeError("capacity check failed after scheduling")
            except RuntimeError:
                pass
        queued.assert_not_called()

    def test_it_targets_the_provisioning_queue(self):
        session = self._session()
        with mock.patch("celery_app.tasks.teardown_lab_resource.apply_async") as queued:
            with transaction.atomic():
                _schedule_lab_teardown(session)
        self.assertEqual(queued.call_args.kwargs["queue"], "provisioning")
        self.assertEqual(queued.call_args.kwargs["args"], [str(session.id)])

    def test_an_unreachable_queue_falls_back_to_an_inline_teardown(self):
        """Better a slow request than a container nobody reclaims, on a box with a
        hard capacity cap. Still after commit, so still outside the lock."""
        session = self._session()
        with mock.patch(
            "celery_app.tasks.teardown_lab_resource.apply_async",
            side_effect=RuntimeError("broker down"),
        ), mock.patch(
            # Constructing a real provisioner opens a socket to the docker daemon,
            # which does not exist in the test environment — and the failure would
            # be swallowed by the fallback's own except, so the assertion below
            # would report "called 0 times" with no hint why.
            "apps.public_api.views.get_provisioner"
        ), mock.patch("apps.public_api.views.terminate_lab_session") as inline:
            with transaction.atomic():
                _schedule_lab_teardown(session)
        inline.assert_called_once()

    def test_a_failing_inline_fallback_does_not_raise(self):
        """This runs in an on_commit callback; raising there would surface as a 500
        on a request that had already succeeded."""
        session = self._session()
        with mock.patch(
            "celery_app.tasks.teardown_lab_resource.apply_async",
            side_effect=RuntimeError("broker down"),
        ), mock.patch("apps.public_api.views.get_provisioner"), mock.patch(
            "apps.public_api.views.terminate_lab_session",
            side_effect=RuntimeError("d4 unreachable"),
        ):
            with transaction.atomic():
                _schedule_lab_teardown(session)  # must not raise


class TheTaskItselfTests(_Base):
    def test_it_tears_down_the_resource(self):
        session = self._session()
        from celery_app.tasks import teardown_lab_resource

        with mock.patch("apps.labs.provisioner.get_provisioner"), mock.patch(
            "apps.labs.provisioner.terminate_lab_session"
        ) as term:
            result = teardown_lab_resource(str(session.id))
        term.assert_called_once()
        self.assertEqual(result["status"], "terminated")

    def test_a_session_with_no_resource_is_a_no_op(self):
        session = self._session(container_id="")
        from celery_app.tasks import teardown_lab_resource

        with mock.patch("apps.labs.provisioner.get_provisioner"), mock.patch(
            "apps.labs.provisioner.terminate_lab_session"
        ) as term:
            result = teardown_lab_resource(str(session.id))
        term.assert_not_called()
        self.assertEqual(result["status"], "no_resource")

    def test_a_deleted_session_is_a_no_op_rather_than_an_error(self):
        import uuid

        from celery_app.tasks import teardown_lab_resource

        self.assertEqual(
            teardown_lab_resource(str(uuid.uuid4()))["status"], "gone"
        )

    def test_a_failure_is_retried_rather_than_swallowed(self):
        """The inline version logged a warning and moved on. A teardown that
        quietly fails is a container running against a hard capacity cap."""
        session = self._session()
        from celery_app.tasks import teardown_lab_resource

        with mock.patch("apps.labs.provisioner.get_provisioner"), mock.patch(
            "apps.labs.provisioner.terminate_lab_session",
            side_effect=RuntimeError("d4 unreachable"),
        ), mock.patch.object(
            teardown_lab_resource, "retry", side_effect=RuntimeError("retried")
        ) as retry:
            with self.assertRaises(RuntimeError):
                teardown_lab_resource(str(session.id))
        retry.assert_called_once()


class TheTransactionNoLongerDoesNetworkIoTests(_Base):
    def test_the_start_view_does_not_terminate_inline(self):
        import inspect

        from apps.public_api import views

        src = inspect.getsource(views.StartLabView)
        self.assertNotIn(
            "terminate_lab_session(old_provisioner", src,
            "StartLabView still tears labs down inline, inside the advisory lock",
        )
        self.assertIn("_schedule_lab_teardown", src)

    def test_the_session_is_still_marked_terminated_synchronously(self):
        """Capacity accounting must be atomic with the INSERT — deferring the DB
        half too would let two concurrent starts both see room under the cap."""
        import inspect

        from apps.public_api import views

        src = inspect.getsource(views.StartLabView)
        self.assertIn("existing.mark_terminated()", src)
