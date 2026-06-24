"""Monitoring dashboard builder, health readiness, and course catalog tests."""

import unittest
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fixitlab-test",
    }
}


class MonitoringDashboardBuilderTest(SimpleTestCase):
    @override_settings(CACHES=LOCMEM_CACHE)
    def test_add_reorder_remove_panel(self):
        from apps.vmware_sim.monitoring_engine import _ensure_session, apply_action, get_state

        session_id = "test-dash-builder-unit"
        _ensure_session(session_id, "")
        state = get_state(session_id, "")
        dash_uid = state["grafana"]["dashboards"][0]["uid"]
        before = len(state["grafana"]["dashboards"][0]["panels"])

        added = apply_action(session_id, "add_panel", {
            "dashboard_uid": dash_uid,
            "title": "Custom panel",
            "expr": "up",
            "type": "stat",
        })
        self.assertTrue(added["ok"])
        new_id = added["panel"]["id"]

        st = get_state(session_id)
        panels = st["grafana"]["dashboards"][0]["panels"]
        self.assertEqual(len(panels), before + 1)

        order = [p["id"] for p in panels]
        order[0], order[-1] = order[-1], order[0]
        reordered = apply_action(session_id, "reorder_panels", {
            "dashboard_uid": dash_uid,
            "order": order,
        })
        self.assertTrue(reordered["ok"])

        removed = apply_action(session_id, "remove_panel", {
            "dashboard_uid": dash_uid,
            "panel_id": new_id,
        })
        self.assertTrue(removed["ok"])
        self.assertEqual(len(get_state(session_id)["grafana"]["dashboards"][0]["panels"]), before)


class CourseCatalogTest(unittest.TestCase):
    def test_catalog_generates_hundreds_of_modules(self):
        from apps.tutorials.management.commands.course_catalog import build_catalog_specs

        specs = build_catalog_specs()
        self.assertGreaterEqual(len(specs), 180)
        slugs = {s["slug"] for s in specs}
        self.assertEqual(len(slugs), len(specs))
        self.assertTrue(all(s.get("course_slug") for s in specs))


class HealthReadinessTest(SimpleTestCase):
    @override_settings(VAULT_ENABLED="", CACHES=LOCMEM_CACHE)
    def test_liveness_ok(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    @override_settings(VAULT_ENABLED="", CACHES=LOCMEM_CACHE)
    @patch("apps.accounts.health.connection.ensure_connection")
    def test_readiness_shape(self, _mock_db):
        resp = self.client.get("/api/health/ready/", follow=True)
        self.assertIn(resp.status_code, (200, 503))
        body = resp.json()
        self.assertIn("checks", body)
        self.assertIn("vault", body["checks"])
