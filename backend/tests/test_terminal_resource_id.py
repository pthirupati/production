"""Terminal consumer resource ID resolution for simulation labs."""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.terminal.consumers import TerminalConsumer


class TerminalResourceIdTests(TestCase):
    def test_simulation_primary_uses_container_id(self):
        consumer = TerminalConsumer()
        consumer.provider_type = "simulation"
        consumer._terminal_host = "primary"
        consumer.lab_session = MagicMock(
            container_id="sim-abc123",
            instance_id="",
            lab_hosts=[],
        )
        self.assertEqual(consumer._get_resource_id(), "sim-abc123")

    def test_docker_primary_uses_container_id(self):
        consumer = TerminalConsumer()
        consumer.provider_type = "docker"
        consumer._terminal_host = "primary"
        consumer.lab_session = MagicMock(
            container_id="docker-id",
            instance_id="",
            lab_hosts=[],
        )
        self.assertEqual(consumer._get_resource_id(), "docker-id")

    def test_cloud_primary_uses_instance_id(self):
        consumer = TerminalConsumer()
        consumer.provider_type = "aws_ec2"
        consumer._terminal_host = "primary"
        consumer.lab_session = MagicMock(
            container_id="",
            instance_id="i-12345",
            lab_hosts=[],
        )
        self.assertEqual(consumer._get_resource_id(), "i-12345")

    def test_simulation_companion_host_from_lab_hosts(self):
        consumer = TerminalConsumer()
        consumer.provider_type = "simulation"
        consumer._terminal_host = "web1"
        consumer.lab_session = MagicMock(
            container_id="sim-primary",
            instance_id="",
            lab_hosts=[
                {"name": "primary", "container_id": "sim-primary"},
                {"name": "web1", "container_id": "sim-primary-web1"},
            ],
        )
        self.assertEqual(consumer._get_resource_id(), "sim-primary-web1")
