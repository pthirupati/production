"""Postgres full-text + trigram search for the Scenario catalog.

This migration is **Postgres-only**. It:
  1. enables the ``pg_trgm`` extension,
  2. builds a *functional* GIN index on the weighted ``to_tsvector`` expression
     the search view annotates at query time (title A > subtitle B >
     category C > description D), so full-text ranking is index-backed, and
  3. builds a ``pg_trgm`` GIN index on ``title`` for typo-tolerant trigram
     matching.

SQLite-safety
-------------
The local/offline test DB is SQLite (``config.test_settings`` → sqlite
``:memory:``), which has none of ``pg_trgm``, ``to_tsvector`` or GIN indexes.
Every operation here is gated on ``schema_editor.connection.vendor ==
'postgresql'`` and becomes a **no-op on SQLite**, so ``migrate`` and the test
suite still apply cleanly. The migration also adds no model-state fields
(no ``SearchVectorField``), so it needs neither ``django.contrib.postgres`` in
INSTALLED_APPS nor a follow-up ``makemigrations``.

CI note: GitHub Actions runs the suite on Postgres, so the real DDL below is
exercised there.
"""
from django.db import migrations


# The tsvector expression here MUST stay byte-for-byte in sync with the
# SearchVector(...) annotation in apps.public_api.views.ScenariosListView so the
# planner can use this functional index. If you change the weights/columns/config
# in the view, change them here too (and vice versa).
_TSVECTOR_EXPR = (
    "("
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(subtitle, '')), 'B') || "
    "setweight(to_tsvector('english', coalesce(category, '')), 'C') || "
    "setweight(to_tsvector('english', coalesce(description, '')), 'D')"
    ")"
)

CREATE_SQL = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
    # Functional GIN index backing the query-time full-text search.
    f"CREATE INDEX IF NOT EXISTS scenario_fts_gin "
    f"ON question_bank_scenario USING gin ({_TSVECTOR_EXPR});",
    # Trigram GIN index on title for typo-tolerant similarity search.
    "CREATE INDEX IF NOT EXISTS scenario_title_trgm "
    "ON question_bank_scenario USING gin (title gin_trgm_ops);",
]

DROP_SQL = [
    "DROP INDEX IF EXISTS scenario_title_trgm;",
    "DROP INDEX IF EXISTS scenario_fts_gin;",
    # Deliberately do NOT drop the pg_trgm extension on reverse — other objects
    # may depend on it and dropping a shared extension is rarely what you want.
]


def _run(sql_statements):
    def _inner(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            # SQLite (and any non-Postgres backend): nothing to do.
            return
        for stmt in sql_statements:
            schema_editor.execute(stmt)

    return _inner


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0022_projecttask_validation_scenario_projectstage_and_more"),
    ]

    operations = [
        migrations.RunPython(_run(CREATE_SQL), _run(DROP_SQL)),
    ]
