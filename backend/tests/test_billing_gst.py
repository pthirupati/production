"""GST computation + invoice rendering tests (PRODUCTION_AUDIT FIN-01).

Verifies:
  * GST is computed server-side, tax-INCLUSIVE (total unchanged), and the
    breakup balances (taxable + tax == total; cgst + sgst == tax).
  * GST is gated on GST_ENABLED *and* a configured BUSINESS_GSTIN.
  * The Razorpay order amount equals the GST-inclusive total (paise).
  * The breakup is persisted on the transaction at order-creation and rendered
    on the invoice (CGST/SGST intra-state, IGST inter-state, GSTIN shown).
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.billing.gst import compute_gst, gst_should_charge
from apps.billing.models import PaymentTransaction, SubscriptionInvoice
from apps.question_bank.models import Technology

User = get_user_model()

GST_ON = dict(
    GST_ENABLED=True,
    GST_RATE=Decimal("0.18"),
    BUSINESS_GSTIN="29ABCDE1234F1Z5",
    BUSINESS_STATE="Karnataka",
)


class GstComputeTest(TestCase):
    @override_settings(**GST_ON)
    def test_inclusive_breakup_balances(self):
        b = compute_gst(1180)
        # Tax-inclusive: total unchanged, taxable + tax == total.
        self.assertEqual(b.total_amount, Decimal("1180.00"))
        self.assertEqual(b.taxable_amount, Decimal("1000.00"))
        self.assertEqual(b.gst_amount, Decimal("180.00"))
        self.assertEqual(b.taxable_amount + b.gst_amount, b.total_amount)
        # Intra-state split is exact.
        self.assertEqual(b.cgst_amount, Decimal("90.00"))
        self.assertEqual(b.sgst_amount, Decimal("90.00"))
        self.assertEqual(b.cgst_amount + b.sgst_amount, b.gst_amount)
        self.assertEqual(b.igst_amount, Decimal("0.00"))
        self.assertFalse(b.is_inter_state)

    @override_settings(**GST_ON)
    def test_order_amount_equals_inclusive_total_paise(self):
        # The price the user pays (₹499) is the GST-inclusive total; the Razorpay
        # order must be created for exactly that many paise.
        b = compute_gst(499)
        self.assertEqual(b.total_amount, Decimal("499.00"))
        self.assertEqual(b.total_paise, 49900)
        # And it still balances at an odd amount.
        self.assertEqual(b.taxable_amount + b.gst_amount, Decimal("499.00"))

    @override_settings(**GST_ON)
    def test_inter_state_uses_igst(self):
        b = compute_gst(1180, place_of_supply="Maharashtra")
        self.assertTrue(b.is_inter_state)
        self.assertEqual(b.igst_amount, Decimal("180.00"))
        self.assertEqual(b.cgst_amount, Decimal("0.00"))
        self.assertEqual(b.sgst_amount, Decimal("0.00"))
        self.assertEqual(b.place_of_supply, "Maharashtra")

    @override_settings(GST_ENABLED=False, BUSINESS_GSTIN="29ABCDE1234F1Z5", GST_RATE=Decimal("0.18"))
    def test_disabled_when_flag_off(self):
        self.assertFalse(gst_should_charge())
        b = compute_gst(1000)
        self.assertEqual(b.gst_amount, Decimal("0.00"))
        self.assertEqual(b.taxable_amount, Decimal("1000.00"))
        self.assertEqual(b.total_amount, Decimal("1000.00"))

    @override_settings(GST_ENABLED=True, BUSINESS_GSTIN="", GST_RATE=Decimal("0.18"))
    def test_disabled_without_gstin(self):
        # GST_ENABLED but no registration → no tax charged (safe pre-registration).
        self.assertFalse(gst_should_charge())
        b = compute_gst(1000)
        self.assertEqual(b.gst_amount, Decimal("0.00"))


@override_settings(
    RAZORPAY_KEY_ID="rzp_test",
    RAZORPAY_KEY_SECRET="test_secret",
    ROOT_URLCONF="config.urls",
    SECURE_SSL_REDIRECT=False,
    **GST_ON,
)
class GstOrderAndInvoiceTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="gstuser", email="gst@test.com", password="Pass123!x",
        )
        self.client.force_authenticate(user=self.user)
        self.tech = Technology.objects.create(
            name="Kubernetes", icon="k8s", price=1180, is_active=True,
        )

    def test_order_creates_transaction_with_gst_and_inclusive_amount(self):
        fake_order = {"id": "order_gst_1", "amount": 118000, "currency": "INR", "notes": {}}
        mock_client = MagicMock()
        mock_client.order.create.return_value = fake_order

        with patch("razorpay.Client", return_value=mock_client):
            resp = self.client.post(
                "/api/billing/razorpay/order/",
                data={"technology_id": self.tech.id},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200, resp.content)

        # The Razorpay order must be created for the GST-inclusive total in paise.
        _, kwargs = mock_client.order.create.call_args
        order_amount_paise = kwargs["data"]["amount"]
        self.assertEqual(order_amount_paise, 118000)  # ₹1180 * 100

        tx = PaymentTransaction.objects.get(gateway_order_id="order_gst_1")
        self.assertEqual(tx.amount, Decimal("1180.00"))
        self.assertEqual(tx.taxable_amount, Decimal("1000.00"))
        self.assertEqual(tx.gst_amount, Decimal("180.00"))
        self.assertEqual(tx.cgst_amount + tx.sgst_amount, tx.gst_amount)
        self.assertEqual(tx.gst_rate, Decimal("0.1800"))
        # Server-computed total == taxable + tax.
        self.assertEqual(tx.taxable_amount + tx.gst_amount, tx.amount)

    def test_invoice_carries_and_renders_gst_breakup(self):
        from apps.billing.gst import compute_gst
        from apps.billing.invoice_service import (
            create_invoice_for_transaction,
            render_invoice_html,
        )

        b = compute_gst(1180)
        tx = PaymentTransaction.objects.create(
            user=self.user,
            amount=b.total_amount,
            taxable_amount=b.taxable_amount,
            gst_rate=b.gst_rate,
            gst_amount=b.gst_amount,
            cgst_amount=b.cgst_amount,
            sgst_amount=b.sgst_amount,
            igst_amount=b.igst_amount,
            place_of_supply=b.place_of_supply,
            currency="INR",
            payment_method="razorpay",
            status="success",
            idempotency_key="gst-inv-key-1",
            gateway_order_id="order_gst_inv",
            gateway_payment_id="pay_gst_inv",
        )
        invoice = create_invoice_for_transaction(tx)
        self.assertIsNotNone(invoice)
        # Breakup copied onto the invoice + business GSTIN stamped.
        self.assertEqual(invoice.taxable_amount, Decimal("1000.00"))
        self.assertEqual(invoice.gst_amount, Decimal("180.00"))
        self.assertEqual(invoice.cgst_amount, Decimal("90.00"))
        self.assertEqual(invoice.sgst_amount, Decimal("90.00"))
        self.assertEqual(invoice.gstin, "29ABCDE1234F1Z5")

        html = render_invoice_html(invoice)
        self.assertIn("CGST", html)
        self.assertIn("SGST", html)
        self.assertIn("29ABCDE1234F1Z5", html)  # GSTIN on the tax invoice
        self.assertIn("Taxable value", html)

    @override_settings(GST_ENABLED=False)
    def test_invoice_without_gst_shows_subtotal_only(self):
        from apps.billing.gst import compute_gst
        from apps.billing.invoice_service import (
            create_invoice_for_transaction,
            render_invoice_html,
        )

        b = compute_gst(1180)  # GST off → no tax
        tx = PaymentTransaction.objects.create(
            user=self.user,
            amount=b.total_amount,
            taxable_amount=b.taxable_amount,
            gst_amount=b.gst_amount,
            gst_rate=b.gst_rate,
            currency="INR",
            payment_method="razorpay",
            status="success",
            idempotency_key="nogst-inv-key-1",
            gateway_payment_id="pay_nogst",
        )
        invoice = create_invoice_for_transaction(tx)
        self.assertEqual(invoice.gst_amount, Decimal("0.00"))
        html = render_invoice_html(invoice)
        self.assertNotIn("CGST", html)
        self.assertIn("Subtotal", html)


class GstAdminToggleTest(TestCase):
    """GST is driven by the admin PlatformSettings (DB), overriding env — so the
    owner enables GST / sets the GSTIN from the admin panel with no redeploy."""

    def _platform(self, **kw):
        from apps.adminpanel.models import PlatformSettings
        return PlatformSettings.objects.create(**kw)

    def test_db_enables_gst_without_env(self):
        # No env GST settings; enable purely via the admin singleton.
        self._platform(
            gst_enabled=True, business_gstin="29ABCDE1234F1Z5",
            business_state="Karnataka", gst_rate=Decimal("0.18"),
        )
        self.assertTrue(gst_should_charge())
        b = compute_gst(1180)
        self.assertEqual(b.taxable_amount, Decimal("1000.00"))
        self.assertEqual(b.gst_amount, Decimal("180.00"))
        self.assertEqual(b.gstin, "29ABCDE1234F1Z5")

    def test_default_admin_row_skips_gst(self):
        # No env GST and a default admin row (gst_enabled=False) → "skip GST":
        # payments still work, full amount taxable with zero tax.
        self._platform(gst_enabled=False, business_gstin="")
        self.assertFalse(gst_should_charge())
        b = compute_gst(1180)
        self.assertEqual(b.gst_amount, Decimal("0.00"))
        self.assertEqual(b.total_amount, Decimal("1180.00"))

    def test_enabled_without_gstin_skips(self):
        # Enabled but no GSTIN → cannot legally levy → skip (safe default).
        self._platform(gst_enabled=True, business_gstin="")
        self.assertFalse(gst_should_charge())
