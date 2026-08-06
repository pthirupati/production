"""Granting interview access must record who did it and for whom.

Audit Z1-15 covered the billing admin's bulk actions; this is the same class of
change on a different surface. `AdminInterviewEntitlementView` grants a **10-year
premium entitlement with 999 interviews** — the single most valuable thing an
operator can hand out here — and it left no record at all.

The failure-path test earns its place: the helper logs when auditing fails, and
`logger` was not defined in that module. `manage.py check` passed, because the name
is only resolved at runtime inside the `except` block. So the error handler itself
would have raised `NameError` — a bug that fires only when something has already
gone wrong, which is the worst place to put one. Nothing but exercising that branch
would have found it.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.interviews.models import InterviewEntitlement, InterviewPlanTier

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="entadmin", email="entadmin@example.com",
            password="Str0ng-Pass-1", is_staff=True, is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="grantee", email="grantee@example.com", password="Str0ng-Pass-1"
        )
        InterviewPlanTier.objects.get_or_create(
            code="premium", defaults={"name": "Premium", "is_active": True}
        )
        InterviewPlanTier.objects.get_or_create(
            code="pro", defaults={"name": "Pro", "is_active": True}
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        # Real route (found by grep, not guessed): apps/adminpanel/urls.py:210 under
        # the /api/admin/ prefix. The view identifies the target by EMAIL in the body,
        # not by a URL id.
        self.url = "/api/admin/interviews/entitlements/"

    def _audit_rows(self):
        return AuditLog.objects.filter(
            metadata__target_user_id=self.target.id
        )


class GrantsAreAuditedTests(_Base):
    def _grant_free(self):
        return self.client.post(
            self.url, {"email": self.target.email, "grant_free": True}, format="json"
        )

    def test_ten_year_grant_is_recorded(self):
        resp = self._grant_free()
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test would otherwise pass by "
            "skipping, which is how six vacuous tests got written here first",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            self._audit_rows().exists(),
            "a 10-year premium entitlement was granted with no audit record",
        )

    def test_the_record_names_the_operator(self):
        resp = self._grant_free()
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test would otherwise pass by "
            "skipping, which is how six vacuous tests got written here first",
        )
        row = self._audit_rows().first()
        self.assertEqual(
            row.user_id, self.admin.id,
            "the audit row does not say who granted the access",
        )

    def test_the_record_names_the_recipient_and_the_value(self):
        resp = self._grant_free()
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test would otherwise pass by "
            "skipping, which is how six vacuous tests got written here first",
        )
        meta = self._audit_rows().first().metadata
        self.assertEqual(meta["target_email"], "grantee@example.com")
        self.assertEqual(meta["event"], "interview_grant_free")
        self.assertEqual(meta["plan"], "premium")
        self.assertIn("interviews_remaining", meta)
        self.assertIn("period_end", meta)

    def test_plan_activation_is_also_recorded(self):
        resp = self.client.post(
            self.url, {"email": self.target.email, "plan_code": "pro"}, format="json"
        )
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test would otherwise pass by "
            "skipping, which is how six vacuous tests got written here first",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        row = self._audit_rows().filter(
            metadata__event="interview_plan_activated"
        ).first()
        self.assertIsNotNone(row, "activating a paid plan left no record")
        self.assertEqual(row.metadata["plan"], "pro")

    def test_the_grant_itself_still_happens(self):
        resp = self._grant_free()
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test would otherwise pass by "
            "skipping, which is how six vacuous tests got written here first",
        )
        ent = InterviewEntitlement.objects.get(user=self.target)
        self.assertTrue(ent.is_active)
        self.assertTrue(ent.is_complimentary)


class AuditFailureIsSurvivableTests(_Base):
    """The helper is best-effort: support must stay able to act on a live problem.

    This is also the branch that caught an undefined `logger` in the module —
    referenced only inside `except`, so it passed every static check and would have
    raised NameError the first time auditing genuinely failed.
    """

    def test_a_failing_audit_does_not_break_the_grant(self):
        with mock.patch(
            "apps.audit.models.AuditLog.objects.create",
            side_effect=RuntimeError("audit table gone"),
        ):
            resp = self.client.post(
            self.url, {"email": self.target.email, "grant_free": True}, format="json"
        )
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test would otherwise pass by "
            "skipping, which is how six vacuous tests got written here first",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(InterviewEntitlement.objects.filter(user=self.target).exists())

    def test_a_failing_audit_logs_rather_than_raising(self):
        from apps.interviews import admin_views

        with mock.patch(
            "apps.audit.models.AuditLog.objects.create",
            side_effect=RuntimeError("audit table gone"),
        ), self.assertLogs(admin_views.logger, level="ERROR") as captured:
            admin_views._audit_entitlement_grant(
                mock.Mock(user=self.admin), self.target,
                event="interview_grant_free", detail={},
            )
        self.assertTrue(
            any("NOT audited" in line for line in captured.output),
            "the failure path did not report the missing audit record",
        )
