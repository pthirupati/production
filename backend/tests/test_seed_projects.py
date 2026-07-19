"""Integrity proof for the guided end-to-end Projects seeded by `seed_projects`.

This test seeds the real Technology records (from scenarios/*/technology.yaml via
`seed_scenarios --merge-only`) and then runs `seed_projects`, asserting that:

  1. The command runs clean and is idempotent (a second run creates nothing new).
  2. Every ACTIVE technology a learner can subscribe to has at least 5 projects
     (the "zero-to-hero" guarantee).
  3. Every project has a non-trivial multi-phase task list, unique slug, valid
     difficulty/architecture choices, and a non-empty objectives list.
  4. Every task's `jira_key` is unique within its project and its `depends_on`
     (declared in the seed data as a jira_key string) resolves to a real
     ProjectTask in the SAME project — never a dangling or cross-project link.
  5. The cross-technology capstone projects are present and wired with
     dependencies.

If any of these break, the Projects feature ships broken data, so this is a
fail-closed guarantee.
"""

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase

from apps.question_bank.models import Project, ProjectTask, Technology

SCENARIOS_ROOT = Path(settings.BASE_DIR).parent / "scenarios"

# Minimum projects every active, learner-facing technology must offer.
MIN_PROJECTS_PER_TECH = 5

# Internal/grouping technologies that are NOT standalone learning subjects and
# are therefore exempt from the per-technology minimum. `shared` backs
# cross-technology shared-server scenarios; the rest are deactivated legacy
# buckets whose scenarios were merged elsewhere.
#
# The enterprise incident-simulation technologies (Commvault, NetApp, Dell EMC,
# physical Datacenter, SOC/SIEM, Azure) ship exclusively through the
# Labs/Scenarios system — each is a live break/fix console simulator (see
# apps/vmware_sim/*_engine.py) rather than a from-scratch "build a project"
# subject like AWS, React, or MySQL. They are intentionally excluded from the
# guided-Projects zero-to-hero guarantee until/unless that content type is
# authored for them.
NON_SUBJECT_SLUGS = {"shared", "commvault", "netapp", "dellemc", "datacenter", "soc", "azure", "gcp", "openstack"}

# Cross-technology capstones that must exist (slug -> primary technology slug).
EXPECTED_CAPSTONES = {
    "capstone-vmware-linux-k8s-app": "vmware",
    "capstone-terraform-ansible-app-monitoring": "terraform",
    "capstone-docker-cicd-k8s-observability": "docker",
    "capstone-baremetal-hypervisor-cloud": "baremetal",
    "capstone-security-end-to-end": "security",
}

VALID_DIFFICULTIES = {c[0] for c in Project.DIFFICULTY_CHOICES}
VALID_ARCHITECTURES = {c[0] for c in Project.ARCHITECTURE_CHOICES}


class SeedProjectsIntegrityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Build the Technology records exactly the way production does, then seed
        # the projects on top of them.
        call_command("seed_scenarios", "--dir", str(SCENARIOS_ROOT), "--merge-only", verbosity=0)
        call_command("seed_projects", verbosity=0)

    def test_starter_projects_preserved(self):
        """The two original starter projects must still seed (under the real
        Linux slug `linux`, not the historical `linux-administration`)."""
        for slug in ("linux-2tier-nginx", "linux-3tier-lb-app-db"):
            proj = Project.objects.filter(slug=slug).first()
            self.assertIsNotNone(proj, f"starter project '{slug}' missing")
            self.assertEqual(proj.technology.slug, "linux")

    def test_every_active_technology_has_min_projects(self):
        """Each active, learner-facing technology offers >= MIN_PROJECTS_PER_TECH."""
        techs = (
            Technology.objects.filter(is_active=True)
            .exclude(slug__in=NON_SUBJECT_SLUGS)
            .annotate(n=Count("projects"))
            .order_by("slug")
        )
        # Sanity: we actually have a meaningful set of technologies to check.
        self.assertGreaterEqual(techs.count(), 15)
        under = {t.slug: t.n for t in techs if t.n < MIN_PROJECTS_PER_TECH}
        self.assertEqual(
            under, {}, f"technologies below {MIN_PROJECTS_PER_TECH} projects: {under}"
        )

    def test_projects_are_well_formed(self):
        """Every project has objectives, a valid difficulty/architecture, and a
        substantial multi-phase task list."""
        self.assertGreater(Project.objects.count(), 50)
        for proj in Project.objects.all():
            with self.subTest(project=proj.slug):
                self.assertTrue(proj.slug, "project has empty slug")
                self.assertTrue(proj.description.strip(), f"{proj.slug} has empty description")
                self.assertIsInstance(proj.objectives, list)
                self.assertGreaterEqual(len(proj.objectives), 1, f"{proj.slug} has no objectives")
                self.assertIn(proj.difficulty, VALID_DIFFICULTIES)
                self.assertIn(proj.architecture_type, VALID_ARCHITECTURES)
                # Multi-phase: at least a few tasks per project.
                self.assertGreaterEqual(
                    proj.tasks.count(), 4, f"{proj.slug} has too few tasks to be multi-phase"
                )

    def test_tasks_are_well_formed_and_unique(self):
        """Every task has the fields the Jira-bot UI needs, and jira_keys are
        unique within their project."""
        for proj in Project.objects.all():
            keys = list(proj.tasks.values_list("jira_key", flat=True))
            with self.subTest(project=proj.slug):
                self.assertEqual(len(keys), len(set(keys)), f"duplicate jira_key in {proj.slug}")
            for task in proj.tasks.all():
                with self.subTest(task=f"{proj.slug}:{task.jira_key}"):
                    self.assertTrue(task.title.strip(), "task has empty title")
                    self.assertTrue(task.description.strip(), "task has empty description")
                    self.assertTrue(
                        task.acceptance_criteria.strip(), "task has empty acceptance_criteria"
                    )
                    # The hint is what the Jira bot shows — it must be present.
                    self.assertTrue(task.hint.strip(), "task has empty hint")

    def test_depends_on_resolves_within_same_project(self):
        """Any wired dependency points to a real task in the same project."""
        deps = ProjectTask.objects.filter(depends_on__isnull=False).select_related(
            "project", "depends_on", "depends_on__project"
        )
        # The seed data declares many dependencies; make sure they actually wired.
        self.assertGreater(deps.count(), 50)
        for task in deps:
            with self.subTest(task=f"{task.project.slug}:{task.jira_key}"):
                self.assertEqual(
                    task.depends_on.project_id,
                    task.project_id,
                    "depends_on points to a task in a different project",
                )

    def test_cross_technology_capstones_present(self):
        """The cross-tech capstones exist, sit under their primary technology,
        and have dependency-wired phases."""
        for slug, tech_slug in EXPECTED_CAPSTONES.items():
            with self.subTest(capstone=slug):
                proj = Project.objects.filter(slug=slug).first()
                self.assertIsNotNone(proj, f"capstone '{slug}' missing")
                self.assertEqual(proj.technology.slug, tech_slug)
                self.assertGreaterEqual(proj.tasks.count(), 6)
                self.assertGreaterEqual(
                    proj.tasks.filter(depends_on__isnull=False).count(),
                    1,
                    f"capstone '{slug}' has no wired dependencies",
                )

    def test_seed_is_idempotent(self):
        """Re-running the command creates nothing new and preserves counts."""
        before_projects = Project.objects.count()
        before_tasks = ProjectTask.objects.count()
        call_command("seed_projects", verbosity=0)
        self.assertEqual(Project.objects.count(), before_projects)
        self.assertEqual(ProjectTask.objects.count(), before_tasks)
