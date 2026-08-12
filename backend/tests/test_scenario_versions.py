"""
Scenario version history (audit B7).

The table was write-only and the writer had three defects: every save marked a
new row is_active=True without clearing the previous one, version numbers came
from count()+1 (which reuses a number after a delete and trips the
unique_together), and every failure was swallowed by a bare `except: pass`.
"""
from django.contrib import admin
from django.test import TestCase

from apps.question_bank.models import Scenario, Technology
from apps.scenario_versions.models import ScenarioVersion
from apps.scenario_versions.utils import get_active_version, get_version_history


class ScenarioVersionCaptureTests(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="VersionTech")
        self.scenario = Scenario.objects.create(
            technology=self.tech,
            slug="version-scn",
            title="Original",
            difficulty="easy",
        )

    def _versions(self):
        return ScenarioVersion.objects.filter(scenario=self.scenario)

    def test_exactly_one_active_version_after_repeated_edits(self):
        """The core bug: three saves left three rows all flagged is_active."""
        self.scenario.title = "Second"
        self.scenario.save()
        self.scenario.title = "Third"
        self.scenario.save()

        self.assertEqual(self._versions().count(), 3)
        self.assertEqual(self._versions().filter(is_active=True).count(), 1)

        active = get_active_version(self.scenario)
        self.assertIsNotNone(active)
        self.assertEqual(active.version, 3)

    def test_active_version_reflects_latest_definition(self):
        self.scenario.title = "Renamed"
        self.scenario.save()

        active = get_active_version(self.scenario)
        self.assertIn("Renamed", active.changelog)

    def test_version_numbers_survive_a_deleted_row(self):
        """count()+1 reused version 2 here and blew up on unique_together."""
        self.scenario.title = "Second"
        self.scenario.save()
        self.scenario.title = "Third"
        self.scenario.save()

        # Drop a middle version, as a history-pruning job would.
        self._versions().filter(version=2).delete()

        self.scenario.title = "Fourth"
        self.scenario.save()

        versions = sorted(self._versions().values_list("version", flat=True))
        self.assertEqual(versions, [1, 3, 4])
        self.assertEqual(self._versions().filter(is_active=True).count(), 1)
        self.assertEqual(get_active_version(self.scenario).version, 4)

    def test_unchanged_save_does_not_create_a_version(self):
        """Re-saving without touching the definition must not grow the table."""
        self.scenario.save()
        self.scenario.save()

        self.assertEqual(self._versions().count(), 1)

    def test_active_version_is_always_the_highest_numbered(self):
        """The no-op check compares against the highest version, so "highest"
        and "active" must not be able to drift apart."""
        for title in ("Second", "Third", "Fourth"):
            self.scenario.title = title
            self.scenario.save()

        highest = self._versions().order_by("-version").first()
        self.assertTrue(highest.is_active)
        self.assertEqual(get_active_version(self.scenario).pk, highest.pk)

    def test_history_is_newest_first(self):
        self.scenario.title = "Second"
        self.scenario.save()

        history = list(get_version_history(self.scenario))
        self.assertEqual([v.version for v in history], [2, 1])

    def test_scenario_versions_are_readable_in_admin(self):
        """The audit's ask: the app has a reader, not just a writer."""
        self.assertIn(ScenarioVersion, admin.site._registry)

        model_admin = admin.site._registry[ScenarioVersion]
        version = get_active_version(self.scenario)

        self.assertEqual(model_admin.summary(version), "Original")
        self.assertIn("Original", model_admin.snapshot(version))
        self.assertEqual(model_admin.position(version), "v1 of 1")

        # An audit trail nobody can forge after the fact.
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
