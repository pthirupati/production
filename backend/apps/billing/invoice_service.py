"""Subscription invoice generation and retrieval."""

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from .models import PaymentTransaction, SubscriptionInvoice


def _invoice_number(transaction):
    ts = timezone.now().strftime("%Y%m%d")
    short = str(transaction.id).replace("-", "")[:8].upper()
    return f"INV-{ts}-{short}"


def create_invoice_for_transaction(transaction: PaymentTransaction) -> SubscriptionInvoice | None:
    """Create a stored invoice for a successful payment (idempotent)."""
    if transaction.status != "success":
        return None

    existing = SubscriptionInvoice.objects.filter(payment_transaction=transaction).first()
    if existing:
        return existing

    sub = transaction.tech_subscription
    tech_name = ""
    subscription_id = ""
    period_end = None
    if sub:
        tech_name = sub.technology.name
        subscription_id = sub.subscription_id
        period_end = sub.expires_at
    elif transaction.plan:
        tech_name = f"{transaction.plan.name} Plan"
        subscription_id = transaction.plan.code.upper()
    elif isinstance(transaction.gateway_response, dict) and transaction.gateway_response.get("product") == "interview":
        tech_name = f"Interview {transaction.gateway_response.get('plan_code', 'plan').title()}"
        subscription_id = transaction.gateway_response.get("plan_code", "interview")

    period_start = transaction.verified_at or transaction.created_at

    # GST breakup carried from the transaction (computed server-side at order
    # creation — PRODUCTION_AUDIT FIN-01). For legacy transactions written before
    # GST fields existed, taxable_amount may be 0; fall back to (re)computing from
    # the inclusive amount so the invoice always balances.
    from .gst import compute_gst

    taxable = transaction.taxable_amount
    gst_rate = transaction.gst_rate
    gst_amount = transaction.gst_amount
    cgst = transaction.cgst_amount
    sgst = transaction.sgst_amount
    igst = transaction.igst_amount
    place_of_supply = transaction.place_of_supply
    if (taxable or 0) <= 0:
        b = compute_gst(transaction.amount, place_of_supply=place_of_supply)
        taxable, gst_rate, gst_amount = b.taxable_amount, b.gst_rate, b.gst_amount
        cgst, sgst, igst = b.cgst_amount, b.sgst_amount, b.igst_amount
        place_of_supply = b.place_of_supply

    invoice = SubscriptionInvoice.objects.create(
        invoice_number=_invoice_number(transaction),
        user=transaction.user,
        payment_transaction=transaction,
        tech_subscription=sub,
        technology_name=tech_name,
        subscription_id=subscription_id,
        amount=transaction.amount,
        taxable_amount=taxable,
        gst_rate=gst_rate,
        gst_amount=gst_amount,
        cgst_amount=cgst,
        sgst_amount=sgst,
        igst_amount=igst,
        place_of_supply=place_of_supply,
        gstin=(getattr(settings, "BUSINESS_GSTIN", "") or "").strip(),
        hsn_sac=(getattr(settings, "GST_HSN_SAC", "") or "").strip(),
        currency=transaction.currency,
        payment_method=transaction.get_payment_method_display(),
        gateway_payment_id=transaction.gateway_payment_id or "",
        period_start=period_start,
        period_end=period_end,
    )
    send_invoice_email(invoice)
    return invoice


def send_invoice_email(invoice: SubscriptionInvoice) -> None:
    """Email invoice HTML to the user."""
    try:
        from apps.notifications.tasks import send_notification_email

        user = invoice.user
        html_body = render_invoice_html(invoice)
        ctx = invoice_context(invoice)
        send_notification_email.delay(
            subject=f"FixitLab Invoice {invoice.invoice_number}",
            to_email=user.email,
            template="emails/subscription_confirmation.html",
            context={
                **ctx,
                "invoice_html": html_body,
                "message": f"Your payment invoice {invoice.invoice_number} is attached below.",
            },
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to send invoice email: %s", exc)


def backfill_invoices_for_user(user):
    """Create invoices for past successful payments missing records."""
    txs = PaymentTransaction.objects.filter(user=user, status="success").select_related(
        "tech_subscription", "tech_subscription__technology", "plan"
    )
    for tx in txs:
        if not SubscriptionInvoice.objects.filter(payment_transaction=tx).exists():
            create_invoice_for_transaction(tx)


def _money(value, currency: str) -> str:
    """Format a Decimal money value for display (₹1,234.00 for INR)."""
    from decimal import Decimal

    value = value or Decimal("0")
    if currency == "INR":
        return f"₹{value:,.2f}"
    return f"{currency} {value:,.2f}"


def invoice_context(invoice: SubscriptionInvoice) -> dict:
    user = invoice.user
    has_gst = (invoice.gst_amount or 0) > 0
    return {
        "invoice_number": invoice.invoice_number,
        "username": user.get_full_name() or user.username,
        "email": user.email,
        "invoice_date": invoice.created_at.strftime("%B %d, %Y"),
        "payment_method": invoice.payment_method,
        "technology": invoice.technology_name,
        "plan_name": "1-Year Technology Access",
        "amount": _money(invoice.amount, invoice.currency),
        # GST tax invoice breakup (PRODUCTION_AUDIT FIN-01).
        "has_gst": has_gst,
        "is_inter_state": (invoice.igst_amount or 0) > 0,
        "taxable_amount": _money(invoice.taxable_amount or invoice.amount, invoice.currency),
        "gst_amount": _money(invoice.gst_amount, invoice.currency),
        "cgst_amount": _money(invoice.cgst_amount, invoice.currency),
        "sgst_amount": _money(invoice.sgst_amount, invoice.currency),
        "igst_amount": _money(invoice.igst_amount, invoice.currency),
        "gst_rate_pct": f"{(invoice.gst_rate or 0) * 100:.0f}",
        "gst_half_rate_pct": f"{(invoice.gst_rate or 0) * 100 / 2:.1f}",
        "place_of_supply": invoice.place_of_supply or "",
        "hsn_sac": invoice.hsn_sac or "",
        "subscription_id": invoice.subscription_id,
        "billing_period": "1 Year",
        "period_start": invoice.period_start.strftime("%B %d, %Y") if invoice.period_start else "",
        "period_end": invoice.period_end.strftime("%B %d, %Y") if invoice.period_end else "",
        "business_name": getattr(settings, "BUSINESS_NAME", "FixitLab"),
        "business_address": getattr(settings, "BUSINESS_ADDRESS", ""),
        "business_gstin": invoice.gstin or getattr(settings, "BUSINESS_GSTIN", ""),
        "gateway_payment_id": invoice.gateway_payment_id,
        "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
    }


def render_invoice_html(invoice: SubscriptionInvoice) -> str:
    return render_to_string("invoices/subscription_invoice.html", invoice_context(invoice))


def invoice_list_payload(invoice: SubscriptionInvoice) -> dict:
    product_type = "technology"
    if invoice.technology_name.lower().startswith("interview"):
        product_type = "interview"
    elif invoice.payment_transaction_id:
        gw = invoice.payment_transaction.gateway_response or {}
        if isinstance(gw, dict) and gw.get("product") == "interview":
            product_type = "interview"

    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "technology": invoice.technology_name,
        "product_type": product_type,
        "subscription_id": invoice.subscription_id,
        "amount": str(invoice.amount),
        "taxable_amount": str(invoice.taxable_amount),
        "gst_rate": str(invoice.gst_rate),
        "gst_amount": str(invoice.gst_amount),
        "cgst_amount": str(invoice.cgst_amount),
        "sgst_amount": str(invoice.sgst_amount),
        "igst_amount": str(invoice.igst_amount),
        "place_of_supply": invoice.place_of_supply,
        "gstin": invoice.gstin,
        "currency": invoice.currency,
        "payment_method": invoice.payment_method,
        "created_at": invoice.created_at.isoformat(),
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
        "gateway_payment_id": invoice.gateway_payment_id,
    }
