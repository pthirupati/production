"""
Tests for the global lab-capacity cap (PRODUCTION_AUDIT SCALE-01).

The single Docker labs engine has finite capacity. StartLabView must shed new
starts with a clean 503 (NOT a 500 / stack trace) once the platform-wide
``MAX_CONCURRENT_LABS`` ceiling is reached, must free the slot when a session is
torn down, and must not overshoot the cap under concurrent starts.
"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
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


def require_postgres(test_case, reason):
    """Skip a lock-dependent test on SQLite — but never silently in CI.

    These race tests are the only thing exercising the advisory-lock paths, and
    the guard used to be purely vendor-conditional (``if vendor == "sqlite":
    skipTest``). That is correct locally, where SQLite is intentional, but it
    also means CI reports ``OK (skipped=1)`` if the Postgres service container
    ever fails to come up or ``config.test_settings`` stops selecting it — the
    exact coverage CI exists to provide would vanish and the run would still be
    green.

    So on GitHub Actions a SQLite vendor is a hard failure, not a skip: CI is
    explicitly provisioned with postgres:16 (.github/workflows/ci.yml and the
    ci-tests job in tests.yml), so landing on SQLite there is always a broken
    harness rather than an expected environment.
    """
    if connection.vendor != "sqlite":
        return
    if os.environ.get("GITHUB_ACTIONS") == "true":
        test_case.fail(
            f"{reason}: CI must run these tests against the Postgres service "
            f"container, but connection.vendor == 'sqlite'. The Postgres service "
            f"or config.test_settings DB selection is broken — do not skip this."
        )
    test_case.skipTest(reason)


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
        require_postgres(self, "Race-safety requires PostgreSQL advisory locks")

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


@override_settings(MAX_CONCURRENT_LABS=3)
class StartLabSessionCapacityTests(TestCase):
    """``apps.labs.sessions.start_lab_session`` must honour the global ceiling.

    Audit L1506/L1511. This helper used to INSERT a PROVISIONING row without ever
    calling ``at_global_capacity``, so every caller of it bypassed
    ``MAX_CONCURRENT_LABS`` outright. The two known call paths were moved off it,
    which is what makes these tests the only thing standing between a future
    caller and the same bypass.

    Gate logic only: the advisory lock is a documented no-op on SQLite, so true
    cross-connection concurrency is covered by ``CapacityCapRaceTests`` (Postgres)
    rather than here.
    """

    def setUp(self):
        self.scenario = _make_docker_scenario(slug="cap-helper")
        self.holders = [
            User.objects.create_user(username=f"sh{i}", email=f"sh{i}@t.com", password="Pass123!x")
            for i in range(3)
        ]
        self.user = User.objects.create_user(
            username="sh-starter", email="sh-starter@t.com", password="Pass123!x",
        )

    def _fill_to_cap(self):
        for holder in self.holders:
            _running_docker_session(holder, self.scenario)
        self.assertEqual(count_active_engine_labs(), 3)

    @patch("apps.labs.sessions.get_provisioner")
    def test_refuses_to_create_session_at_capacity(self, mock_get_provisioner):
        from apps.labs.sessions import LabCapacityError, start_lab_session

        self._fill_to_cap()
        before = LabSession.objects.count()

        with self.assertRaises(LabCapacityError):
            start_lab_session(self.user, self.scenario)

        # The whole point: a shed start must leave NO row behind. Pre-fix this
        # helper had already INSERTed a PROVISIONING row before anything could
        # object, permanently consuming a slot beyond the cap.
        self.assertEqual(LabSession.objects.count(), before)
        self.assertFalse(
            LabSession.objects.filter(user=self.user).exists(),
            "start_lab_session created a session past MAX_CONCURRENT_LABS",
        )
        # And it must bail out *before* touching the provisioner — an over-cap
        # start that still provisions is exactly the engine exhaustion the cap
        # exists to prevent.
        mock_get_provisioner.assert_not_called()

    @patch("apps.labs.sessions.get_provisioner")
    def test_starts_normally_under_capacity(self, mock_get_provisioner):
        """The gate must shed only at the ceiling, not break the happy path."""
        from apps.labs.sessions import start_lab_session

        _running_docker_session(self.holders[0], self.scenario)  # 1 of 3 used
        mock_get_provisioner.return_value.provision.return_value = ("res-1", "name-1")

        session = start_lab_session(self.user, self.scenario)

        self.assertEqual(session.status, "RUNNING")
        self.assertEqual(session.user, self.user)
        mock_get_provisioner.return_value.provision.assert_called_once()

    @patch("apps.labs.sessions.get_provisioner")
    def test_cloud_start_exempt_from_global_ceiling(self, mock_get_provisioner):
        """Per-VM cloud providers run against vendor quota, so the cap must not shed them."""
        from apps.labs.sessions import start_lab_session

        self._fill_to_cap()
        self.scenario.infrastructure_type = "digitalocean"
        self.scenario.lab_mode = "digitalocean"
        self.scenario.save(update_fields=["infrastructure_type", "lab_mode"])
        mock_get_provisioner.return_value.provision.return_value = ("droplet-1", "droplet-name")

        session = start_lab_session(self.user, self.scenario)

        self.assertEqual(session.provider, "digitalocean")
        self.assertEqual(session.status, "RUNNING")

    @patch("apps.labs.sessions.get_provisioner")
    def test_failed_provision_releases_the_slot(self, mock_get_provisioner):
        """A dead start must not hold a capacity slot forever.

        FAILED is terminal, so ``count_active_engine_labs`` stops counting it —
        that is what returns the slot. Without this, a run of provisioning
        failures would silently eat the platform's whole ceiling.
        """
        from apps.labs.sessions import start_lab_session

        _running_docker_session(self.holders[0], self.scenario)
        mock_get_provisioner.return_value.provision.side_effect = RuntimeError("ssh down")

        with self.assertRaises(RuntimeError):
            start_lab_session(self.user, self.scenario)

        session = LabSession.objects.get(user=self.user)
        self.assertEqual(session.status, "FAILED")
        self.assertEqual(count_active_engine_labs(), 1, "failed start kept its capacity slot")

    def test_reserve_does_no_network_io_inside_the_lock(self):
        """The reserve phase must stay pure-DB.

        The capacity advisory lock is platform-wide and transaction-scoped: any
        SSH/API round trip inside that block serialises *every* lab start on the
        platform behind the slowest provision. Pinning the split here so the two
        phases cannot be re-merged back into one atomic block.
        """
        from apps.labs.sessions import reserve_lab_session

        with patch("apps.labs.sessions.get_provisioner") as mock_get_provisioner:
            session = reserve_lab_session(self.user, self.scenario)

        self.assertEqual(session.status, "PROVISIONING")
        mock_get_provisioner.assert_not_called()


class RequirePostgresGuardTests(TestCase):
    """The CI skip-guard itself must not be able to go silent.

    B8 (audit L1554) asks for the advisory-lock race tests to actually *run* in
    CI. The infrastructure for that already exists, so the residual risk is not
    "CI lacks Postgres" but "CI silently stops using it and nobody notices":
    a vendor-only skip turns that regression into a green run. These tests pin
    the guard's behaviour in both environments so the loud-in-CI property cannot
    be quietly reverted.
    """

    def test_skips_on_sqlite_outside_ci(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}, clear=False), \
                patch.object(type(connections["default"]), "vendor", "sqlite"):
            with self.assertRaises(unittest.SkipTest):
                require_postgres(self, "needs pg")

    def test_fails_loudly_on_sqlite_inside_ci(self):
        # The whole point: in CI a SQLite vendor must break the build instead of
        # skipping, because CI is provisioned with postgres:16 and landing on
        # SQLite there means the harness is broken.
        #
        # Caught as BaseException on purpose. SkipTest does NOT inherit from
        # Exception, so the obvious `assertRaises(self.failureException)` lets a
        # regressed guard raise SkipTest straight through the assertion — this
        # very test then reports "skipped" and the suite still prints OK. That
        # is the exact silent-skip failure mode being defended against, so the
        # test must not be susceptible to it. Verified by mutation: reverting
        # the guard to a vendor-only skipTest turns this into a real failure.
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False), \
                patch.object(type(connections["default"]), "vendor", "sqlite"):
            try:
                require_postgres(self, "needs pg")
            except BaseException as exc:  # noqa: BLE001 - see rationale above
                raised = exc
            else:
                raised = None

        self.assertIsNotNone(raised, "guard must not pass silently on SQLite in CI")
        self.assertNotIsInstance(
            raised, unittest.SkipTest,
            "guard skipped instead of failing in CI — the race tests would "
            "vanish from CI while the run still reports OK",
        )
        self.assertIsInstance(raised, self.failureException)
        self.assertIn("connection.vendor == 'sqlite'", str(raised))

    def test_no_op_on_postgres_in_ci(self):
        # Must neither skip nor fail when the vendor is correct.
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False), \
                patch.object(type(connections["default"]), "vendor", "postgresql"):
            require_postgres(self, "needs pg")
