"""Tests for Learning Journeys: seed command, model integrity, and read-only API.

These build just enough REAL catalog content (a technology + the scenarios,
project, and certification track that the ``junior-linux-admin-rhcsa`` journey
references) so we can assert the seeded steps resolve against existing content
and the API returns resolved titles — without needing the full 5,400-scenario
production seed.
"""

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.question_bank.models import (
    LearningJourney,
    JourneyStep,
    Technology,
    Scenario,
    Project,
)
from apps.certifications.models import CertificationTrack


# Slugs the seeded journeys reference (subset — enough to prove resolution).
LINUX_SCENARIO_SLUGS = [
    "academy-linux-001-learn-users-groups",
    "academy-linux-002-build-permissions-acl",
    "academy-linux-003-operate-systemd-services",
    "academy-linux-006-security-networking-firewalld",
]
LINUX_PROJECT_SLUGS = ["linux-fundamentals-first-server", "linux-lvm-storage-build"]


def _seed_minimal_catalog():
    """Create the real content the Junior Linux Admin journey references."""
    linux = Technology.objects.create(name="Linux Administration", slug="linux")
    # The four other journeys' primary techs — so primary_technology resolves.
    for name, slug in [
        ("Terraform", "terraform"),
        ("Kubernetes", "kubernetes"),
        ("DevSecOps Supply Chain", "devsecops-supplychain"),
        ("Prometheus", "prometheus"),
    ]:
        Technology.objects.create(name=name, slug=slug)

    for i, slug in enumerate(LINUX_SCENARIO_SLUGS):
        Scenario.objects.create(
            technology=linux,
            slug=slug,
            title=f"Linux lab {i}",
            category="Core Skills",
            difficulty="easy",
            description="x",
        )
    for slug in LINUX_PROJECT_SLUGS:
        Project.objects.create(
            technology=linux, title=slug.replace("-", " ").title(), slug=slug,
            description="x",
        )
    CertificationTrack.objects.create(
        slug="rhcsa", code="RHCSA", name="Red Hat Certified System Administrator",
        technology=linux,
    )
    return linux


class LearningJourneySeedTests(TestCase):
    def setUp(self):
        _seed_minimal_catalog()
        call_command("seed_learning_journeys")

    def test_seeds_exactly_five_active_journeys(self):
        self.assertEqual(LearningJourney.objects.count(), 5)
        self.assertEqual(LearningJourney.objects.filter(is_active=True).count(), 5)
        slugs = set(LearningJourney.objects.values_list("slug", flat=True))
        self.assertEqual(
            slugs,
            {
                "junior-linux-admin-rhcsa",
                "cloud-engineer-terraform-aws",
                "kubernetes-sre-cka",
                "devsecops-engineer-supply-chain",
                "sre-incident-responder",
            },
        )

    def test_seed_is_idempotent(self):
        call_command("seed_learning_journeys")  # second run
        self.assertEqual(LearningJourney.objects.count(), 5)
        # Steps rebuilt, not duplicated.
        journey = LearningJourney.objects.get(slug="junior-linux-admin-rhcsa")
        self.assertEqual(journey.steps.count(), 7)

    def test_every_journey_has_five_to_eight_ordered_steps_ending_in_milestone(self):
        for journey in LearningJourney.objects.all():
            steps = list(journey.steps.all())
            self.assertGreaterEqual(len(steps), 5, journey.slug)
            self.assertLessEqual(len(steps), 8, journey.slug)
            # Orders are 0..n-1 and monotonically increasing.
            self.assertEqual(
                [s.order for s in steps], list(range(len(steps))), journey.slug
            )
            # Ends in a clear milestone.
            self.assertEqual(steps[-1].kind, "milestone", journey.slug)

    def test_journeys_mix_kinds(self):
        journey = LearningJourney.objects.get(slug="junior-linux-admin-rhcsa")
        kinds = {s.kind for s in journey.steps.all()}
        self.assertTrue(
            {"tutorial_course", "scenarios", "project", "certification", "milestone"}
            <= kinds
        )

    def test_seeded_steps_reference_existing_content(self):
        """Scenario/project/cert refs on the linux journey point at real rows."""
        journey = LearningJourney.objects.get(slug="junior-linux-admin-rhcsa")
        for step in journey.steps.all():
            if step.kind == "scenarios":
                for slug in step.ref_slugs:
                    self.assertTrue(
                        Scenario.objects.filter(slug=slug).exists(),
                        f"scenario {slug} missing",
                    )
            elif step.kind == "project":
                self.assertTrue(
                    Project.objects.filter(slug=step.ref_slug).exists(),
                    f"project {step.ref_slug} missing",
                )
            elif step.kind == "certification":
                self.assertTrue(
                    CertificationTrack.objects.filter(slug=step.ref_slug).exists(),
                    f"cert {step.ref_slug} missing",
                )

    def test_missing_reference_does_not_break_the_journey(self):
        """A dangling ref renders as unresolved rather than 404-ing the journey."""
        journey = LearningJourney.objects.get(slug="junior-linux-admin-rhcsa")
        # Add a scenarios step pointing at a non-existent slug.
        JourneyStep.objects.create(
            journey=journey, order=99, kind="scenarios",
            title="Broken ref", ref_slugs=["does-not-exist-scenario"],
        )
        client = APIClient()
        resp = client.get("/api/journeys/junior-linux-admin-rhcsa/")
        self.assertEqual(resp.status_code, 200)
        broken = [s for s in resp.json()["steps"] if s["title"] == "Broken ref"][0]
        self.assertEqual(broken["references"][0]["resolved"], False)
        self.assertEqual(broken["references"][0]["title"], "does-not-exist-scenario")


class LearningJourneyAPITests(TestCase):
    def setUp(self):
        _seed_minimal_catalog()
        call_command("seed_learning_journeys")
        self.client = APIClient()

    def test_list_returns_all_active_journeys(self):
        resp = self.client.get("/api/journeys/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 5)
        first = data[0]
        for field in ("slug", "title", "role_label", "level", "step_count", "steps"):
            self.assertIn(field, first)
        self.assertEqual(first["slug"], "junior-linux-admin-rhcsa")  # order=0
        self.assertEqual(first["step_count"], 7)

    def test_list_is_public_allowany(self):
        resp = APIClient().get("/api/journeys/")  # no auth
        self.assertEqual(resp.status_code, 200)

    def test_detail_returns_ordered_resolved_steps(self):
        resp = self.client.get("/api/journeys/junior-linux-admin-rhcsa/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["slug"], "junior-linux-admin-rhcsa")
        orders = [s["order"] for s in data["steps"]]
        self.assertEqual(orders, sorted(orders))

        # The scenarios step resolves each real slug to its real title.
        scen_step = [s for s in data["steps"] if s["kind"] == "scenarios"][0]
        for ref in scen_step["references"]:
            self.assertTrue(ref["resolved"], ref["slug"])
            self.assertNotEqual(ref["title"], ref["slug"])  # real title, not slug echo

        # The certification step resolves to the track's real name.
        cert_step = [s for s in data["steps"] if s["kind"] == "certification"][0]
        cert_ref = cert_step["references"][0]
        self.assertTrue(cert_ref["resolved"])
        self.assertEqual(
            cert_ref["title"], "Red Hat Certified System Administrator"
        )

    def test_unknown_slug_returns_404(self):
        resp = self.client.get("/api/journeys/no-such-journey/")
        self.assertEqual(resp.status_code, 404)

    def test_inactive_journey_not_listed_and_404_on_detail(self):
        j = LearningJourney.objects.get(slug="kubernetes-sre-cka")
        j.is_active = False
        j.save(update_fields=["is_active"])
        listing = self.client.get("/api/journeys/").json()
        self.assertNotIn("kubernetes-sre-cka", {x["slug"] for x in listing})
        self.assertEqual(
            self.client.get("/api/journeys/kubernetes-sre-cka/").status_code, 404
        )
