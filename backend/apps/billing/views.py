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

import stripe
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q as models_Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
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
        razorpay_ready = "ready" if razorpay_configured else "down"
        stripe_ready = "ready" if stripe_configured else "down"

        banner_message = None
        if not razorpay_configured and not stripe_configured:
            banner_message = (
                "Payment gateway is currently unavailable. "
                "Free scenarios still work. Paid subscriptions will open once billing is configured."
            )
        elif not razorpay_configured:
            banner_message = "Razorpay unavailable — international card payments via Stripe are available."

        return Response({
            "razorpay_configured": razorpay_configured,
            "stripe_configured": stripe_configured,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID if razorpay_configured else None,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY if stripe_configured else None,
            "status": razorpay_ready if razorpay_configured else stripe_ready,
            "available": razorpay_configured or stripe_configured,
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
            discounted, coupon = apply_coupon_to_amount(code, original_amount)
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
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        from apps.question_bank.models import Technology
        from apps.notifications.tasks import send_payment_error_notification

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
                amount, coupon_applied = apply_coupon_to_amount(coupon_code, amount)
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
    throttle_classes = [BillingRateThrottle]

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
            return Response(
                {"error": "Payment verification failed — amount or order mismatch."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Create verified subscription
        sub_id = TechnologySubscription.generate_subscription_id(
            technology.name, request.user.username
        )

        tech_sub = TechnologySubscription.objects.create(
            user=request.user,
            technology=technology,
            subscription_id=sub_id,
            amount=amount,
            is_active=True,
            payment_verified=True,
        )

        if coupon_applied:
            from .coupon_service import redeem_coupon
            redeem_coupon(coupon_applied)

        logger.info(f"Payment verified for user {request.user.username}: {razorpay_payment_id} — {technology.name}")

        # Send all emails (confirmation + admin + invoice)
        CreateRazorpayOrderView()._send_subscription_emails(
            request.user, technology, sub_id, amount
        )

        return Response({
            "subscription_id": sub_id,
            "technology": technology.name,
            "amount": str(amount),
            "coupon_applied": coupon_applied.code if coupon_applied else None,
            "is_active": True,
            "payment_verified": True,
            "razorpay_payment_id": razorpay_payment_id,
        }, status=http_status.HTTP_201_CREATED)

    def _verify_signature(self, order_id, payment_id, signature):
        """Verify Razorpay payment signature using HMAC SHA256."""
        if not settings.RAZORPAY_KEY_SECRET:
            logger.warning("Razorpay key secret not configured — skipping verification")
            return True  # Skip verification in demo mode

        try:
            message = f"{order_id}|{payment_id}"
            expected_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def _verify_payment_with_gateway(self, order_id, payment_id, expected_amount_inr):
        """Fetch payment from Razorpay and validate order + amount server-side."""
        if not settings.RAZORPAY_KEY_SECRET or not settings.RAZORPAY_KEY_ID:
            return True  # demo mode

        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            payment = client.payment.fetch(payment_id)
            if payment.get("order_id") != order_id:
                return False
            if int(payment.get("amount", 0)) != int(expected_amount_inr) * 100:
                return False
            if payment.get("status") not in ("captured", "authorized"):
                return False
            return True
        except Exception as e:
            logger.error(f"Razorpay payment fetch failed: {e}")
            return False


class TechnologySubscribeView(APIView):
    """Subscribe to a specific technology (legacy / demo fallback)."""
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

        # Check if already subscribed (active and not expired)
        from .subscription_utils import activate_technology_subscription, is_tech_subscription_active

        existing = TechnologySubscription.objects.filter(
            user=request.user, technology=technology
        ).order_by("-created_at").first()
        if existing and is_tech_subscription_active(existing):
            return Response(
                {"error": "Already subscribed to this technology", "subscription_id": existing.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Determine price from technology (server-side — never trust client)
        amount = getattr(technology, 'price', 0) or 0

        if existing:
            # Renewal of expired/inactive subscription
            tech_sub = existing
            tech_sub.amount = amount
            activate_technology_subscription(tech_sub, renew=True)
            sub_id = tech_sub.subscription_id
        else:
            # Generate unique subscription ID
            sub_id = TechnologySubscription.generate_subscription_id(
                technology.name, request.user.username
            )
            tech_sub = TechnologySubscription.objects.create(
                user=request.user,
                technology=technology,
                subscription_id=sub_id,
                amount=amount,
            )
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from common.currency import get_price_in_currency, get_usd_to_inr_rate

        if not request.user.is_staff:
            return Response(
                {"error": "Admin access required"},
                status=http_status.HTTP_403_FORBIDDEN,
            )

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
    throttle_classes = [BillingRateThrottle]

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

        # Check if already subscribed (race condition guard)
        existing = TechnologySubscription.objects.filter(
            user=request.user, technology=technology, is_active=True
        ).first()
        if existing:
            cache.delete(cache_key)
            return Response(
                {"error": "Already subscribed", "subscription_id": existing.subscription_id},
                status=http_status.HTTP_409_CONFLICT,
            )

        amount = token_data["amount"]
        sub_id = TechnologySubscription.generate_subscription_id(
            technology.name, request.user.username
        )

        # Create subscription
        tech_sub = TechnologySubscription.objects.create(
            user=request.user,
            technology=technology,
            subscription_id=sub_id,
            amount=amount,
            is_active=True,
            payment_verified=True,
        )

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

        try:
            invoice = SubscriptionInvoice.objects.select_related("user").get(pk=invoice_id)
        except SubscriptionInvoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=http_status.HTTP_404_NOT_FOUND)

        if invoice.user_id != request.user.id and not request.user.is_staff:
            return Response({"error": "Forbidden"}, status=http_status.HTTP_403_FORBIDDEN)

        html = render_invoice_html(invoice)
        filename = f"{invoice.invoice_number}.html"
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
