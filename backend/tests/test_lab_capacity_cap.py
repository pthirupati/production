"""
Tests for the global lab-capacity cap (PRODUCTION_AUDIT SCALE-01).

The single Docker labs engine has finite capacity. StartLabView must shed new
starts with a clean 503 (NOT a 500 / stack trace) once the platform-wide
``MAX_CONCURRENT_LABS`` ceiling is reached, must free the slot when a session is
torn down, and must not overshoot the cap under concurrent starts.
"""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.labs.capacity import (
    at_global_capacity,
    consumes_engine_capacity,
    count_active_engine_labs,
)
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


def _make_docker_scenario(slug="cap-docker"):
    tech = Technology.objects.create(
        name=f"Tech {slug}", slug=slug, description="x", price=0, is_active=True,
    )
    return Scenario.objects.create(
        title=f"Scenario {slug}", description="x", technology=tech,
        slug=slug, category="Linux", difficulty="easy",
        lab_mode="docker", is_free=True, is_active=True,
    )


def _running_docker_session(user, scenario):
    """A session that occupies engine capacity (docker + RUNNING)."""
    return LabSession.objects.create(
        user=user, scenario=scenario, status="RUNNING", provider="docker",
        duration_limit=3600,
    )


class CapacityHelperTests(TestCase):
    """Unit-level checks of the capacity primitives."""

    def setUp(self):
        self.scenario = _make_docker_scenario()
        self.users = [
            User.objects.create_user(username=f"u{i}", email=f"u{i}@t.com", password="Pass123!x")
            for i in range(3)
        ]

    def test_docker_and_simulation_consume_capacity_cloud_does_not(self):
        # The cap is uniform resource/abuse protection: both the docker engine
        # and the in-process simulation engine (the default route for most
        # scenarios) consume shared platform capacity. Only per-VM cloud
        # providers (own vendor quota) are exempt.
        self.assertTrue(consumes_engine_capacity("docker"))
        self.assertTrue(consumes_engine_capacity(""))  # default == docker
        self.assertTrue(consumes_engine_capacity("simulation"))
        self.assertFalse(consumes_engine_capacity("aws_ec2"))
        self.assertFalse(consumes_engine_capacity("digitalocean"))

    def test_count_includes_active_docker_and_simulation_not_terminal(self):
        _running_docker_session(self.users[0], self.scenario)
        # PROVISIONING also counts.
        LabSession.objects.create(
            user=self.users[1], scenario=self.scenario, status="PROVISIONING",
            provider="docker", duration_limit=3600,
        )
        # Terminal sessions must NOT count.
        LabSession.objects.create(
            user=self.users[2], scenario=self.scenario, status="TERMINATED",
            provider="docker", duration_limit=3600,
        )
        # An active simulation session DOES count (uniform cap).
        LabSession.objects.create(
            user=self.users[2], scenario=self.scenario, status="RUNNING",
            provider="simulation", duration_limit=3600,
        )
        self.assertEqual(count_active_engine_labs(), 3)

    @override_settings(MAX_CONCURRENT_LABS=1)
    def test_at_global_capacity_true_for_all_shared_providers_when_full(self):
        _running_docker_session(self.users[0], self.scenario)
        # At the ceiling, BOTH a docker start and a simulation start are shed —
        # the cap applies uniformly to every shared-capacity provisioner.
        self.assertTrue(at_global_capacity("docker"))
        self.assertTrue(at_global_capacity("simulation"))
        # A cloud start is still exempt (its own vendor quota governs it).
        self.assertFalse(at_global_capacity("aws_ec2"))


@override_settings(MAX_CONCURRENT_LABS=2)
class CapacityCapEndpointTests(TestCase):
    """StartLabView returns a clean 503 at the cap and frees the slot on teardown."""

    def setUp(self):
        self.scenario = _make_docker_scenario()
        # Two OTHER users already hold the only two engine slots.
        self.holders = [
            User.objects.create_user(username=f"h{i}", email=f"h{i}@t.com", password="Pass123!x")
            for i in range(2)
        ]
        self.sessions = [_running_docker_session(h, self.scenario) for h in self.holders]
        self.user = User.objects.create_user(
            username="starter", email="starter@t.com", password="Pass123!x",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = f"/api/labs/{self.scenario.id}/start/"

    def test_returns_503_not_500_at_capacity(self):
        before = LabSession.objects.count()
        res = self.client.post(self.url, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE, res.content)
        self.assertEqual(res.json().get("code"), "CAPACITY_FULL")
        # Friendly message, no stack trace.
        self.assertIn("capacity", res.json().get("error", "").lower())
        # No session was created for the shed request.
        self.assertEqual(LabSession.objects.count(), before)
        self.assertFalse(
            LabSession.objects.filter(user=self.user).exists(),
            "A shed start must not leave a session behind",
        )

    @patch("apps.public_api.views.sync_lab_started", return_value={"jira_enabled": False})
    @patch("celery_app.tasks.provision_docker_lab")
    def test_slot_released_on_teardown_allows_new_start(self, mock_provision, mock_jira):
        # At capacity → 503.
        res = self.client.post(self.url, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

        # Tear one session down (the normal teardown path sets a terminal status).
        self.sessions[0].mark_terminated()
        self.assertEqual(count_active_engine_labs(), 1)

        # Slot freed → the same start now succeeds (no 500, no 503).
        res2 = self.client.post(self.url, format="json")
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED, res2.content)
        self.assertTrue(
            LabSession.objects.filter(user=self.user, status="PROVISIONING").exists()
        )
        mock_provision.delay.assert_called_once()

    @patch("apps.public_api.views.sync_lab_started", return_value={"jira_enabled": False})
    @patch("celery_app.tasks.provision_docker_lab")
    @override_settings(MAX_CONCURRENT_LABS=100)
    def test_under_capacity_start_succeeds(self, mock_provision, mock_jira):
        res = self.client.post(self.url, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)


class CapacityCapRaceTests(TransactionTestCase):
    """
    Concurrent starts must never collectively overshoot MAX_CONCURRENT_LABS.

    Uses real threads against Postgres so the advisory-lock serialisation is
    exercised. Skipped on SQLite (no cross-connection row/advisory locking — the
    advisory lock is a documented no-op there).
    """

    def setUp(self):
        self.scenario = _make_docker_scenario(slug="cap-race")
        self.users = []
        for i in range(10):
            u = User.objects.create_user(
                username=f"race{i}", email=f"race{i}@t.com", password="Pass123!x",
            )
            self.users.append(u)

    @override_settings(MAX_CONCURRENT_LABS=5)
    # Patches are installed once for the whole test (not per-thread) so the
    # shared module globals aren't stomped by concurrent enter/exit. Tasks run
    # eagerly under CELERY_TASK_ALWAYS_EAGER, so mocking .delay keeps the real
    # Docker provisioner out of the request path; sync_lab_started is mocked to
    # avoid any Jira/network call.
    @patch("celery_app.tasks.provision_docker_lab")
    @patch("apps.public_api.views.sync_lab_started", return_value={"jira_enabled": False})
    def test_concurrent_starts_do_not_exceed_cap(self, mock_jira, mock_provision):
        if connection.vendor == "sqlite":
            self.skipTest("Race-safety requires PostgreSQL advisory locks")

        results = {}

        def start(index):
            try:
                client = APIClient()
                client.force_authenticate(user=self.users[index])
                res = client.post(f"/api/labs/{self.scenario.id}/start/", format="json")
                results[index] = res.status_code
            except Exception as e:  # pragma: no cover - surfaced via assertion below
                results[index] = f"error: {e}"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(start, range(10)))

        # No request 500'd.
        self.assertNotIn(
            500, results.values(),
            f"capacity gate must never 500: {results}",
        )
        for code in results.values():
            self.assertIn(
                code, (status.HTTP_201_CREATED, status.HTTP_503_SERVICE_UNAVAILABLE),
                f"unexpected status: {results}",
            )

        # Count every shared-capacity session (docker + simulation): the docker
        # lab_mode scenario resolves to the in-process simulation engine at
        # runtime, so the created sessions carry provider="simulation" — but the
        # uniform cap governs them just the same.
        created = count_active_engine_labs()
        # The cap must hold exactly — never overshoot.
        self.assertLessEqual(created, 5, f"overshot cap: {created} active, results={results}")
        # And we should fill right up to it (10 racers, cap 5).
        self.assertEqual(created, 5, f"expected to fill the cap: {results}")
        shed = sum(1 for c in results.values() if c == status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(shed, 5, f"expected 5 shed with 503: {results}")
