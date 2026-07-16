"""Tests for Jira @team mention bots."""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.jira_integration import team_bots
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

    def test_network_configure_eth1(self):
        text = "@network team configure eth1"
        teams = parse_team_mentions(text)
        actions = resolve_team_actions(text, teams, "linux-nic-add-vmware-rescan")
        self.assertEqual(actions[0][1], "network_nic_added")

    def test_security_approve_firewall(self):
        text = "@security team approve firewall change"
        teams = parse_team_mentions(text)
        self.assertIn("security", teams)
        actions = resolve_team_actions(text, teams, "sim-rhel-firewall")
        self.assertEqual(actions[0][1], "security_approved")

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


class TeamReplyDeliveryTests(TestCase):
    """End-to-end delivery: reply comment MUST persist AND action MUST apply.

    Regression guard for BUG C — @team mentions "did nothing": the delayed reply
    runs in a separate Celery process whose in-memory simulation-engine registry
    is empty, so the state-change action was silently dropped. The reply comment
    posted, but backup_taken / *_stopped / disk / nic were never applied.
    """

    def setUp(self):
        from apps.question_bank.models import Scenario, Technology
        from apps.labs.models import LabSession
        from apps.jira_integration.models import UserScenarioJiraTicket

        User = get_user_model()
        self.user = User.objects.create_user(username="learner", email="l@x.com", password="x")
        tech = Technology.objects.create(name="RHEL")
        self.scenario = Scenario.objects.create(
            technology=tech, slug="sim-rhel-patching", title="RHEL Patching",
            category="linux", difficulty="medium", description="patch it",
            initial_state="broken",
        )
        self.session = LabSession.objects.create(
            user=self.user, scenario=self.scenario, provider="simulated",
            jira_issue_key="FIX-DEL-1",
        )
        self.ticket = UserScenarioJiraTicket.objects.create(
            user=self.user, scenario=self.scenario, issue_key="FIX-DEL-1",
            jira_status="In Progress", simulated=True, last_session=self.session,
        )

    def _comment_count(self):
        from apps.jira_integration.models import JiraCommentLog
        return JiraCommentLog.objects.filter(issue_key="FIX-DEL-1").count()

    def test_reply_comment_persisted(self):
        team_bots.deliver_team_reply_now(
            "FIX-DEL-1", str(self.session.id), "Backup Team",
            "✓ Full backup completed and verified on backup server.",
            ["backup_taken"], "sim-rhel-patching",
        )
        from apps.jira_integration.models import JiraCommentLog
        bot = JiraCommentLog.objects.filter(issue_key="FIX-DEL-1", author="Backup Team")
        self.assertTrue(bot.exists(), "Team bot reply comment was not persisted")

    def test_action_applied_to_snapshot_when_engine_not_in_memory(self):
        """The Celery worker has no live engine -> must restore snapshot, apply
        the action, and re-persist it."""
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
        from apps.labs.provisioner.simulation.sim_persistence import (
            snapshot_engine, restore_engine,
        )
        from apps.labs.provisioner.simulation import shell as shell_mod

        # Web worker persisted a fresh snapshot (backup NOT yet taken).
        engine = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        self.assertFalse(engine.shell.state.ops_backup_taken)
        self.session.simulation_snapshot = snapshot_engine(engine)
        self.session.save(update_fields=["simulation_snapshot"])

        # Celery worker: empty in-memory registry (separate process).
        shell_mod._SIM_SESSIONS.clear()

        team_bots.deliver_team_reply_now(
            "FIX-DEL-1", str(self.session.id), "Backup Team",
            "✓ Full backup completed and verified on backup server.",
            ["backup_taken"], "sim-rhel-patching",
        )

        self.session.refresh_from_db()
        restored = restore_engine(self.session.simulation_snapshot)
        self.assertIsNotNone(restored)
        self.assertTrue(
            restored.shell.state.ops_backup_taken,
            "backup_taken action was not applied to the persisted snapshot",
        )

    def test_storage_disk_action_applied_to_snapshot(self):
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
        from apps.labs.provisioner.simulation.sim_persistence import (
            snapshot_engine, restore_engine,
        )
        from apps.labs.provisioner.simulation import shell as shell_mod

        engine = UnifiedSimulationEngine(scenario_slug="sim-rhel-lvm-extend", simulation_type="rhel")
        engine.shell.state.storage_disk_provisioned = False
        self.session.simulation_snapshot = snapshot_engine(engine)
        self.session.save(update_fields=["simulation_snapshot"])
        shell_mod._SIM_SESSIONS.clear()

        team_bots.deliver_team_reply_now(
            "FIX-DEL-1", str(self.session.id), "Storage Team",
            "✓ New disk provisioned.", ["storage_disk_added"], "sim-rhel-lvm-extend",
        )

        self.session.refresh_from_db()
        restored = restore_engine(self.session.simulation_snapshot)
        self.assertTrue(restored.shell.state.storage_disk_provisioned)

    def test_live_engine_path_does_not_clobber_web_worker_snapshot(self):
        """When the engine IS live in-process (gunicorn sync fallback), we must
        mutate it but NOT overwrite the DB snapshot (web worker owns that)."""
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
        from apps.labs.provisioner.simulation import shell as shell_mod

        engine = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        shell_mod.register_sim_session(
            str(self.session.id), "res-1", "rhel", {"engine": engine},
        )
        # No DB snapshot written yet.
        self.assertFalse(bool(self.session.simulation_snapshot))

        team_bots.deliver_team_reply_now(
            "FIX-DEL-1", str(self.session.id), "Backup Team",
            "✓ Full backup completed.", ["backup_taken"], "sim-rhel-patching",
        )

        # Live engine mutated in place.
        self.assertTrue(engine.shell.state.ops_backup_taken)
        # DB snapshot untouched (web worker's per-command persistence owns it).
        self.session.refresh_from_db()
        self.assertFalse(bool(self.session.simulation_snapshot))
        shell_mod._SIM_SESSIONS.clear()


class CoachHelpRequestTests(SimpleTestCase):
    def test_help_phrases_detected(self):
        self.assertTrue(team_bots.is_help_request("I'm stuck — need a hint"))
        self.assertTrue(team_bots.is_help_request("where do I start?"))
        self.assertFalse(team_bots.is_help_request("@backup team please take backup"))

    def test_coach_reply_includes_collaboration(self):
        class FakeTicket:
            description = (
                "## Incident\n\n### Acceptance criteria (definition of done)\n"
                "- Quarantine the host\n- Close the alert\n\n"
                "### Lab tools for this scenario\n- **Lab terminal**\n- **SOC console**\n"
            )
            scenario = None

        author, msg = team_bots.build_coach_reply(FakeTicket())
        self.assertEqual(author, "Change Management Bot")
        self.assertIn("Acceptance criteria", msg)
        self.assertIn("@security team", msg)
        self.assertIn("SOC console", msg)
