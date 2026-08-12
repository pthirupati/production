"""Clearing the security audit trail must itself be recorded.

Audit Z2-4. The Django admin correctly forbids deleting `AuditLog` rows
(`has_delete_permission` returns False) — but the **API** exposes a `clear_all`
action that wipes every security-relevant audit row, plus failed `EmailLog` and
failed `PaymentTransaction` records, with no trace that it happened.

That undermines the rest of the audit work: admin grants of paid access are recorded
precisely so "how did this account get this?" is answerable later, and an audit log
that can be silently emptied provides the *appearance* of accountability rather than
the fact of it.

The load-bearing detail is which action the meta-row uses. `admin_action` is
deliberately **not** in `_SECURITY_CLEAR_ACTIONS`, so the record survives the very
sweep it describes. A meta-audit deleted by its own operation would be worse than
none, because the resulting gap looks like "nothing happened" instead of "the trail
was cleared here".
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="secadmin", email="secadmin@example.com",
            password="Str0ng-Pass-1", is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.url = "/api/admin/security/actions/"
        # Rows the sweep is meant to delete.
        for action in ("login_failed", "security_alert", "payment_failed"):
            AuditLog.objects.create(action=action, resource="/x", metadata={})
        # A grant record of the kind Z1-15 added — this must NOT be swept.
        AuditLog.objects.create(
            user=self.admin, action="admin_action",
            resource="/admin/billing/subscription/1",
            metadata={"event": "subscription_activate", "target_user_id": 99},
        )

    def _clear(self, action="clear_all"):
        resp = self.client.post(self.url, {"action": action}, format="json")
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test must fail on a wrong URL rather "
            "than pass silently",
        )
        return resp

    def _meta_rows(self):
        return AuditLog.objects.filter(metadata__event="security_audit_cleared")


class ClearingIsRecordedTests(_Base):
    def test_clearing_writes_a_meta_audit_row(self):
        resp = self._clear()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertTrue(
            self._meta_rows().exists(),
            "the security audit trail was wiped with no record that it happened",
        )

    def test_the_meta_row_survives_the_sweep_it_describes(self):
        """`admin_action` is outside _SECURITY_CLEAR_ACTIONS on purpose. If the
        meta-row were swept by clear_all, the gap would read as 'nothing happened'."""
        self._clear()
        self.assertEqual(
            self._meta_rows().count(), 1,
            "the meta-audit row deleted itself along with the trail",
        )

    def test_it_names_the_operator(self):
        self._clear()
        row = self._meta_rows().first()
        self.assertEqual(
            row.user_id, self.admin.id,
            "the record does not say who cleared the audit trail",
        )

    def test_it_records_what_was_cleared_and_how_much(self):
        self._clear()
        meta = self._meta_rows().first().metadata
        self.assertEqual(meta["clear_action"], "clear_all")
        self.assertGreater(
            meta["rows_deleted"], 0,
            "the record does not say how many rows were destroyed",
        )

    def test_a_targeted_clear_is_recorded_too(self):
        self._clear("clear_payment_failures")
        row = self._meta_rows().first()
        self.assertIsNotNone(row)
        self.assertEqual(row.metadata["clear_action"], "clear_payment_failures")

    def test_repeated_clears_each_leave_a_record(self):
        self._clear()
        self._clear()
        self.assertEqual(self._meta_rows().count(), 2)


class GrantRecordsSurviveTests(_Base):
    """The Z1-15 accountability trail must not be collateral damage."""

    def test_admin_grant_records_are_not_swept(self):
        self._clear()
        self.assertTrue(
            AuditLog.objects.filter(
                metadata__event="subscription_activate"
            ).exists(),
            "clear_all destroyed the record of who granted paid access",
        )

    def test_the_targeted_rows_really_were_deleted(self):
        """Guard the guard: if the sweep silently stopped working, every assertion
        above would pass while nothing was being protected."""
        self._clear()
        self.assertFalse(
            AuditLog.objects.filter(action="login_failed").exists(),
            "clear_all did not actually clear anything — these tests would be vacuous",
        )


class MetaAuditFailureIsSurvivableTests(_Base):
    """Best-effort: a bookkeeping failure must not wedge an admin action mid-flight.

    Checked because the equivalent helper elsewhere referenced an undefined `logger`
    inside its `except` block — passing every static check and raising NameError only
    once auditing genuinely failed.
    """

    def test_a_failing_meta_audit_does_not_break_the_clear(self):
        real_create = AuditLog.objects.create

        def _fail_only_meta(**kwargs):
            if (kwargs.get("metadata") or {}).get("event") == "security_audit_cleared":
                raise RuntimeError("audit table gone")
            return real_create(**kwargs)

        with mock.patch.object(
            AuditLog.objects, "create", side_effect=_fail_only_meta
        ):
            resp = self._clear()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))

    def test_a_failing_meta_audit_logs_rather_than_raising(self):
        from apps.adminpanel import views as admin_views

        real_create = AuditLog.objects.create

        def _fail_only_meta(**kwargs):
            if (kwargs.get("metadata") or {}).get("event") == "security_audit_cleared":
                raise RuntimeError("audit table gone")
            return real_create(**kwargs)

        with mock.patch.object(
            AuditLog.objects, "create", side_effect=_fail_only_meta
        ), self.assertLogs(admin_views.logger, level="ERROR") as captured:
            self._clear()
        self.assertTrue(
            any("meta-audit" in line.lower() for line in captured.output),
            "the failure path did not report that the deletion is unattributed",
        )
