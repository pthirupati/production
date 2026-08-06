import logging
from celery import shared_task
from .email import send_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, retry_kwargs={"max_retries": 3})
def send_notification_email(self, subject, to_email, template, context=None, headers=None):
    """
    Async email sender via Celery (same path as subscription/invoice emails).
    Uses Gmail API → SendGrid → SMTP via notifications.email.send_email.
    """
    from .idempotency import already_delivered, idempotency_key, mark_delivered, message_id_for

    # Retries re-run with the arguments serialised at enqueue, so this key is stable
    # across them while a genuinely new message produces a different one (audit
    # Z6-16).
    key = idempotency_key(subject, to_email, template, context)
    if already_delivered(key):
        logger.info(
            "Skipping duplicate send to %s (template=%s) — already accepted by the "
            "provider on an earlier attempt",
            to_email, template,
        )
        return True

    # A retry inside the ambiguous window (provider accepted, then the connection
    # timed out) reuses the Message-ID of the send that may already have arrived, so
    # clients that de-duplicate on it collapse the two. Set only when the caller has
    # not supplied one.
    headers = dict(headers or {})
    headers.setdefault("Message-ID", message_id_for(key))

    ok = send_email(
        subject=subject,
        to_email=to_email,
        template=template,
        context=context,
        headers=headers,
    )
    if not ok:
        raise RuntimeError(f"Email delivery failed for {to_email} (template={template})")
    mark_delivered(key)
    return True


@shared_task
def create_in_app_notification(user_id, notification_type, title, message="", metadata=None):
    """
    Create an in-app notification for a user.
    Called from signals/views when events happen (achievements, lab expiry, etc.)
    """
    try:
        from django.contrib.auth import get_user_model

        from .email_helpers import deliver_inapp_notification

        user = get_user_model().objects.filter(id=user_id).first()
        if user is None:
            return False
        # Honours should_notify_inapp — this generic task used to write straight to
        # the table, so it ignored the very preference three sibling tasks checked.
        deliver_inapp_notification(user, notification_type, title, message, metadata)
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

        # In-app notification
        if prefs.should_notify_inapp("system"):
            create_in_app_notification(
                user_id=user_id,
                notification_type="system",
                title=f"Challenge Solved: {scenario_title}",
                message=f"Score: {score} | Time: {time_taken}",
                metadata={"score": score, "scenario": scenario_title},
            )

        from .email_helpers import queue_user_email

        queue_user_email(
            user,
            subject=f"FixitLab: Challenge Solved — {scenario_title}",
            template="emails/lab_completed.html",
            context={
                "username": user.username,
                "scenario_title": scenario_title,
                "score": score,
                "time_taken": time_taken,
                "hints_used": hints_used,
                "dashboard_url": f"{settings.FRONTEND_URL}/dashboard",
            },
            email_type="lab_completed",
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
            from .email_helpers import queue_user_email

            queue_user_email(
                user,
                subject=f"FixitLab: Achievement Unlocked — {achievement_name}!",
                template="emails/achievement.html",
                context={
                    "username": user.username,
                    "achievement_name": achievement_name,
                    "achievement_icon": ACHIEVEMENT_ICONS.get(achievement_key, "🏆"),
                    "achievement_description": ACHIEVEMENT_DESCS.get(achievement_key, ""),
                    "dashboard_url": f"{settings.FRONTEND_URL}/achievements",
                },
                email_type="achievement",
            )
    except Exception as e:
        logger.warning(f"Failed to send achievement notification: {e}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, retry_kwargs={"max_retries": 3})
def send_lab_completion_notification(self, user_id, scenario_id, score, time_seconds):
    """
    Send an email notification when a user passes lab validation.
    Records the send in EmailLog and respects user notification preferences.
    """
    try:
        from django.contrib.auth import get_user_model
        from django.conf import settings
        from apps.question_bank.models import Scenario
        from .models import NotificationPreference, EmailLog

        User = get_user_model()
        user = User.objects.get(id=user_id)
        scenario = Scenario.objects.get(id=scenario_id)

        prefs = NotificationPreference.get_for_user(user)

        # In-app notification
        if prefs.should_notify_inapp("system"):
            create_in_app_notification.delay(
                user_id=user_id,
                notification_type="system",
                title=f"Challenge Solved: {scenario.title}",
                message=f"Score: {score} | Time: {time_seconds}s",
                metadata={"score": score, "scenario_id": scenario_id, "scenario_title": scenario.title},
            )

        # Email — respect user preference for lab_completed
        if prefs.should_email("lab_completed"):
            minutes = time_seconds // 60
            seconds = time_seconds % 60
            time_display = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

            subject = f"You solved {scenario.title}!"
            to_email = user.email
            template = "emails/lab_completed.html"
            context = {
                "username": user.get_full_name() or user.username,
                "scenario_title": scenario.title,
                "score": score,
                "time_taken": time_seconds,
                "time_display": time_display,
                "hints_used": 0,
                "dashboard_url": f"{settings.FRONTEND_URL}/dashboard",
            }

            ok = send_email(subject=subject, to_email=to_email, template=template, context=context)
            status_val = "sent" if ok else "failed"
            EmailLog.objects.create(
                subject=subject,
                to_email=to_email,
                template=template,
                status=status_val,
            )

            if not ok:
                raise RuntimeError(f"Email delivery failed for {to_email}")
    except Exception as e:
        logger.warning(f"Failed to send lab completion notification for user {user_id}: {e}")
        raise


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
                    "support_url": f"{settings.FRONTEND_URL}/contact",
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
                        "admin_url": f"{settings.FRONTEND_URL}/admin/subscriptions",
                    },
                )
        except Exception as e:
            logger.error(f"Failed to send payment error alert to tech support: {e}")
            
    except Exception as e:
        logger.error(f"Payment error notification failed: {e}")
