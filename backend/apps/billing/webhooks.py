"""
Stripe webhook handlers — delegated to StripeWebhookView in views.py.

These standalone functions are kept for backwards compatibility and can be
called from management commands or Celery tasks if needed.
"""
import logging
from .models import Plan, Subscription
from .services import get_user_subscription

logger = logging.getLogger(__name__)


def handle_payment_success(payload):
    """
    Handle successful payment — upgrade user's plan.
    Called after Stripe checkout.session.completed.
    """
    user_id = payload.get("user_id")
    plan_code = payload.get("plan_code")
    stripe_subscription_id = payload.get("stripe_subscription_id", "")

    if not user_id or not plan_code:
        logger.error(f"Missing data in payment payload: {payload}")
        return False

    try:
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User = get_user_model()
        user = User.objects.get(id=int(user_id))
        plan = Plan.objects.get(code=plan_code)

        subscription = get_user_subscription(user)
        subscription.plan = plan
        subscription.stripe_subscription_id = stripe_subscription_id
        subscription.is_active = True
        subscription.started_at = timezone.now()
        subscription.save()

        logger.info(f"User {user.username} upgraded to {plan_code}")
        return True

    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        return False


def handle_subscription_cancel(payload):
    """
    Handle subscription cancellation — downgrade to free plan.
    """
    stripe_subscription_id = payload.get("stripe_subscription_id", "")

    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription_id
        )
        free_plan = Plan.objects.get(code="free")
        subscription.plan = free_plan
        subscription.stripe_subscription_id = ""
        subscription.save()
        logger.info(f"User {subscription.user.username} downgraded to free")
        return True
    except Subscription.DoesNotExist:
        logger.warning(f"No subscription for Stripe ID {stripe_subscription_id}")
        return False


