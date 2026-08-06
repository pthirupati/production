"""What was charged, in what currency, to whom — cannot be rewritten later.

Audit Z1-15 noted there is no immutable ledger: `PaymentTransaction` was fully
mutable, so any code path (or a support script) could silently change the amount of a
completed sale. A financial record that can be retroactively edited is a record of the
present, not of what happened.

The shape of the fix came from measuring what legitimately changes after creation:
only `status`, `gateway_order_id`, `gateway_response`, `refunded_amount` and
`error_message`. Full immutability would have been wrong — a transaction properly
moves pending → processing → success → refunded, and locking the row would break every
one of those. So the *financial facts* are frozen and the lifecycle stays open.

Known limit, stated rather than hidden: `queryset.update()` bypasses `save()`, so this
guards ordinary object writes, not deliberate bulk SQL. Closing that needs a database
trigger — a migration-level decision.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.billing.models import LedgerIntegrityError, PaymentTransaction

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ledger", email="ledger@example.com", password="Str0ng-Pass-1"
        )
        self.other = User.objects.create_user(
            username="ledger2", email="ledger2@example.com", password="Str0ng-Pass-1"
        )
        self.txn = PaymentTransaction.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            taxable_amount=Decimal("499.00"),
            currency="INR",
            payment_method="razorpay",
            status="success",
            idempotency_key="ledger-key-1",
        )


class FinancialFactsAreFrozenTests(_Base):
    def test_the_amount_cannot_be_changed(self):
        self.txn.amount = Decimal("1.00")
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save()

    def test_the_currency_cannot_be_changed(self):
        self.txn.currency = "USD"
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save()

    def test_the_payer_cannot_be_changed(self):
        """Reassigning a payment to another account would launder a refund."""
        self.txn.user = self.other
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save()

    def test_the_idempotency_key_cannot_be_changed(self):
        """It is the replay guard; rewriting it re-opens double-fulfilment."""
        self.txn.idempotency_key = "something-else"
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save()

    def test_the_tax_split_cannot_be_changed(self):
        self.txn.gst_amount = Decimal("999.00")
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save()

    def test_a_targeted_save_cannot_smuggle_a_change_through(self):
        """update_fields naming a frozen field must still be checked."""
        self.txn.amount = Decimal("1.00")
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save(update_fields=["amount"])

    def test_the_stored_value_is_unchanged_after_a_refusal(self):
        self.txn.amount = Decimal("1.00")
        with self.assertRaises(LedgerIntegrityError):
            self.txn.save()
        self.assertEqual(
            PaymentTransaction.objects.get(pk=self.txn.pk).amount, Decimal("499.00")
        )

    def test_the_error_says_what_to_do_instead(self):
        self.txn.amount = Decimal("1.00")
        with self.assertRaises(LedgerIntegrityError) as ctx:
            self.txn.save()
        self.assertIn("refund", str(ctx.exception).lower())


class TheLifecycleStillWorksTests(_Base):
    """Freezing the row entirely would have broken every real payment flow."""

    def test_status_can_advance(self):
        self.txn.status = "refunded"
        self.txn.save(update_fields=["status"])
        self.assertEqual(
            PaymentTransaction.objects.get(pk=self.txn.pk).status, "refunded"
        )

    def test_refunded_amount_can_be_recorded(self):
        self.txn.refunded_amount = Decimal("499.00")
        self.txn.status = "refunded"
        self.txn.save(update_fields=["refunded_amount", "status"])
        self.assertEqual(
            PaymentTransaction.objects.get(pk=self.txn.pk).refunded_amount,
            Decimal("499.00"),
        )

    def test_gateway_identifiers_can_be_attached_after_creation(self):
        """The order id arrives from the gateway after the row exists."""
        self.txn.gateway_order_id = "order_abc"
        self.txn.gateway_response = {"ok": True}
        self.txn.save(update_fields=["gateway_order_id", "gateway_response"])
        fresh = PaymentTransaction.objects.get(pk=self.txn.pk)
        self.assertEqual(fresh.gateway_order_id, "order_abc")

    def test_a_full_save_with_no_financial_change_is_allowed(self):
        self.txn.status = "processing"
        self.txn.save()  # no update_fields — must not raise

    def test_creating_a_transaction_is_unaffected(self):
        PaymentTransaction.objects.create(
            user=self.user, amount=Decimal("199.00"),
            taxable_amount=Decimal("199.00"), currency="INR",
            payment_method="stripe", status="pending",
            idempotency_key="ledger-key-2",
        )
        self.assertEqual(PaymentTransaction.objects.filter(user=self.user).count(), 2)


class TheGuardIsNotVacuousTests(_Base):
    """A guard that cannot fire protects nothing — this session's recurring bug."""

    def test_the_frozen_list_covers_the_money_and_the_payer(self):
        frozen = set(PaymentTransaction.FROZEN_FIELDS)
        for essential in ("amount", "currency", "user_id", "idempotency_key"):
            self.assertIn(
                essential, frozen,
                f"{essential} is not frozen — the ledger can be rewritten",
            )

    def test_lifecycle_fields_are_deliberately_not_frozen(self):
        frozen = set(PaymentTransaction.FROZEN_FIELDS)
        for mutable in ("status", "refunded_amount", "gateway_order_id"):
            self.assertNotIn(
                mutable, frozen,
                f"{mutable} is frozen — real payment flows would break",
            )
