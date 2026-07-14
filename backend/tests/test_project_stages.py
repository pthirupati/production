"""Tests for the additive ProjectStage staged-workflow feature.

Covers the guarantees of the ProjectStage model + staged ProjectStartView +
per-task validation gate, and that FLAT projects are entirely unchanged:

  - A flat project (no stages) starts by opening its single project.lab_scenario,
    exactly as before, and its API payload reports is_staged=False with stages=[].
  - A staged project's ProjectStartView opens the CURRENT stage's lab (stage 1
    when nothing is done; the next incomplete stage as tasks complete) and
    reports is_staged=True plus a current_stage block.
  - A staged stage whose own lab is null falls back to the project-level lab.
  - The validation gate: a task with a validation_scenario cannot be marked done
    until the user has a PASSED LabSession for it; without a validator, the task
    self-attests (backward-compatible).
  - The seeded reference capstone CAP8 has its 7 stages wired to real labs.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.question_bank.models import (
    Project,
    ProjectStage,
    ProjectTask,
    Scenario,
    Technology,
    UserTaskProgress,
)

User = get_user_model()


def _mk_scenario(tech, slug, **extra):
    defaults = dict(
        technology=tech,
        slug=slug,
        title=slug,
        category="x",
        difficulty="easy",
        description="x",
        is_active=True,
    )
    defaults.update(extra)
    return Scenario.objects.create(**defaults)


class FlatProjectUnchangedTests(TestCase):
    """A project with NO stages must behave exactly as it did pre-feature."""

    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="Linux", slug="linux", is_active=True)
        cls.lab = _mk_scenario(cls.tech, "flat-project-lab", is_free=True)
        cls.project = Project.objects.create(
            technology=cls.tech,
            title="Flat Project",
            slug="flat-project",
            description="d",
            objectives=["o"],
            lab_scenario=cls.lab,
        )
        cls.t1 = ProjectTask.objects.create(
            project=cls.project, jira_key="F-1", title="t1", description="d", order=1,
        )
        cls.user = User.objects.create_user(username="flatuser", password="pw")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_start_opens_project_lab_scenario(self):
        resp = self.client.post(f"/api/projects/{self.project.id}/start/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["lab_scenario_id"], self.lab.id)
        self.assertEqual(resp.data["lab_scenario_slug"], "flat-project-lab")
        # Flat = not staged; no current_stage block.
        self.assertFalse(resp.data["is_staged"])
        self.assertNotIn("current_stage", resp.data)

    def test_task_without_validator_self_attests(self):
        # No validation_scenario on the task -> marking done just works (200).
        resp = self.client.post(
            f"/api/projects/{self.project.id}/tasks/{self.t1.id}/update/",
            {"status": "done"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "done")


class StagedProjectStartTests(TestCase):
    """A staged project opens the CURRENT stage's lab, advancing as tasks finish."""

    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="SRE", slug="sre", is_active=True)
        cls.proj_lab = _mk_scenario(cls.tech, "staged-project-fallback-lab", is_free=True)
        cls.lab1 = _mk_scenario(cls.tech, "stage1-lab", is_free=True)
        cls.lab2 = _mk_scenario(cls.tech, "stage2-lab", is_free=True)

        cls.project = Project.objects.create(
            technology=cls.tech,
            title="Staged Project",
            slug="staged-project",
            description="d",
            objectives=["o"],
            lab_scenario=cls.proj_lab,  # project-level fallback lab
        )
        # Stage 1 (has its own lab), stage 2 (has its own lab),
        # stage 3 (NO lab -> must fall back to project.lab_scenario).
        cls.s1 = ProjectStage.objects.create(
            project=cls.project, order=1, title="Stage 1",
            stage_technology=cls.tech, lab_scenario=cls.lab1,
        )
        cls.s2 = ProjectStage.objects.create(
            project=cls.project, order=2, title="Stage 2",
            stage_technology=cls.tech, lab_scenario=cls.lab2,
        )
        cls.s3 = ProjectStage.objects.create(
            project=cls.project, order=3, title="Stage 3 (doc)",
            stage_technology=None, lab_scenario=None,
        )
        cls.t1 = ProjectTask.objects.create(
            project=cls.project, jira_key="S-1", title="t1", description="d",
            order=1, stage=cls.s1,
        )
        cls.t2 = ProjectTask.objects.create(
            project=cls.project, jira_key="S-2", title="t2", description="d",
            order=2, stage=cls.s2,
        )
        cls.t3 = ProjectTask.objects.create(
            project=cls.project, jira_key="S-3", title="t3", description="d",
            order=3, stage=cls.s3,
        )
        cls.user = User.objects.create_user(username="stageduser", password="pw")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_start_opens_stage_one_lab_when_nothing_done(self):
        resp = self.client.post(f"/api/projects/{self.project.id}/start/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["is_staged"])
        # The current stage is stage 1 -> its lab, not project.lab_scenario.
        self.assertEqual(resp.data["lab_scenario_id"], self.lab1.id)
        self.assertEqual(resp.data["lab_scenario_slug"], "stage1-lab")
        self.assertEqual(resp.data["current_stage"]["order"], 1)

    def test_start_advances_to_next_stage_as_tasks_complete(self):
        # Complete all of stage 1's tasks -> current stage becomes stage 2.
        UserTaskProgress.objects.create(user=self.user, task=self.t1, status="done")
        resp = self.client.post(f"/api/projects/{self.project.id}/start/")
        self.assertEqual(resp.data["lab_scenario_id"], self.lab2.id)
        self.assertEqual(resp.data["current_stage"]["order"], 2)

    def test_stage_without_lab_falls_back_to_project_lab(self):
        # Finish stages 1 and 2; current stage is 3, which has no lab of its own,
        # so Start must fall back to the project-level lab_scenario.
        UserTaskProgress.objects.create(user=self.user, task=self.t1, status="done")
        UserTaskProgress.objects.create(user=self.user, task=self.t2, status="done")
        resp = self.client.post(f"/api/projects/{self.project.id}/start/")
        self.assertEqual(resp.data["current_stage"]["order"], 3)
        self.assertEqual(resp.data["lab_scenario_id"], self.proj_lab.id)

    def test_serialized_project_includes_ordered_stages(self):
        # The technology-detail projects payload exposes the ordered stages.
        resp = self.client.get(f"/api/technologies/{self.tech.slug}/")
        self.assertEqual(resp.status_code, 200)
        projects = resp.data.get("projects", [])
        staged = next(p for p in projects if p["slug"] == "staged-project")
        self.assertTrue(staged["is_staged"])
        orders = [s["order"] for s in staged["stages"]]
        self.assertEqual(orders, [1, 2, 3])
        self.assertEqual(staged["stages"][0]["lab_scenario_slug"], "stage1-lab")


class ValidationGateTests(TestCase):
    """A task with a validation_scenario gates status=done on a PASSED lab."""

    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="PG", slug="pg", is_active=True)
        cls.validator = _mk_scenario(cls.tech, "gate-lab", is_free=True)
        cls.project = Project.objects.create(
            technology=cls.tech, title="Gated Project", slug="gated-project",
            description="d", objectives=["o"],
        )
        cls.task = ProjectTask.objects.create(
            project=cls.project, jira_key="G-1", title="t", description="d",
            order=1, validation_scenario=cls.validator,
        )
        cls.user = User.objects.create_user(username="gateuser", password="pw")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_done_blocked_without_passed_lab(self):
        resp = self.client.post(
            f"/api/projects/{self.project.id}/tasks/{self.task.id}/update/",
            {"status": "done"},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["error"], "validation_required")
        self.assertEqual(resp.data["validation_scenario_slug"], "gate-lab")
        # Status must NOT have flipped to done.
        utp = UserTaskProgress.objects.get(user=self.user, task=self.task)
        self.assertNotEqual(utp.status, "done")

    def test_done_allowed_after_passing_lab(self):
        LabSession.objects.create(
            user=self.user, scenario=self.validator, validation_passed=True,
        )
        resp = self.client.post(
            f"/api/projects/{self.project.id}/tasks/{self.task.id}/update/",
            {"status": "done"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "done")

    def test_non_done_status_never_gated(self):
        # Moving to in_progress must never hit the validation gate.
        resp = self.client.post(
            f"/api/projects/{self.project.id}/tasks/{self.task.id}/update/",
            {"status": "in_progress"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "in_progress")


class Cap8ReferenceStagesTests(TestCase):
    """The seeded reference capstone CAP8 must have its 7 stages wired."""

    @classmethod
    def setUpTestData(cls):
        from pathlib import Path

        from django.conf import settings
        from django.core.management import call_command

        scenarios_root = Path(settings.BASE_DIR).parent / "scenarios"
        call_command("seed_scenarios", "--dir", str(scenarios_root), "--merge-only", verbosity=0)
        call_command("seed_projects", verbosity=0)

    def test_cap8_has_seven_stages_with_labs_and_lessons(self):
        proj = Project.objects.get(slug="capstone-black-friday-sre-incident")
        stages = list(proj.stages.order_by("order"))
        self.assertEqual(len(stages), 7)
        self.assertEqual([s.order for s in stages], [1, 2, 3, 4, 5, 6, 7])
        # Every stage carries the "where pipelines break" lesson and a handoff.
        for s in stages:
            self.assertTrue(s.breakpoint_note.strip(), f"stage {s.order} missing breakpoint_note")
            self.assertTrue(s.handoff_artifact, f"stage {s.order} missing handoff_artifact")
        by_order = {s.order: s for s in stages}
        # Stages 1-4 and 6 resolve to real labs; the Nginx (5) + postmortem (7)
        # stages intentionally have no lab.
        self.assertEqual(by_order[1].lab_scenario.slug, "academy-prometheus-010-integration-exporters")
        self.assertEqual(by_order[2].lab_scenario.slug, "academy-python-003-operate-http-api")
        self.assertEqual(by_order[3].lab_scenario.slug, "pg-connection-pool")
        self.assertEqual(by_order[4].lab_scenario.slug, "academy-kubernetes-010-integration-autoscaling")
        self.assertIsNone(by_order[5].lab_scenario)
        self.assertEqual(by_order[6].lab_scenario.slug, "academy-prometheus-010-integration-exporters")
        self.assertIsNone(by_order[7].lab_scenario)
        # Per-stage technology resolved where a lab exists.
        self.assertEqual(by_order[3].stage_technology.slug, "postgresql")

    def test_cap8_tasks_bind_to_stages_and_validators(self):
        proj = Project.objects.get(slug="capstone-black-friday-sre-incident")
        t1 = proj.tasks.get(jira_key="CAP8-1")
        self.assertIsNotNone(t1.stage)
        self.assertEqual(t1.stage.order, 1)
        self.assertEqual(t1.validation_scenario.slug, "academy-prometheus-010-integration-exporters")
        # The Nginx stage task self-attests (no validator).
        t5 = proj.tasks.get(jira_key="CAP8-5")
        self.assertIsNone(t5.validation_scenario)

    def test_other_capstones_stay_flat(self):
        # CAP9 (and every non-CAP8 project) must remain flat — zero stages.
        cap9 = Project.objects.get(slug="capstone-strangle-monolith-microservices")
        self.assertEqual(cap9.stages.count(), 0)
        # Sanity: only CAP8 has stages across the whole catalog.
        staged_slugs = set(
            ProjectStage.objects.values_list("project__slug", flat=True)
        )
        self.assertEqual(staged_slugs, {"capstone-black-friday-sre-incident"})
