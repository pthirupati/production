"""Razorpay checkout for certification track subscriptions."""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certifications.models import CertificationTrack, CertificationTrackSubscription
from apps.certifications.services.access import effective_cert_prices

logger = logging.getLogger(__name__)


def _verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not all([order_id, payment_id, signature]):
        return False
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return False
    try:
        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
        return True
    except Exception:
        return False


def fulfill_cert_track_subscription(*, user, track, amount_inr: int, razorpay_payment_id: str, order_id: str):
    """Activate or renew cert-track subscription (idempotent)."""
    from datetime import timedelta

    now = timezone.now()
    existing = CertificationTrackSubscription.objects.filter(
        user=user,
        track=track,
        is_active=True,
        expires_at__gt=now,
    ).first()
    if existing:
        return existing, False

    sub_id = f"cert-{track.slug}-{user.id}-{int(now.timestamp())}"
    sub = CertificationTrackSubscription.objects.create(
        user=user,
        track=track,
        subscription_id=sub_id[:200],
        is_active=True,
        expires_at=now + timedelta(days=365),
    )
    import hashlib

    from apps.billing.models import PaymentTransaction
    from apps.billing.gst import compute_gst, place_of_supply_for

    breakup = compute_gst(amount_inr, place_of_supply=place_of_supply_for(user))
    # PaymentTransaction.idempotency_key is unique=True with no default. This
    # create() omitted it, so the FIRST certification purchase platform-wide
    # inserted "" and EVERY subsequent one raised IntegrityError — after Razorpay
    # capture had already been verified and after the subscription row above was
    # created. Depending on ATOMIC_REQUESTS that either charged the customer and
    # rolled back the grant, or granted access and lost the ledger row. Either
    # way it broke on the second cert sale ever.
    #
    # Deterministic key derived from (user, track, order): a replayed verify for
    # the same Razorpay order is idempotent rather than a duplicate charge record.
    idem = hashlib.sha256(
        f"cert-v1-{user.id}-{track.id}-{order_id or razorpay_payment_id}".encode()
    ).hexdigest()
    PaymentTransaction.objects.get_or_create(
        idempotency_key=idem,
        defaults=dict(
            user=user,
            amount=breakup.total_amount,
            taxable_amount=breakup.taxable_amount,
            gst_rate=breakup.gst_rate,
            gst_amount=breakup.gst_amount,
            cgst_amount=breakup.cgst_amount,
            sgst_amount=breakup.sgst_amount,
            igst_amount=breakup.igst_amount,
            place_of_supply=breakup.place_of_supply,
            currency="INR",
            payment_method="razorpay",
            status="success",
            gateway_order_id=order_id,
            gateway_payment_id=razorpay_payment_id,
            gateway_response={
                "product_type": "certification_track",
                "track_slug": track.slug,
                "track_id": track.id,
            },
        ),
    )
    return sub, True


class CertRazorpayOrderView(APIView):
    """POST /api/certifications/billing/razorpay/order/ { track_slug }"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        slug = (request.data.get("track_slug") or request.data.get("cert") or "").strip()
        if not slug:
            return Response({"error": "track_slug is required"}, status=400)
        try:
            track = CertificationTrack.objects.get(slug=slug, is_active=True)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Track not found"}, status=404)

        if track.is_free:
            return Response({"error": "This track is free — no payment required"}, status=400)

        pricing = effective_cert_prices(track)
        amount = int(pricing["standalone_price"] or pricing["bundled_price"] or track.price or 0)
        if amount <= 0:
            return Response({"error": "Price not configured for this certification track"}, status=400)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({"error": "Payment gateway unavailable", "code": "GATEWAY_UNAVAILABLE"}, status=503)

        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        amount_paise = amount * 100
        order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"cert_{track.id}_{request.user.id}"[:40],
                "notes": {
                    "product_type": "certification_track",
                    "track_slug": track.slug,
                    "track_id": str(track.id),
                    "user_id": str(request.user.id),
                },
            }
        )
        return Response(
            {
                "order_id": order["id"],
                "amount": amount,
                "amount_paise": amount_paise,
                "currency": "INR",
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "track_slug": track.slug,
                "track_name": track.name,
                "technology_id": track.technology_id,
                "user_email": request.user.email,
                "user_name": request.user.get_full_name() or request.user.username,
            }
        )


class CertRazorpayVerifyView(APIView):
    """POST /api/certifications/billing/razorpay/verify/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("razorpay_order_id")
        payment_id = request.data.get("razorpay_payment_id")
        signature = request.data.get("razorpay_signature")
        track_slug = (request.data.get("track_slug") or request.data.get("cert") or "").strip()

        if not all([order_id, payment_id, signature, track_slug]):
            return Response({"error": "Missing payment fields"}, status=400)
        if not _verify_signature(order_id, payment_id, signature):
            return Response({"error": "Invalid payment signature"}, status=400)

        try:
            track = CertificationTrack.objects.get(slug=track_slug, is_active=True)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Track not found"}, status=404)

        from apps.billing.razorpay_fulfillment import verify_razorpay_payment_captured

        amount = int(track.price or 0)
        pricing = effective_cert_prices(track)
        amount = int(pricing["standalone_price"] or pricing["bundled_price"] or amount)
        if not verify_razorpay_payment_captured(order_id, payment_id, amount):
            return Response({"error": "Payment not captured"}, status=400)

        sub, created = fulfill_cert_track_subscription(
            user=request.user,
            track=track,
            amount_inr=amount,
            razorpay_payment_id=payment_id,
            order_id=order_id,
        )
        return Response(
            {
                "success": True,
                "created": created,
                "subscription_id": sub.subscription_id,
                "track_slug": track.slug,
                "redirect": f"/certifications/{track.slug}",
            }
        )
