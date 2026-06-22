"""
Billing Celery tasks.

Tasks:
- fail_stuck_payment_transactions — auto-fail transactions stuck in
  'processing' for more than 30 minutes (e.g. user closed browser before
  verify call returned).
- retry_invoice_creation — retry invoice generation for successful
  transactions that have no invoice record.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# PRODUCTION_AUDIT REL-06: async methods (UPI/netbanking) can complete LONG after
# the user leaves the page, and the capture webhook may be delayed. Failing after
# 30 min could mark a genuinely PAID transaction as failed. We (a) only auto-fail
# after a window well beyond Razorpay's webhook SLA, and (b) never fail a
# transaction whose payment the gateway reports as captured/authorized — those are
# reconciled (captured → fulfil; authorized → leave processing) instead.
STUCK_TRANSACTION_TIMEOUT_MINUTES = 6 * 60  # 6 hours


def _reconcile_or_fail_one(tx) -> str:
    """Reconcile a single stuck transaction against the gateway.

    Returns one of: ``"captured"``, ``"authorized"``, ``"failed"``, ``"skipped"``.
    A transaction is marked failed ONLY on a definitive gateway failure (or when
    the gateway has no payment at all for the order). A captured payment is
    fulfilled; an authorized/pending payment is left in ``processing`` for the
    webhook to finish.
    """
    from .razorpay_fulfillment import verify_razorpay_payment_captured

    order_id = tx.gateway_order_id or ""
    # Razorpay is the only async gateway here. If keys aren't configured we can't
    # reconcile, so be conservative and DO NOT fail — leave it for manual review.
    if tx.payment_method != "razorpay" or not order_id:
        return "skipped"
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        logger.warning(
            "Cannot reconcile tx %s — Razorpay keys not configured; leaving in processing",
            tx.id,
        )
        return "skipped"

    try:
        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        payments = client.order.payments(order_id)
        items = (payments or {}).get("items") or []
    except Exception as exc:
        # Gateway error — never fail on uncertainty; retry next run.
        logger.warning("Reconcile fetch failed for tx %s (order=%s): %s", tx.id, order_id, exc)
        return "skipped"

    if not items:
        # No payment attempt at all against this order after the long window →
        # the user genuinely abandoned checkout. Safe to fail.
        tx.mark_failed("Auto-failed: no payment attempt found for order after timeout")
        logger.info("Auto-failed abandoned tx %s (order=%s, no payments)", tx.id, order_id)
        return "failed"

    statuses = {p.get("status") for p in items}
    # Find a captured payment to fulfil.
    captured = next((p for p in items if p.get("status") == "captured"), None)
    if captured:
        payment_id = captured.get("id", "")
        expected_inr = int(tx.amount)
        if verify_razorpay_payment_captured(order_id, payment_id, expected_inr):
            from .payment_service import PaymentService

            # Merge (don't overwrite) so the order metadata needed to resolve the
            # product to fulfil is preserved — see payment_controller capture.
            merged = tx.gateway_response if isinstance(tx.gateway_response, dict) else {}
            merged = {**merged, "payment": captured}
            tx.mark_success(gateway_payment_id=payment_id, gateway_response=merged)
            svc = PaymentService(user=tx.user, amount=tx.amount, currency=tx.currency, payment_method="razorpay")
            svc.transaction = tx
            svc._activate_subscription(tx)
            logger.warning(
                "Reconciled tx %s: payment %s was CAPTURED — fulfilled (was stuck in processing)",
                tx.id, payment_id,
            )
            return "captured"
        logger.warning("Captured payment %s failed re-verification for tx %s — leaving processing", payment_id, tx.id)
        return "skipped"

    if "authorized" in statuses:
        # Money is held but not captured — do NOT fail; webhook/capture will resolve it.
        return "authorized"

    # Every payment against this order is in a definitive non-success state.
    if statuses and statuses.issubset({"failed"}):
        tx.mark_failed("Auto-failed: gateway reports payment failed")
        logger.info("Auto-failed tx %s — gateway payment(s) failed (order=%s)", tx.id, order_id)
        return "failed"

    # created/pending or anything ambiguous → leave for next run.
    return "skipped"


@shared_task(
    name="billing.fail_stuck_payment_transactions",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def fail_stuck_payment_transactions(self):
    """
    Reconcile PaymentTransactions stuck in 'processing' beyond the timeout window
    against the gateway, and mark as failed ONLY those with a definitive gateway
    failure / no payment attempt (PRODUCTION_AUDIT REL-06).

    Schedule this via Celery Beat (e.g. every 15-30 minutes).
    """
    from .models import PaymentTransaction

    cutoff = timezone.now() - timedelta(minutes=STUCK_TRANSACTION_TIMEOUT_MINUTES)
    stuck = PaymentTransaction.objects.filter(
        status="processing",
        updated_at__lt=cutoff,
    ).select_related("user")
    total = stuck.count()
    if total == 0:
        return "No stuck transactions found."

    failed = captured = left = 0
    for tx in stuck.iterator():
        try:
            result = _reconcile_or_fail_one(tx)
            if result == "failed":
                failed += 1
            elif result == "captured":
                captured += 1
            else:
                left += 1
        except Exception as exc:
            logger.error("Error reconciling transaction %s: %s", tx.id, exc)
            left += 1

    return (
        f"Reconciled {total} stuck transaction(s): "
        f"{failed} failed, {captured} captured/fulfilled, {left} left in processing."
    )


@shared_task(
    name="billing.retry_invoice_creation",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 5},
)
def retry_invoice_creation(self, transaction_id: str):
    """
    Retry invoice creation for a specific successful transaction that
    failed to produce an invoice record (e.g. due to a DB/template error).

    Called with a 60-second delay from _activate_subscription on invoice failure.
    """
    from .models import PaymentTransaction, SubscriptionInvoice
    from .invoice_service import create_invoice_for_transaction

    try:
        tx = PaymentTransaction.objects.select_related(
            "tech_subscription", "tech_subscription__technology", "plan"
        ).get(id=transaction_id)
    except PaymentTransaction.DoesNotExist:
        logger.warning("retry_invoice_creation: transaction %s not found", transaction_id)
        return

    if tx.status != "success":
        logger.info(
            "retry_invoice_creation: skipping tx %s with status %s",
            transaction_id, tx.status,
        )
        return

    if SubscriptionInvoice.objects.filter(payment_transaction=tx).exists():
        logger.info(
            "retry_invoice_creation: invoice already exists for tx %s", transaction_id
        )
        return

    invoice = create_invoice_for_transaction(tx)
    if invoice:
        logger.info(
            "retry_invoice_creation: created invoice %s for tx %s",
            invoice.invoice_number, transaction_id,
        )
    else:
        raise RuntimeError(
            f"create_invoice_for_transaction returned None for tx {transaction_id}"
        )
