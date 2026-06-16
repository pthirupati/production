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
from django.utils import timezone

logger = logging.getLogger(__name__)

STUCK_TRANSACTION_TIMEOUT_MINUTES = 30


@shared_task(
    name="billing.fail_stuck_payment_transactions",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def fail_stuck_payment_transactions(self):
    """
    Find PaymentTransactions stuck in 'processing' for > 30 minutes
    and mark them as failed.

    Schedule this via Celery Beat every 15 minutes.
    """
    from .models import PaymentTransaction

    cutoff = timezone.now() - timedelta(minutes=STUCK_TRANSACTION_TIMEOUT_MINUTES)
    stuck = PaymentTransaction.objects.filter(
        status="processing",
        updated_at__lt=cutoff,
    )
    count = stuck.count()
    if count == 0:
        return "No stuck transactions found."

    for tx in stuck.iterator():
        try:
            tx.mark_failed(
                f"Auto-failed after {STUCK_TRANSACTION_TIMEOUT_MINUTES} minutes in processing state"
            )
            logger.warning(
                "Auto-failed stuck transaction %s (user=%s, amount=%s %s, order=%s)",
                tx.id, tx.user_id, tx.amount, tx.currency, tx.gateway_order_id,
            )
        except Exception as exc:
            logger.error("Error auto-failing transaction %s: %s", tx.id, exc)

    return f"Auto-failed {count} stuck transaction(s)."


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
