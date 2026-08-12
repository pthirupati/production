"""Session 82: sqlite SQL path + SMOTE shim."""

from django.test import SimpleTestCase, TestCase

from apps.labs.code_exec import grade_submission, resolve_runtime
from apps.vmware_sim.datascience_v2_facades import (
    _parse_sql,
    _run_sql_sqlite,
    apply_v2_action,
    execute_dataset_sql,
    seed_v2,
)

COLS = ["name", "age", "city"]
ROWS = [
    {"name": "Ada", "age": 36, "city": "London"},
    {"name": "Bob", "age": 22, "city": "Paris"},
    {"name": "Cara", "age": 36, "city": "London"},
]


class SqliteSqlPathTests(TestCase):
    def test_sqlite_group_by_and_join(self):
        rows, msg = _run_sql_sqlite(
            "SELECT city, COUNT(*) AS n FROM t GROUP BY city ORDER BY city",
            COLS, ROWS,
        )
        self.assertEqual(len(rows), 2)
        self.assertIn("2", msg)
        by_city = {r["city"]: int(r["n"]) for r in rows}
        self.assertEqual(by_city["London"], 2)

        tables = {
            "orders": {
                "columns": ["id", "city", "qty"],
                "rows": [
                    {"id": 1, "city": "London", "qty": 2},
                    {"id": 2, "city": "Paris", "qty": 1},
                ],
            },
        }
        joined, _ = _run_sql_sqlite(
            "SELECT t.name, orders.qty FROM t JOIN orders ON t.city = orders.city",
            COLS, ROWS, tables=tables,
        )
        self.assertGreaterEqual(len(joined), 3)

    def test_execute_falls_back_to_facade(self):
        # Facadé-only dialect still works via execute_dataset_sql fallback if needed;
        # standard SQL should hit sqlite.
        rows, _ = execute_dataset_sql("SELECT name FROM t WHERE age > 30", COLS, ROWS)
        self.assertEqual({r["name"] for r in rows}, {"Ada", "Cara"})
        facade, _ = _parse_sql("SELECT name FROM t WHERE age > 30", COLS, ROWS)
        self.assertEqual(len(facade), 2)

    def test_run_sql_action_uses_sqlite(self):
        st = seed_v2()
        st["dataset"] = {"columns": COLS, "rows": ROWS}
        out = apply_v2_action(st, "run_sql", {
            "sql": "SELECT city, COUNT(*) AS n FROM t GROUP BY city",
        })
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["result"]["rows"], 2)


class SmoteShimTests(SimpleTestCase):
    def test_smote_balances_minority(self):
        self.assertEqual(resolve_runtime({"language": "sklearn"}), "python")
        result = grade_submission(
            "python",
            "X = [[0],[0],[0],[1]]\n"
            "y = [0,0,0,1]\n"
            "Xs, ys = SMOTE(random_state=1).fit_resample(X, y)\n",
            [
                {"name": "balanced", "code": "assert ys.count(0) == ys.count(1)", "hidden": False},
                {"name": "len", "code": "assert len(Xs) == 6", "hidden": False},
            ],
            authoring_language="sklearn",
        )
        self.assertTrue(result.all_passed, result.error or result)
