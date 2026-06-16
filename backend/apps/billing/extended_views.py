"""Phase 2 billing: unified summary, Stripe tech checkout, org seat checkout."""

from __future__ import annotations

import logging
import secrets

import stripe
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status as http_status

from .models import Plan, Subscription, TechnologySubscription
from .services import get_user_subscription
from .views import BillingRateThrottle, get_user_subscription as _get_sub

logger = logging.getLogger(__name__)


def _interview_subscription_payload(user) -> dict:
    from apps.interviews.services.entitlements import get_entitlement_payload

    ent = get_entitlement_payload(user)
    tier = ent.get("plan") or {}
    return {
        "product_type": "interview",
        "plan_code": tier.get("code"),
        "plan_name": tier.get("name"),
        "is_active": ent.get("is_active"),
        "expired": ent.get("expired"),
        "renewal_required": ent.get("renewal_required"),
        "interviews_remaining": ent.get("interviews_remaining"),
        "interviews_total": ent.get("interviews_total"),
        "interviews_used": ent.get("interviews_used"),
        "days_remaining": ent.get("days_remaining"),
        "period_start": ent.get("period_start"),
        "period_end": ent.get("period_end"),
        "billing_period_days": ent.get("billing_period_days", 365),
        "max_rounds": tier.get("max_rounds"),
    }


def _payment_history_payload(user) -> list:
    from apps.billing.models import PaymentTransaction, SubscriptionInvoice
    from apps.billing.invoice_service import invoice_list_payload

    txs = PaymentTransaction.objects.filter(user=user, status="success").order_by("-verified_at", "-created_at")[:100]
    invoices = {str(i.payment_transaction_id): i for i in SubscriptionInvoice.objects.filter(user=user).select_related("payment_transaction")}
    rows = []
    for tx in txs:
        gw = tx.gateway_response if isinstance(tx.gateway_response, dict) else {}
        product = gw.get("product", "technology")
        plan_code = gw.get("plan_code", "")
        coupon = gw.get("coupon_code", "")
        original = gw.get("original_amount") or gw.get("amount_inr")
        discount_saved = gw.get("discount_saved", 0)
        inv = invoices.get(str(tx.id))
        label = f"Interview {plan_code.title()}" if product == "interview" else (
            tx.tech_subscription.technology.name if tx.tech_subscription_id else (tx.plan.name if tx.plan_id else "Subscription")
        )
        rows.append({
            "id": str(tx.id),
            "product_type": product,
            "label": label,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "payment_method": tx.get_payment_method_display(),
            "gateway_payment_id": tx.gateway_payment_id,
            "coupon_code": coupon or None,
            "original_amount": str(original) if original else None,
            "discount_saved": discount_saved or 0,
            "paid_at": (tx.verified_at or tx.created_at).isoformat(),
            "invoice_id": str(inv.id) if inv else None,
            "invoice_number": inv.invoice_number if inv else None,
        })
    return rows


class SubscriptionsOverviewView(APIView):
    """Full subscription audit for user — tech, interview, payments, invoices."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.billing.invoice_service import backfill_invoices_for_user, invoice_list_payload
        from apps.billing.models import SubscriptionInvoice
        from apps.billing.subscription_utils import subscription_status_payload, user_has_complimentary_access
        from apps.billing.services import get_user_plan_info

        user = request.user
        backfill_invoices_for_user(user)
        plan_info = get_user_plan_info(user)
        tech_subs = TechnologySubscription.objects.filter(user=user).select_related("technology").order_by("-created_at")
        invoices = SubscriptionInvoice.objects.filter(user=user).order_by("-created_at")[:50]

        tech_rows = []
        for sub in tech_subs:
            status = subscription_status_payload(sub)
            days = max(0, (sub.expires_at - timezone.now()).days) if sub.expires_at else None
            tech_rows.append({
                "id": str(sub.id),
                "product_type": "technology",
                "subscription_id": sub.subscription_id,
                "technology": sub.technology.name,
                "technology_slug": sub.technology.slug,
                "amount": str(sub.amount),
                "payment_method": sub.payment_method,
                "payment_verified": sub.payment_verified,
                "created_at": sub.created_at.isoformat(),
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "days_remaining": days,
                **status,
            })

        return Response({
            "platform_plan": plan_info,
            "complimentary_access": user_has_complimentary_access(user),
            "technology_subscriptions": tech_rows,
            "interview_subscription": _interview_subscription_payload(user),
            "payment_history": _payment_history_payload(user),
            "invoices": [invoice_list_payload(inv) for inv in invoices],
        })


def _create_technology_subscription(user, technology, amount, payment_method="stripe"):
    """Shared helper after successful payment."""
    from datetime import timedelta

    sub_id = f"TECH-{technology.slug.upper()}-{secrets.token_hex(4).upper()}"
    expires = timezone.now() + timedelta(days=365)
    sub, _ = TechnologySubscription.objects.update_or_create(
        user=user,
        technology=technology,
        defaults={
            "subscription_id": sub_id,
            "amount": amount,
            "is_active": True,
            "expires_at": expires,
            "payment_method": payment_method,
        },
    )
    return sub


class UnifiedBillingView(APIView):
    """Single payload for Profile / Pricing — plan, tech subs, org access, gateways."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import OrganizationMember
        from apps.billing.subscription_utils import user_has_complimentary_access
        from apps.billing.services import get_user_plan_info
        from apps.question_bank.models import Technology

        user = request.user
        plan_info = get_user_plan_info(user)
        tech_subs = TechnologySubscription.objects.filter(user=user).select_related("technology").order_by("-created_at")
        org_memberships = OrganizationMember.objects.filter(
            user=user, organization__is_active=True,
        ).select_related("organization")

        stripe_ok = bool(settings.STRIPE_SECRET_KEY)
        razorpay_ok = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)

        return Response({
            "plan": plan_info["plan"],
            "usage": plan_info["usage"],
            "complimentary_access": user_has_complimentary_access(user),
            "technology_subscriptions": [
                {
                    "id": s.id,
                    "technology": {"id": s.technology_id, "name": s.technology.name, "slug": s.technology.slug},
                    "is_active": s.is_active,
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "amount": str(s.amount),
                    "subscription_id": s.subscription_id,
                    "payment_method": s.payment_method,
                    "payment_verified": s.payment_verified,
                    "created_at": s.created_at.isoformat(),
                    "days_remaining": max(0, (s.expires_at - timezone.now()).days) if s.expires_at else None,
                }
                for s in tech_subs
            ],
            "interview_subscription": _interview_subscription_payload(user),
            "organizations": [
                {
                    "name": m.organization.name,
                    "slug": m.organization.slug,
                    "role": m.role,
                    "seat_limit": m.organization.seat_limit,
                }
                for m in org_memberships
            ],
            "gateways": {
                "stripe_configured": stripe_ok,
                "razorpay_configured": razorpay_ok,
                "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY if stripe_ok else None,
                "razorpay_key_id": settings.RAZORPAY_KEY_ID if razorpay_ok else None,
                "recommended": "razorpay" if razorpay_ok else ("stripe" if stripe_ok else None),
            },
            "available_technologies": Technology.objects.filter(is_active=True, coming_soon=False).count(),
        })


class CreateStripeTechCheckoutView(APIView):
    """Stripe Checkout for a single technology subscription (USD/international)."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        from apps.question_bank.models import Technology
        from .coupon_service import apply_coupon_to_amount, CouponError
        from common.currency import get_usd_to_inr_rate

        if not settings.STRIPE_SECRET_KEY:
            return Response({"error": "Stripe is not configured."}, status=http_status.HTTP_503_SERVICE_UNAVAILABLE)

        technology_id = request.data.get("technology_id")
        currency = (request.data.get("currency") or "USD").upper()
        if currency not in ("USD", "INR"):
            currency = "USD"

        try:
            technology = Technology.objects.get(id=technology_id, is_active=True)
        except Technology.DoesNotExist:
            return Response({"error": "Technology not found"}, status=404)

        if TechnologySubscription.objects.filter(user=request.user, technology=technology, is_active=True).exists():
            return Response({"error": "Already subscribed"}, status=409)

        amount_inr = int(getattr(technology, "price", 0) or 0)
        coupon_code = (request.data.get("coupon_code") or "").strip()
        if coupon_code:
            try:
                amount_inr, _coupon = apply_coupon_to_amount(coupon_code, amount_inr)
            except CouponError as exc:
                return Response({"error": str(exc)}, status=400)

        if amount_inr <= 0:
            return Response({"error": "Price not configured"}, status=400)

        if currency == "USD":
            rate = float(get_usd_to_inr_rate())
            unit_amount = max(100, int(round((amount_inr / rate) * 100)))
            currency = "usd"
        else:
            unit_amount = amount_inr * 100
            currency = "inr"

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
                        "currency": currency,
                        "unit_amount": unit_amount,
                        "product_data": {"name": f"FixitLab — {technology.name} (1 year)"},
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{settings.FRONTEND_URL}/pricing?success=true&technology={technology.slug}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing?cancelled=true",
                metadata={
                    "fixitlab_user_id": str(request.user.id),
                    "technology_id": str(technology.id),
                    "amount_inr": str(amount_inr),
                    "coupon_code": coupon_code,
                    "checkout_type": "technology",
                },
            )
            return Response({"checkout_url": session.url, "session_id": session.id})
        except stripe.error.StripeError as exc:
            logger.error("Stripe tech checkout failed: %s", exc)
            return Response({"error": str(exc)}, status=502)


class OrgSeatCheckoutView(APIView):
    """Create Razorpay order for org seat expansion + technology grants."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request, slug):
        from apps.accounts.models import Organization, OrganizationMember, OrganizationTechnologyGrant
        from apps.question_bank.models import Technology

        try:
            org = Organization.objects.get(slug=slug, is_active=True)
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found"}, status=404)

        try:
            member = OrganizationMember.objects.get(organization=org, user=request.user)
        except OrganizationMember.DoesNotExist:
            return Response({"error": "Access denied"}, status=403)
        if member.role not in ("owner", "admin"):
            return Response({"error": "Only owners/admins can purchase seats"}, status=403)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({"error": "Payment gateway unavailable"}, status=503)

        seats = int(request.data.get("seats") or org.seat_limit)
        seats = max(seats, org.member_count)
        tech_ids = request.data.get("technology_ids") or []
        seat_price = int(getattr(settings, "ORG_SEAT_PRICE_INR", 4999))
        tech_price = 0
        technologies = []
        for tid in tech_ids:
            try:
                t = Technology.objects.get(id=tid, is_active=True)
                technologies.append(t)
                tech_price += int(t.price or 0)
            except Technology.DoesNotExist:
                continue

        amount_inr = (seats * seat_price) + tech_price
        if amount_inr <= 0:
            return Response({"error": "Invalid checkout amount"}, status=400)

        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount": amount_inr * 100,
            "currency": "INR",
            "receipt": f"org_{org.slug}_{request.user.id}"[:40],
            "notes": {
                "checkout_type": "organization",
                "org_id": str(org.id),
                "org_slug": org.slug,
                "seats": str(seats),
                "technology_ids": ",".join(str(t.id) for t in technologies),
                "user_id": str(request.user.id),
            },
        })
        return Response({
            "order_id": order["id"],
            "amount": amount_inr,
            "currency": "INR",
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "organization": org.name,
            "seats": seats,
            "technologies": [t.name for t in technologies],
        })


def fulfill_stripe_technology_checkout(session: dict) -> None:
    """Called from Stripe webhook when checkout_type=technology."""
    from django.contrib.auth import get_user_model
    from apps.question_bank.models import Technology

    metadata = session.get("metadata") or {}
    if metadata.get("checkout_type") != "technology":
        return
    user_id = metadata.get("fixitlab_user_id")
    tech_id = metadata.get("technology_id")
    amount_inr = int(metadata.get("amount_inr") or 0)
    if not user_id or not tech_id:
        return
    User = get_user_model()
    user = User.objects.get(id=int(user_id))
    technology = Technology.objects.get(id=int(tech_id))
    _create_technology_subscription(user, technology, amount_inr, payment_method="stripe")
    logger.info("Stripe tech subscription created for %s — %s", user.email, technology.slug)


def fulfill_org_razorpay_order(notes: dict) -> None:
    """Apply org seats and tech grants after Razorpay payment."""
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Organization, OrganizationTechnologyGrant
    from apps.question_bank.models import Technology

    if notes.get("checkout_type") != "organization":
        return
    org = Organization.objects.get(id=notes["org_id"])
    seats = int(notes.get("seats") or org.seat_limit)
    org.seat_limit = max(org.seat_limit, seats)
    org.save(update_fields=["seat_limit", "updated_at"])
    expires = timezone.now() + timedelta(days=365)
    for tid in (notes.get("technology_ids") or "").split(","):
        tid = tid.strip()
        if not tid:
            continue
        try:
            tech = Technology.objects.get(id=int(tid))
        except (Technology.DoesNotExist, ValueError):
            continue
        OrganizationTechnologyGrant.objects.update_or_create(
            organization=org,
            technology=tech,
            defaults={"expires_at": expires, "is_active": True},
        )
    logger.info("Org checkout fulfilled for %s (%s seats)", org.slug, seats)
