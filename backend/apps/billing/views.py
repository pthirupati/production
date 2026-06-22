"""
Stripe Checkout + Webhook views for FixitLab billing.
Razorpay integration for per-technology subscriptions.

Flow (Razorpay — technology subscriptions):
1. User clicks "Subscribe" on the Pricing page.
2. Frontend calls POST /api/billing/razorpay/order/ with { "technology_id": <id> }.
3. Backend creates a Razorpay Order and returns order_id + key_id.
4. Frontend opens Razorpay Checkout modal (or navigates to PaymentPage in demo mode).
5. User pays → Razorpay returns payment details to frontend.
6. Frontend calls POST /api/billing/razorpay/verify/ with payment details.
7. Backend verifies signature, creates TechnologySubscription, sends invoice email.

Flow (Demo mode — no Razorpay configured):
1. User clicks "Subscribe" → backend returns a payment_token.
2. Frontend navigates to /payment page with token + tech info.
3. User selects payment method, enters details, enters OTP.
4. Frontend calls POST /api/billing/confirm-payment/ with { payment_token, payment_method }.
5. Backend validates token, creates subscription, sends emails.

Flow (Stripe — plan-based):
1. User clicks "Upgrade to Pro" on the Pricing page.
2. Frontend calls POST /api/billing/checkout/ with { "plan": "pro" }.
3. Stripe Checkout Session created → redirect → webhook on completion.
"""
import json
import hmac
import hashlib
import logging
import secrets
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import stripe
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q as models_Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from common.throttles import PaymentRateThrottle
from rest_framework import status as http_status

from .models import Plan, Subscription, TechnologySubscription
from .services import get_user_subscription
from common.logging_utils import get_structured_logger

logger = logging.getLogger(__name__)
structured_logger = get_structured_logger(__name__)



class BillingRateThrottle(UserRateThrottle):
    """Rate limit for payment-related endpoints."""
    rate = '30/minute'

# Map plan code → settings key for Stripe Price ID
PLAN_PRICE_MAP = {
    "pro": "STRIPE_PRO_PRICE_ID",
    "enterprise": "STRIPE_TEAM_PRICE_ID",
}


class CreateCheckoutSessionView(APIView):
    """Create a Stripe Checkout Session for plan upgrade."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        plan_code = request.data.get("plan")
        if plan_code not in PLAN_PRICE_MAP:
            return Response(
                {"error": "Invalid plan. Choose 'pro' or 'enterprise'."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Check Stripe is configured
        if not settings.STRIPE_SECRET_KEY:
            return Response(
                {"error": "Payment system is not configured yet. Contact admin."},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe_price_id_key = PLAN_PRICE_MAP[plan_code]
        stripe_price_id = getattr(settings, stripe_price_id_key, "")
        if not stripe_price_id:
            return Response(
                {"error": f"Stripe Price ID not configured for {plan_code}. Contact admin."},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Get or create Stripe customer
        subscription = get_user_subscription(request.user)
        customer_id = subscription.stripe_customer_id

        try:
            if not customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    metadata={
                        "fixitlab_user_id": str(request.user.id),
                        "username": request.user.username,
                    },
                )
                customer_id = customer.id
                subscription.stripe_customer_id = customer_id
                subscription.save()

            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": stripe_price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=f"{settings.SITE_URL}/pricing?session_id={{CHECKOUT_SESSION_ID}}&success=true",
                cancel_url=f"{settings.SITE_URL}/pricing?cancelled=true",
                metadata={
                    "fixitlab_user_id": str(request.user.id),
                    "plan_code": plan_code,
                },
            )

            return Response({"checkout_url": session.url})

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout: {e}")
            return Response(
                {"error": "Payment service error. Please try again later."},
                status=http_status.HTTP_502_BAD_GATEWAY,
            )


class StripeWebhookView(APIView):
    """
    Handle Stripe webhooks.
    Key events:
    - checkout.session.completed → upgrade user's plan
    - customer.subscription.deleted → downgrade to free
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.warning("Stripe webhook secret not configured")
            return Response(status=http_status.HTTP_400_BAD_REQUEST)

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.warning("Invalid Stripe webhook payload")
            return Response(status=http_status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            return Response(status=http_status.HTTP_400_BAD_REQUEST)

        event_type = event["type"]
        data = event["data"]["object"]

        # Idempotency: skip duplicate webhook deliveries
        from django.core.cache import cache as _cache
        _idem_key = f"stripe_webhook_legacy:{event['id']}"
        if not _cache.add(_idem_key, True, timeout=86400):
            logger.info("Duplicate Stripe webhook (legacy) ignored: %s", event['id'])
            return Response({"status": "duplicate"})

        logger.info(f"Stripe webhook received: {event_type}")

        if event_type == "checkout.session.completed":
            self._handle_checkout_completed(data)
        elif event_type == "customer.subscription.deleted":
            self._handle_subscription_cancelled(data)
        elif event_type == "customer.subscription.updated":
            self._handle_subscription_updated(data)

        return Response({"status": "ok"})

    def _handle_checkout_completed(self, session):
        """Upgrade plan or fulfill technology subscription."""
        metadata = session.get("metadata", {}) or {}
        if metadata.get("checkout_type") == "technology":
            from .extended_views import fulfill_stripe_technology_checkout
            fulfill_stripe_technology_checkout(session)
            return
        if metadata.get("checkout_type") == "interview":
            from apps.interviews.billing_views import fulfill_stripe_interview_checkout
            fulfill_stripe_interview_checkout(session)
            return

        user_id = metadata.get("fixitlab_user_id")
        plan_code = metadata.get("plan_code")
        stripe_subscription_id = session.get("subscription", "")

        if not user_id or not plan_code:
            logger.error(f"Missing metadata in checkout session: {metadata}")
            return

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=int(user_id))

            plan = Plan.objects.get(code=plan_code)
            subscription = get_user_subscription(user)
            subscription.plan = plan
            subscription.stripe_subscription_id = stripe_subscription_id or ""
            subscription.is_active = True
            subscription.started_at = timezone.now()
            subscription.save()

            logger.info(f"User {user.username} upgraded to {plan_code}")

        except Exception as e:
            logger.error(f"Error handling checkout completion: {e}")

    def _handle_subscription_cancelled(self, stripe_sub):
        """Downgrade user back to free plan on cancellation."""
        stripe_sub_id = stripe_sub.get("id", "")
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            free_plan = Plan.objects.get(code="free")
            subscription.plan = free_plan
            subscription.stripe_subscription_id = ""
            subscription.save()
            logger.info(f"User {subscription.user.username} downgraded to free (subscription cancelled)")
        except Subscription.DoesNotExist:
            logger.warning(f"No subscription found for Stripe sub {stripe_sub_id}")

    def _handle_subscription_updated(self, stripe_sub):
        """Handle subscription status changes (e.g. payment failed)."""
        stripe_sub_id = stripe_sub.get("id", "")
        sub_status = stripe_sub.get("status", "")

        try:
            subscription = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            if sub_status in ("past_due", "unpaid", "cancelled"):
                subscription.is_active = False
                subscription.save()
                logger.info(f"Subscription {stripe_sub_id} marked inactive: {sub_status}")
            elif sub_status == "active":
                subscription.is_active = True
                subscription.save()
        except Subscription.DoesNotExist:
            pass


class BillingStatusView(APIView):
    """Check if payment gateways are configured."""
    permission_classes = [AllowAny]

    def get(self, request):
        stripe_configured = bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRO_PRICE_ID)
        razorpay_configured = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        return Response({
            "stripe_configured": stripe_configured,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY if stripe_configured else None,
            "razorpay_configured": razorpay_configured,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID if razorpay_configured else None,
        })


class PaymentGatewayStatusView(APIView):
    """Check if payment gateway is ready and return configuration status."""
    permission_classes = [AllowAny]

    def get(self, request):
        razorpay_configured = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        stripe_configured = bool(settings.STRIPE_SECRET_KEY)
        gateway_configured = razorpay_configured or stripe_configured

        # Admin master switch: payments only go live when the owner enables them
        # AND a gateway is configured. Until then the warning shows. This lets the
        # owner add keys, verify, then flip the switch (the "enable payment" button).
        payments_enabled = True
        try:
            from apps.adminpanel.models import PlatformSettings
            ps = PlatformSettings.objects.first()
            if ps is not None:
                payments_enabled = ps.payments_enabled
        except Exception:
            pass
        available = gateway_configured and payments_enabled

        razorpay_ready = "ready" if (razorpay_configured and payments_enabled) else "down"
        stripe_ready = "ready" if (stripe_configured and payments_enabled) else "down"

        banner_message = None
        if not gateway_configured:
            banner_message = (
                "Payment gateway is currently unavailable. "
                "Free scenarios still work. Paid subscriptions will open once billing is configured."
            )
        elif not payments_enabled:
            banner_message = (
                "Payments are configured but not yet enabled. "
                "An admin can turn them on in Admin → Settings → Payments & Tax."
            )
        elif not razorpay_configured:
            banner_message = "Razorpay unavailable — international card payments via Stripe are available."

        return Response({
            "razorpay_configured": razorpay_configured,
            "stripe_configured": stripe_configured,
            "payments_enabled": payments_enabled,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID if (razorpay_configured and available) else None,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY if (stripe_configured and available) else None,
            "status": razorpay_ready if razorpay_configured else stripe_ready,
            "available": available,
            "recommended_gateway": "razorpay" if razorpay_configured else ("stripe" if stripe_configured else None),
            "banner_message": banner_message,
            "banner_type": "warning" if banner_message else None,
        })


class ValidateCouponView(APIView):
    """Preview coupon discount before checkout."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        from apps.question_bank.models import Technology
        from .coupon_service import apply_coupon_to_amount, CouponError

        code = (request.data.get("coupon_code") or "").strip()
        technology_id = request.data.get("technology_id")
        if not code:
            return Response({"error": "coupon_code is required"}, status=http_status.HTTP_400_BAD_REQUEST)
        if not technology_id:
            return Response({"error": "technology_id is required"}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            technology = Technology.objects.get(id=technology_id, is_active=True)
        except Technology.DoesNotExist:
            return Response({"error": "Technology not found"}, status=http_status.HTTP_404_NOT_FOUND)

        original_amount = int(getattr(technology, "price", 0) or 0)
        if original_amount <= 0:
            return Response({"error": "Price not configured for this technology"}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            discounted, coupon = apply_coupon_to_amount(code, original_amount, user=request.user)
        except CouponError as exc:
            return Response({"valid": False, "error": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response({
            "valid": True,
            "code": coupon.code,
            "description": coupon.description,
            "original_amount": original_amount,
            "discounted_amount": discounted,
            "discount_saved": original_amount - discounted,
            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.discount_value),
        })


class CreateRazorpayOrderView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentRateThrottle]

    def post(self, request):
        from apps.question_bank.models import Technology
        from apps.notifications.tasks import send_payment_error_notification

        # Platform maintenance blocks new payments (admin exempt)
        if not (request.user.is_staff or request.user.is_superuser):
            try:
                from apps.adminpanel.platform_config import is_maintenance_active
                if is_maintenance_active():
                    from apps.adminpanel.models import PlatformSettings
                    row = PlatformSettings.objects.filter(pk=1).first()
                    msg = (row.maintenance_message if row else None) or "FixitLab is currently under maintenance. Payments are temporarily unavailable."
                    return Response({"error": "maintenance", "message": msg}, status=503)
            except Exception:
                pass

        technology_id = request.data.get("technology_id")
        if not technology_id:
            return Response(
                {"error": "technology_id is required"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            technology = Technology.objects.get(id=technology_id, is_active=True)
        except Technology.DoesNotExist:
            return Response(
                {"error": "Technology not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Check if already subscribed
        existing = TechnologySubscription.objects.filter(
            user=request.user, technology=technology, is_active=True
        ).first()
        if existing:
            return Response(
                {"error": "Already subscribed to this technology", "subscription_id": existing.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Get server-side price (never trust client)
        amount = int(getattr(technology, 'price', 0) or 0)
        coupon_code = (request.data.get("coupon_code") or "").strip()
        coupon_applied = None
        original_amount = amount
        if coupon_code:
            from .coupon_service import apply_coupon_to_amount, CouponError
            try:
                amount, coupon_applied = apply_coupon_to_amount(coupon_code, amount, user=request.user)
            except CouponError as exc:
                return Response({"error": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response(
                {"error": "Price not configured for this technology"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Amount in paise (INR smallest unit)
        amount_paise = amount * 100

        # Payment gateway must be configured — no fake/demo checkout in production
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response(
                {
                    "error": "Payment gateway is temporarily unavailable. Please try again later or contact support.",
                    "code": "GATEWAY_UNAVAILABLE",
                    "support_email": settings.SUPPORT_EMAIL,
                },
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"tech_{technology.id}_{request.user.id}",
                "notes": {
                    "technology_id": str(technology.id),
                    "technology_name": technology.name,
                    "user_id": str(request.user.id),
                    "username": request.user.username,
                    "coupon_code": coupon_applied.code if coupon_applied else "",
                    "original_amount": str(original_amount),
                },
            }

            order = client.order.create(data=order_data)

            from .razorpay_fulfillment import create_technology_payment_transaction
            create_technology_payment_transaction(
                user=request.user,
                amount=amount,
                order=order,
                technology_id=technology.id,
                coupon_code=coupon_applied.code if coupon_applied else "",
            )

            return Response({
                "order_id": order["id"],
                "amount": amount,
                "original_amount": original_amount,
                "amount_paise": amount_paise,
                "currency": "INR",
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "technology": technology.name,
                "technology_id": technology.id,
                "user_email": request.user.email,
                "user_name": request.user.get_full_name() or request.user.username,
                "coupon_applied": coupon_applied.code if coupon_applied else None,
                "discount_saved": original_amount - amount if coupon_applied else 0,
            })

        except Exception as e:
            error_msg = str(e)
            structured_logger.error(
                "Razorpay order creation failed",
                user_id=request.user.id,
                email=request.user.email,
                technology_id=technology.id,
                technology_name=technology.name,
                error_message=error_msg,
                tags=["payment", "razorpay", "error"]
            )
            
            # Send error notification
            try:
                send_payment_error_notification.delay(
                    user_id=request.user.id,
                    email=request.user.email,
                    technology_name=technology.name,
                    error_message=f"Order creation failed: {error_msg}",
                )
            except Exception as notify_err:
                structured_logger.error(
                    "Failed to send payment error notification",
                    user_id=request.user.id,
                    email=request.user.email,
                    error_message=str(notify_err),
                    tags=["payment", "notification", "error"]
                )
            
            # Return error. Don't cascade to demo mode if gateway is configured but failing.
            return Response(
                {
                    "error": "Payment gateway error. Our team has been notified. Please try again later or contact support.",
                    "code": "GATEWAY_ERROR",
                    "support_email": settings.SUPPORT_EMAIL,
                },
                status=http_status.HTTP_502_BAD_GATEWAY,
            )

    def _create_direct_subscription(self, request, technology, amount):
        """Demo mode: return a payment token instead of creating subscription directly.
        Frontend will navigate to payment page; user confirms → calls confirm-payment endpoint."""

        payment_token = secrets.token_urlsafe(32)

        # Store token in cache for 30 minutes
        cache.set(
            f"payment_token:{payment_token}",
            {
                "user_id": request.user.id,
                "technology_id": technology.id,
                "technology_name": technology.name,
                "amount": amount,
                "username": request.user.username,
                "email": request.user.email,
                "full_name": request.user.get_full_name() or request.user.username,
            },
            timeout=1800,  # 30 minutes
        )

        return Response({
            "payment_token": payment_token,
            "technology": technology.name,
            "technology_id": technology.id,
            "amount": amount,
            "currency": "INR",
            "user_email": request.user.email,
            "user_name": request.user.get_full_name() or request.user.username,
            "payment_mode": "gateway",
        }, status=http_status.HTTP_200_OK)

    def _send_subscription_emails(self, user, technology, sub_id, amount):
        """Send subscription confirmation + admin + invoice emails."""
        from apps.notifications.email_helpers import queue_user_email
        from apps.notifications.tasks import send_notification_email

        try:
            queue_user_email(
                user,
                subject=f"FixitLab Subscription Confirmed - {technology.name}",
                template="emails/subscription_confirmation.html",
                context={
                    "username": user.get_full_name() or user.username,
                    "technology": technology.name,
                    "plan_name": "Technology Access",
                    "amount": f"₹{amount}",
                    "expiry_date": "Lifetime",
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                    "subscription_id": sub_id,
                },
                email_type="subscription",
            )
        except Exception as e:
            logger.error(f"Failed to send user subscription email: {e}")

        try:
            send_notification_email.delay(
                subject=f"[ADMIN] New Subscription - {technology.name} - {user.username}",
                to_email=settings.PAYMENT_EMAIL,
                template="emails/subscription_admin_notification.html",
                context={
                    "username": user.get_full_name() or user.username,
                    "email": user.email,
                    "technology": technology.name,
                    "plan_name": "Technology Access",
                    "amount": f"₹{amount}",
                    "subscription_id": sub_id,
                    "payment_date": timezone.now().strftime("%B %d, %Y"),
                },
            )
        except Exception as e:
            logger.error(f"Failed to send admin subscription email: {e}")

        # Invoice email (respects subscription email preference)
        try:
            queue_user_email(
                user,
                subject=f"FixitLab Invoice — {technology.name} Subscription",
                template="emails/subscription_invoice.html",
                context={
                    "username": user.get_full_name() or user.username,
                    "email": user.email,
                    "technology": technology.name,
                    "plan_name": "Technology Access — Lifetime",
                    "amount": f"₹{amount}",
                    "subscription_id": sub_id,
                    "invoice_date": timezone.now().strftime("%B %d, %Y"),
                    "invoice_number": f"INV-{sub_id}",
                    "payment_method": "Razorpay",
                    "billing_period": "Lifetime",
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                },
                email_type="subscription",
            )
        except Exception as e:
            logger.error(f"Failed to send invoice email: {e}")

        # In-app notification
        try:
            from apps.notifications.tasks import create_in_app_notification
            create_in_app_notification.delay(
                user_id=user.id,
                notification_type="system",
                title=f"Subscribed to {technology.name}",
                message=f"Your subscription ID is {sub_id}. You now have full access to all {technology.name} scenarios. An invoice has been sent to your email.",
            )
        except Exception as e:
            logger.error(f"Failed to send subscription notification: {e}")


class VerifyRazorpayPaymentView(APIView):
    """Verify Razorpay payment signature and create subscription."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentRateThrottle]

    def post(self, request):
        from apps.question_bank.models import Technology
        from apps.notifications.tasks import send_payment_error_notification

        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")
        technology_id = request.data.get("technology_id")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, technology_id]):
            return Response(
                {"error": "Missing required payment verification fields"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            technology = Technology.objects.get(id=technology_id, is_active=True)
        except Technology.DoesNotExist:
            return Response(
                {"error": "Technology not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Check if already subscribed
        existing = TechnologySubscription.objects.filter(
            user=request.user, technology=technology, is_active=True
        ).first()
        if existing:
            return Response(
                {"error": "Already subscribed", "subscription_id": existing.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Verify Razorpay signature
        if not self._verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            logger.warning(f"Razorpay signature verification failed for user {request.user.username}")
            
            # Send error notification
            try:
                send_payment_error_notification.delay(
                    user_id=request.user.id,
                    email=request.user.email,
                    technology_name=technology.name,
                    error_message="Payment verification failed - invalid signature",
                    order_id=razorpay_order_id,
                )
            except Exception as notify_err:
                logger.error(f"Failed to send payment error notification: {notify_err}")
            
            return Response(
                {
                    "error": "Payment verification failed. Our support team has been notified. Please contact support if the problem persists.",
                    "support_email": settings.SUPPORT_EMAIL,
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        from .models import PaymentTransaction
        from .razorpay_fulfillment import fulfill_technology_subscription
        from django.db import transaction as db_transaction

        # Use select_for_update inside an atomic block to prevent the race
        # condition where two concurrent verify requests both pass the
        # duplicate check and both activate the subscription.
        with db_transaction.atomic():
            tx = PaymentTransaction.objects.select_for_update(
                nowait=False
            ).filter(
                gateway_order_id=razorpay_order_id,
                user=request.user,
            ).first()
        if tx and tx.status == "success" and tx.tech_subscription_id:
            sub = tx.tech_subscription
            return Response({
                "subscription_id": sub.subscription_id,
                "technology": technology.name,
                "amount": str(sub.amount),
                "is_active": True,
                "payment_verified": True,
                "razorpay_payment_id": tx.gateway_payment_id or razorpay_payment_id,
                "already_verified": True,
            }, status=http_status.HTTP_200_OK)

        # Server-side price — prefer Razorpay order amount (supports coupons); fallback to catalog price
        amount = int(getattr(technology, "price", 0) or 0)
        coupon_applied = None
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            try:
                import razorpay
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                order = client.order.fetch(razorpay_order_id)
                if isinstance(order, dict):
                    order_notes = order.get("notes") or {}
                    raw_order_amount = order.get("amount")
                    try:
                        if raw_order_amount is not None:
                            parsed = int(raw_order_amount) // 100
                            if parsed > 0:
                                amount = parsed
                    except (TypeError, ValueError):
                        pass
                    coupon_code = (order_notes.get("coupon_code") or "").strip()
                    if coupon_code:
                        from .coupon_service import validate_coupon
                        try:
                            # Resolve the coupon for redemption at fulfilment.
                            # Don't pre-reject on the per-user check here: the
                            # authoritative per-user guard is the unique row in
                            # redeem_coupon, and the payment is already verified.
                            coupon_applied = validate_coupon(coupon_code)
                        except Exception:
                            coupon_applied = None
            except Exception as e:
                logger.warning("Could not fetch Razorpay order %s: %s", razorpay_order_id, e)

        if amount <= 0:
            amount = int(getattr(technology, "price", 0) or 0)
        if amount <= 0:
            return Response(
                {"error": "Invalid technology price"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if not self._verify_payment_with_gateway(
            razorpay_order_id, razorpay_payment_id, amount
        ):
            logger.warning(
                "Razorpay payment amount/order mismatch for user %s order %s",
                request.user.username, razorpay_order_id,
            )
            if tx:
                tx.mark_failed("Amount or order mismatch")
            return Response(
                {"error": "Payment verification failed — amount or order mismatch."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        tech_sub, created = fulfill_technology_subscription(
            user=request.user,
            technology=technology,
            amount=amount,
            razorpay_payment_id=razorpay_payment_id,
            transaction=tx,
            coupon_applied=coupon_applied,
        )

        logger.info(
            "Payment verified for user %s: %s — %s (created=%s)",
            request.user.username, razorpay_payment_id, technology.name, created,
        )

        return Response({
            "subscription_id": tech_sub.subscription_id,
            "technology": technology.name,
            "amount": str(amount),
            "coupon_applied": coupon_applied.code if coupon_applied else None,
            "is_active": True,
            "payment_verified": True,
            "razorpay_payment_id": razorpay_payment_id,
        }, status=http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK)

    def _verify_signature(self, order_id, payment_id, signature):
        """Verify Razorpay payment signature using the official Razorpay client utility.

        SECURITY_AUDIT P-02: FAIL CLOSED. A missing gateway secret must NEVER
        pass signature verification. The demo skip is permitted ONLY in an
        explicit local-dev/demo mode (``DEBUG and DEMO_PAYMENT_ENABLED``); in
        production a missing ``RAZORPAY_KEY_SECRET`` always returns False so no
        subscription is ever activated without a real, signed payment.
        """
        if not settings.RAZORPAY_KEY_SECRET:
            if getattr(settings, "DEBUG", False) and getattr(settings, "DEMO_PAYMENT_ENABLED", False):
                logger.warning("Razorpay key secret not configured — demo skip (DEBUG only)")
                return True
            logger.error("Razorpay key secret not configured — failing signature verification closed")
            return False

        try:
            import razorpay
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def _verify_payment_with_gateway(self, order_id, payment_id, expected_amount_inr):
        """Fetch payment from Razorpay and validate order + amount server-side.

        Returns False (never raises) so callers can treat a Razorpay API failure
        as a verification failure — the subscription is NOT activated when this
        returns False.

        SECURITY_AUDIT P-02: FAIL CLOSED on a missing gateway secret. The demo
        pass is allowed ONLY in explicit local-dev/demo mode
        (``DEBUG and DEMO_PAYMENT_ENABLED``); production always returns False.
        """
        if not settings.RAZORPAY_KEY_SECRET or not settings.RAZORPAY_KEY_ID:
            if getattr(settings, "DEBUG", False) and getattr(settings, "DEMO_PAYMENT_ENABLED", False):
                return True
            logger.error("Razorpay keys not configured — failing payment verification closed")
            return False

        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            payment = client.payment.fetch(payment_id)
        except Exception as e:
            # payment.fetch() failure must NOT result in silent success.
            logger.error(
                "Razorpay payment.fetch failed for %s — rejecting verification: %s",
                payment_id, e,
            )
            return False

        if payment.get("order_id") != order_id:
            logger.warning(
                "Razorpay order_id mismatch: got %s expected %s",
                payment.get("order_id"), order_id,
            )
            return False
        if int(payment.get("amount", 0)) != int(expected_amount_inr) * 100:
            logger.warning(
                "Razorpay amount mismatch for %s: got %s expected %s paise",
                payment_id, payment.get("amount"), int(expected_amount_inr) * 100,
            )
            return False
        if payment.get("status") != "captured":
            logger.warning(
                "Razorpay payment %s not captured (status=%s)",
                payment_id, payment.get("status"),
            )
            return False
        return True


class TechnologySubscribeView(APIView):
    """Activate access to a FREE (price == 0) technology.

    SECURITY_AUDIT P-01: this endpoint must NEVER grant a paid subscription
    without a gateway-confirmed payment. It used to call
    ``activate_technology_subscription`` for any technology with no payment
    check at all, so any logged-in user could obtain a year of paid access for
    free with a single POST. It is now hard-gated to ``price == 0`` technologies
    only; paid tracks must go through the Razorpay order → signature-verified
    confirm flow (``CreateRazorpayOrderView`` + ``VerifyRazorpayPaymentView``),
    which is the only path that activates a subscription, and only after
    ``_verify_payment_with_gateway`` confirms a captured payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.question_bank.models import Technology
        from apps.notifications.tasks import send_notification_email, create_in_app_notification

        technology_id = request.data.get("technology_id")
        if not technology_id:
            return Response(
                {"error": "technology_id is required"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            technology = Technology.objects.get(id=technology_id, is_active=True)
        except Technology.DoesNotExist:
            return Response(
                {"error": "Technology not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Determine price from technology (server-side — never trust client)
        amount = int(getattr(technology, 'price', 0) or 0)

        # SECURITY_AUDIT P-01: refuse to activate a PAID technology here. Paid
        # access is only ever granted by the signature/gateway-verified Razorpay
        # path, never by this no-payment endpoint. Only price == 0 ("free") may
        # be self-activated.
        if amount > 0:
            return Response(
                {
                    "error": "This technology requires checkout. Please complete payment to subscribe.",
                    "code": "PAYMENT_REQUIRED",
                },
                status=http_status.HTTP_402_PAYMENT_REQUIRED,
            )

        # Check if already subscribed (active and not expired)
        from .subscription_utils import (
            activate_technology_subscription,
            get_or_create_technology_subscription,
            is_tech_subscription_active,
        )

        existing = TechnologySubscription.objects.filter(
            user=request.user, technology=technology
        ).order_by("-created_at").first()
        if existing and is_tech_subscription_active(existing):
            return Response(
                {"error": "Already subscribed to this technology", "subscription_id": existing.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )

        if existing:
            # Renewal of expired/inactive subscription
            tech_sub = existing
            tech_sub.amount = amount
            activate_technology_subscription(tech_sub, renew=True)
            sub_id = tech_sub.subscription_id
        else:
            sub_id = TechnologySubscription.generate_subscription_id(
                technology.name, request.user.username
            )
            tech_sub, created = get_or_create_technology_subscription(
                request.user,
                technology,
                defaults={
                    "subscription_id": sub_id,
                    "amount": amount,
                },
            )
            if not created and is_tech_subscription_active(tech_sub):
                return Response(
                    {"error": "Already subscribed to this technology", "subscription_id": tech_sub.subscription_id},
                    status=http_status.HTTP_409_CONFLICT,
                )
            if not tech_sub.subscription_id:
                tech_sub.subscription_id = sub_id
            tech_sub.amount = amount
            activate_technology_subscription(tech_sub, renew=True)

        # Get user profile info
        profile = getattr(request.user, "profile", None)
        phone = profile.phone_number if profile else "N/A"
        expiry_str = tech_sub.expires_at.strftime("%B %d, %Y") if tech_sub.expires_at else "1 Year"

        # Send email to user
        try:
            from django.utils import timezone
            send_notification_email.delay(
                subject=f"FixitLab Subscription Confirmed - {technology.name}",
                to_email=request.user.email,
                template="emails/subscription_confirmation.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "technology": technology.name,
                    "plan_name": "1-Year Technology Access",
                    "amount": f"₹{amount}",
                    "expiry_date": expiry_str,
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                    "subscription_id": sub_id,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send user subscription email: {e}")

        # Send email to admin (PAYMENT_EMAIL)
        try:
            send_notification_email.delay(
                subject=f"[ADMIN] New Subscription - {technology.name} - {request.user.username}",
                to_email=settings.PAYMENT_EMAIL,
                template="emails/subscription_admin_notification.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "email": request.user.email,
                    "technology": technology.name,
                    "plan_name": "Technology Access",
                    "amount": f"₹{amount}",
                    "subscription_id": sub_id,
                    "payment_date": timezone.now().strftime("%B %d, %Y"),
                },
            )
        except Exception as e:
            logger.error(f"Failed to send admin subscription email: {e}")

        # Invoice email
        try:
            send_notification_email.delay(
                subject=f"FixitLab Invoice — {technology.name} Subscription",
                to_email=request.user.email,
                template="emails/subscription_invoice.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "email": request.user.email,
                    "technology": technology.name,
                    "plan_name": "1-Year Technology Access — Annual",
                    "amount": f"₹{amount}",
                    "subscription_id": sub_id,
                    "invoice_date": timezone.now().strftime("%B %d, %Y"),
                    "invoice_number": f"INV-{sub_id}",
                    "payment_method": "Online Payment",
                    "billing_period": "1 Year",
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                },
            )
        except Exception as e:
            logger.error(f"Failed to send invoice email: {e}")

        # In-app notification
        try:
            create_in_app_notification.delay(
                user_id=request.user.id,
                notification_type="system",
                title=f"Subscribed to {technology.name}",
                message=f"Your subscription ID is {sub_id}. You now have full access to all {technology.name} scenarios.",
            )
        except Exception as e:
            logger.error(f"Failed to send subscription notification: {e}")

        return Response({
            "subscription_id": sub_id,
            "technology": technology.name,
            "amount": str(amount),
            "is_active": True,
            "expires_at": tech_sub.expires_at.isoformat() if tech_sub.expires_at else None,
        }, status=http_status.HTTP_201_CREATED)


class UserTechSubscriptionsView(APIView):
    """Get all technology subscriptions for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .subscription_utils import subscription_status_payload, user_has_complimentary_access

        subs = TechnologySubscription.objects.filter(
            user=request.user
        ).select_related("technology").order_by("-created_at")

        data = []
        for sub in subs:
            status = subscription_status_payload(sub)
            data.append({
                "id": str(sub.id),
                "subscription_id": sub.subscription_id,
                "technology": {
                    "id": sub.technology.id,
                    "name": sub.technology.name,
                    "slug": sub.technology.slug,
                },
                "amount": str(sub.amount),
                **status,
            })

        return Response({
            "subscriptions": data,
            "complimentary_access": user_has_complimentary_access(request.user),
        })


class SubscriptionLogsView(APIView):
    """Admin-only: Get all subscription logs with filters and currency conversion."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from common.currency import get_price_in_currency, get_usd_to_inr_rate

        # Filters
        tech_filter = request.query_params.get("technology", "").strip()
        status_filter = request.query_params.get("status", "").strip()  # active, expired, all
        user_filter = request.query_params.get("user", "").strip()
        date_from = request.query_params.get("date_from", "").strip()
        date_to = request.query_params.get("date_to", "").strip()
        display_currency = request.query_params.get("currency", "INR").upper()

        subs = TechnologySubscription.objects.all().select_related(
            "user", "technology"
        ).order_by("-created_at")

        # Apply filters
        if tech_filter:
            subs = subs.filter(technology__name__icontains=tech_filter)
        if status_filter == "active":
            from django.utils import timezone as tz
            from django.db.models import Q
            now = tz.now()
            subs = subs.filter(is_active=True).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            )
        elif status_filter == "expired":
            from django.utils import timezone as tz
            from django.db.models import Q
            now = tz.now()
            subs = subs.filter(
                Q(is_active=False) | Q(expires_at__lte=now)
            )
        if user_filter:
            subs = subs.filter(
                models_Q(user__username__icontains=user_filter) |
                models_Q(user__email__icontains=user_filter)
            )
        if date_from:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_from, "%Y-%m-%d")
                subs = subs.filter(created_at__date__gte=dt.date())
            except ValueError:
                pass
        if date_to:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_to, "%Y-%m-%d")
                subs = subs.filter(created_at__date__lte=dt.date())
            except ValueError:
                pass

        subs = subs[:500]

        # Get exchange rate once for all conversions
        exchange_rate = float(get_usd_to_inr_rate()) if display_currency == "USD" else None

        # Calculate totals
        from .subscription_utils import is_tech_subscription_active
        total_inr = sum(float(sub.amount) for sub in subs if is_tech_subscription_active(sub))
        total_display = total_inr
        if display_currency == "USD" and exchange_rate:
            total_display = round(total_inr / exchange_rate, 2)

        data = []
        for sub in subs:
            amount_inr = float(sub.amount)
            if display_currency == "USD" and exchange_rate:
                amount_display = round(amount_inr / exchange_rate, 2)
                amount_str = f"${amount_display}"
            else:
                amount_display = amount_inr
                amount_str = f"₹{int(amount_inr)}"

            from .subscription_utils import subscription_status_payload
            status = subscription_status_payload(sub)

            data.append({
                "id": str(sub.id),
                "subscription_id": sub.subscription_id,
                "user": {
                    "id": sub.user.id,
                    "username": sub.user.username,
                    "email": sub.user.email,
                },
                "technology": sub.technology.name,
                "amount": str(sub.amount),
                "amount_inr": amount_inr,
                "amount_display": amount_str,
                "payment_verified": sub.payment_verified,
                "created_at": sub.created_at.isoformat(),
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                **status,
            })

        return Response({
            "logs": data,
            "total_revenue": total_display,
            "total_revenue_inr": total_inr,
            "display_currency": display_currency,
            "exchange_rate": exchange_rate,
            "total_count": len(data),
            "active_count": sum(1 for d in data if d["is_active"]),
        })


class CancelTechSubscriptionView(APIView):
    """Cancel a technology subscription."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub_id = request.data.get("subscription_id")
        if not sub_id:
            return Response(
                {"error": "subscription_id is required"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            sub = TechnologySubscription.objects.get(
                subscription_id=sub_id, user=request.user, is_active=True
            )
        except TechnologySubscription.DoesNotExist:
            return Response(
                {"error": "Active subscription not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        sub.is_active = False
        sub.save()

        # Send cancellation notification
        try:
            from apps.notifications.tasks import create_in_app_notification
            from apps.notifications.email_helpers import queue_user_email
            create_in_app_notification.delay(
                user_id=request.user.id,
                notification_type="system",
                title=f"Subscription Cancelled — {sub.technology.name}",
                message=f"Your subscription (ID: {sub_id}) has been cancelled. You can resubscribe anytime.",
            )
            queue_user_email(
                request.user,
                subject=f"FixitLab: Subscription Cancelled — {sub.technology.name}",
                template="emails/subscription_cancelled.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "technology": sub.technology.name,
                    "subscription_id": sub_id,
                },
                email_type="subscription",
            )
        except Exception as e:
            logger.warning(f"Failed to send cancellation notification: {e}")

        return Response({
            "subscription_id": sub_id,
            "technology": sub.technology.name,
            "is_active": False,
        })


class ConfirmPaymentView(APIView):
    """
    Confirm a payment (demo/gateway mode).
    Called after the user completes the payment flow on the frontend payment page.
    Validates the payment_token and creates the subscription.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentRateThrottle]

    def post(self, request):
        from django.conf import settings
        from apps.question_bank.models import Technology
        from apps.notifications.tasks import send_notification_email, create_in_app_notification

        razorpay_configured = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        demo_enabled = getattr(settings, "DEMO_PAYMENT_ENABLED", False) and not razorpay_configured

        if not razorpay_configured and not demo_enabled:
            return Response(
                {
                    "error": "Payment gateway is not configured. Subscriptions are unavailable until payments are enabled.",
                    "code": "GATEWAY_UNAVAILABLE",
                },
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not getattr(settings, "DEMO_PAYMENT_ENABLED", False):
            return Response(
                {"error": "Demo payment is disabled. Use Razorpay checkout."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        payment_token = request.data.get("payment_token")
        payment_method = request.data.get("payment_method", "card")

        if not payment_token:
            return Response(
                {"error": "payment_token is required"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve and validate token from cache
        cache_key = f"payment_token:{payment_token}"
        token_data = cache.get(cache_key)

        if not token_data:
            return Response(
                {"error": "Payment session expired or invalid. Please try again."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Verify token belongs to current user
        if token_data["user_id"] != request.user.id:
            return Response(
                {"error": "Invalid payment session"},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        try:
            technology = Technology.objects.get(id=token_data["technology_id"], is_active=True)
        except Technology.DoesNotExist:
            return Response(
                {"error": "Technology not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        from .subscription_utils import (
            activate_technology_subscription,
            get_or_create_technology_subscription,
            is_tech_subscription_active,
        )

        existing = TechnologySubscription.objects.filter(
            user=request.user, technology=technology, is_active=True
        ).first()
        if existing and is_tech_subscription_active(existing):
            cache.delete(cache_key)
            return Response(
                {"error": "Already subscribed", "subscription_id": existing.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )

        amount = token_data["amount"]
        sub_id = TechnologySubscription.generate_subscription_id(
            technology.name, request.user.username
        )

        tech_sub, created = get_or_create_technology_subscription(
            request.user,
            technology,
            defaults={
                "subscription_id": sub_id,
                "amount": amount,
                "is_active": True,
                "payment_verified": True,
            },
        )
        if not created and is_tech_subscription_active(tech_sub):
            cache.delete(cache_key)
            return Response(
                {"error": "Already subscribed", "subscription_id": tech_sub.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )
        if not tech_sub.subscription_id:
            tech_sub.subscription_id = sub_id
        tech_sub.amount = amount
        activate_technology_subscription(tech_sub, renew=True)

        # Delete the token so it can't be reused
        cache.delete(cache_key)

        logger.info(
            f"Payment confirmed for {request.user.username}: {technology.name} "
            f"(₹{amount}) via {payment_method}"
        )

        # Map payment method codes to display labels
        METHOD_LABELS = {
            "card": "Credit/Debit Card",
            "credit_card": "Credit Card",
            "debit_card": "Debit Card",
            "upi": "UPI",
            "netbanking": "Net Banking",
            "wallet": "Wallet",
        }
        method_label = METHOD_LABELS.get(payment_method, "Online Payment")

        # Send subscription + invoice emails
        try:
            send_notification_email.delay(
                subject=f"FixitLab Subscription Confirmed - {technology.name}",
                to_email=request.user.email,
                template="emails/subscription_confirmation.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "technology": technology.name,
                    "plan_name": "Technology Access",
                    "amount": f"₹{amount}",
                    "expiry_date": "Lifetime",
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                    "subscription_id": sub_id,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send subscription email: {e}")

        try:
            send_notification_email.delay(
                subject=f"[ADMIN] New Subscription - {technology.name} - {request.user.username}",
                to_email=settings.PAYMENT_EMAIL,
                template="emails/subscription_admin_notification.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "email": request.user.email,
                    "technology": technology.name,
                    "plan_name": "Technology Access",
                    "amount": f"₹{amount}",
                    "subscription_id": sub_id,
                    "payment_date": timezone.now().strftime("%B %d, %Y"),
                    "payment_method": method_label,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send admin email: {e}")

        try:
            send_notification_email.delay(
                subject=f"FixitLab Invoice — {technology.name} Subscription",
                to_email=request.user.email,
                template="emails/subscription_invoice.html",
                context={
                    "username": request.user.get_full_name() or request.user.username,
                    "email": request.user.email,
                    "technology": technology.name,
                    "plan_name": "Technology Access — Lifetime",
                    "amount": f"₹{amount}",
                    "subscription_id": sub_id,
                    "invoice_date": timezone.now().strftime("%B %d, %Y"),
                    "invoice_number": f"INV-{sub_id}",
                    "payment_method": method_label,
                    "billing_period": "Lifetime",
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                },
            )
        except Exception as e:
            logger.error(f"Failed to send invoice email: {e}")

        try:
            create_in_app_notification.delay(
                user_id=request.user.id,
                notification_type="system",
                title=f"Subscribed to {technology.name}",
                message=f"Payment of ₹{amount} confirmed via {method_label}. Subscription ID: {sub_id}. You now have full access to all {technology.name} scenarios.",
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

        return Response({
            "subscription_id": sub_id,
            "technology": technology.name,
            "amount": str(amount),
            "is_active": True,
            "payment_verified": True,
            "payment_method": method_label,
        }, status=http_status.HTTP_201_CREATED)


class CurrencyRateView(APIView):
    """Get current exchange rate and convert prices."""
    permission_classes = [AllowAny]

    def get(self, request):
        from common.currency import get_usd_to_inr_rate, get_price_in_currency

        currency = request.query_params.get("currency", "INR").upper()
        amount = request.query_params.get("amount", "0")

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0

        rate = get_usd_to_inr_rate()

        result = {
            "exchange_rate": float(rate),
            "default_currency": settings.DEFAULT_CURRENCY,
            "requested_currency": currency,
        }

        if amount > 0:
            result["conversion"] = get_price_in_currency(amount, currency)

        return Response(result)


class UserInvoicesView(APIView):
    """List downloadable invoices for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .invoice_service import backfill_invoices_for_user, invoice_list_payload

        backfill_invoices_for_user(request.user)
        invoices = (
            request.user.subscription_invoices.all()
            .select_related("payment_transaction")
            .order_by("-created_at")[:100]
        )
        return Response({"invoices": [invoice_list_payload(inv) for inv in invoices]})


class InvoiceDownloadView(APIView):
    """Download invoice HTML (user owns invoice or admin)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        from django.http import HttpResponse
        from .models import SubscriptionInvoice
        from .invoice_service import render_invoice_html

        if request.user.is_staff:
            invoice = get_object_or_404(SubscriptionInvoice.objects.select_related("user"), pk=invoice_id)
        else:
            invoice = get_object_or_404(
                SubscriptionInvoice.objects.select_related("user"),
                pk=invoice_id,
                user=request.user,
            )

        html = render_invoice_html(invoice)
        filename = f"{invoice.invoice_number}.html"
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class RazorpayRefundView(APIView):
    """
    Admin-only: issue a partial or full refund for a Razorpay payment.

    POST /api/billing/razorpay/refund/
    Body: { "payment_id": "pay_xxx", "amount": 499 }   (amount in INR)

    PRODUCTION_AUDIT FIN-02 — hardened:
      * The transaction row is locked with ``select_for_update`` inside a single
        ``transaction.atomic()`` so two concurrent refunds (double-click / two
        admins) are serialised — the second sees the first's effect.
      * Cumulative refunds can NEVER exceed the captured ``amount``: the ceiling
        is checked against ``amount - refunded_amount`` under the lock, and
        ``refunded_amount`` is bumped before the row is released.
      * All money math is :class:`~decimal.Decimal` (no float rounding of paise).
      * Idempotent: an explicit/derived idempotency key is sent to Razorpay (the
        gateway dedupes a retried refund), the Razorpay ``refund.id`` is persisted
        in ``gateway_response['refunds']``, and a refund whose id we've already
        recorded is treated as a no-op success rather than refunding again.
    """
    permission_classes = [IsAdminUser]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        from django.db import transaction as db_transaction
        from .models import PaymentTransaction

        payment_id = (request.data.get("payment_id") or "").strip()
        amount_inr = request.data.get("amount")
        # Optional client-supplied idempotency key; otherwise derive a stable one
        # from (payment_id, amount) so an identical retry hits the same Razorpay
        # refund instead of creating a second one.
        idem_key = (request.data.get("idempotency_key") or "").strip()

        if not payment_id:
            return Response(
                {"error": "payment_id is required"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if amount_inr is None or amount_inr == "":
            return Response(
                {"error": "amount is required (in INR)"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Decimal paise — never float. Quantise to whole paise.
        try:
            amount_dec = Decimal(str(amount_inr))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid amount"}, status=http_status.HTTP_400_BAD_REQUEST)
        if amount_dec <= 0:
            return Response({"error": "Amount must be positive"}, status=http_status.HTTP_400_BAD_REQUEST)
        amount_paise = int((amount_dec * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response(
                {"error": "Razorpay is not configured"},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not idem_key:
            idem_key = hashlib.sha256(
                f"refund-{payment_id}-{amount_paise}".encode()
            ).hexdigest()

        try:
            import razorpay
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            # Everything below is serialised per-transaction under a row lock so
            # the ceiling check and the refund issuance can't interleave.
            with db_transaction.atomic():
                tx = (
                    PaymentTransaction.objects.select_for_update()
                    .filter(gateway_payment_id=payment_id)
                    .first()
                )
                if not tx:
                    return Response(
                        {"error": "No transaction found for this payment ID"},
                        status=http_status.HTTP_404_NOT_FOUND,
                    )
                if tx.status not in ("success", "refunded"):
                    return Response(
                        {"error": "Only a captured/successful payment can be refunded"},
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )

                # Idempotency: if this exact idempotency key already produced a
                # refund, return it without calling the gateway again.
                gw = tx.gateway_response if isinstance(tx.gateway_response, dict) else {}
                existing_refunds = gw.get("refunds") or []
                for r in existing_refunds:
                    if r.get("idempotency_key") and r["idempotency_key"] == idem_key:
                        return Response({
                            "refund_id": r.get("id"),
                            "payment_id": payment_id,
                            "amount_inr": str((Decimal(str(r.get("amount", 0))) / 100)),
                            "status": r.get("status", "processed"),
                            "already_refunded": True,
                        }, status=http_status.HTTP_200_OK)

                # Ceiling: cumulative refunds may never exceed the captured amount.
                captured_paise = int((tx.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                already_paise = int((tx.refunded_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if amount_paise > captured_paise - already_paise:
                    return Response(
                        {
                            "error": "Refund exceeds refundable amount",
                            "captured_inr": str(tx.amount),
                            "already_refunded_inr": str(tx.refunded_amount),
                            "refundable_inr": str(tx.amount - tx.refunded_amount),
                        },
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )

                # Issue the refund. Pass idempotency so a gateway-level retry is
                # deduped by Razorpay itself.
                refund = client.payment.refund(
                    payment_id,
                    {
                        "amount": amount_paise,
                        "notes": {"by": request.user.username},
                    },
                    headers={"X-Razorpay-Idempotency": idem_key},
                )

                # Persist the refund id + bump cumulative refunded amount.
                existing_refunds.append({
                    "id": refund.get("id", ""),
                    "amount": amount_paise,
                    "idempotency_key": idem_key,
                    "status": refund.get("status", ""),
                    "by": request.user.username,
                })
                gw["refunds"] = existing_refunds
                tx.gateway_response = gw
                tx.refunded_amount = (tx.refunded_amount or Decimal("0")) + amount_dec
                # Mark fully refunded only when the whole captured amount is back.
                if tx.refunded_amount >= tx.amount:
                    tx.status = "refunded"
                tx.save(update_fields=["gateway_response", "refunded_amount", "status"])

            logger.info(
                "Refund issued by admin %s: payment_id=%s amount=₹%s refund_id=%s",
                request.user.username, payment_id, amount_dec, refund.get("id", ""),
            )
            return Response({
                "refund_id": refund.get("id"),
                "payment_id": payment_id,
                "amount_inr": str(amount_dec),
                "status": refund.get("status"),
            }, status=http_status.HTTP_201_CREATED)

        except Exception as e:
            # Log the detail server-side; do not echo the raw gateway/SDK
            # exception text back to the client (may leak internals).
            logger.error(f"Razorpay refund failed for {payment_id}: {e}")
            return Response(
                {"error": "Refund failed. Please check the payment ID and try again, or contact support."},
                status=http_status.HTTP_502_BAD_GATEWAY,
            )
