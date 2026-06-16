"""Tests for Jira @team mention bots."""

from django.test import SimpleTestCase

from apps.jira_integration.team_bots import (
    build_team_reply,
    parse_team_mentions,
    resolve_team_actions,
)


class TeamMentionTests(SimpleTestCase):
    def test_parse_backup_database_application(self):
        text = "@backup team @database team @application team please stop for patching"
        teams = parse_team_mentions(text)
        self.assertIn("backup", teams)
        self.assertIn("database", teams)
        self.assertIn("application", teams)

    def test_parse_storage_team(self):
        self.assertIn("storage", parse_team_mentions("@storage team add 50G disk"))

    def test_patching_actions(self):
        text = "@backup team @database team @application team stop for patching"
        teams = parse_team_mentions(text)
        actions = resolve_team_actions(text, teams, "sim-rhel-patching")
        ids = {a[1] for a in actions}
        self.assertIn("backup_taken", ids)
        self.assertIn("database_stopped", ids)
        self.assertIn("application_stopped", ids)

    def test_storage_disk_action(self):
        text = "@storage team please add disk for LVM"
        teams = parse_team_mentions(text)
        actions = resolve_team_actions(text, teams, "sim-rhel-lvm-extend")
        self.assertEqual(actions[0][1], "storage_disk_added")

    def test_start_database_action(self):
        text = "@database team please start database"
        teams = parse_team_mentions(text)
        actions = resolve_team_actions(text, teams, "sim-rhel-patching")
        self.assertEqual(actions[0][1], "database_started")

    def test_network_nic_action(self):
        text = "@network team please add secondary IP 10.0.0.20/24"
        teams = parse_team_mentions(text)
        actions = resolve_team_actions(text, teams, "sim-rhel-network-nic")
        self.assertEqual(actions[0][1], "network_nic_added")

    def test_mount_failure_reply(self):
        from apps.jira_integration.team_bots import build_mount_failure_reply

        class FakeTicket:
            pass

        author, msg = build_mount_failure_reply(FakeTicket())
        self.assertIn("mount", msg.lower())
        self.assertIn("mount -a", msg.lower())


class TeamReplyTextTests(SimpleTestCase):
    def test_consolidated_stop_reply(self):
        class FakeScenario:
            slug = "sim-rhel-patching"

        class FakeTicket:
            scenario = FakeScenario()
            last_session_id = None

        teams = ["backup", "database", "application"]
        actions = [
            ("backup", "backup_taken"),
            ("database", "database_stopped"),
            ("application", "application_stopped"),
        ]
        author, msg = build_team_reply(teams, actions, FakeTicket(), "stop for patching")
        self.assertIn("backup", msg.lower())
        self.assertIn("database", msg.lower())
        self.assertIn("application", msg.lower())
