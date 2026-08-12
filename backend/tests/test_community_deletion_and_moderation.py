"""Audit Z3-8 — deleting one account erased other people's conversations.

`Thread.author` and `Reply.author` were both `CASCADE`. Deleting a user
hard-deleted their threads, and `Reply.thread` cascades from there, so **every
reply on those threads went too** — including replies written by people who had
nothing to do with the deletion. One person leaving rewrote a discussion for
everyone else in it.

`SET_NULL` is the standard answer (Reddit, Stack Overflow, Discourse) and it still
satisfies erasure: severing the link is what removes the personal data, and the
content remains as `[deleted]`.

Two smaller defects fixed alongside:

* `ThreadDetailView.patch` wrote `title` straight through with `setattr`, so a
  301-character title reached a `CharField(max_length=300)` and came back as a
  `DataError` — a 500 for a plainly bad request.
* pin / lock / soft-delete left **no record of who did it**, so "why was my thread
  removed?" had no answer and neither did "who removed it". Same argument as the
  Z2-4 meta-audit: a trail that can be bypassed provides the appearance of
  accountability rather than the fact of it.

The moderation rows use `action="admin_action"` on purpose — that action sits
outside `_SECURITY_CLEAR_ACTIONS`, so they survive the security-log sweep. A
moderation record deleted by an unrelated cleanup would be worse than none,
because the resulting gap reads as "nothing happened".
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.community.models import Reply, Thread

User = get_user_model()

PASSWORD = "Str0ng-Pass-1"


class _Base(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@example.com", password=PASSWORD
        )
        self.bystander = User.objects.create_user(
            username="bystander", email="bystander@example.com", password=PASSWORD
        )
        self.mod = User.objects.create_user(
            username="mod", email="mod@example.com", password=PASSWORD, is_staff=True
        )
        self.thread = Thread.objects.create(
            author=self.author, title="How do I fix DNS?", body="It is broken."
        )
        self.reply = Reply.objects.create(
            thread=self.thread, author=self.bystander, body="Check resolv.conf"
        )
        self.client = APIClient()

    def _url(self):
        return f"/api/community/threads/{self.thread.id}/"


class DeletingAnAccountKeepsTheConversationTests(_Base):
    def test_the_thread_survives_its_author_leaving(self):
        self.author.delete()
        self.assertTrue(
            Thread.objects.filter(pk=self.thread.pk).exists(),
            "deleting a user hard-deleted their thread",
        )

    def test_other_peoples_replies_survive(self):
        """The damage that made this worse than ordinary data loss: the bystander
        never left, and their reply disappeared anyway."""
        self.author.delete()
        self.assertTrue(
            Reply.objects.filter(pk=self.reply.pk).exists(),
            "a bystander's reply was destroyed because the thread author left",
        )

    def test_the_author_link_is_severed(self):
        """This is what actually erases the personal data."""
        self.author.delete()
        self.thread.refresh_from_db()
        self.assertIsNone(self.thread.author_id)

    def test_a_reply_author_leaving_keeps_the_reply(self):
        self.bystander.delete()
        self.reply.refresh_from_db()
        self.assertIsNone(self.reply.author_id)
        self.assertEqual(self.reply.body, "Check resolv.conf")

    def test_the_api_renders_a_placeholder_rather_than_null(self):
        """`author: null` would make every consumer write its own special case."""
        self.author.delete()
        resp = self.client.get(self._url())
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self._url()} is not routed — this test must fail on a wrong URL "
            "rather than pass silently",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertEqual(resp.data["author"]["username"], "[deleted]")
        self.assertIsNone(resp.data["author"]["id"])

    def test_a_live_author_still_renders_normally(self):
        """Guard the guard: if the placeholder were returned unconditionally, every
        test above would pass while the API stopped naming anyone."""
        resp = self.client.get(self._url())
        self.assertEqual(resp.data["author"]["username"], "author")

    def test_an_orphaned_thread_cannot_be_edited_by_anyone(self):
        """`thread.author != request.user` must not become true-for-everyone."""
        self.author.delete()
        self.client.force_authenticate(user=self.bystander)
        resp = self.client.patch(self._url(), {"title": "Mine now"}, format="json")
        self.assertEqual(resp.status_code, 403)


class TitleValidationTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.author)

    def test_an_overlong_title_is_a_400_not_a_500(self):
        resp = self.client.patch(self._url(), {"title": "x" * 301}, format="json")
        self.assertEqual(resp.status_code, 400, getattr(resp, "data", resp))

    def test_a_title_at_the_limit_is_accepted(self):
        """Off-by-one here would reject legitimate titles."""
        resp = self.client.patch(self._url(), {"title": "x" * 300}, format="json")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))

    def test_a_blank_title_is_rejected(self):
        resp = self.client.patch(self._url(), {"title": "   "}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_the_thread_is_unchanged_after_a_rejection(self):
        self.client.patch(self._url(), {"title": "x" * 301}, format="json")
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.title, "How do I fix DNS?")


class ModerationIsRecordedTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.mod)

    def _mod_rows(self):
        return AuditLog.objects.filter(metadata__event="thread_moderated")

    def test_locking_someone_elses_thread_is_recorded(self):
        resp = self.client.patch(self._url(), {"is_locked": True}, format="json")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertTrue(self._mod_rows().exists())

    def test_it_names_the_moderator_and_the_change(self):
        self.client.patch(self._url(), {"is_pinned": True}, format="json")
        row = self._mod_rows().first()
        self.assertEqual(row.user_id, self.mod.id)
        self.assertEqual(row.metadata["changes"]["is_pinned"], True)
        self.assertEqual(row.metadata["thread_id"], str(self.thread.id))

    def test_soft_deleting_someone_elses_thread_is_recorded(self):
        resp = self.client.delete(self._url())
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self._mod_rows().first().metadata["changes"]["is_deleted"], True)

    def test_an_author_editing_their_own_thread_is_not_moderation(self):
        """Logging ordinary edits would bury the rows that matter."""
        self.client.force_authenticate(user=self.author)
        self.client.patch(self._url(), {"title": "Updated"}, format="json")
        self.assertFalse(self._mod_rows().exists())

    def test_an_author_deleting_their_own_thread_is_not_moderation(self):
        self.client.force_authenticate(user=self.author)
        self.client.delete(self._url())
        self.assertFalse(self._mod_rows().exists())

    def test_a_no_op_change_is_not_recorded(self):
        """Re-sending the current value is not a moderation event."""
        self.client.patch(self._url(), {"is_locked": False}, format="json")
        self.assertFalse(self._mod_rows().exists())

    def test_the_action_survives_the_security_log_sweep(self):
        """`admin_action` is outside _SECURITY_CLEAR_ACTIONS on purpose — a record
        deleted by an unrelated cleanup reads as 'nothing happened'."""
        self.client.patch(self._url(), {"is_locked": True}, format="json")
        self.assertEqual(self._mod_rows().first().action, "admin_action")
