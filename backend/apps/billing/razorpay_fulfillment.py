"""Shared Razorpay payment fulfillment — verify path + webhook backup."""

from __future__ import annotations

import hashlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def technology_id_from_transaction(transaction) -> int | None:
    """Resolve technology_id from transaction metadata."""
    if transaction.tech_subscription_id:
        return transaction.tech_subscription.technology_id
    resp = transaction.gateway_response or {}
    if isinstance(resp.get("technology_id"), int):
        return resp["technology_id"]
    order = resp.get("order") or {}
    notes = order.get("notes") or {}
    raw = notes.get("technology_id")
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    raw = resp.get("technology_id")
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    return None


def create_technology_payment_transaction(*, user, amount, order, technology_id, coupon_code=""):
    """Create audit record when Razorpay order is created."""
    from .models import PaymentTransaction

    key_src = f"{user.id}-{technology_id}-{amount}-{order['id']}"
    idempotency_key = hashlib.sha256(key_src.encode()).hexdigest()
    return PaymentTransaction.objects.create(
        user=user,
        amount=amount,
        currency="INR",
        payment_method="razorpay",
        status="processing",
        idempotency_key=idempotency_key,
        gateway_order_id=order["id"],
        gateway_response={
            "order": order,
            "technology_id": technology_id,
            "coupon_code": coupon_code or "",
            "product_type": "technology",
        },
    )


def fulfill_technology_subscription(
    *,
    user,
    technology,
    amount,
    razorpay_payment_id,
    transaction=None,
    coupon_applied=None,
    payment_payload=None,
):
    """
    Activate technology subscription after verified payment.
    Idempotent — safe for verify API and webhook.
    """
    from .models import TechnologySubscription
    from .subscription_utils import activate_technology_subscription, get_or_create_technology_subscription

    existing = TechnologySubscription.objects.filter(
        user=user,
        technology=technology,
        is_active=True,
        payment_verified=True,
    ).first()
    if existing:
        if transaction and transaction.status != "success":
            transaction.tech_subscription = existing
            transaction.mark_success(
                gateway_payment_id=razorpay_payment_id,
                gateway_response=payment_payload or transaction.gateway_response,
            )
        return existing, False

    sub_id = TechnologySubscription.generate_subscription_id(technology.name, user.username)
    sub, created = get_or_create_technology_subscription(
        user,
        technology,
        defaults={
            "subscription_id": sub_id,
            "amount": amount,
            "is_active": False,
            "payment_verified": False,
        },
    )
    if not created and sub.is_active and sub.payment_verified:
        if transaction and transaction.status != "success":
            transaction.tech_subscription = sub
            transaction.mark_success(
                gateway_payment_id=razorpay_payment_id,
                gateway_response=payment_payload or transaction.gateway_response,
            )
        return sub, False
    if not sub.subscription_id:
        sub.subscription_id = sub_id
    sub.amount = amount
    activate_technology_subscription(sub, renew=True)

    if coupon_applied:
        from .coupon_service import redeem_coupon
        redeem_coupon(coupon_applied)

    if transaction:
        transaction.tech_subscription = sub
        transaction.mark_success(
            gateway_payment_id=razorpay_payment_id,
            gateway_response=payment_payload or transaction.gateway_response,
        )
        try:
            from .invoice_service import create_invoice_for_transaction
            create_invoice_for_transaction(transaction)
        except Exception as exc:
            logger.warning("Invoice creation failed for tx %s: %s", transaction.id, exc)

    send_technology_subscription_emails(user, technology, sub.subscription_id, amount)
    return sub, True


def send_technology_subscription_emails(user, technology, sub_id, amount):
    """Reuse billing view email bundle."""
    from .views import CreateRazorpayOrderView
    CreateRazorpayOrderView()._send_subscription_emails(user, technology, sub_id, amount)


def plan_code_from_transaction(transaction) -> str | None:
    resp = transaction.gateway_response or {}
    if resp.get("plan_code"):
        return str(resp["plan_code"])
    order = resp.get("order") or {}
    notes = order.get("notes") or {}
    code = notes.get("plan_code")
    return str(code) if code else None


def product_type_from_transaction(transaction) -> str | None:
    resp = transaction.gateway_response or {}
    if resp.get("product_type"):
        return str(resp["product_type"])
    if resp.get("product") == "interview":
        return "interview"
    order = resp.get("order") or {}
    notes = order.get("notes") or {}
    if notes.get("product") == "interview":
        return "interview"
    if notes.get("technology_id"):
        return "technology"
    return None


def create_interview_payment_transaction(*, user, amount, order, plan_code: str):
    from .models import PaymentTransaction

    key_src = f"{user.id}-interview-{plan_code}-{amount}-{order['id']}"
    idempotency_key = hashlib.sha256(key_src.encode()).hexdigest()
    return PaymentTransaction.objects.create(
        user=user,
        amount=amount,
        currency="INR",
        payment_method="razorpay",
        status="processing",
        idempotency_key=idempotency_key,
        gateway_order_id=order["id"],
        gateway_response={
            "order": order,
            "product": "interview",
            "product_type": "interview",
            "plan_code": plan_code,
        },
    )


def fulfill_interview_plan_payment(
    *,
    user,
    plan_code: str,
    razorpay_payment_id: str,
    transaction=None,
    payment_payload=None,
):
    """Activate interview plan after verified payment. Idempotent."""
    from django.utils import timezone
    from apps.interviews.billing_views import activate_interview_plan
    from apps.interviews.models import InterviewEntitlement, InterviewPlanTier

    tier = InterviewPlanTier.objects.filter(code=plan_code, is_active=True).first()
    if not tier:
        raise ValueError(f"Interview plan not found: {plan_code}")

    ent = InterviewEntitlement.objects.filter(user=user).select_related("plan_tier").first()
    if (
        ent
        and ent.is_active
        and ent.plan_tier
        and ent.plan_tier.code == plan_code
        and ent.period_end
        and ent.period_end > timezone.now()
        and not ent.is_complimentary
        and not ent.is_admin_granted_free
    ):
        if transaction and transaction.status != "success":
            transaction.mark_success(
                gateway_payment_id=razorpay_payment_id,
                gateway_response=payment_payload or transaction.gateway_response,
            )
        return ent, False

    ent = activate_interview_plan(user, tier)

    if transaction:
        transaction.mark_success(
            gateway_payment_id=razorpay_payment_id,
            gateway_response=payment_payload or transaction.gateway_response,
        )
        try:
            from .invoice_service import create_invoice_for_transaction
            create_invoice_for_transaction(transaction)
        except Exception as exc:
            logger.warning("Interview invoice failed for tx %s: %s", transaction.id, exc)

    send_interview_subscription_email(user, tier, ent)
    return ent, True


def send_interview_subscription_email(user, tier, ent) -> None:
    try:
        from apps.notifications.tasks import send_notification_email

        send_notification_email.delay(
            subject=f"Interview {tier.name} activated — FixitLab",
            to_email=user.email,
            template="emails/interview_subscribed.html",
            context={
                "plan_name": tier.name,
                "interviews_remaining": ent.interviews_remaining,
                "dashboard_url": f"{settings.FRONTEND_URL}/interviews",
            },
        )
    except Exception as exc:
        logger.warning("Interview subscription email failed: %s", exc)


def verify_razorpay_payment_captured(order_id: str, payment_id: str, expected_amount_inr: int) -> bool:
    """Fetch payment from Razorpay — must be captured with matching order + amount."""
    from django.conf import settings as django_settings

    if not django_settings.RAZORPAY_KEY_SECRET or not django_settings.RAZORPAY_KEY_ID:
        return getattr(django_settings, "DEMO_PAYMENT_ENABLED", False)
    try:
        import razorpay

        client = razorpay.Client(
            auth=(django_settings.RAZORPAY_KEY_ID, django_settings.RAZORPAY_KEY_SECRET)
        )
        payment = client.payment.fetch(payment_id)
        if payment.get("order_id") != order_id:
            return False
        if int(payment.get("amount", 0)) != int(expected_amount_inr) * 100:
            return False
        if payment.get("status") != "captured":
            return False
        return True
    except Exception as exc:
        logger.error("Razorpay payment fetch failed: %s", exc)
        return False

