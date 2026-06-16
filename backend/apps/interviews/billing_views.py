"""Razorpay checkout for Interview Studio plans."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import PaymentTransaction
from apps.billing.views import BillingRateThrottle
from apps.interviews.models import InterviewEntitlement, InterviewPlanTier
from apps.interviews.services.entitlements import get_entitlement_payload

logger = logging.getLogger(__name__)

INTERVIEW_SUBSCRIPTION_DAYS = 365


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    secret = settings.RAZORPAY_KEY_SECRET
    if not secret:
        return getattr(settings, "DEMO_PAYMENT_ENABLED", False)
    try:
        message = f"{order_id}|{payment_id}"
        expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as exc:
        logger.error("Razorpay signature error: %s", exc)
        return False


def activate_interview_plan(user, tier: InterviewPlanTier) -> InterviewEntitlement:
    """Activate or renew interview plan — 1 year validity, attempt credits per tier."""
    ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
    attempts = int(tier.interviews_per_month or 10)
    if tier.code in ("pro", "premium"):
        attempts = 10
    now = timezone.now()
    ent.plan_tier = tier
    ent.is_active = True
    ent.is_complimentary = False
    ent.is_admin_granted_free = False
    ent.interviews_remaining = attempts
    ent.period_start = now
    ent.period_end = now + timedelta(days=INTERVIEW_SUBSCRIPTION_DAYS)
    ent.save()
    return ent


class CreateInterviewRazorpayOrderView(APIView):
    """POST /api/interviews/billing/razorpay/order/ { plan_code: pro|premium }"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        plan_code = (request.data.get("plan_code") or "").strip().lower()
        if plan_code not in ("pro", "premium"):
            return Response({"error": "plan_code must be pro or premium"}, status=400)

        tier = InterviewPlanTier.objects.filter(code=plan_code, is_active=True).first()
        if not tier:
            return Response({"error": "Interview plan not found"}, status=404)

        amount = int(tier.price_inr)
        if amount <= 0:
            return Response({"error": "Plan price not configured"}, status=400)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            if getattr(settings, "DEMO_PAYMENT_ENABLED", False):
                token = uuid.uuid4().hex
                return Response({
                    "demo_mode": True,
                    "payment_token": token,
                    "plan_code": plan_code,
                    "plan_name": tier.name,
                    "amount": amount,
                    "amount_paise": amount * 100,
                    "currency": "INR",
                })
            return Response(
                {"error": "Payment gateway unavailable", "code": "GATEWAY_UNAVAILABLE"},
                status=503,
            )

        amount_paise = amount * 100
        try:
            import razorpay

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order = client.order.create(
                data={
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": f"interview_{plan_code}_{request.user.id}",
                    "notes": {
                        "product": "interview",
                        "product_type": "interview",
                        "plan_code": plan_code,
                        "user_id": str(request.user.id),
                    },
                }
            )
            from apps.billing.razorpay_fulfillment import create_interview_payment_transaction

            create_interview_payment_transaction(
                user=request.user,
                amount=amount,
                order=order,
                plan_code=plan_code,
            )
            return Response({
                "order_id": order["id"],
                "amount": amount,
                "amount_paise": amount_paise,
                "currency": "INR",
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "plan_code": plan_code,
                "plan_name": tier.name,
                "user_email": request.user.email,
                "user_name": request.user.get_full_name() or request.user.username,
            })
        except Exception as exc:
            logger.exception("Interview Razorpay order failed")
            return Response({"error": str(exc)[:200]}, status=500)


class VerifyInterviewRazorpayPaymentView(APIView):
    """POST /api/interviews/billing/razorpay/verify/"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        order_id = request.data.get("razorpay_order_id")
        payment_id = request.data.get("razorpay_payment_id")
        signature = request.data.get("razorpay_signature")
        plan_code = (request.data.get("plan_code") or "").strip().lower()

        if not all([order_id, payment_id, signature, plan_code]):
            return Response({"error": "Missing payment fields"}, status=400)

        tier = InterviewPlanTier.objects.filter(code=plan_code, is_active=True).first()
        if not tier:
            return Response({"error": "Plan not found"}, status=404)

        if not verify_razorpay_signature(order_id, payment_id, signature):
            return Response({"error": "Payment verification failed"}, status=400)

        amount = int(tier.price_inr)
        from apps.billing.razorpay_fulfillment import (
            fulfill_interview_plan_payment,
            verify_razorpay_payment_captured,
        )

        tx = PaymentTransaction.objects.filter(
            gateway_order_id=order_id,
            user=request.user,
        ).first()
        if tx and tx.status == "success":
            return Response({
                "success": True,
                "plan_code": plan_code,
                "entitlement": get_entitlement_payload(request.user),
                "already_verified": True,
            })

        if not verify_razorpay_payment_captured(order_id, payment_id, amount):
            if tx:
                tx.mark_failed("Payment not captured or amount mismatch")
            return Response({"error": "Payment verification failed — not captured"}, status=400)

        try:
            fulfill_interview_plan_payment(
                user=request.user,
                plan_code=plan_code,
                razorpay_payment_id=payment_id,
                transaction=tx,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        return Response({
            "success": True,
            "plan_code": plan_code,
            "entitlement": get_entitlement_payload(request.user),
        }, status=201)


class DemoActivateInterviewPlanView(APIView):
    """POST /api/interviews/billing/demo-activate/ — local dev only."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(settings, "DEMO_PAYMENT_ENABLED", False) and not request.user.is_staff:
            return Response({"error": "Demo activation disabled"}, status=403)
        plan_code = (request.data.get("plan_code") or "pro").lower()
        tier = InterviewPlanTier.objects.filter(code=plan_code, is_active=True).first()
        if not tier:
            return Response({"error": "Plan not found"}, status=404)
        activate_interview_plan(request.user, tier)
        return Response({"success": True, "entitlement": get_entitlement_payload(request.user)})


class CreateInterviewStripeCheckoutView(APIView):
    """POST /api/interviews/billing/stripe/checkout/ { plan_code, currency }"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        import stripe
        from apps.billing.subscription_utils import get_user_subscription
        from common.currency import get_usd_to_inr_rate

        if not settings.STRIPE_SECRET_KEY:
            return Response({"error": "Stripe is not configured"}, status=503)

        plan_code = (request.data.get("plan_code") or "").strip().lower()
        if plan_code not in ("pro", "premium"):
            return Response({"error": "plan_code must be pro or premium"}, status=400)

        tier = InterviewPlanTier.objects.filter(code=plan_code, is_active=True).first()
        if not tier:
            return Response({"error": "Plan not found"}, status=404)

        amount_inr = int(tier.price_inr)
        if amount_inr <= 0:
            return Response({"error": "Plan price not configured"}, status=400)

        currency = (request.data.get("currency") or "USD").upper()
        if currency == "INR":
            unit_amount = amount_inr * 100
            stripe_currency = "inr"
        else:
            rate = float(get_usd_to_inr_rate())
            unit_amount = max(100, int(round((amount_inr / rate) * 100)))
            stripe_currency = "usd"

        stripe.api_key = settings.STRIPE_SECRET_KEY
        subscription = get_user_subscription(request.user)
        customer_id = subscription.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                metadata={"fixitlab_user_id": str(request.user.id)},
            )
            customer_id = customer.id
            subscription.stripe_customer_id = customer_id
            subscription.save()

        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": stripe_currency,
                        "unit_amount": unit_amount,
                        "product_data": {"name": f"FixitLab Interview — {tier.name}"},
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{settings.FRONTEND_URL}/payment?product=interview&interview_plan={plan_code}&stripe=1",
                cancel_url=f"{settings.FRONTEND_URL}/interviews?cancelled=1",
                metadata={
                    "fixitlab_user_id": str(request.user.id),
                    "plan_code": plan_code,
                    "amount_inr": str(amount_inr),
                    "checkout_type": "interview",
                },
            )
            return Response({"checkout_url": session.url, "session_id": session.id})
        except stripe.error.StripeError as exc:
            logger.exception("Interview Stripe checkout failed")
            return Response({"error": str(exc)[:200]}, status=502)


def fulfill_stripe_interview_checkout(session: dict) -> None:
    """Stripe webhook: activate interview plan after payment."""
    metadata = session.get("metadata", {}) or {}
    if metadata.get("checkout_type") != "interview":
        return
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user_id = metadata.get("fixitlab_user_id")
    plan_code = metadata.get("plan_code")
    if not user_id or not plan_code:
        return
    user = User.objects.get(id=int(user_id))
    tier = InterviewPlanTier.objects.filter(code=plan_code, is_active=True).first()
    if not tier:
        return
    amount = int(metadata.get("amount_inr") or tier.price_inr)
    session_id = session.get("id", "")
    idem = PaymentTransaction.generate_idempotency_key(user.id, amount, "INR")
    tx, created = PaymentTransaction.objects.get_or_create(
        idempotency_key=idem,
        defaults={
            "user": user,
            "amount": amount,
            "currency": "INR",
            "payment_method": "stripe",
            "status": "success",
            "gateway_order_id": session_id,
            "gateway_payment_id": session.get("payment_intent") or session_id,
            "gateway_response": {"product": "interview", "plan_code": plan_code},
            "verified_at": timezone.now(),
        },
    )
    if created:
        try:
            from apps.billing.invoice_service import create_invoice_for_transaction
            create_invoice_for_transaction(tx)
        except Exception:
            pass
    activate_interview_plan(user, tier)
