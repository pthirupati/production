"""Session 80: SQL JOIN / GROUP BY façade + residual polish fixtures."""

from django.test import TestCase

from apps.vmware_sim.datascience_v2_facades import _parse_sql, apply_v2_action, seed_v2

COLS = ["name", "age", "city"]
ROWS = [
    {"name": "Ada", "age": 36, "city": "London"},
    {"name": "Bob", "age": 22, "city": "Paris"},
    {"name": "Cara", "age": 36, "city": "London"},
]

ORDERS_COLS = ["id", "city", "qty"]
ORDERS = [
    {"id": 1, "city": "London", "qty": 2},
    {"id": 2, "city": "Paris", "qty": 1},
    {"id": 3, "city": "London", "qty": 5},
]


class SqlJoinGroupByTests(TestCase):
    def test_group_by_count_differs_by_city(self):
        rows, msg = _parse_sql(
            "SELECT city, COUNT(*) FROM t GROUP BY city", COLS, ROWS,
        )
        by_city = {r["city"]: r["count"] for r in rows}
        self.assertEqual(by_city["London"], 2)
        self.assertEqual(by_city["Paris"], 1)
        self.assertIn("2", msg)

    def test_group_by_sum_age(self):
        rows, _ = _parse_sql(
            "SELECT city, SUM(age) AS total FROM t GROUP BY city", COLS, ROWS,
        )
        by_city = {r["city"]: r["total"] for r in rows}
        self.assertEqual(by_city["London"], 72)
        self.assertEqual(by_city["Paris"], 22)

    def test_join_orders_on_city(self):
        tables = {
            "orders": {"columns": ORDERS_COLS, "rows": ORDERS},
        }
        rows, _ = _parse_sql(
            "SELECT * FROM t JOIN orders o ON city = city",
            COLS, ROWS, tables=tables,
        )
        # Ada+Cara (London) × 2 London orders + Bob × 1 Paris = 2*2 + 1 = 5
        self.assertEqual(len(rows), 5)
        self.assertTrue(any("o_qty" in r or "qty" in r for r in rows))

    def test_wrong_group_no_longer_returns_full_table(self):
        grouped, _ = _parse_sql(
            "SELECT city, COUNT(*) FROM t GROUP BY city", COLS, ROWS,
        )
        plain, _ = _parse_sql("SELECT * FROM t", COLS, ROWS)
        self.assertNotEqual(len(grouped), len(plain))

    def test_run_sql_action_passes_tables(self):
        st = seed_v2()
        st["dataset"] = {
            "columns": COLS,
            "rows": ROWS,
            "tables": {"orders": {"columns": ORDERS_COLS, "rows": ORDERS}},
        }
        out = apply_v2_action(st, "run_sql", {
            "sql": "SELECT city, COUNT(*) FROM t GROUP BY city",
        })
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["result"]["rows"], 2)
