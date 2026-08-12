"""Session 85: pandas notebook path + api_client server draft."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology
from apps.vmware_sim.datascience_v2_facades import (
    _looks_like_pandas,
    apply_v2_action,
    seed_v2,
)

User = get_user_model()

COLS = ["name", "age", "city"]
ROWS = [
    {"name": "Ada", "age": 36, "city": "London"},
    {"name": "Bob", "age": 22, "city": "Paris"},
    {"name": "Cara", "age": 36, "city": "London"},
]


class PandasNotebookTests(TestCase):
    def test_looks_like_pandas(self):
        self.assertTrue(_looks_like_pandas("import pandas as pd\ndf.head()"))
        self.assertTrue(_looks_like_pandas("pd.DataFrame({'a':[1]})"))
        self.assertFalse(_looks_like_pandas("df.head()"))

    def test_run_pandas_cell(self):
        st = seed_v2()
        st["dataset"] = {"columns": COLS, "rows": ROWS}
        st["notebooks"][0]["cells"].append({
            "id": "c-pd",
            "type": "code",
            "source": "import pandas as pd\ndf.head(2)",
            "output": None,
        })
        out = apply_v2_action(st, "run_notebook_cell", {"cell_id": "c-pd"})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["cell"]["output"]["type"], "table")
        self.assertEqual(len(out["cell"]["output"]["rows"]), 2)


class ApiClientDraftViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="s85draft", email="s85@test.com", password="Pass123!",
        )
        self.client.force_authenticate(user=self.user)
        tech = Technology.objects.create(
            name="Py85", slug="py-s85", description="x", price=0, is_active=True,
        )
        self.scenario = Scenario.objects.create(
            title="API draft lab", description="d", technology=tech, slug="s85-api-draft",
            category="Python", difficulty="easy", is_free=True, is_active=True,
            lab_mode="simulation", simulation_type="python",
            coding_mode=True,
            coding_spec={"language": "javascript", "api_client": {"enabled": True}},
            time_limit=1200, max_score=100,
        )
        self.session = LabSession.objects.create(
            user=self.user, scenario=self.scenario,
            status="RUNNING", provider="simulation", duration_limit=1200,
        )

    def test_put_get_roundtrip(self):
        put = self.client.put(
            f"/api/labs/{self.session.id}/api-client/draft/",
            {"draft": {"method": "POST", "url": "/api/v1/echo", "ts": 100}},
            format="json",
        )
        self.assertEqual(put.status_code, 200, put.content)
        self.assertTrue(put.json().get("ok"))
        get = self.client.get(f"/api/labs/{self.session.id}/api-client/draft/")
        self.assertEqual(get.status_code, 200)
        draft = get.json()["draft"]
        self.assertEqual(draft["method"], "POST")
        self.assertEqual(draft["url"], "/api/v1/echo")
