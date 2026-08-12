"""Audit Z5-10 — readiness said "healthy" while Redis was dead.

`readiness_check` reported only the database and Vault. Redis could be down and
the container still passed its probe, so the first visible symptom was simulation
labs silently resetting between requests (Z5-4) — which reads as a lab bug, not an
infrastructure outage. Someone had to infer "Redis" from lab behaviour.

The judgement call here is what a dead Redis should *do* to readiness, and the
answer is **degraded, not error**. The cache is configured with
`IGNORE_EXCEPTIONS: True` specifically so a Redis hiccup falls through to the
database instead of 500ing every cached endpoint. Returning 503 would pull the
node out of rotation for a condition the application is deliberately built to
survive — converting a degradation into an outage. So the probe keeps returning
200 and keeps serving; what changes is that it now *names* the failure.

This follows the Vault treatment already in the file, which is the reason the
earlier Vault outage was diagnosable at all.

The Redis probe is a set/get round trip rather than a `try/except`, because
django-redis with `IGNORE_EXCEPTIONS` swallows the connection error and returns
None — a silent miss is the normal signature of a dead Redis, and there is no
exception to catch.
"""
import json
from unittest import mock

from django.test import Client, SimpleTestCase


class _Base(SimpleTestCase):
    # Dead-database tests must not mock ensure_connection as succeeding.
    _mock_db_ok = True

    def setUp(self):
        self.client = Client()
        # SimpleTestCase forbids DB access; readiness probes Postgres first and
        # would otherwise force overall status to "error"/503 and mask the
        # Redis/broker/docker assertions these tests are actually about.
        if self._mock_db_ok:
            self._db_ok = mock.patch(
                "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
                return_value=None,
            )
            self._db_ok.start()
            self.addCleanup(self._db_ok.stop)

    def _ready(self):
        resp = self.client.get("/api/health/ready/")
        self.assertNotEqual(
            resp.status_code, 404,
            "/api/health/ready/ is not routed — this test must fail on a wrong URL "
            "rather than pass silently",
        )
        return resp, json.loads(resp.content)


class TheHappyPathTests(_Base):
    def test_readiness_reports_ok(self):
        resp, body = self._ready()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(body["status"], ("ok", "degraded"))

    def test_every_dependency_is_named(self):
        """The point of the item: a reader should not have to infer which
        dependency is broken from application behaviour."""
        _, body = self._ready()
        for dep in ("database", "vault", "redis", "broker", "docker"):
            self.assertIn(dep, body["checks"], f"{dep} is not reported at all")


class ADeadRedisIsVisibleTests(_Base):
    def test_a_silent_cache_miss_is_reported_as_unavailable(self):
        """django-redis + IGNORE_EXCEPTIONS returns None instead of raising, so a
        `try/except` probe would have reported Redis healthy while it was down."""
        with mock.patch("django.core.cache.cache.get", return_value=None):
            _, body = self._ready()
        self.assertEqual(body["checks"]["redis"]["status"], "unavailable")

    def test_a_raising_cache_is_also_reported(self):
        with mock.patch(
            "django.core.cache.cache.set", side_effect=RuntimeError("redis down")
        ):
            _, body = self._ready()
        self.assertEqual(body["checks"]["redis"]["status"], "unavailable")

    def test_it_says_what_actually_breaks(self):
        """"unavailable" alone still leaves the on-call reader guessing at impact."""
        with mock.patch("django.core.cache.cache.get", return_value=None):
            _, body = self._ready()
        note = body["checks"]["redis"].get("note", "").lower()
        self.assertIn("simulation", note)

    def test_the_overall_status_degrades(self):
        with mock.patch("django.core.cache.cache.get", return_value=None):
            _, body = self._ready()
        self.assertEqual(body["status"], "degraded")

    def test_the_node_keeps_serving(self):
        """A 503 would pull the node from rotation for a condition the cache config
        (`IGNORE_EXCEPTIONS: True`) exists to survive — an outage where there was a
        degradation."""
        with mock.patch("django.core.cache.cache.get", return_value=None):
            resp, _ = self._ready()
        self.assertEqual(
            resp.status_code, 200,
            "a Redis blip now takes the node out of the load balancer",
        )


class ADeadBrokerIsVisibleTests(_Base):
    def test_an_unreachable_broker_degrades_but_does_not_fail(self):
        with mock.patch(
            "celery_app.celery.app.connection", side_effect=RuntimeError("no broker")
        ):
            resp, body = self._ready()
        self.assertEqual(body["checks"]["broker"]["status"], "unavailable")
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(resp.status_code, 200)

    def test_it_says_what_stops_working(self):
        with mock.patch(
            "celery_app.celery.app.connection", side_effect=RuntimeError("no broker")
        ):
            _, body = self._ready()
        self.assertIn("provisioning", body["checks"]["broker"].get("note", "").lower())


class DockerIsNotApplicableOffTheLabHostTests(_Base):
    """The backend runs on the APP node; the docker daemon lives on the lab host.
    Reporting a missing socket as a fault would make every healthy app node look
    broken."""

    def test_a_missing_daemon_is_not_a_failure(self):
        _, body = self._ready()
        self.assertIn(
            body["checks"]["docker"]["status"], ("ok", "not_applicable")
        )

    def test_a_missing_daemon_does_not_degrade_the_node(self):
        with mock.patch("docker.DockerClient", side_effect=RuntimeError("no socket")):
            resp, body = self._ready()
        self.assertEqual(body["checks"]["docker"]["status"], "not_applicable")
        self.assertEqual(resp.status_code, 200)


class ADeadDatabaseStillFailsTests(_Base):
    """Guard the guard: if everything merely 'degrades', readiness stops being a
    probe at all. The database is the one hard dependency."""

    _mock_db_ok = False

    def test_a_dead_database_is_a_503(self):
        with mock.patch(
            "django.db.connection.ensure_connection",
            side_effect=RuntimeError("db gone"),
        ):
            resp, body = self._ready()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(body["status"], "error")

    def test_liveness_is_unaffected(self):
        """Liveness must stay trivial — a failing liveness probe restarts the
        container, which does not fix a dead database."""
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.status_code, 200)
