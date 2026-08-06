"""Audit Z5-18 — a broker outage permanently consumed lab capacity.

Both enqueue sites called `.delay()` unguarded. The failure cascaded rather than
stopping at a 500:

1. the `LabSession` row is created,
2. `.delay()` raises because the broker is unreachable,
3. the row stays `PROVISIONING` and **counts against the global capacity cap** —
   `at_global_capacity` counts live rows deliberately, so that a provider-specific
   cap cannot be bypassed,
4. the beat task that clears stuck sessions cannot run either, because it needs the
   same broker.

So capacity filled with rows nobody could start and nothing could clear, and stayed
that way until someone noticed and cleared them by hand. The platform did not
recover on its own even after the broker came back.

Marking the session `FAILED` is what breaks step 3. The tests below are mostly about
that: the status transition is the fix, and the 503 is just how it is reported.

`FAILED` rather than deleting the row: the attempt happened, and a deleted row
loses that a user tried and could not start a lab — which is exactly the signal you
want after an outage.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.public_api.views import _enqueue_provisioning
from apps.question_bank.models import Scenario, Technology

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="q", email="q@example.com", password=PASSWORD
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )
        self.client = APIClient()

    def _session(self):
        return LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="PROVISIONING",
            provider="docker",
        )


class TheCapacitySlotIsReleasedTests(_Base):
    """The actual bug. Everything else here is reporting."""

    def test_a_broker_failure_marks_the_session_failed(self):
        session = self._session()
        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker unreachable")

        self.assertFalse(_enqueue_provisioning(task, session))

        session.refresh_from_db()
        self.assertEqual(
            session.status, "FAILED",
            "the session stayed PROVISIONING, so it still counts against the "
            "global capacity cap that nothing can clear during a broker outage",
        )

    def test_the_row_is_not_deleted(self):
        """The attempt happened. Deleting it loses that a user tried and could not
        start a lab, which is the signal you want after an outage."""
        session = self._session()
        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker unreachable")

        _enqueue_provisioning(task, session)
        self.assertTrue(LabSession.objects.filter(pk=session.pk).exists())

    def test_a_failed_session_no_longer_counts_as_live(self):
        """`at_global_capacity` counts PROVISIONING/RUNNING rows, so this is what
        actually returns the slot."""
        session = self._session()
        live = {"PROVISIONING", "RUNNING"}
        self.assertIn(session.status, live)

        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker unreachable")
        _enqueue_provisioning(task, session)

        session.refresh_from_db()
        self.assertNotIn(session.status, live)

    def test_a_successful_enqueue_leaves_the_session_alone(self):
        """Guard the guard: marking every session FAILED would 'fix' capacity by
        breaking every lab start."""
        session = self._session()
        task = mock.Mock()

        self.assertTrue(_enqueue_provisioning(task, session))

        session.refresh_from_db()
        self.assertEqual(session.status, "PROVISIONING")
        task.delay.assert_called_once_with(str(session.id))

    def test_it_never_raises_even_if_the_save_fails(self):
        """This runs in the error path of an already-failing request. Raising here
        would turn a broker outage into an unhandled 500 *and* leave the slot held.

        `LabSession` has no `error_message` field — assigning one was my first
        version of this, and it would have raised exactly here.
        """
        session = self._session()
        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker unreachable")

        with mock.patch.object(
            LabSession, "save", side_effect=RuntimeError("database gone")
        ):
            self.assertFalse(_enqueue_provisioning(task, session))

    def test_it_logs_loudly(self):
        """A silently-released slot looks identical to a lab that never started."""
        from apps.public_api import views

        session = self._session()
        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker unreachable")

        with self.assertLogs(views.logger, level="ERROR") as captured:
            _enqueue_provisioning(task, session)
        self.assertTrue(
            any("capacity slot" in line for line in captured.output),
            "the release was not reported, so a broker outage leaves no trace",
        )


class TheResponseIsHonestTests(_Base):
    def test_a_queue_outage_is_a_503_not_a_500(self):
        """The request was valid and the service is temporarily unable to fulfil
        it — which is also what tells a client it is worth retrying."""
        from apps.public_api.views import QUEUE_UNAVAILABLE_RESPONSE

        self.assertEqual(QUEUE_UNAVAILABLE_RESPONSE["code"], "QUEUE_UNAVAILABLE")
        self.assertIn("try again", QUEUE_UNAVAILABLE_RESPONSE["error"].lower())

    def test_both_enqueue_sites_are_guarded(self):
        """The cloud path had the identical unguarded `.delay()`. Fixing only the
        docker one would leave the cascade intact for AWS/DigitalOcean labs."""
        import inspect

        from apps.public_api import views

        src = inspect.getsource(views.StartLabView)
        self.assertEqual(
            src.count("_enqueue_provisioning"), 2,
            "one of the two provisioning enqueue sites is still unguarded",
        )
        self.assertNotIn(
            "provision_docker_lab.delay(", src,
            "the docker enqueue still calls .delay() directly",
        )
        self.assertNotIn(
            "provision_cloud_lab.delay(", src,
            "the cloud enqueue still calls .delay() directly",
        )
