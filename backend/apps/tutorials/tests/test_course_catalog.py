"""Regression tests for two course-catalog defects.

1. A duplicate ``course_slug`` used to merge two courses into one 20-module
   Frankenstein course (two m01s, two m02s, …) with a ``course_title`` picked by
   row ordering. ``all_course_definitions()`` now raises instead.
2. ``default_linked_lab_slug()`` used to fall back to the Linux users/groups
   lab for any unknown topic, so MongoDB/Redis/Jaeger/ELK/Cisco/pfSense/Node.js/
   Bare Metal/Simulation/Django/Jenkins learners were all sent to a Linux lab.
   Unknown topics now return "" (no CTA) and log a warning.

These call the catalog helpers directly — no ``seed_tutorials`` run — so they
stay fast relative to the ~6 minute seed test.
"""

from collections import Counter
from unittest import mock

from django.test import SimpleTestCase

from apps.tutorials.completeness import default_linked_lab_slug
from apps.tutorials.management.commands import course_catalog
from apps.tutorials.management.commands.course_catalog import (
    all_course_definitions,
    build_catalog_specs,
)

LINUX_USERS_GROUPS_LAB = "academy-linux-001-learn-users-groups"

# The only topics legitimately allowed to link to the Linux users/groups lab.
LINUX_LAB_TOPICS = {"linux", "nginx"}


class CourseSlugUniquenessTest(SimpleTestCase):
    """Fix 1 — duplicate course_slug must be impossible."""

    def test_course_slugs_are_unique(self):
        slugs = [c["course_slug"] for c in all_course_definitions()]
        dupes = sorted(slug for slug, n in Counter(slugs).items() if n > 1)
        self.assertEqual(dupes, [], f"duplicate course_slug in catalog: {dupes}")

    def test_each_course_slug_has_exactly_one_course_title(self):
        titles: dict[str, set[str]] = {}
        for course in all_course_definitions():
            titles.setdefault(course["course_slug"], set()).add(course["course_title"])
        conflicts = {slug: sorted(t) for slug, t in titles.items() if len(t) > 1}
        self.assertEqual(
            conflicts, {},
            f"course_slug(s) mapping to more than one course_title: {conflicts}",
        )

    def test_github_actions_courses_are_two_distinct_ten_module_courses(self):
        """The original collision: both entries claimed github-actions-zero-hero."""
        by_slug = {c["course_slug"]: c for c in all_course_definitions()}
        for slug in ("github-actions-zero-hero", "github-actions-ci-zero-hero"):
            self.assertIn(slug, by_slug)
            self.assertEqual(
                len(by_slug[slug]["modules"]), 10,
                f"{slug} should be a 10-module course, not a merged 20-module one",
            )
        self.assertNotEqual(
            by_slug["github-actions-zero-hero"]["course_title"],
            by_slug["github-actions-ci-zero-hero"]["course_title"],
        )

    def test_duplicate_course_slug_raises(self):
        dupe = {
            "course_slug": "duplicate-slug-under-test",
            "course_title": "Duplicate Under Test",
            "topic": "Linux",
            "modules": ["only module"],
        }
        with mock.patch.object(course_catalog, "COURSE_DEFINITIONS", [dupe, {**dupe}]):
            with self.assertRaises(ValueError) as ctx:
                all_course_definitions()
        self.assertIn("duplicate-slug-under-test", str(ctx.exception))


class CatalogSpecUniquenessTest(SimpleTestCase):
    """Fix 1, downstream — expanded specs must not repeat module positions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ~20s to expand; build once and share across the assertions below.
        cls.specs = build_catalog_specs()

    def test_course_slug_and_module_order_pairs_are_unique(self):
        pairs = Counter((s["course_slug"], s["module_order"]) for s in self.specs)
        dupes = sorted(pair for pair, n in pairs.items() if n > 1)
        self.assertEqual(
            dupes, [],
            f"repeated (course_slug, module_order) — merged courses: {dupes}",
        )

    def test_tutorial_slugs_are_unique(self):
        slugs = Counter(s["slug"] for s in self.specs)
        dupes = sorted(slug for slug, n in slugs.items() if n > 1)
        self.assertEqual(dupes, [], f"duplicate tutorial slug: {dupes}")

    def test_each_course_slug_has_one_course_title_in_specs(self):
        titles: dict[str, set[str]] = {}
        for spec in self.specs:
            titles.setdefault(spec["course_slug"], set()).add(spec["course_title"])
        conflicts = {slug: sorted(t) for slug, t in titles.items() if len(t) > 1}
        self.assertEqual(conflicts, {}, f"conflicting course_title in specs: {conflicts}")


class DefaultLinkedLabSlugTest(SimpleTestCase):
    """Fix 2 — no topic may silently inherit the Linux users/groups lab."""

    def test_every_catalog_topic_resolves_to_a_lab(self):
        unlinked = sorted(
            topic for topic in {c["topic"] for c in all_course_definitions()}
            if not default_linked_lab_slug(topic)
        )
        self.assertEqual(
            unlinked, [],
            "catalog topics with no linked lab (add an alias in completeness.py "
            f"or author the scenario): {unlinked}",
        )

    def test_no_topic_falls_back_to_the_linux_users_groups_lab(self):
        misrouted = sorted(
            topic for topic in {c["topic"] for c in all_course_definitions()}
            if default_linked_lab_slug(topic) == LINUX_USERS_GROUPS_LAB
            and topic.lower() not in LINUX_LAB_TOPICS
        )
        self.assertEqual(
            misrouted, [],
            "topics wrongly pointed at the Linux users/groups lab "
            f"(the old catch-all regression): {misrouted}",
        )

    def test_previously_misrouted_topics_have_their_own_labs(self):
        """The 11 topics that shipped a Linux lab as their hands-on link."""
        for topic in (
            "MongoDB", "Redis", "Jaeger", "ELK", "Cisco", "pfSense",
            "Node.js", "Bare Metal", "Simulation", "Django", "Jenkins",
        ):
            with self.subTest(topic=topic):
                slug = default_linked_lab_slug(topic)
                self.assertTrue(slug, f"{topic} resolved to no lab at all")
                self.assertNotEqual(
                    slug, LINUX_USERS_GROUPS_LAB,
                    f"{topic} is still routed to the Linux users/groups lab",
                )

    def test_cloud_topics_link_to_their_own_cloud_labs(self):
        """AWS/Azure/GCP must not be aliased back to Terraform.

        These three topics once carried ``"aws"/"azure"/"gcp" -> "terraform"``
        aliases in ``completeness.py``, so every AWS, Azure and GCP tutorial
        shipped a Terraform lab as its hands-on link — even though
        ``scenarios/aws/`` holds 420 scenarios of its own and azure/gcp 150
        each. The alias entries are deliberately absent now and the glob
        fallback resolves each topic to its own academy lab. If this test
        fails, someone re-added the aliases: delete them, don't retarget the
        assertion.
        """
        for topic, tech in (("AWS", "aws"), ("Azure", "azure"), ("GCP", "gcp")):
            with self.subTest(topic=topic):
                slug = default_linked_lab_slug(topic)
                self.assertTrue(slug, f"{topic} resolved to no lab at all")
                self.assertTrue(
                    slug.startswith(f"academy-{tech}-"),
                    f"{topic} resolved to {slug!r}, which is not one of its own "
                    f"scenarios/{tech}/academy-{tech}-* labs",
                )
                self.assertNotIn(
                    "terraform", slug,
                    f"{topic} is routed back to a Terraform lab ({slug!r}) — the "
                    f'"{tech}": "terraform" alias regression is back in '
                    "completeness.py",
                )

    def test_linux_topics_still_get_the_linux_lab(self):
        self.assertEqual(default_linked_lab_slug("Linux"), LINUX_USERS_GROUPS_LAB)
        self.assertEqual(default_linked_lab_slug("Nginx"), LINUX_USERS_GROUPS_LAB)

    def test_unknown_topic_returns_empty_and_warns(self):
        with self.assertLogs("apps.tutorials.completeness", level="WARNING") as logs:
            self.assertEqual(default_linked_lab_slug("Totally Fake Tech"), "")
        self.assertTrue(
            any("Totally Fake Tech" in line for line in logs.output),
            f"expected a warning naming the unknown topic, got: {logs.output}",
        )
