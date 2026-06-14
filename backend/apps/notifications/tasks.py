import logging
from celery import shared_task
from .email import send_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, retry_kwargs={"max_retries": 3})
def send_notification_email(self, subject, to_email, template, context=None):
    """
    Async email sender via Celery.
    Falls back gracefully — never blocks user-facing operations.
    """
    send_email(
        subject=subject,
        to_email=to_email,
        template=template,
        context=context,
    )


@shared_task
def create_in_app_notification(user_id, notification_type, title, message="", metadata=None):
    """
    Create an in-app notification for a user.
    Called from signals/views when events happen (achievements, lab expiry, etc.)
    """
    try:
        from .models import Notification
        Notification.objects.create(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.warning(f"Failed to create notification for user {user_id}: {e}")


@shared_task
def notify_lab_completed(user_id, scenario_title, score, time_taken, hints_used):
    """Send email + in-app notification when a lab is completed."""
    try:
        from django.contrib.auth import get_user_model
        from django.conf import settings
        from .models import NotificationPreference
        User = get_user_model()
        user = User.objects.get(id=user_id)
        prefs = NotificationPreference.get_for_user(user)

        # In-app notification only (no email — avoids spam)
        if prefs.should_notify_inapp("system"):
            create_in_app_notification(
                user_id=user_id,
                notification_type="system",
                title=f"Challenge Solved: {scenario_title}",
                message=f"Score: {score} | Time: {time_taken}",
                metadata={"score": score, "scenario": scenario_title},
            )
    except Exception as e:
        logger.warning(f"Failed to send lab completion notification: {e}")


@shared_task
def notify_achievement_earned(user_id, achievement_key, achievement_name):
    """Send email + in-app notification when an achievement is earned."""
    try:
        from django.contrib.auth import get_user_model
        from django.conf import settings
        from .models import NotificationPreference
        User = get_user_model()
        user = User.objects.get(id=user_id)
        prefs = NotificationPreference.get_for_user(user)

        ACHIEVEMENT_ICONS = {
            "first_solve": "🎯", "speed_demon": "⚡", "no_hints": "🧠",
            "perfect_score": "💎", "streak_3": "🔥", "streak_7": "🔥🔥",
            "streak_30": "🔥🔥🔥", "easy_master": "🥉", "medium_master": "🥈",
            "hard_master": "🥇", "ten_solves": "🏅", "fifty_solves": "🏆",
            "hundred_solves": "👑",
        }
        ACHIEVEMENT_DESCS = {
            "first_solve": "You solved your first challenge!",
            "speed_demon": "Solved in under 25% of the time limit",
            "no_hints": "Solved without using any hints",
            "perfect_score": "Achieved a near-perfect score",
            "streak_3": "Solved 3 challenges in a row",
            "streak_7": "Solved 7 challenges in a row",
            "streak_30": "Solved 30 challenges in a row",
            "ten_solves": "Solved 10 total challenges",
            "fifty_solves": "Solved 50 total challenges",
            "hundred_solves": "Solved 100 total challenges",
        }

        # In-app notification
        if prefs.should_notify_inapp("achievement"):
            create_in_app_notification(
                user_id=user_id,
                notification_type="achievement",
                title=f"Achievement: {achievement_name}",
                message=ACHIEVEMENT_DESCS.get(achievement_key, ""),
                metadata={"achievement": achievement_key},
            )

        # Email
        if prefs.should_email("achievement"):
            send_email(
                subject=f"FixitLab: Achievement Unlocked — {achievement_name}!",
                to_email=user.email,
                template="emails/achievement.html",
                context={
                    "username": user.username,
                    "achievement_name": achievement_name,
                    "achievement_icon": ACHIEVEMENT_ICONS.get(achievement_key, "🏆"),
                    "achievement_description": ACHIEVEMENT_DESCS.get(achievement_key, ""),
                    "dashboard_url": f"{settings.FRONTEND_URL}/achievements",
                },
            )
    except Exception as e:
        logger.warning(f"Failed to send achievement notification: {e}")


@shared_task
def send_payment_error_notification(user_id, email, technology_name, error_message, order_id=None):
    """
    Send email to both user and tech support when payment fails.
    Called when payment gateway errors occur.
    """
    try:
        from django.conf import settings
        from django.utils import timezone
        
        # Email to user
        try:
            send_email(
                subject="FixitLab: Payment Failed — We're Here to Help",
                to_email=email,
                template="emails/payment_error.html",
                context={
                    "technology_name": technology_name,
                    "error_message": error_message,
                    "order_id": order_id or "N/A",
                    "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "support_email": settings.SUPPORT_EMAIL,
                    "support_url": f"{settings.FRONTEND_URL}/support",
                },
            )
        except Exception as e:
            logger.error(f"Failed to send payment error email to user {user_id}: {e}")
        
        # Email to tech support
        try:
            support_email = getattr(settings, "SUPPORT_EMAIL", "fixitlab.techsupport@gmail.com")
            if support_email:
                send_email(
                    subject="[URGENT] Payment Error Report",
                    to_email=support_email,
                    template="emails/payment_error_admin.html",
                    context={
                        "user_id": user_id,
                        "user_email": email,
                        "technology_name": technology_name,
                        "error_message": error_message,
                        "order_id": order_id or "N/A",
                        "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "admin_url": f"{settings.FRONTEND_URL}/admin/payments",
                    },
                )
        except Exception as e:
            logger.error(f"Failed to send payment error alert to tech support: {e}")
            
    except Exception as e:
        logger.error(f"Payment error notification failed: {e}")
