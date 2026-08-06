"""Audit Z1-13 — the three GST defects that sat *outside* `gst.py`.

`gst.py` itself was already correct: tax-inclusive Decimal math, exact CGST/SGST
splitting, IGST when the states differ. The defects were in everything around it.

1. **Place of supply was never passed.** All five order-creation paths called
   `compute_gst(amount)` with no customer state, so the seller's state was assumed
   and *every* Indian sale booked intra-state CGST+SGST. There was also nowhere to
   put a customer state — no field existed — so the argument could not have been
   passed even by a caller who wanted to. The tests below pin the resolver
   (`place_of_supply_for`) rather than each call site, because the failure that
   matters is a *future* checkout path forgetting again; one resolver is the thing
   that makes forgetting hard.

2. **Foreign currency was taxed as a domestic supply.** A USD Stripe charge went
   through the same intra-state path. Export of services is zero-rated, and GST
   wrongly charged on a card payment cannot be recovered from the customer
   afterwards.

3. **Invoice numbers were not a series.** `INV-{today}-{8 hex of the row UUID}` is
   random and 21 characters; CGST Rule 46(b) requires a *consecutive* serial,
   unique per financial year, at most 16 characters. Random satisfies uniqueness
   and nothing else, and the gap is invisible until an audit asks for invoices 7
   through 12.

The concurrency test is the load-bearing one for (3): the obvious implementation
(`max(...) + 1`) hands the same number to two simultaneous payments, and a
*duplicate* invoice number is worse than a gap — it makes two different sales
indistinguishable in the books.
"""
import pathlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from unittest import skipIf
from django.test import TestCase, TransactionTestCase, override_settings

from apps.accounts.models import Profile
from apps.billing.gst import INDIAN_STATES, compute_gst, place_of_supply_for
from apps.billing.models import InvoiceSeries, PaymentTransaction
from apps.billing.invoice_service import create_invoice_for_transaction

User = get_user_model()

GST_ON = dict(
    GST_ENABLED=True,
    GST_RATE=Decimal("0.18"),
    BUSINESS_GSTIN="29ABCDE1234F1Z5",
    BUSINESS_STATE="Karnataka",
)


class PlaceOfSupplyResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pos", email="pos@example.com", password="Str0ng-Pass-1"
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)

    def test_a_stored_state_is_returned(self):
        self.profile.billing_state = "Maharashtra"
        self.profile.save(update_fields=["billing_state"])
        self.assertEqual(place_of_supply_for(self.user), "Maharashtra")

    def test_no_stored_state_returns_empty_rather_than_guessing(self):
        """Empty is a real answer: with no address on record the B2C rules fall back
        to the supplier's location, which is what compute_gst already does."""
        self.assertEqual(place_of_supply_for(self.user), "")

    def test_a_user_with_no_profile_does_not_explode(self):
        bare = User.objects.create_user(
            username="bare", email="bare@example.com", password="Str0ng-Pass-1"
        )
        Profile.objects.filter(user=bare).delete()
        bare.refresh_from_db()
        self.assertEqual(place_of_supply_for(bare), "")

    def test_none_does_not_explode(self):
        self.assertEqual(place_of_supply_for(None), "")

    def test_whitespace_is_not_mistaken_for_a_state(self):
        """'   ' is truthy; untrimmed it would be passed as a place of supply that
        differs from the seller's state, silently flipping the sale to IGST."""
        self.profile.billing_state = "   "
        self.profile.save(update_fields=["billing_state"])
        self.assertEqual(place_of_supply_for(self.user), "")


@override_settings(**GST_ON)
class TheResolverActuallyChangesTheTaxTests(TestCase):
    """Wiring a resolver that made no difference to the numbers would be theatre."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tax", email="tax@example.com", password="Str0ng-Pass-1"
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)

    def test_an_out_of_state_customer_is_billed_igst(self):
        self.profile.billing_state = "Maharashtra"
        self.profile.save(update_fields=["billing_state"])
        b = compute_gst(1180, place_of_supply=place_of_supply_for(self.user))
        self.assertTrue(b.is_inter_state)
        self.assertEqual(b.igst_amount, Decimal("180.00"))
        self.assertEqual(b.cgst_amount + b.sgst_amount, Decimal("0.00"))

    def test_an_in_state_customer_is_billed_cgst_sgst(self):
        self.profile.billing_state = "Karnataka"
        self.profile.save(update_fields=["billing_state"])
        b = compute_gst(1180, place_of_supply=place_of_supply_for(self.user))
        self.assertFalse(b.is_inter_state)
        self.assertEqual(b.cgst_amount, Decimal("90.00"))
        self.assertEqual(b.sgst_amount, Decimal("90.00"))

    def test_the_customer_never_pays_more_either_way(self):
        """Tax-inclusive pricing: the split changes, the sticker price does not."""
        for state in ("Karnataka", "Maharashtra", ""):
            self.profile.billing_state = state
            self.profile.save(update_fields=["billing_state"])
            b = compute_gst(1180, place_of_supply=place_of_supply_for(self.user))
            self.assertEqual(b.total_amount, Decimal("1180.00"), state)
            self.assertEqual(b.taxable_amount + b.gst_amount, b.total_amount, state)


@override_settings(**GST_ON)
class ExportsAreZeroRatedTests(TestCase):
    def test_a_usd_charge_carries_no_gst(self):
        b = compute_gst(100, currency="USD")
        self.assertEqual(b.gst_amount, Decimal("0.00"))
        self.assertEqual(b.cgst_amount + b.sgst_amount + b.igst_amount, Decimal("0.00"))

    def test_a_usd_charge_is_not_reduced(self):
        """Zero-rating must not quietly change what the customer is billed."""
        b = compute_gst(100, currency="USD")
        self.assertEqual(b.total_amount, Decimal("100.00"))
        self.assertEqual(b.taxable_amount, Decimal("100.00"))

    def test_an_export_is_distinguishable_from_an_unregistered_sale(self):
        """Both are zero-tax and look identical in the numbers; they mean completely
        different things to an auditor, so the reason is recorded."""
        export = compute_gst(100, currency="USD")
        self.assertTrue(export.is_export)
        domestic = compute_gst(1180, currency="INR")
        self.assertFalse(domestic.is_export)
        self.assertGreater(domestic.gst_amount, 0)

    def test_currency_case_does_not_matter(self):
        self.assertTrue(compute_gst(100, currency="usd").is_export)

    def test_an_inr_charge_is_still_taxed(self):
        """Guard the guard: if the export branch caught everything, every test in
        this file about CGST/IGST would pass while all tax silently vanished."""
        self.assertGreater(compute_gst(1180, currency="INR").gst_amount, 0)


class FinancialYearTests(TestCase):
    """The Indian FY runs April–March. Keying the series on the calendar year would
    reset the numbering three months into every year."""

    def test_april_starts_the_new_year(self):
        self.assertEqual(
            InvoiceSeries.financial_year_for(datetime(2026, 4, 1, tzinfo=dt_timezone.utc)),
            "26-27",
        )

    def test_march_is_still_the_previous_year(self):
        self.assertEqual(
            InvoiceSeries.financial_year_for(datetime(2026, 3, 31, tzinfo=dt_timezone.utc)),
            "25-26",
        )

    def test_january_is_the_previous_year(self):
        self.assertEqual(
            InvoiceSeries.financial_year_for(datetime(2027, 1, 15, tzinfo=dt_timezone.utc)),
            "26-27",
        )

    def test_a_century_boundary_stays_two_digits(self):
        self.assertEqual(
            InvoiceSeries.financial_year_for(datetime(2099, 6, 1, tzinfo=dt_timezone.utc)),
            "99-00",
        )


class InvoiceSeriesTests(TestCase):
    def test_numbers_are_consecutive(self):
        got = [InvoiceSeries.allocate() for _ in range(5)]
        tails = [int(n.rsplit("/", 1)[1]) for n in got]
        self.assertEqual(tails, [1, 2, 3, 4, 5], f"not a consecutive series: {got}")

    def test_the_number_fits_the_legal_ceiling(self):
        """CGST Rule 46(b): at most 16 characters. The old form was 21."""
        n = InvoiceSeries.allocate()
        self.assertLessEqual(len(n), 16, f"{n!r} is {len(n)} chars, over the 16 limit")

    def test_the_number_carries_the_financial_year(self):
        n = InvoiceSeries.allocate(moment=datetime(2026, 5, 1, tzinfo=dt_timezone.utc))
        self.assertEqual(n, "FL/26-27/000001")

    def test_each_financial_year_restarts_at_one(self):
        InvoiceSeries.allocate(moment=datetime(2026, 5, 1, tzinfo=dt_timezone.utc))
        InvoiceSeries.allocate(moment=datetime(2026, 5, 2, tzinfo=dt_timezone.utc))
        nxt = InvoiceSeries.allocate(moment=datetime(2027, 5, 1, tzinfo=dt_timezone.utc))
        self.assertEqual(nxt, "FL/27-28/000001")

    def test_the_two_series_do_not_interfere(self):
        InvoiceSeries.allocate(moment=datetime(2027, 5, 1, tzinfo=dt_timezone.utc))
        back = InvoiceSeries.allocate(moment=datetime(2026, 5, 1, tzinfo=dt_timezone.utc))
        self.assertEqual(back, "FL/26-27/000001")


@skipIf(
    connection.vendor == "sqlite",
    "SQLite takes a whole-table write lock and has no row locking, so concurrent "
    "writers here surface as 'database table is locked' rather than as the "
    "correctness question being asked. config/test_settings.py already routes CI "
    "to the Postgres service container for exactly this reason, so this test does "
    "run for real where it matters — it is skipped only on a local SQLite run.",
)
class InvoiceSeriesConcurrencyTests(TransactionTestCase):
    """`max(existing) + 1` passes every test above and still hands two simultaneous
    payments the same number. A duplicate is worse than a gap: two different sales
    become indistinguishable in the books."""

    def test_parallel_allocation_never_repeats_a_number(self):
        def _alloc(_):
            try:
                return InvoiceSeries.allocate()
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(_alloc, range(24)))

        self.assertEqual(
            len(set(numbers)), len(numbers),
            f"duplicate invoice numbers issued under concurrency: "
            f"{sorted(n for n in numbers if numbers.count(n) > 1)}",
        )
        tails = sorted(int(n.rsplit("/", 1)[1]) for n in numbers)
        self.assertEqual(
            tails, list(range(1, len(numbers) + 1)),
            "the series has gaps after concurrent allocation",
        )


class InvoiceGenerationUsesTheSeriesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="inv", email="inv@example.com", password="Str0ng-Pass-1"
        )

    def _txn(self, key):
        return PaymentTransaction.objects.create(
            user=self.user, amount=Decimal("499.00"),
            taxable_amount=Decimal("499.00"), currency="INR",
            payment_method="razorpay", status="success", idempotency_key=key,
        )

    def test_a_generated_invoice_uses_the_series(self):
        inv = create_invoice_for_transaction(self._txn("series-1"))
        self.assertRegex(
            inv.invoice_number, r"^FL/\d\d-\d\d/\d{6}$",
            "the invoice still uses the old random number format",
        )

    def test_consecutive_sales_get_consecutive_invoices(self):
        a = create_invoice_for_transaction(self._txn("series-a"))
        b = create_invoice_for_transaction(self._txn("series-b"))
        self.assertEqual(
            int(b.invoice_number.rsplit("/", 1)[1]),
            int(a.invoice_number.rsplit("/", 1)[1]) + 1,
        )

    def test_regenerating_for_the_same_payment_does_not_burn_a_number(self):
        """`create_invoice_for_transaction` is idempotent; if it allocated first and
        checked afterwards, every retry would leave a hole in the series."""
        txn = self._txn("series-idem")
        first = create_invoice_for_transaction(txn)
        again = create_invoice_for_transaction(txn)
        self.assertEqual(first.invoice_number, again.invoice_number)
        self.assertEqual(
            InvoiceSeries.objects.get(prefix="FL").last_number, 1,
            "a repeat invoice request consumed a serial number",
        )


class StateListTests(TestCase):
    def test_the_seller_state_is_in_the_list(self):
        """If BUSINESS_STATE were spelled differently from the list the profile
        validates against, every in-state customer would be billed IGST."""
        self.assertIn("Karnataka", INDIAN_STATES)

    def test_the_list_covers_all_states_and_union_territories(self):
        self.assertEqual(
            len(INDIAN_STATES), 36,
            "expected 28 states + 8 union territories",
        )

    def test_there_are_no_duplicates(self):
        self.assertEqual(len(set(INDIAN_STATES)), len(INDIAN_STATES))

    def test_the_frontend_list_matches_the_backend_one(self):
        """The dropdown is rendered from a JS copy while the API validates against
        this one, so drift shows up as a 400 on save for exactly the states that
        drifted — a bug nobody would find until a customer in that state tried."""
        import json
        import re

        from django.conf import settings as dj_settings

        js = (
            pathlib.Path(dj_settings.BASE_DIR).parent
            / "frontend" / "src" / "utils" / "indianStates.js"
        ).read_text()
        body = re.search(r"INDIAN_STATES = \[(.*?)\]", js, re.S)
        self.assertIsNotNone(body, "could not find INDIAN_STATES in indianStates.js")
        frontend = json.loads("[" + body.group(1).replace("'", '"').rstrip().rstrip(",") + "]")
        self.assertEqual(
            frontend, list(INDIAN_STATES),
            "the frontend state dropdown has drifted from the backend validator",
        )
