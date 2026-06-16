"""
Production-ready Payment Service.

Handles:
- Payment gateway abstraction (Razorpay, Stripe)
- Idempotency key generation & duplicate prevention
- Server-side payment verification
- Transaction logging
- Error handling & alerts
"""

import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import razorpay
import stripe

from .models import PaymentTransaction, TechnologySubscription, Subscription, Plan

logger = logging.getLogger(__name__)


class PaymentServiceException(Exception):
    """Custom exception for payment service errors."""
    pass


class PaymentService:
    """Abstraction layer for payment gateways."""

    def __init__(self, user, amount, currency="INR", payment_method="razorpay"):
        """Initialize payment service."""
        self.user = user
        self.amount = Decimal(str(amount))
        self.currency = currency
        self.payment_method = payment_method
        self.transaction = None

    def create_transaction(self, tech_subscription=None, plan=None):
        """Create payment transaction record with idempotency key."""
        if not tech_subscription and not plan:
            raise PaymentServiceException("Must provide tech_subscription or plan")

        # Generate idempotency key
        idempotency_key = PaymentTransaction.generate_idempotency_key(
            self.user.id, self.amount, self.currency
        )

        # Check for existing transaction (idempotency)
        existing = PaymentTransaction.objects.filter(
            idempotency_key=idempotency_key,
            status="success"
        ).first()
        
        if existing:
            logger.warning(f"Duplicate payment attempt detected for user {self.user.id}")
            return existing

        # Create new transaction
        self.transaction = PaymentTransaction.objects.create(
            user=self.user,
            amount=self.amount,
            currency=self.currency,
            payment_method=self.payment_method,
            status="pending",
            idempotency_key=idempotency_key,
            tech_subscription=tech_subscription,
            plan=plan,
        )
        logger.info(f"Created transaction {self.transaction.id} for user {self.user.id}")
        return self.transaction

    def create_razorpay_order(self, tech_subscription=None, plan=None, description=""):
        """Create Razorpay order."""
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise PaymentServiceException("Razorpay is not configured")

        # Create transaction first
        transaction = self.create_transaction(tech_subscription, plan)

        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            # Amount in paise (smallest currency unit)
            amount_paise = int(self.amount * 100)

            order_data = {
                "amount": amount_paise,
                "currency": self.currency,
                "receipt": f"txn-{transaction.id}",
                "notes": {
                    "user_id": str(self.user.id),
                    "user_email": self.user.email,
                    "transaction_id": str(transaction.id),
                    "type": "tech_subscription" if tech_subscription else "plan_upgrade",
                }
            }

            order = client.order.create(data=order_data)
            transaction.gateway_order_id = order["id"]
            transaction.gateway_response = order
            transaction.status = "processing"
            transaction.save(update_fields=["gateway_order_id", "gateway_response", "status"])

            logger.info(f"Created Razorpay order {order['id']} for transaction {transaction.id}")

            return {
                "transaction_id": str(transaction.id),
                "order_id": order["id"],
                "key_id": settings.RAZORPAY_KEY_ID,
                "amount": float(self.amount),
                "currency": self.currency,
                "user_email": self.user.email,
            }

        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            transaction.mark_failed(str(e))
            raise PaymentServiceException(f"Failed to create payment order: {str(e)}")

    def verify_razorpay_payment(self, payment_id, order_id, signature):
        """Verify Razorpay payment signature (server-side)."""
        if not settings.RAZORPAY_KEY_SECRET:
            raise PaymentServiceException("Razorpay is not configured")

        try:
            # Use Razorpay client utility for signature verification to avoid
            # any manual HMAC implementation bugs.
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            try:
                client.utility.verify_payment_signature({
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                })
            except razorpay.errors.SignatureVerificationError:
                logger.error(f"Invalid Razorpay signature for payment {payment_id}")
                return False, "Invalid payment signature"

            # Get transaction with select_for_update to prevent race conditions
            # between concurrent verify calls for the same order.
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                try:
                    transaction = PaymentTransaction.objects.select_for_update(
                        nowait=False
                    ).get(
                        gateway_order_id=order_id,
                        user=self.user
                    )
                except PaymentTransaction.DoesNotExist:
                    logger.error(f"Transaction not found for order {order_id}")
                    return False, "Transaction not found"

                # Idempotency: if already verified, skip re-activation
                if transaction.status == "success":
                    logger.info(f"Payment {payment_id} already verified for tx {transaction.id}")
                    return True, "Payment already verified"

                # Fetch payment details from Razorpay — must succeed; do not
                # fall through silently if the fetch raises.
                try:
                    payment = client.payment.fetch(payment_id)
                except Exception as fetch_err:
                    logger.error(f"Razorpay payment.fetch failed for {payment_id}: {fetch_err}")
                    raise PaymentServiceException(
                        f"Could not retrieve payment details from Razorpay: {fetch_err}"
                    )

                # Validate payment amount and currency
                if payment.get("amount") != int(transaction.amount * 100):
                    logger.error(f"Amount mismatch for payment {payment_id}")
                    return False, "Amount mismatch"

                if payment.get("currency") != transaction.currency:
                    logger.error(f"Currency mismatch for payment {payment_id}")
                    return False, "Currency mismatch"

                if payment.get("status") != "captured":
                    logger.warning(f"Payment not captured: {payment.get('status')}")
                    return False, f"Payment status: {payment.get('status')}"

                # Mark transaction as successful
                transaction.mark_success(
                    gateway_payment_id=payment_id,
                    gateway_response=payment
                )

                # CRITICAL: Activate subscription ONLY after verification
                self._activate_subscription(transaction)

            logger.info(f"Payment verified successfully for transaction {transaction.id}")
            return True, "Payment verified"

        except PaymentServiceException:
            raise
        except Exception as e:
            logger.error(f"Razorpay verification failed: {e}")
            raise PaymentServiceException(f"Verification failed: {str(e)}")

    def create_stripe_checkout(self, plan, return_url=""):
        """Create Stripe checkout session."""
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentServiceException("Stripe is not configured")

        try:
            transaction = self.create_transaction(plan=plan)
            stripe.api_key = settings.STRIPE_SECRET_KEY

            session = stripe.checkout.Session.create(
                customer_email=self.user.email,
                payment_method_types=["card"],
                line_items=[{
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}&success=true",
                cancel_url=f"{return_url}?cancelled=true",
                metadata={
                    "user_id": str(self.user.id),
                    "plan_code": plan.code,
                    "transaction_id": str(transaction.id),
                },
            )

            transaction.gateway_order_id = session.id
            transaction.status = "processing"
            transaction.save(update_fields=["gateway_order_id", "status"])

            return {
                "transaction_id": str(transaction.id),
                "checkout_url": session.url,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout failed: {e}")
            raise PaymentServiceException(f"Stripe error: {str(e)}")

    def _activate_subscription(self, transaction):
        """Activate subscription after payment verification."""
        from .subscription_utils import activate_technology_subscription, subscription_expires_at
        from .razorpay_fulfillment import fulfill_technology_subscription, technology_id_from_transaction
        from apps.question_bank.models import Technology

        if transaction.tech_subscription:
            sub = transaction.tech_subscription
            activate_technology_subscription(sub, renew=True)
            logger.info(f"Activated tech subscription {sub.id} until {sub.expires_at}")

        elif transaction.plan:
            subscription = Subscription.objects.get_or_create(
                user=self.user,
                defaults={"plan": transaction.plan, "is_active": True}
            )[0]
            subscription.plan = transaction.plan
            subscription.is_active = True
            subscription.started_at = timezone.now()
            subscription.expires_at = subscription_expires_at()
            subscription.save(update_fields=["plan", "is_active", "started_at", "expires_at"])
            logger.info(f"Upgraded user {self.user.id} to plan {transaction.plan.code}")

        else:
            tech_id = technology_id_from_transaction(transaction)
            if tech_id:
                try:
                    technology = Technology.objects.get(id=tech_id, is_active=True)
                    fulfill_technology_subscription(
                        user=transaction.user,
                        technology=technology,
                        amount=int(transaction.amount),
                        razorpay_payment_id=transaction.gateway_payment_id or "",
                        transaction=transaction,
                    )
                except Technology.DoesNotExist:
                    logger.warning("Technology %s not found for tx %s", tech_id, transaction.id)
            else:
                from .razorpay_fulfillment import (
                    fulfill_interview_plan_payment,
                    plan_code_from_transaction,
                    product_type_from_transaction,
                )
                if product_type_from_transaction(transaction) == "interview":
                    plan_code = plan_code_from_transaction(transaction)
                    if plan_code:
                        try:
                            fulfill_interview_plan_payment(
                                user=transaction.user,
                                plan_code=plan_code,
                                razorpay_payment_id=transaction.gateway_payment_id or "",
                                transaction=transaction,
                            )
                        except ValueError as exc:
                            logger.warning("Interview fulfillment failed tx %s: %s", transaction.id, exc)

        try:
            from .invoice_service import create_invoice_for_transaction
            create_invoice_for_transaction(transaction)
        except Exception as e:
            logger.warning(f"Invoice creation failed for tx {transaction.id}: {e}")
            # Queue a Celery retry so the user always receives a receipt.
            try:
                from .tasks import retry_invoice_creation
                retry_invoice_creation.apply_async(
                    args=[str(transaction.id)],
                    countdown=60,  # retry after 60 seconds
                )
                logger.info(
                    "Queued invoice retry for tx %s", transaction.id
                )
            except Exception as task_err:
                logger.error(
                    "Could not queue invoice retry for tx %s: %s",
                    transaction.id, task_err,
                )

    def check_gateway_configured(self):
        """Check if any payment gateway is configured."""
        razorpay_ok = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        stripe_ok = bool(settings.STRIPE_SECRET_KEY)
        return {"razorpay": razorpay_ok, "stripe": stripe_ok}
