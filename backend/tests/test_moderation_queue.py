"""Abuse reports must reach a moderator.

ThreadReport was a well-modelled table that NOTHING read: reason choices, a status
workflow, a unique-per-reporter constraint, and a working write path — but it was
never registered in community/admin.py and has no adminpanel endpoint. `status` sat
at "open" forever. Reporting abuse did literally nothing, and moderation was "an
admin happens to scroll the recent-threads list".
"""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.community.admin import ThreadAdmin, ThreadReportAdmin
from apps.community.models import Thread, ThreadReport

User = get_user_model()


class ModerationQueueTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="poster", email="poster@example.com", password="Str0ng-Pass-1"
        )
        self.r1 = User.objects.create_user(
            username="rep1", email="rep1@example.com", password="Str0ng-Pass-1"
        )
        self.r2 = User.objects.create_user(
            username="rep2", email="rep2@example.com", password="Str0ng-Pass-1"
        )
        self.staff = User.objects.create_user(
            username="mod", email="mod@example.com", password="Str0ng-Pass-1",
            is_staff=True, is_superuser=True,
        )
        self.thread = Thread.objects.create(
            title="Suspicious post", body="buy my thing", author=self.author
        )
        self.rf = RequestFactory()

    def _request(self):
        req = self.rf.get("/admin/")
        req.user = self.staff
        return req

    def test_threadreport_is_registered(self):
        """The whole bug: the model existed and was unreachable."""
        self.assertIn(ThreadReport, admin.site._registry)

    def test_report_appears_in_the_queue(self):
        ThreadReport.objects.create(thread=self.thread, reporter=self.r1, reason="spam")
        ma = ThreadReportAdmin(ThreadReport, admin.site)
        self.assertEqual(ma.get_queryset(self._request()).count(), 1)

    def test_actions_close_a_report(self):
        rep = ThreadReport.objects.create(
            thread=self.thread, reporter=self.r1, reason="abuse"
        )
        self.assertEqual(rep.status, "open")
        ma = ThreadReportAdmin(ThreadReport, admin.site)
        req = self._request()
        # messages framework needs a session-ish request; admin actions use
        # messages.success, so attach the minimum.
        setattr(req, "session", {})
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(req, "_messages", FallbackStorage(req))

        ma.action_mark_reviewed(req, ThreadReport.objects.filter(pk=rep.pk))
        rep.refresh_from_db()
        self.assertEqual(rep.status, "reviewed")

        ma.action_dismiss(req, ThreadReport.objects.filter(pk=rep.pk))
        rep.refresh_from_db()
        self.assertEqual(rep.status, "dismissed")

    def test_thread_list_surfaces_open_report_count(self):
        """A reported thread must be visible where moderators actually look."""
        ThreadReport.objects.create(thread=self.thread, reporter=self.r1, reason="spam")
        ThreadReport.objects.create(thread=self.thread, reporter=self.r2, reason="abuse")

        ma = ThreadAdmin(Thread, admin.site)
        row = ma.get_queryset(self._request()).get(pk=self.thread.pk)
        self.assertEqual(row._open_reports, 2)
        self.assertIn("2", str(ma.open_reports(row)))

    def test_reviewed_reports_drop_out_of_the_open_count(self):
        rep = ThreadReport.objects.create(
            thread=self.thread, reporter=self.r1, reason="spam"
        )
        rep.status = "reviewed"
        rep.save(update_fields=["status"])

        ma = ThreadAdmin(Thread, admin.site)
        row = ma.get_queryset(self._request()).get(pk=self.thread.pk)
        self.assertEqual(row._open_reports, 0)
        self.assertEqual(ma.open_reports(row), "—")

    def test_report_content_is_immutable_in_admin(self):
        """A report records what a USER said; only the decision is editable."""
        ma = ThreadReportAdmin(ThreadReport, admin.site)
        for field in ("thread", "reporter", "reason", "details", "created_at"):
            self.assertIn(field, ma.readonly_fields)
        self.assertNotIn("status", ma.readonly_fields)

    def test_open_count_annotation_is_not_n_plus_one(self):
        """Annotated, not counted per row — the changelist shows 100 threads."""
        for i in range(5):
            t = Thread.objects.create(title=f"t{i}", body="x", author=self.author)
            ThreadReport.objects.create(thread=t, reporter=self.r1, reason="spam")

        ma = ThreadAdmin(Thread, admin.site)
        qs = ma.get_queryset(self._request())
        with self.assertNumQueries(1):
            list(qs.values("id", "_open_reports"))
