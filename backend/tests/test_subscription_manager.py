"""subscription-manager realism + paced follow streams."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.shell import StreamedCommandResult
from apps.jira_integration.team_bots import (
    looks_like_failed_team_mention,
    parse_team_mentions,
)


class SubscriptionManagerTests(SimpleTestCase):
    def test_status_current_when_healthy(self):
        sh = RHELShell(hostname="rhel9")
        out = sh.run("subscription-manager status")
        self.assertIn("Overall Status:", out)
        self.assertIn("Current", out)
        self.assertEqual(sh.state.last_exit_code, 0)

    def test_broken_entitlement_then_refresh(self):
        sh = RHELShell(scenario_slug="rhel-subscription-manager-config", hostname="rhel9")
        before = sh.run("subscription-manager status")
        self.assertIn("Invalid", before)
        self.assertNotEqual(sh.state.last_exit_code, 0)
        refresh = sh.run("subscription-manager refresh")
        self.assertIn("refreshed", refresh.lower())
        after = sh.run("subscription-manager status")
        self.assertIn("Current", after)
        repos = sh.run("subscription-manager repos --list")
        self.assertIn("rhel-9-for-x86_64-baseos-rpms", repos)
        self.assertIn("Enabled:   1", repos)
        repo_file = sh.state.read_file("/etc/yum.repos.d/redhat.repo") or ""
        self.assertIn("rhel-9-for-x86_64-baseos-rpms", repo_file)
        self.assertIn("enabled=1", repo_file)

    def test_register_with_ticket_credentials(self):
        st = RHELOSState(hostname="rhel9")
        st.rhsm_registered = False
        st.rhsm_entitlement_valid = False
        sh = RHELShell(state=st)
        bad = sh.run("subscription-manager register --username wrong --password bad")
        self.assertIn("401", bad)
        ok = sh.run(
            "subscription-manager register "
            "--username lab-admin@fixitlab.internal "
            "--password 'RedHatLab!Practice2024' "
            "--org 15678901"
        )
        self.assertIn("registered", ok.lower())
        self.assertTrue(st.rhsm_registered)
        self.assertTrue(st.rhsm_entitlement_valid)

    def test_ping_stream_handler_paces_lines(self):
        sh = RHELShell(hostname="rhel9")
        handler = sh.create_stream_handler()
        out = handler("ping -c 3 127.0.0.1")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertGreaterEqual(len(out.lines), 4)
        self.assertEqual(out.delay_s, 1.0)

    def test_journalctl_follow_is_streamed(self):
        sh = RHELShell(hostname="rhel9")
        handler = sh.create_stream_handler()
        out = handler("journalctl -f")
        self.assertIsInstance(out, StreamedCommandResult)
        self.assertTrue(any("follow tick" in ln for ln in out.lines))


class TeamMentionCoachTests(SimpleTestCase):
    def test_team_storage_order(self):
        self.assertIn("storage", parse_team_mentions("@team storage please add disk"))

    def test_near_miss_coach(self):
        self.assertTrue(looks_like_failed_team_mention("@storageteam add disk"))
        self.assertFalse(looks_like_failed_team_mention("@storage team add disk"))
        self.assertFalse(looks_like_failed_team_mention("checking logs now"))
