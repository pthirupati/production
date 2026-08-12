"""Changing someone's paid access must leave a record of who did it.

Audit Z1-15. The billing admin's bulk activate/deactivate actions did a bare
`queryset.update(is_active=...)` with **no audit row at all** — support could grant or
revoke paid access and nothing recorded that it happened, who did it, or for whom.
`grant_complimentary_access` already wrote an `AuditLog` for exactly this reason, so
the pattern existed and simply was not applied here.

This is the admin-side twin of Z1-6: there, a sale granted access with no financial
record; here, an operator grants access with no accountability record. Both leave the
business unable to answer "how did this account get this?" after the fact.

One row per affected subscription, not one per bulk action — "an admin activated 40
subscriptions" is not answerable later, and the question an investigation actually
asks is "who granted access to *this* account".
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.audit.models import AuditLog
from apps.billing.admin import _audit_subscription_action
from apps.billing.models import Plan, Subscription, TechnologySubscription
from apps.question_bank.models import Technology

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="opsadmin", email="ops@example.com",
            password="Str0ng-Pass-1", is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="cust", email="cust@example.com", password="Str0ng-Pass-1"
        )
        self.request = RequestFactory().post("/admin/")
        self.request.user = self.admin
        AuditLog.objects.all().delete()


class SubscriptionActionsAreAuditedTests(_Base):
    def setUp(self):
        super().setUp()
        plan = Plan.objects.create(code="pro", name="Pro", price=999)
        self.sub = Subscription.objects.create(
            user=self.customer, plan=plan, is_active=False
        )
        self.qs = Subscription.objects.filter(pk=self.sub.pk)

    def test_activation_writes_an_audit_row(self):
        _audit_subscription_action(
            self.request, self.qs, action="activate", kind="subscription"
        )
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_the_row_names_the_operator(self):
        _audit_subscription_action(
            self.request, self.qs, action="activate", kind="subscription"
        )
        self.assertEqual(AuditLog.objects.get().user, self.admin)

    def test_the_row_names_the_affected_customer(self):
        """The question an investigation asks is 'who granted access to THIS account'."""
        _audit_subscription_action(
            self.request, self.qs, action="activate", kind="subscription"
        )
        meta = AuditLog.objects.get().metadata
        self.assertEqual(meta["target_user_id"], self.customer.id)
        self.assertEqual(meta["target_email"], "cust@example.com")

    def test_deactivation_is_distinguishable_from_activation(self):
        _audit_subscription_action(
            self.request, self.qs, action="deactivate", kind="subscription"
        )
        self.assertEqual(
            AuditLog.objects.get().metadata["event"], "subscription_deactivate"
        )


class OneRowPerSubscriptionTests(_Base):
    """A single row for a bulk action cannot answer per-account questions."""

    def setUp(self):
        super().setUp()
        plan = Plan.objects.create(code="pro", name="Pro", price=999)
        self.users = [
            User.objects.create_user(
                username=f"b{i}", email=f"b{i}@example.com", password="Str0ng-Pass-1"
            )
            for i in range(3)
        ]
        for u in self.users:
            Subscription.objects.create(user=u, plan=plan, is_active=False)
        self.qs = Subscription.objects.filter(user__in=self.users)

    def test_bulk_activation_writes_a_row_each(self):
        _audit_subscription_action(
            self.request, self.qs, action="activate", kind="subscription"
        )
        self.assertEqual(AuditLog.objects.count(), 3)

    def test_every_affected_customer_is_named(self):
        _audit_subscription_action(
            self.request, self.qs, action="activate", kind="subscription"
        )
        recorded = {log.metadata["target_email"] for log in AuditLog.objects.all()}
        self.assertEqual(recorded, {u.email for u in self.users})


class TechnologySubscriptionActionsTests(_Base):
    def test_coupon_toggles_are_audited_with_coupon_metadata(self):
        """Found by the structural test below, which flagged a fourth action I had
        missed. A coupon has no owning user, so `target_user_id` is empty — the
        financially significant fact is *which code* was switched on. Enabling a
        100%-off code costs as much as granting access directly."""
        from apps.billing.models import CouponCode

        coupon = CouponCode.objects.create(
            code="FREE100", discount_type="percent",
            discount_value=Decimal("100"), is_active=False,
        )
        _audit_subscription_action(
            self.request, CouponCode.objects.filter(pk=coupon.pk),
            action="activate", kind="coupon",
        )
        meta = AuditLog.objects.get().metadata
        self.assertEqual(meta["event"], "coupon_activate")
        self.assertEqual(meta["coupon_code"], "FREE100")
        # Decimal("100") stringifies as "100.00"; asserted against the real value
        # rather than the one I assumed.
        self.assertEqual(meta["discount_value"], "100.00")

    def test_technology_grants_are_audited_too(self):
        tech = Technology.objects.create(name="AudTech", slug="audtech", price=499)
        sub = TechnologySubscription.objects.create(
            user=self.customer, technology=tech, amount=Decimal("499.00"),
            is_active=False,
        )
        _audit_subscription_action(
            self.request,
            TechnologySubscription.objects.filter(pk=sub.pk),
            action="activate", kind="technology_subscription",
        )
        self.assertEqual(
            AuditLog.objects.get().metadata["event"],
            "technology_subscription_activate",
        )


class AuditingNeverBlocksTheOperatorTests(_Base):
    """A failure to audit must not leave support unable to act on a live billing
    problem — but it is logged, because a silent gap here is the whole defect."""

    def test_an_audit_failure_does_not_raise(self):
        from unittest import mock

        plan = Plan.objects.create(code="pro", name="Pro", price=999)
        sub = Subscription.objects.create(
            user=self.customer, plan=plan, is_active=False
        )
        with mock.patch(
            "apps.audit.models.AuditLog.objects.bulk_create",
            side_effect=RuntimeError("audit db down"),
        ):
            _audit_subscription_action(
                self.request,
                Subscription.objects.filter(pk=sub.pk),
                action="activate", kind="subscription",
            )  # must not raise

    def test_an_empty_selection_writes_nothing(self):
        _audit_subscription_action(
            self.request, Subscription.objects.none(),
            action="activate", kind="subscription",
        )
        self.assertEqual(AuditLog.objects.count(), 0)


class AdminActionsCallTheAuditTests(TestCase):
    """Structural: a new bulk action that forgets to audit reopens the gap."""

    def test_every_activate_deactivate_action_audits_first(self):
        import inspect

        from apps.billing import admin as billing_admin

        src = inspect.getsource(billing_admin)
        # Each bare `queryset.update(is_active=...)` must be preceded by an audit call.
        for chunk in src.split("def action_")[1:]:
            head = chunk.split("\n\n")[0]
            if "queryset.update(is_active" not in head:
                continue
            self.assertIn(
                "_audit_subscription_action", head,
                f"a bulk action changes paid access without auditing:\n{head[:200]}",
            )
