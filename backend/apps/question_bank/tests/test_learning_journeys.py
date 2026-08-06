"""Tests for Learning Journeys: seed command, model integrity, and read-only API.

These build just enough REAL catalog content (a technology + the scenarios,
project, and certification track that the ``junior-linux-admin-rhcsa`` journey
references) so we can assert the seeded steps resolve against existing content
and the API returns resolved titles — without needing the full 5,400-scenario
production seed.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.question_bank.models import (
    LearningJourney,
    JourneyStep,
    Technology,
    Scenario,
    Project,
    UserProjectProgress,
)
from apps.certifications.models import CertificationTrack, ExamAttempt
from apps.progress.models import UserScenarioProgress
from apps.tutorials.models import Tutorial, TutorialProgress

User = get_user_model()


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


class JourneyTutorialCourseResolutionTests(TestCase):
    """tutorial_course steps must resolve against the real tutorial catalog.

    A "course" is the set of Tutorial rows sharing a ``course_slug``, so these
    tests seed multiple modules per course to prove the view groups them into
    one title instead of emitting a row (or a query) per module.
    """

    COURSE_SLUG = "linux-sysadmin-zero-hero"  # the linux journey's step-0 ref
    COURSE_TITLE = "Linux Sysadmin: Zero to Hero"

    def setUp(self):
        _seed_minimal_catalog()
        call_command("seed_learning_journeys")
        self.client = APIClient()

    def _make_course(self, *, modules=3, course_title=None, is_published=True):
        for i in range(modules):
            Tutorial.objects.create(
                slug=f"{self.COURSE_SLUG}-module-{i}",
                title=f"Module {i}",
                course_slug=self.COURSE_SLUG,
                course_title=self.COURSE_TITLE if course_title is None else course_title,
                module_order=i,
                is_published=is_published,
            )

    def _course_ref(self):
        resp = self.client.get("/api/journeys/junior-linux-admin-rhcsa/")
        self.assertEqual(resp.status_code, 200)
        steps = [s for s in resp.json()["steps"] if s["kind"] == "tutorial_course"]
        self.assertEqual(len(steps), 1)
        refs = steps[0]["references"]
        self.assertEqual(len(refs), 1, "one ref per course, not one per module")
        return steps[0], refs[0]

    def test_resolves_course_slug_to_the_catalog_course_title(self):
        self._make_course()
        step, ref = self._course_ref()
        self.assertEqual(ref["slug"], self.COURSE_SLUG)
        self.assertTrue(ref["resolved"])
        self.assertEqual(ref["title"], self.COURSE_TITLE)
        # The resolved title is the catalog's, not the step's stored copy.
        self.assertNotEqual(ref["title"], step["title"])

    def test_blank_course_titles_do_not_win_over_a_real_one(self):
        """Some catalog rows leave course_title blank; a real title must win."""
        Tutorial.objects.create(
            slug=f"{self.COURSE_SLUG}-module-blank", title="Module blank",
            course_slug=self.COURSE_SLUG, course_title="", module_order=0,
        )
        self._make_course(modules=1)
        _step, ref = self._course_ref()
        self.assertTrue(ref["resolved"])
        self.assertEqual(ref["title"], self.COURSE_TITLE)

    def test_unseeded_course_keeps_the_steps_stored_title(self):
        """No tutorials seeded: degrade to the stored title, never a raw slug."""
        self.assertFalse(Tutorial.objects.exists())
        step, ref = self._course_ref()
        self.assertFalse(ref["resolved"])
        self.assertEqual(ref["title"], step["title"])
        self.assertNotEqual(ref["title"], ref["slug"])

    def test_course_with_only_blank_titles_is_unresolved(self):
        self._make_course(course_title="")
        step, ref = self._course_ref()
        self.assertFalse(ref["resolved"])
        self.assertEqual(ref["title"], step["title"])

    def test_unpublished_course_does_not_resolve(self):
        self._make_course(is_published=False)
        step, ref = self._course_ref()
        self.assertFalse(ref["resolved"])
        self.assertEqual(ref["title"], step["title"])

    def test_resolution_cost_is_flat_in_module_count(self):
        """Guards the N+1 the single-pass context exists to prevent.

        Absolute counts churn with unrelated middleware, so assert the shape
        that actually matters: 12 modules must cost the same as 2.
        """
        self._make_course(modules=2)
        small = self._detail_query_count()
        Tutorial.objects.all().delete()
        self._make_course(modules=12)
        self.assertEqual(self._detail_query_count(), small)

    def _detail_query_count(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as cap:
            resp = self.client.get("/api/journeys/junior-linux-admin-rhcsa/")
        self.assertEqual(resp.status_code, 200)
        return len(cap)


class JourneyNextStepTests(TestCase):
    """GET /api/journeys/next/ — the dashboard's "where was I?" answer.

    The seeded junior-linux-admin-rhcsa journey is the fixture throughout; its
    steps are, in order:

        0 tutorial_course  linux-sysadmin-zero-hero
        1 scenarios        001, 002, 003
        2 scenarios        006
        3 project          linux-fundamentals-first-server
        4 project          linux-lvm-storage-build
        5 certification    rhcsa
        6 milestone        (no reference)

    No tutorials are seeded unless a test asks for them, so step 0 usually has
    nothing measurable behind it and drops out of the counts.
    """

    URL = "/api/journeys/next/"

    def setUp(self):
        _seed_minimal_catalog()
        call_command("seed_learning_journeys")
        self.user = User.objects.create_user(username="alice", password="pw12345!")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _complete_scenarios(self, *slugs, user=None):
        for slug in slugs:
            UserScenarioProgress.objects.create(
                user=user or self.user,
                scenario=Scenario.objects.get(slug=slug),
                completed=True,
            )

    def _complete_project(self, slug):
        UserProjectProgress.objects.create(
            user=self.user, project=Project.objects.get(slug=slug), status="completed"
        )

    def _complete_linux_labs_and_projects(self):
        """Everything on the linux journey except the certification step."""
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS)
        for slug in LINUX_PROJECT_SLUGS:
            self._complete_project(slug)

    def _pass_exam(self, track_slug):
        ExamAttempt.objects.create(
            user=self.user,
            track=CertificationTrack.objects.get(slug=track_slug),
            status="passed",
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def _next(self, expect=200):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, expect)
        return resp.json()

    # ── access ───────────────────────────────────────────────────────────────
    def test_requires_authentication(self):
        """Unlike list/detail this is per-user, so it is not AllowAny."""
        resp = APIClient().get(self.URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_next_is_not_swallowed_by_the_slug_route(self):
        """`next` must hit this view, not 404 as a lookup for a journey slug."""
        self.assertEqual(self.client.get(self.URL).status_code, 200)

    # ── the "not started" case ───────────────────────────────────────────────
    def test_returns_null_when_the_user_has_completed_nothing(self):
        data = self._next()
        self.assertIsNone(data["journey"])
        self.assertIsNone(data["next_step"])

    def test_an_incomplete_attempt_does_not_enroll_the_user(self):
        """Browsing a lab is not progress — only completion counts.

        Otherwise a single abandoned scenario would enrol the user in whichever
        journey happens to mention it, and the dashboard would nag about a
        track they never chose.
        """
        UserScenarioProgress.objects.create(
            user=self.user,
            scenario=Scenario.objects.get(slug=LINUX_SCENARIO_SLUGS[0]),
            completed=False,
            attempts=3,
        )
        self.assertIsNone(self._next()["journey"])

    # ── picking the next step ────────────────────────────────────────────────
    def test_points_at_the_first_unfinished_item_within_a_partial_step(self):
        self._complete_scenarios(LINUX_SCENARIO_SLUGS[0], LINUX_SCENARIO_SLUGS[1])
        data = self._next()

        self.assertEqual(data["journey"]["slug"], "junior-linux-admin-rhcsa")
        step = data["next_step"]
        self.assertEqual(step["kind"], "scenarios")
        # Not the step's first ref — the first one still outstanding.
        self.assertEqual(step["slug"], LINUX_SCENARIO_SLUGS[2])
        self.assertEqual(step["link"], f"/scenarios/{LINUX_SCENARIO_SLUGS[2]}")
        self.assertEqual((step["items_completed"], step["items_total"]), (2, 3))

    def test_advances_to_the_next_step_once_a_step_is_finished(self):
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3])
        step = self._next()["next_step"]
        self.assertEqual(step["order"], 2)
        self.assertEqual(step["slug"], LINUX_SCENARIO_SLUGS[3])

    def test_step_counts_describe_measurable_steps_only(self):
        """The milestone and the unseeded course carry no progress signal.

        Counting them would show "1/7" to someone who has finished one of the
        five steps that can actually be completed.
        """
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3])
        journey = self._next()["journey"]
        self.assertEqual(journey["completed_steps"], 1)
        self.assertEqual(journey["total_steps"], 5)  # 2 scenarios + 2 projects + 1 cert

    def test_target_title_is_the_content_title_not_the_step_title(self):
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3])
        step = self._next()["next_step"]
        self.assertEqual(
            step["target_title"],
            Scenario.objects.get(slug=LINUX_SCENARIO_SLUGS[3]).title,
        )
        self.assertNotEqual(step["target_title"], step["title"])

    def test_falls_back_to_the_step_title_when_the_target_is_unresolvable(self):
        """A dangling ref still names something, same rule as the detail view."""
        journey = LearningJourney.objects.get(slug="junior-linux-admin-rhcsa")
        journey.steps.filter(order__gte=2).delete()
        JourneyStep.objects.create(
            journey=journey, order=2, kind="scenarios",
            title="Broken ref step", ref_slugs=["does-not-exist-scenario"],
        )
        # Finish step 1 so the user has real progress and lands on the broken step.
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3])
        step = self._next()["next_step"]
        self.assertEqual(step["slug"], "does-not-exist-scenario")
        self.assertEqual(step["target_title"], "Broken ref step")

    def test_milestone_steps_are_never_offered_as_the_next_step(self):
        """A milestone has no reference, so it can never be marked done.

        Treated as work it would pin "next" to the milestone forever, and the
        card would tell the user to go do something with nowhere to click.
        """
        self._complete_linux_labs_and_projects()
        step = self._next()["next_step"]
        self.assertEqual(step["kind"], "certification")  # skips straight to step 5

    # ── link targets per kind ────────────────────────────────────────────────
    def test_certification_step_links_to_the_track_page(self):
        self._complete_linux_labs_and_projects()
        step = self._next()["next_step"]
        self.assertEqual(step["link"], "/certifications/rhcsa")
        self.assertEqual(step["target_title"], "Red Hat Certified System Administrator")

    def test_project_step_has_no_link_because_the_spa_has_no_project_route(self):
        """Honest null beats a dead link. Revisit if /projects/<slug> lands."""
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS)
        step = self._next()["next_step"]
        self.assertEqual(step["kind"], "project")
        self.assertIsNone(step["link"])
        self.assertEqual(step["slug"], "linux-fundamentals-first-server")
        # Still names the capstone so the card can say what is next.
        self.assertTrue(step["target_title"])

    def test_tutorial_course_step_links_to_the_first_unread_module(self):
        """A course step must resolve to a real /tutorials/<slug>.

        course_slug is not itself a routable slug, so linking it would 404.
        """
        for i in range(3):
            Tutorial.objects.create(
                slug=f"linux-sysadmin-zero-hero-module-{i}", title=f"Module {i}",
                topic="Linux", course_slug="linux-sysadmin-zero-hero",
                course_title="Linux Sysadmin: Zero to Hero", module_order=i,
            )
        TutorialProgress.objects.create(
            user=self.user,
            tutorial=Tutorial.objects.get(slug="linux-sysadmin-zero-hero-module-0"),
            completed=True,
        )
        step = self._next()["next_step"]
        self.assertEqual(step["kind"], "tutorial_course")
        self.assertEqual(step["link"], "/tutorials/linux-sysadmin-zero-hero-module-1")
        self.assertEqual(step["target_title"], "Module 1")
        self.assertEqual((step["items_completed"], step["items_total"]), (1, 3))

    # ── journey selection ────────────────────────────────────────────────────
    def test_a_finished_journey_is_not_reported_as_in_progress(self):
        self._complete_linux_labs_and_projects()
        self._pass_exam("rhcsa")
        data = self._next()
        self.assertIsNone(data["journey"])
        self.assertIsNone(data["next_step"])

    def test_progress_is_scoped_to_the_requesting_user(self):
        other = User.objects.create_user(username="bob", password="pw12345!")
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3], user=other)
        self.assertIsNone(self._next()["journey"])

    def test_inactive_journeys_are_ignored(self):
        journey = LearningJourney.objects.get(slug="junior-linux-admin-rhcsa")
        journey.is_active = False
        journey.save(update_fields=["is_active"])
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3])
        self.assertIsNone(self._next()["journey"])

    def test_the_journey_with_more_completed_items_wins(self):
        """Journeys share content, so overlap alone can't pick one; effort does.

        The linux journey is order=0 and would win on catalog order, so a rival
        at order=9 winning proves the ranking follows completed work. The rival
        gets one scenario the linux journey doesn't reference, which is what
        puts it ahead 5 items to 4.
        """
        extra = Scenario.objects.create(
            technology=Technology.objects.get(slug="linux"),
            slug="rival-only-lab", title="Rival only lab",
            category="Core Skills", difficulty="easy", description="x",
        )
        rival = LearningJourney.objects.create(
            slug="rival-track", title="Rival Track", order=9,
        )
        JourneyStep.objects.create(
            journey=rival, order=0, kind="scenarios",
            title="Rival labs", ref_slugs=LINUX_SCENARIO_SLUGS + [extra.slug],
        )
        JourneyStep.objects.create(
            journey=rival, order=1, kind="project",
            title="Rival capstone", ref_slug="linux-lvm-storage-build",
        )
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS, extra.slug)

        data = self._next()
        self.assertEqual(data["journey"]["slug"], "rival-track")
        # And it resumes inside the rival, not at the linux journey's capstone.
        self.assertEqual(data["next_step"]["title"], "Rival capstone")

    def test_cost_does_not_grow_with_the_number_of_journeys(self):
        """One pass over all journeys, not a progress query per journey."""
        self._complete_scenarios(*LINUX_SCENARIO_SLUGS[:3])
        baseline = self._query_count()
        for i in range(6):
            extra = LearningJourney.objects.create(
                slug=f"extra-{i}", title=f"Extra {i}", order=20 + i,
            )
            JourneyStep.objects.create(
                journey=extra, order=0, kind="scenarios",
                title="Labs", ref_slugs=LINUX_SCENARIO_SLUGS[:1],
            )
        self.assertEqual(self._query_count(), baseline)

    def _query_count(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as cap:
            resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        return len(cap)
