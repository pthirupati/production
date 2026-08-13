"""Durable pending Jira @team replies (audit X2b)."""

from django.test import TestCase
from django.utils import timezone

from apps.jira_integration import pending_team_replies as ptr
from apps.jira_integration.models import PendingTeamReply


class PendingTeamReplyTests(TestCase):
    def test_enqueue_and_list(self):
        row = ptr.enqueue_pending_team_reply(
            issue_key="LAB-1",
            session_id="s1",
            author="ops-bot",
            message="on it",
            actions=["backup_taken"],
            delay_seconds=60,
        )
        self.assertTrue(row["id"])
        pending = ptr.list_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["issue_key"], "LAB-1")
        self.assertEqual(PendingTeamReply.objects.count(), 1)
        self.assertTrue(timezone.is_aware(PendingTeamReply.objects.get().deliver_at))

    def test_sweep_delivers_due_rows(self):
        ptr.enqueue_pending_team_reply(
            issue_key="LAB-DUE",
            session_id="",
            author="ops-bot",
            message="done",
            delay_seconds=0,
        )
        delivered = []

        def fake_deliver(issue_key, session_id, author, message, actions, scenario_slug=""):
            delivered.append(issue_key)

        import apps.jira_integration.team_bots as tb
        original = tb.deliver_team_reply_now
        tb.deliver_team_reply_now = fake_deliver
        try:
            result = ptr.deliver_due_pending_team_replies()
        finally:
            tb.deliver_team_reply_now = original

        self.assertEqual(result["delivered"], 1)
        self.assertEqual(delivered, ["LAB-DUE"])
        self.assertEqual(ptr.list_pending(), [])
        self.assertEqual(PendingTeamReply.objects.count(), 0)

    def test_cancel_for_issue(self):
        ptr.enqueue_pending_team_reply(
            issue_key="LAB-X", session_id="", author="a", message="m", delay_seconds=10,
        )
        self.assertEqual(ptr.cancel_pending_for_issue("LAB-X"), 1)
        self.assertEqual(ptr.list_pending(), [])
        self.assertEqual(PendingTeamReply.objects.count(), 0)
