"""Regression: terminal welcome must not sync-ORM in async connect (WS 4500)."""

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
)
class TerminalWelcomeNoSyncOrmTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="term-e2e", email="term-e2e@example.com", password="x",
        )
        self.tech, _ = Technology.objects.get_or_create(
            slug="linux", defaults={"name": "Linux", "price": 499, "is_free": False},
        )
        self.scenario, _ = Scenario.objects.get_or_create(
            slug="etc-hosts-breaks-app-test",
            defaults={
                "title": "Hosts file breaks app",
                "technology": self.tech,
                "lab_mode": "simulation",
                "simulation_type": "generic",
                "is_active": True,
                "is_free": True,
                "description": "CONTEXT: test\n\nENVIRONMENT: test\n\nOBJECTIVE: test",
                "objectives": ["fix hosts"],
                "time_limit": 900,
                "max_score": 100,
            },
        )
        if self.scenario.technology_id != self.tech.id:
            self.scenario.technology = self.tech
            self.scenario.lab_mode = "simulation"
            self.scenario.simulation_type = "generic"
            self.scenario.save()
        self.session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="RUNNING",
            provider="simulation",
            container_id="sim-test-term-001",
            duration_limit=900,
        )
    def test_get_session_prefetches_technology_and_welcome_strings(self):
        from apps.terminal.consumers import TerminalConsumer

        consumer = TerminalConsumer()
        sess = async_to_sync(consumer._get_session)(str(self.session.id), self.user)
        self.assertIsNotNone(sess)
        with self.assertNumQueries(0):
            slug = sess.scenario.technology.slug
        self.assertEqual(slug, "linux")
        self.assertEqual(consumer._welcome_scenario_title, "Hosts file breaks app")
        self.assertIn("Lab Server", consumer._welcome_provider_label)
        self.assertNotRegex(consumer._welcome_provider_label, r"(?i)simulation")

    def test_welcome_label_uses_lab_server_persona(self):
        from apps.labs.provisioner.simulation.sim_types import lab_server_banner
        from apps.terminal.consumers import _resolve_lab_provider_label

        banner = lab_server_banner("generic", "etc-hosts-breaks-app")
        self.assertNotRegex(banner, r"(?i)simulation")
        self.assertIn("Lab Server", banner)

        label = _resolve_lab_provider_label(
            "simulation", "datacenter", "datacenter", "academy-datacenter-141-learn-racks-15",
        )
        self.assertEqual(label, "Physical Data Center Host")
        self.assertNotRegex(label, r"(?i)simulation")

    def test_create_exec_stream_runs_via_database_sync_to_async(self):
        """ensure_sim_session ORM must not run on the event-loop thread."""
        from apps.terminal.consumers import TerminalConsumer

        consumer = TerminalConsumer()
        consumer.lab_session = async_to_sync(consumer._get_session)(
            str(self.session.id), self.user,
        )
        consumer.provider_type = "simulation"
        consumer._terminal_host = "primary"

        # Should complete without SynchronousOnlyOperation.
        exec_id, holder = async_to_sync(consumer._create_exec_stream)(
            self.session.container_id,
        )
        self.assertTrue(exec_id)
        self.assertIsNotNone(holder)
