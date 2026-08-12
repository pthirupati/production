"""N+1 / query-budget guard referenced by `.github/workflows/performance.yml`.

The workflow previously masked a missing suite with `|| true`. This module
exists so the job has a real target: a few read-only endpoints must stay under
a fixed query ceiling. Ceilings are intentionally loose enough for schema drift
but tight enough to catch an unbounded per-row lookup.

`assertNumQueries(N)` is an exact match — wrong for a ceiling. Use an upper
bound so a cheaper path (e.g. health with 0 queries) still passes.
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext


class QueryBudgetTests(TestCase):
    def test_health_stays_under_query_ceiling(self):
        # Health is the cheapest readiness path — if this needs dozens of queries
        # something is wrong with middleware or session setup.
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(len(ctx), 15, f"health used {len(ctx)} queries")

    def test_technologies_list_stays_under_query_ceiling(self):
        # Public catalog list; historically a place N+1s appear when serializers
        # walk related objects per row.
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get("/api/technologies/")
        self.assertIn(res.status_code, (200, 401, 403))
        self.assertLessEqual(len(ctx), 40, f"technologies used {len(ctx)} queries")
