"""
Production Payment API Controller.

Endpoints:
- POST /api/billing/status/ — Check if payment gateways are configured
- POST /api/billing/create-order/ — Create Razorpay order
- POST /api/billing/verify-payment/ — Verify payment + activate subscription
- POST /api/billing/webhook/razorpay/ — Razorpay webhook handler
- POST /api/billing/webhook/stripe/ — Stripe webhook handler
"""

import json
import logging
import hmac
import hashlib
from decimal import Decimal
import stripe

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework import status as http_status

from .models import TechnologySubscription, Plan, PaymentTransaction
from .payment_service import PaymentService, PaymentServiceException
from .email_service import EmailAlertService
from .services import get_user_subscription

logger = logging.getLogger(__name__)


class BillingRateThrottle(UserRateThrottle):
    """Rate limit for payment-related endpoints."""
    rate = '30/minute'


class PaymentStatusView(APIView):
    """Check payment gateway configuration."""
    permission_classes = [AllowAny]

    def get(self, request):
        """Check which gateways are configured."""
        try:
            service = PaymentService(user=None, amount=0)
            gateways = service.check_gateway_configured()
        except Exception as exc:
            logger.warning("Payment status check failed: %s", exc)
            return Response({
                "configured": False,
                "message": "Payment gateway status unavailable.",
                "gateways": {"razorpay": False, "stripe": False},
            }, status=http_status.HTTP_200_OK)

        if not any(gateways.values()):
            logger.warning("Payment gateways not configured")
            return Response({
                "configured": False,
                "message": "Payment gateway is not configured. Please contact support.",
                "gateways": gateways,
            }, status=http_status.HTTP_200_OK)

        return Response({
            "configured": True,
            "gateways": gateways,
        })


class CreatePaymentOrderView(APIView):
    """Create payment order (Razorpay)."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        """POST /api/billing/create-order/
        {
            "technology_id": "...",
            "currency": "INR"
        }
        """
        from apps.question_bank.models import Technology

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
            user=request.user,
            technology=technology,
            is_active=True,
            payment_verified=True
        ).first()

        if existing:
            return Response(
                {"error": "You already have access to this technology"},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Get server-side price (CRITICAL: never trust client)
        amount = Decimal(str(getattr(technology, 'price', 0) or 0))
        if amount <= 0:
            return Response(
                {"error": "Price not configured for this technology"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        currency = request.data.get("currency", "INR")

        try:
            # Create tech subscription (pending verification)
            tech_sub = TechnologySubscription.objects.create(
                user=request.user,
                technology=technology,
                amount=amount,
                is_active=False,  # Will activate after payment
                payment_verified=False,
            )

            # Create payment order via service
            service = PaymentService(
                user=request.user,
                amount=amount,
                currency=currency,
                payment_method="razorpay"
            )

            order_data = service.create_razorpay_order(
                tech_subscription=tech_sub,
                description=f"Subscribe to {technology.name}"
            )

            return Response(order_data, status=http_status.HTTP_201_CREATED)

        except PaymentServiceException as e:
            logger.error(str(e))
            EmailAlertService.send_payment_error_alert(
                request.user,
                technology.name,
                str(e),
                request.data
            )
            return Response(
                {"error": str(e)},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception(f"Order creation error: {e}")
            EmailAlertService.send_payment_error_alert(
                request.user,
                technology.name,
                str(e),
                request.data
            )
            return Response(
                {"error": "Failed to create payment order"},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyPaymentView(APIView):
    """Verify payment (server-side) and activate subscription."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        """POST /api/billing/verify-payment/
        {
            "razorpay_order_id": "...",
            "razorpay_payment_id": "...",
            "razorpay_signature": "...",
            "transaction_id": "..."
        }
        """
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")
        transaction_id = request.data.get("transaction_id")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, transaction_id]):
            return Response(
                {"error": "Missing payment verification fields"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get transaction
            transaction = PaymentTransaction.objects.get(
                id=transaction_id,
                user=request.user,
                status__in=["pending", "processing"]
            )

            # Create service with same user/amount/currency
            service = PaymentService(
                user=request.user,
                amount=transaction.amount,
                currency=transaction.currency,
                payment_method="razorpay"
            )
            service.transaction = transaction

            # Verify payment (server-side)
            verified, message = service.verify_razorpay_payment(
                razorpay_payment_id,
                razorpay_order_id,
                razorpay_signature
            )

            if not verified:
                transaction.mark_failed(message)
                EmailAlertService.send_payment_error_alert(
                    request.user,
                    "Technology Subscription",
                    message,
                    request.data
                )
                logger.warning(f"Payment verification failed: {message}")
                return Response(
                    {"error": message},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Send confirmation emails
            if transaction.tech_subscription:
                self._send_subscription_emails(
                    request.user,
                    transaction.tech_subscription.technology,
                    transaction.tech_subscription.subscription_id,
                    transaction.amount
                )

            EmailAlertService.send_payment_success_email(request.user, transaction)

            logger.info(f"Payment verified and subscription activated for user {request.user.id}")

            return Response({
                "success": True,
                "message": "Payment verified successfully",
                "transaction_id": str(transaction.id),
                "subscription_id": str(transaction.tech_subscription.subscription_id) if transaction.tech_subscription else None,
            }, status=http_status.HTTP_200_OK)

        except PaymentTransaction.DoesNotExist:
            return Response(
                {"error": "Transaction not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )
        except PaymentServiceException as e:
            logger.error(str(e))
            EmailAlertService.send_payment_error_alert(
                request.user,
                "Technology Subscription",
                str(e),
                request.data
            )
            return Response(
                {"error": str(e)},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception(f"Payment verification error: {e}")
            EmailAlertService.send_payment_error_alert(
                request.user,
                "Technology Subscription",
                str(e),
                request.data
            )
            return Response(
                {"error": "Verification failed"},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _send_subscription_emails(self, user, technology, sub_id, amount):
        """Send confirmation emails (can be async task later)."""
        try:
            # This would typically be an async task
            from apps.notifications.tasks import send_notification_email
            from django.core.mail import EmailMultiAlternatives

            # User email
            msg_body = f"Welcome! You now have access to {technology.name}"
            msg = EmailMultiAlternatives(
                subject=f"Subscription Confirmed - {technology.name}",
                body=msg_body,
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email]
            )
            msg.send(fail_silently=True)

            # Admin email
            msg_admin = EmailMultiAlternatives(
                subject=f"[NEW SUBSCRIPTION] {technology.name} - {user.email}",
                body=f"User {user.email} subscribed to {technology.name}. Subscription ID: {sub_id}",
                from_email=settings.EMAIL_HOST_USER,
                to=[getattr(settings, 'PAYMENT_EMAIL', settings.PRIMARY_EMAIL)]
            )
            msg_admin.send(fail_silently=True)

        except Exception as e:
            logger.error(f"Failed to send subscription emails: {e}")


class RazorpayWebhookView(APIView):
    """Handle Razorpay webhook events."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        """Razorpay webhook endpoint."""
        try:
            payload = request.body
            signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE", "")

            # Verify webhook signature
            if not self._verify_webhook_signature(payload, signature):
                logger.warning("Invalid Razorpay webhook signature")
                return Response(
                    {"error": "Invalid signature"},
                    status=http_status.HTTP_401_UNAUTHORIZED,
                )

            event = json.loads(payload)
            event_type = event.get("event", "")

            logger.info(f"Razorpay webhook: {event_type}")

            if event_type == "payment.authorized":
                self._handle_payment_authorized(event)
            elif event_type == "payment.failed":
                self._handle_payment_failed(event)
            elif event_type == "payment.captured":
                self._handle_payment_captured(event)

            return Response({"status": "ok"})

        except json.JSONDecodeError:
            logger.error("Invalid webhook payload")
            return Response(
                {"error": "Invalid JSON"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return Response(
                {"error": "Error processing webhook"},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _verify_webhook_signature(self, payload, signature):
        """Verify Razorpay webhook signature."""
        secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "") or settings.RAZORPAY_KEY_SECRET
        if not secret:
            return False

        expected_sig = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_sig)

    def _handle_payment_authorized(self, event):
        """Handle payment.authorized event."""
        try:
            payment_data = event.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payment_data.get("order_id", "")
            payment_id = payment_data.get("id", "")

            transaction = PaymentTransaction.objects.filter(
                gateway_order_id=order_id
            ).first()

            if transaction:
                logger.info(f"Payment authorized: {payment_id}")

        except Exception as e:
            logger.error(f"Error handling payment.authorized: {e}")

    def _handle_payment_failed(self, event):
        """Handle payment.failed event."""
        try:
            payment_data = event.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payment_data.get("order_id", "")
            reason = payment_data.get("vpa", "") or "Payment declined"

            transaction = PaymentTransaction.objects.filter(
                gateway_order_id=order_id
            ).first()

            if transaction:
                transaction.mark_failed(reason)
                logger.warning(f"Payment failed for transaction {transaction.id}: {reason}")

        except Exception as e:
            logger.error(f"Error handling payment.failed: {e}")

    def _handle_payment_captured(self, event):
        """Handle payment.captured event."""
        try:
            payment_data = event.get("payload", {}).get("payment", {}).get("entity", {})
            payment_id = payment_data.get("id", "")
            order_id = payment_data.get("order_id", "")

            # Idempotent handling: find transaction and process only once
            transaction = PaymentTransaction.objects.filter(gateway_order_id=order_id).first()

            if not transaction:
                logger.warning(f"No transaction found for order_id={order_id} (payment_id={payment_id})")
                return

            # Use DB-level locking to prevent concurrent processing
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                tx = PaymentTransaction.objects.select_for_update().get(id=transaction.id)

                # If already successful with same payment id, skip
                if tx.status == 'success' and tx.gateway_payment_id == payment_id:
                    logger.info(f"Duplicate webhook ignored for payment {payment_id}")
                    return

                # Mark as processing to avoid races
                tx.status = 'processing'
                tx.save(update_fields=['status'])

                tx.mark_success(gateway_payment_id=payment_id, gateway_response=payment_data)
                service = PaymentService(
                    user=tx.user,
                    amount=tx.amount,
                    currency=tx.currency,
                    payment_method="razorpay",
                )
                service.transaction = tx
                service._activate_subscription(tx)
                logger.info(f"Payment captured and subscription activated: {payment_id} -> tx {tx.id}")

        except Exception as e:
            logger.error(f"Error handling payment.captured: {e}")


class StripeWebhookView(APIView):
    """Handle Stripe webhook events with signature verification and idempotency."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.error("Stripe webhook secret not configured")
            return Response({"error": "Stripe not configured"}, status=http_status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            event = stripe.Webhook.construct_event(
                payload=payload, sig_header=sig_header, secret=settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.error("Invalid Stripe webhook payload")
            return Response({"error": "Invalid payload"}, status=http_status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            return Response({"error": "Invalid signature"}, status=http_status.HTTP_401_UNAUTHORIZED)

        # Idempotency: use event id
        event_id = event.get('id')
        cache_key = f"stripe_webhook:{event_id}"
        # cache.add returns True only if key was added (not present)
        added = cache.add(cache_key, True, timeout=60 * 60)
        if not added:
            logger.info(f"Duplicate Stripe webhook ignored: {event_id}")
            return Response({"status": "duplicate"})

        event_type = event.get('type')
        logger.info(f"Stripe webhook received: {event_type} (id={event_id})")

        try:
            if event_type == 'checkout.session.completed':
                self._handle_checkout_session_completed(event)
            elif event_type == 'invoice.payment_succeeded':
                self._handle_invoice_payment_succeeded(event)
            # Add more event types as needed

            return Response({"status": "ok"})
        except Exception as e:
            logger.exception(f"Error processing Stripe event {event_id}: {e}")
            return Response({"error": "processing error"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_checkout_session_completed(self, event):
        session = event.get('data', {}).get('object', {})
        session_id = session.get('id')

        if not session_id:
            logger.warning("Stripe session.completed without id")
            return

        transaction = PaymentTransaction.objects.filter(gateway_order_id=session_id).first()
        if not transaction:
            logger.warning(f"No transaction for Stripe session {session_id}")
            return

        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            tx = PaymentTransaction.objects.select_for_update().get(id=transaction.id)
            if tx.status == 'success':
                logger.info(f"Stripe session already processed for tx {tx.id}")
                return

            # Fetch session details from Stripe to validate amounts
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                stripe_session = stripe.checkout.Session.retrieve(session_id)
            except Exception as e:
                logger.error(f"Failed to retrieve Stripe session {session_id}: {e}")
                tx.mark_failed(str(e))
                return

            # Validate amount if available (may be subscription-based)
            amount_total = getattr(stripe_session, 'amount_total', None) or stripe_session.get('amount_total')
            if amount_total is not None:
                # Stripe amount is in cents
                expected = int(tx.amount * 100)
                if int(amount_total) != expected:
                    tx.mark_failed('Amount mismatch')
                    logger.error(f"Stripe amount mismatch for tx {tx.id}: expected {expected}, got {amount_total}")
                    return

            # Mark success and activate subscription
            tx.mark_success(gateway_payment_id=stripe_session.payment_intent or stripe_session.id, gateway_response=stripe_session)
            service = PaymentService(user=tx.user, amount=tx.amount, currency=tx.currency, payment_method='stripe')
            service.transaction = tx
            service._activate_subscription(tx)

    def _handle_invoice_payment_succeeded(self, event):
        invoice = event.get('data', {}).get('object', {})
        invoice_id = invoice.get('id')

        if not invoice_id:
            logger.warning('Stripe invoice.payment_succeeded without id')
            return

        transaction = PaymentTransaction.objects.filter(gateway_order_id=invoice_id).first()
        if not transaction:
            logger.warning(f"No transaction for Stripe invoice {invoice_id}")
            return

        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            tx = PaymentTransaction.objects.select_for_update().get(id=transaction.id)
            if tx.status == 'success':
                logger.info(f"Stripe invoice already processed for tx {tx.id}")
                return

            # Mark success
            tx.mark_success(gateway_payment_id=invoice.get('charge') or invoice_id, gateway_response=invoice)
            service = PaymentService(user=tx.user, amount=tx.amount, currency=tx.currency, payment_method='stripe')
            service.transaction = tx
            service._activate_subscription(tx)
