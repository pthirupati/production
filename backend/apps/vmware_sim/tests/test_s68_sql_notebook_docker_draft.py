"""Session 68 polish: SQL parse, notebook cells, Docker layer build, IDE draft."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology
from apps.vmware_sim import docker_engine as de
from apps.vmware_sim.datascience_v2_facades import _parse_sql, apply_v2_action, seed_v2

User = get_user_model()

COLS = ["name", "age", "city"]
ROWS = [
    {"name": "Ada", "age": 36, "city": "London"},
    {"name": "Bob", "age": 22, "city": "Paris"},
    {"name": "Cara", "age": 36, "city": "London"},
]


class SqlParseTests(TestCase):
    def test_where_filters_and_count_differs(self):
        all_rows, _ = _parse_sql("SELECT * FROM t", COLS, ROWS)
        self.assertEqual(len(all_rows), 3)
        filtered, msg = _parse_sql("SELECT * FROM t WHERE city = 'London'", COLS, ROWS)
        self.assertEqual(len(filtered), 2)
        self.assertIn("2", msg)
        count_rows, _ = _parse_sql("SELECT COUNT(*) FROM t WHERE age > 30", COLS, ROWS)
        self.assertEqual(count_rows[0]["count"], 2)

    def test_order_limit_project(self):
        rows, _ = _parse_sql(
            "SELECT name FROM t ORDER BY age ASC LIMIT 1", COLS, ROWS
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {"name": "Bob"})
        self.assertNotIn("age", rows[0])


class NotebookFacadeTests(TestCase):
    def _state(self):
        st = seed_v2()
        st["dataset"] = {"columns": COLS, "rows": ROWS}
        return st

    def test_head_vs_shape_vs_describe(self):
        st = self._state()
        head = apply_v2_action(st, "run_notebook_cell", {"cell_id": "c2"})
        self.assertTrue(head["ok"])
        self.assertEqual(head["cell"]["output"]["type"], "table")

        st["notebooks"][0]["cells"].append(
            {"id": "c3", "type": "code", "source": "df.shape", "output": None}
        )
        shape = apply_v2_action(st, "run_notebook_cell", {"cell_id": "c3"})
        self.assertIn("(3, 3)", shape["cell"]["output"]["text"])

        st["notebooks"][0]["cells"].append(
            {"id": "c4", "type": "code", "source": "df.describe()", "output": None}
        )
        desc = apply_v2_action(st, "run_notebook_cell", {"cell_id": "c4"})
        self.assertIn("age:", desc["cell"]["output"]["text"])


class DockerLayerBuildTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self):
        sid = "test-s68-docker-layers"
        de.drop_session(sid)
        de.get_state(sid, "")
        return sid

    def test_build_layers_cache_and_fail_no_image(self):
        sid = self._sid()
        df = (
            "FROM alpine:3.19\n"
            "RUN echo hello\n"
            "COPY app.py /app.py\n"
        )
        files = {"app.py": "print(1)\n", ".dockerignore": "*.pyc\n"}
        r1 = de.apply_action(sid, "build_image", {
            "dockerfile": df, "tag": "demo:s68", "files": files,
        })
        self.assertTrue(r1.get("ok"), r1)
        self.assertGreaterEqual(len(r1.get("layers") or []), 2)
        digests = [L["digest"] for L in r1["layers"]]
        self.assertEqual(len(digests), len(set(digests)))

        r2 = de.apply_action(sid, "build_image", {
            "dockerfile": df, "tag": "demo:s68", "files": files,
        })
        self.assertTrue(r2.get("ok"), r2)
        self.assertGreater(r2.get("cache_hits", 0), 0)

        fail = de.apply_action(sid, "build_image", {
            "dockerfile": "FROM alpine\nRUN FAIL_BUILD\n",
            "tag": "demo:broken",
        })
        self.assertFalse(fail.get("ok"))
        entry = de.get_state(sid, "")
        tags = [i.get("repoTag") for i in (entry.get("daemon") or {}).get("images") or []]
        self.assertNotIn("demo:broken", tags)

        miss = de.apply_action(sid, "run_container", {
            "name": "nope",
            "image": "demo:broken",
            "create_missing_image": False,
        })
        self.assertFalse(miss.get("ok"))
        self.assertIn("Unable to find image", miss.get("error", ""))

    def test_require_digest_pin(self):
        sid = self._sid()
        r = de.apply_action(sid, "build_image", {
            "dockerfile": "FROM alpine:3.19\nRUN true\n",
            "tag": "pin:test",
            "require_digest_pin": True,
        })
        self.assertFalse(r.get("ok"))
        self.assertIn("digest", r.get("error", "").lower())


class IdeDraftPersistenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="s68draft", email="s68@test.com", password="Pass123!"
        )
        self.client.force_authenticate(user=self.user)
        tech = Technology.objects.create(
            name="Py68", slug="py-s68", description="x", price=0, is_active=True,
        )
        self.scenario = Scenario.objects.create(
            title="Draft lab", description="d", technology=tech, slug="s68-ide-draft",
            category="Python", difficulty="easy", is_free=True, is_active=True,
            lab_mode="simulation", simulation_type="python",
            coding_mode=True,
            coding_spec={
                "language": "python",
                "entrypoint": "solution.py",
                "files": [{"path": "solution.py", "content": "pass\n"}],
                "visible_tests": [],
                "hidden_tests": [],
            },
            time_limit=1200, max_score=100,
        )

    def test_put_get_and_coding_spec_includes_draft(self):
        session = LabSession.objects.create(
            user=self.user, scenario=self.scenario,
            status="RUNNING", provider="simulation", duration_limit=1200,
        )
        put = self.client.put(
            f"/api/labs/{session.id}/ide-draft/",
            {"files": {"solution.py": "def add(a,b): return a+b\n"}},
            format="json",
        )
        self.assertEqual(put.status_code, 200, put.content)
        body = put.json()
        self.assertTrue(body.get("ok"))
        self.assertIn("solution.py", body["draft"]["files"])

        get = self.client.get(f"/api/labs/{session.id}/ide-draft/")
        self.assertEqual(get.status_code, 200)
        self.assertEqual(
            get.json()["draft"]["files"]["solution.py"],
            "def add(a,b): return a+b\n",
        )

        spec = self.client.get(f"/api/labs/{session.id}/coding-spec/")
        self.assertEqual(spec.status_code, 200)
        ide = spec.json().get("ide_draft")
        self.assertIsInstance(ide, dict)
        self.assertIn("solution.py", ide["files"])
