"""SQL submissions must be auto-gradeable, and must fail closed.

`SUPPORTED_LANGUAGES` was {python, javascript}; everything else returned
`needs_review`, which by design never auto-passes. That is why the 150
postgresql/sqlite/mysql scenarios are declared `language: python` with a
`solution.py` — not sloppiness, but the only gradeable option. "Correcting" those
scenarios to `language: sql` before the grader understood SQL would have made them
permanently unsolvable (§Y2f).

SQL grades through the Python runtime driving stdlib sqlite3 against a throwaway
in-memory database: no new image, binary or dependency, so it needed no change to
the labs engine. Tests are Python snippets with query helpers in scope, so they
assert on real query RESULTS rather than on the text of the SQL — the distinction
between a grader and a spell-checker.
"""
from django.test import SimpleTestCase

from apps.labs.code_exec import (
    NEEDS_REVIEW_LANGUAGES,
    PYTHON_HOSTED_LANGUAGES,
    SUPPORTED_LANGUAGES,
    grade_submission,
    language_runtime_available,
)

SCHEMA = """
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL);
INSERT INTO orders VALUES (1, 10, 99.5), (2, 10, 10.0), (3, 20, 5.25);
CREATE INDEX idx_orders_customer ON orders(customer_id);
"""


def _t(code, name="t", hidden=False):
    return {"name": name, "code": code, "hidden": hidden}


class RegistrationTests(SimpleTestCase):
    def test_sql_is_supported_and_not_needs_review(self):
        self.assertIn("sql", SUPPORTED_LANGUAGES)
        self.assertNotIn("sql", NEEDS_REVIEW_LANGUAGES)

    def test_sql_runtime_is_always_available(self):
        """sqlite3 is stdlib — there is no binary to install or image to pull."""
        self.assertTrue(language_runtime_available("sql"))
        self.assertIn("sql", PYTHON_HOSTED_LANGUAGES)

    def test_bash_is_still_needs_review(self):
        """Unchanged: bash cannot be auto-graded, so it must never auto-pass."""
        r = grade_submission("bash", "echo hi", [_t("assert True")])
        self.assertTrue(r.needs_review)
        self.assertFalse(r.all_passed)


class GradingTests(SimpleTestCase):
    def test_correct_solution_passes(self):
        r = grade_submission("sql", SCHEMA, [
            _t('assert scalar("SELECT COUNT(*) FROM orders") == 3', "count"),
            _t('assert "orders" in tables()', "table", hidden=True),
        ])
        self.assertTrue(r.ran)
        self.assertTrue(r.all_passed, r.error)

    def test_query_helpers_are_all_in_scope(self):
        r = grade_submission("sql", SCHEMA, [
            _t('assert columns("orders") == ["id", "customer_id", "total"]', "columns"),
            _t('assert "idx_orders_customer" in indexes("orders")', "indexes"),
            _t('assert len(rows("SELECT * FROM orders WHERE customer_id=10")) == 2', "rows"),
            _t('assert scalar("SELECT total FROM orders WHERE id=1") == 99.5', "scalar"),
            _t('assert isinstance(explain("SELECT * FROM orders"), str)', "explain"),
        ])
        self.assertTrue(r.all_passed, r.error)

    def test_explain_can_prove_an_index_is_used(self):
        """The point of an indexing lab: assert the plan, not the DDL text."""
        r = grade_submission("sql", SCHEMA, [
            _t('assert "idx_orders_customer" in '
               'explain("SELECT * FROM orders WHERE customer_id = 10")', "plan"),
        ])
        self.assertTrue(r.all_passed, r.error)

    def test_tables_hides_sqlite_internals(self):
        r = grade_submission("sql", SCHEMA, [
            _t('assert all(not t.startswith("sqlite_") for t in tables())', "internal"),
        ])
        self.assertTrue(r.all_passed, r.error)


class FailsClosedTests(SimpleTestCase):
    """Every way of not solving the lab must produce all_passed=False."""

    ONE_TEST = [_t('assert scalar("SELECT COUNT(*) FROM orders") == 3')]

    def test_wrong_data_fails(self):
        r = grade_submission(
            "sql", "CREATE TABLE orders(id INTEGER); INSERT INTO orders VALUES (1);",
            self.ONE_TEST,
        )
        self.assertFalse(r.all_passed)

    def test_missing_table_fails(self):
        r = grade_submission("sql", "CREATE TABLE other(id INTEGER);", self.ONE_TEST)
        self.assertFalse(r.all_passed)

    def test_empty_submission_fails(self):
        r = grade_submission("sql", "", self.ONE_TEST)
        self.assertFalse(r.all_passed)

    def test_no_tests_never_auto_passes(self):
        r = grade_submission("sql", SCHEMA, [])
        self.assertFalse(r.all_passed)
        self.assertIn("No tests", r.error)

    def test_syntax_error_is_reported_once_not_per_test(self):
        r = grade_submission("sql", "CREATE TABL orders(", [
            _t("assert True", "a"), _t("assert True", "b"),
        ])
        self.assertFalse(r.all_passed)
        self.assertFalse(r.ran)

    def test_syntax_error_message_is_sqlites_not_a_python_traceback(self):
        """A learner needs 'near "TABL": syntax error', not our harness frames."""
        r = grade_submission("sql", "CREATE TABL orders(", self.ONE_TEST)
        self.assertIn("syntax error", r.error)
        self.assertNotIn("Traceback", r.error)
        self.assertNotIn("code_exec", r.error)


class TestSemanticsTests(SimpleTestCase):
    def test_assertion_message_reaches_the_learner(self):
        r = grade_submission("sql", "CREATE TABLE t(id INTEGER);", [
            _t('assert scalar("SELECT COUNT(*) FROM t") == 5, "expected 5 rows"', "rc"),
        ])
        self.assertFalse(r.all_passed)
        self.assertEqual(r.outcomes[0].message, "expected 5 rows")

    def test_each_test_gets_a_fresh_database(self):
        """A test that INSERTs must not change the next test's result — otherwise
        grading depends on test ordering."""
        r = grade_submission(
            "sql", "CREATE TABLE t(id INTEGER); INSERT INTO t VALUES (1);",
            [
                _t('db.execute("INSERT INTO t VALUES (2)"); '
                   'assert scalar("SELECT COUNT(*) FROM t") == 2', "mutate"),
                _t('assert scalar("SELECT COUNT(*) FROM t") == 1, '
                   '"state leaked from the previous test"', "isolated"),
            ],
        )
        self.assertTrue(r.all_passed, r.error)

    def test_hidden_flag_is_preserved(self):
        r = grade_submission("sql", SCHEMA, [
            _t("assert True", "vis", hidden=False),
            _t("assert True", "hid", hidden=True),
        ])
        by_name = {o.name: o for o in r.outcomes}
        self.assertFalse(by_name["vis"].hidden)
        self.assertTrue(by_name["hid"].hidden)

    def test_hidden_test_logic_is_never_serialised(self):
        r = grade_submission("sql", SCHEMA, [
            _t('assert scalar("SELECT COUNT(*) FROM orders") == 3', "secret", hidden=True),
        ])
        self.assertNotIn("SELECT COUNT", str(r.public_dict()))
