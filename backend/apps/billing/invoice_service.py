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

    period_start = transaction.verified_at or transaction.created_at

    invoice = SubscriptionInvoice.objects.create(
        invoice_number=_invoice_number(transaction),
        user=transaction.user,
        payment_transaction=transaction,
        tech_subscription=sub,
        technology_name=tech_name,
        subscription_id=subscription_id,
        amount=transaction.amount,
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


def invoice_context(invoice: SubscriptionInvoice) -> dict:
    user = invoice.user
    return {
        "invoice_number": invoice.invoice_number,
        "username": user.get_full_name() or user.username,
        "email": user.email,
        "invoice_date": invoice.created_at.strftime("%B %d, %Y"),
        "payment_method": invoice.payment_method,
        "technology": invoice.technology_name,
        "plan_name": "1-Year Technology Access",
        "amount": f"₹{int(invoice.amount)}" if invoice.currency == "INR" else f"{invoice.currency} {invoice.amount}",
        "subscription_id": invoice.subscription_id,
        "billing_period": "1 Year",
        "period_start": invoice.period_start.strftime("%B %d, %Y") if invoice.period_start else "",
        "period_end": invoice.period_end.strftime("%B %d, %Y") if invoice.period_end else "",
        "business_name": getattr(settings, "BUSINESS_NAME", "FixitLab"),
        "business_address": getattr(settings, "BUSINESS_ADDRESS", ""),
        "business_gstin": getattr(settings, "BUSINESS_GSTIN", ""),
        "gateway_payment_id": invoice.gateway_payment_id,
        "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
    }


def render_invoice_html(invoice: SubscriptionInvoice) -> str:
    return render_to_string("invoices/subscription_invoice.html", invoice_context(invoice))


def invoice_list_payload(invoice: SubscriptionInvoice) -> dict:
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "technology": invoice.technology_name,
        "subscription_id": invoice.subscription_id,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "payment_method": invoice.payment_method,
        "created_at": invoice.created_at.isoformat(),
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
        "gateway_payment_id": invoice.gateway_payment_id,
    }
