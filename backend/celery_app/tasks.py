import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def debug_task(self):
    """Simple test task to verify Celery is working."""
    import time
    time.sleep(2)
    return {"task_id": self.request.id, "status": "completed"}


@shared_task
def cleanup_expired_labs():
    """
    Terminate lab sessions that have exceeded their time limit.
    Also cleans up sessions stuck in PROVISIONING for more than 10 minutes.
    Handles Docker containers, AWS EC2 instances, and DigitalOcean droplets.
    Runs every 5 minutes via Celery Beat.
    """
    from apps.labs.models import LabSession
    from apps.labs.provisioner import get_provisioner

    terminated = 0

    # ── 1. Clean up expired RUNNING sessions (iterate in chunks to avoid OOM) ──
    from django.utils import timezone as tz
    now = tz.now()
    # Filter by expires_at for sessions that have it set (new sessions after migration)
    # Fall back to Python check for legacy sessions without expires_at
    sessions_with_expiry = LabSession.objects.filter(
        status="RUNNING", expires_at__lte=now
    ).select_related("scenario", "user").iterator(chunk_size=200)
    for session in sessions_with_expiry:
        logger.info(f"Terminating expired session {session.id} (provider: {session.provider})")
        resource_id = session.container_id or session.instance_id
        if resource_id:
            try:
                provisioner = get_provisioner(session.provider or "docker")
                provisioner.terminate(resource_id, session_id=str(session.id))
            except Exception as e:
                logger.error(f"Error terminating resource: {e}")

        session.status = "EXPIRED"
        session.ended_at = timezone.now()
        session.save()
        terminated += 1

        try:
            from apps.jira_integration.sync import sync_lab_expired
            sync_lab_expired(session)
        except Exception as e:
            logger.warning(f"Jira sync on lab expiry failed: {e}")

        # Notify user about expired lab
        try:
            from apps.notifications.tasks import create_in_app_notification
            from apps.notifications.models import NotificationPreference
            from apps.notifications.email_helpers import queue_user_email
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=session.user_id)
            prefs = NotificationPreference.get_for_user(user)

            if prefs.should_notify_inapp("lab_expired"):
                create_in_app_notification.delay(
                    user_id=session.user_id,
                    notification_type="lab_expired",
                    title=f"Lab Expired: {session.scenario.title}",
                    message=f"Your lab session expired after {session.duration_limit // 60} minutes. You can try again anytime!",
                    metadata={"scenario_slug": session.scenario.slug},
                )

            if prefs.should_email("lab_expired"):
                from django.conf import settings as django_settings

                queue_user_email(
                    user,
                    subject=f"FixitLab: Lab Session Expired — {session.scenario.title}",
                    template="emails/lab_expired.html",
                    context={
                        "username": user.username,
                        "scenario_title": session.scenario.title,
                        "duration_minutes": session.duration_limit // 60,
                        "scenarios_url": f"{django_settings.FRONTEND_URL}/scenarios",
                    },
                    email_type="lab_expired",
                )
        except Exception as e:
            logger.warning(f"Failed to notify user about expired lab: {e}")

    # Legacy sessions without expires_at: fall back to Python check
    legacy_sessions = LabSession.objects.filter(
        status="RUNNING", expires_at__isnull=True
    ).select_related("scenario", "user").iterator(chunk_size=200)
    for session in legacy_sessions:
        if not session.is_expired:
            continue
        logger.info(f"Terminating expired legacy session {session.id} (provider: {session.provider})")
        resource_id = session.container_id or session.instance_id
        if resource_id:
            try:
                provisioner = get_provisioner(session.provider or "docker")
                provisioner.terminate(resource_id, session_id=str(session.id))
            except Exception as e:
                logger.error(f"Error terminating resource: {e}")

        session.status = "EXPIRED"
        session.ended_at = timezone.now()
        session.save()
        terminated += 1

        try:
            from apps.jira_integration.sync import sync_lab_expired
            sync_lab_expired(session)
        except Exception as e:
            logger.warning(f"Jira sync on lab expiry failed: {e}")

        try:
            from apps.notifications.tasks import create_in_app_notification
            from apps.notifications.models import NotificationPreference
            from apps.notifications.email_helpers import queue_user_email
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=session.user_id)
            prefs = NotificationPreference.get_for_user(user)

            if prefs.should_notify_inapp("lab_expired"):
                create_in_app_notification.delay(
                    user_id=session.user_id,
                    notification_type="lab_expired",
                    title=f"Lab Expired: {session.scenario.title}",
                    message=f"Your lab session expired after {session.duration_limit // 60} minutes. You can try again anytime!",
                    metadata={"scenario_slug": session.scenario.slug},
                )

            if prefs.should_email("lab_expired"):
                from django.conf import settings as django_settings

                queue_user_email(
                    user,
                    subject=f"FixitLab: Lab Session Expired — {session.scenario.title}",
                    template="emails/lab_expired.html",
                    context={
                        "username": user.username,
                        "scenario_title": session.scenario.title,
                        "duration_minutes": session.duration_limit // 60,
                        "scenarios_url": f"{django_settings.FRONTEND_URL}/scenarios",
                    },
                    email_type="lab_expired",
                )
        except Exception as e:
            logger.warning(f"Failed to notify user about expired lab: {e}")

    # ── 2. Clean up stuck PROVISIONING sessions (>10 minutes) ──
    stuck_cutoff = timezone.now() - timedelta(minutes=10)
    stuck_sessions = LabSession.objects.filter(
        status="PROVISIONING",
        started_at__lt=stuck_cutoff,
    ).iterator(chunk_size=100)
    stuck_cleaned = 0
    for session in stuck_sessions:
        logger.warning(
            f"Cleaning up stuck PROVISIONING session {session.id} "
            f"(started {session.started_at}, provider: {session.provider})"
        )
        # Terminate any associated cloud resource
        resource_id = session.container_id or session.instance_id
        if resource_id:
            try:
                provisioner = get_provisioner(session.provider or "docker")
                provisioner.terminate(resource_id, session_id=str(session.id))
                logger.info(f"Terminated stuck resource {resource_id}")
            except Exception as e:
                logger.error(f"Error terminating stuck resource {resource_id}: {e}")

        session.status = "FAILED"
        session.ended_at = timezone.now()
        session.instance_id = None
        session.ssh_host = ""
        session.save()
        stuck_cleaned += 1

    logger.info(f"Cleanup: terminated {terminated} expired, {stuck_cleaned} stuck sessions")
    return {"terminated": terminated, "stuck_cleaned": stuck_cleaned}


@shared_task
def cleanup_orphaned_containers():
    """
    Remove Docker containers and cloud instances that don't have a matching active lab session.
    Safety net for resources that weren't cleaned up properly.
    """
    from apps.labs.models import LabSession
    from apps.labs.provisioner import get_provisioner

    results = {}

    # Clean up Docker containers
    try:
        docker_provisioner = get_provisioner("docker")
        docker_cleaned = docker_provisioner.cleanup_expired(max_age_seconds=7200)
        results["docker"] = docker_cleaned
    except Exception as e:
        logger.error(f"Docker cleanup failed: {e}")
        results["docker_error"] = str(e)

    # Clean up AWS EC2 instances (if fully configured)
    try:
        from django.conf import settings
        if (
            getattr(settings, "AWS_ACCESS_KEY_ID", "")
            and getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
            and getattr(settings, "AWS_LAB_SUBNET_ID", "")
            and getattr(settings, "AWS_LAB_SECURITY_GROUP_ID", "")
        ):
            ec2_provisioner = get_provisioner("aws_ec2")
            ec2_cleaned = ec2_provisioner.cleanup_expired(max_age_seconds=7200)
            results["aws_ec2"] = ec2_cleaned
    except Exception as e:
        logger.warning(f"EC2 cleanup skipped: {e}")
        results["aws_ec2_error"] = str(e)

    # Clean up DigitalOcean droplets (if configured)
    try:
        from django.conf import settings
        if getattr(settings, "DO_API_TOKEN", ""):
            do_provisioner = get_provisioner("digitalocean")
            do_cleaned = do_provisioner.cleanup_expired(max_age_seconds=7200)
            results["digitalocean"] = do_cleaned
    except Exception as e:
        logger.error(f"DO cleanup failed: {e}")
        results["digitalocean_error"] = str(e)

    return results


@shared_task
def recalculate_leaderboard():
    """
    Recalculate global leaderboard from progress data.
    Runs hourly via Celery Beat.
    """
    from apps.progress.models import UserScenarioProgress
    from apps.leaderboard.models import LeaderboardEntry
    from django.db.models import Sum, Count
    from django.db import transaction

    # Compute from progress
    rankings = (
        UserScenarioProgress.objects.filter(completed=True)
        .values("user_id")
        .annotate(
            total_score=Sum("best_score"),
            completed_count=Count("id"),
        )
        .order_by("-total_score")
    )

    entries = []
    for rank, data in enumerate(rankings, 1):
        entries.append(LeaderboardEntry(
            user_id=data["user_id"],
            scenario=None,  # Global leaderboard
            score=data["total_score"],
            rank=rank,
        ))

    # Batch upsert: delete old and create new in batches to reduce lock time
    with transaction.atomic():
        LeaderboardEntry.objects.filter(scenario__isnull=True).delete()
        batch_size = 500
        for i in range(0, len(entries), batch_size):
            LeaderboardEntry.objects.bulk_create(entries[i:i + batch_size])
    logger.info(f"Leaderboard recalculated: {len(entries)} entries")
    return {"entries": len(entries)}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def provision_cloud_lab(self, session_id):
    """
    Asynchronously provision an AWS EC2 or DigitalOcean instance for a lab session.
    Called by StartLabView for cloud-based scenarios so the HTTP response returns
    immediately while the instance boots in the background.
    The frontend polls session status, transitioning from PROVISIONING → RUNNING.

    Idempotent: provision() checks for existing instance_id and resumes
    instead of launching a second instance on retry.
    """
    from apps.labs.models import LabSession
    from apps.labs.provisioner import get_provisioner

    try:
        session = LabSession.objects.select_related("scenario", "user").get(
            pk=session_id, status="PROVISIONING"
        )
    except LabSession.DoesNotExist:
        logger.warning(f"provision_cloud_lab: session {session_id} not found or not PROVISIONING")
        return {"status": "skipped", "reason": "session not found or wrong status"}

    infra_type = session.provider or "docker"
    attempt = self.request.retries + 1
    logger.info(
        f"Provisioning cloud lab {session_id} ({infra_type}) for "
        f"{session.user.username} [attempt {attempt}/{self.max_retries + 1}]"
    )

    try:
        provisioner = get_provisioner(infra_type)

        # provision() is idempotent: if session already has instance_id,
        # it resumes that instance instead of launching a new one.
        resource_id, resource_name = provisioner.provision(session)

        # Refresh session from DB — provision() may have saved instance_id already
        session.refresh_from_db()

        if infra_type == "docker":
            session.container_id = resource_id
            session.container_name = resource_name
        else:
            session.instance_id = resource_id

        session.status = "RUNNING"
        session.save()

        # NOTE: attempt counting is done in StartLabView (not here)
        # to avoid double-counting on retries.

        logger.info(f"Cloud lab {session_id} provisioned successfully: {resource_id}")
        return {"status": "running", "resource_id": resource_id}

    except Exception as e:
        logger.error(f"Cloud lab provisioning failed for {session_id}: {e}")

        # Refresh session — provision() may have saved partial state
        session.refresh_from_db()

        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying provision for {session_id} in {self.default_retry_delay}s "
                f"(attempt {attempt}/{self.max_retries + 1})"
            )
            raise self.retry(exc=e)

        # Final failure: clean up any orphaned instance
        if session.instance_id:
            try:
                provisioner = get_provisioner(infra_type)
                provisioner.terminate(session.instance_id, session_id=str(session.id))
                logger.info(f"Cleaned up orphaned instance {session.instance_id}")
            except Exception as te:
                logger.error(f"Failed to clean up instance {session.instance_id}: {te}")

        session.status = "FAILED"
        session.instance_id = None
        session.ssh_host = ""
        session.save()

        # Notify user of failure
        try:
            from apps.notifications.tasks import create_in_app_notification
            create_in_app_notification.delay(
                user_id=session.user_id,
                notification_type="lab_failed",
                title=f"Lab Failed: {session.scenario.title}",
                message="Failed to launch cloud server. Please try again.",
                metadata={"scenario_slug": session.scenario.slug},
            )
        except Exception:
            pass

        return {"status": "failed", "error": str(e)}


@shared_task(
    bind=True,
    name="celery_app.tasks.provision_docker_lab",
    queue="provisioning",
    max_retries=2,
    default_retry_delay=5,
)
def provision_docker_lab(self, session_id: str):
    """Provision a Docker/simulation lab asynchronously."""
    from apps.labs.models import LabSession
    from apps.labs.provisioner import get_provisioner

    try:
        session = LabSession.objects.select_related("scenario").get(id=session_id)
    except LabSession.DoesNotExist:
        logger.error("provision_docker_lab: session %s not found", session_id)
        return

    if session.status not in ("PROVISIONING",):
        logger.info("provision_docker_lab: session %s already in status %s, skipping", session_id, session.status)
        return

    try:
        provisioner = get_provisioner(session.provider or "docker")
        resource_id, resource_name = provisioner.provision(session)
        session.container_id = resource_id
        session.container_name = resource_name
        session.status = "RUNNING"
        session.save(update_fields=["container_id", "container_name", "status"])
        logger.info("provision_docker_lab: session %s running (container %s)", session_id, resource_id)
    except Exception as exc:
        logger.error("provision_docker_lab: provisioning failed for session %s: %s", session_id, exc)
        session.status = "FAILED"
        session.save(update_fields=["status"])
        raise self.retry(exc=exc)


@shared_task
def cleanup_expired_otps():
    """
    Remove expired OTP records older than 24 hours.
    Prevents unbounded table growth.
    """
    from apps.accounts.models import EmailVerificationOTP
    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = EmailVerificationOTP.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Cleaned up {deleted} expired OTPs")
    return {"deleted_otps": deleted}


@shared_task
def cleanup_expired_tokens():
    """
    Remove used/expired password reset tokens older than 7 days.
    """
    from apps.accounts.models import PasswordResetToken
    cutoff = timezone.now() - timedelta(days=7)
    deleted, _ = PasswordResetToken.objects.filter(
        created_at__lt=cutoff
    ).delete()
    logger.info(f"Cleaned up {deleted} expired password reset tokens")
    return {"deleted_tokens": deleted}


@shared_task
def cleanup_old_audit_logs():
    """
    Remove audit log entries older than 90 days.
    Keep recent history while preventing unbounded growth.
    """
    from apps.audit.models import AuditLog
    cutoff = timezone.now() - timedelta(days=90)
    deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Cleaned up {deleted} old audit log entries")
    return {"deleted_audit_logs": deleted}


@shared_task
def cleanup_old_notifications():
    """
    Remove read notifications older than 60 days.
    Keep unread notifications indefinitely.
    """
    from apps.notifications.models import Notification
    cutoff = timezone.now() - timedelta(days=60)
    deleted, _ = Notification.objects.filter(
        read=True, created_at__lt=cutoff
    ).delete()
    logger.info(f"Cleaned up {deleted} old read notifications")
    return {"deleted_notifications": deleted}


@shared_task
def process_subscription_expiry():
    """
    Deactivate expired technology subscriptions and send renewal reminders
    7 days before expiry (in-app + email).
    """
    from django.conf import settings
    from django.db.models import Q
    from apps.billing.models import TechnologySubscription
    from apps.billing.subscription_utils import (
        RENEWAL_WARNING_DAYS,
        is_tech_subscription_active,
    )
    from apps.notifications.tasks import create_in_app_notification, send_notification_email

    now = timezone.now()
    warning_cutoff = now + timedelta(days=RENEWAL_WARNING_DAYS)

    expired_count = 0
    reminder_count = 0

    # Deactivate subscriptions past expiry
    expired_qs = TechnologySubscription.objects.filter(
        is_active=True,
        expires_at__isnull=False,
        expires_at__lte=now,
    ).select_related("user", "technology")

    for sub in expired_qs.iterator(chunk_size=200):
        sub.is_active = False
        sub.save(update_fields=["is_active"])
        expired_count += 1
        try:
            create_in_app_notification.delay(
                user_id=sub.user_id,
                notification_type="system",
                title=f"Subscription Expired — {sub.technology.name}",
                message=(
                    f"Your {sub.technology.name} subscription has expired. "
                    "Renew to regain access to all scenarios."
                ),
                metadata={"technology_slug": sub.technology.slug, "needs_renewal": True},
            )
        except Exception as e:
            logger.warning(f"Failed expiry notification for sub {sub.id}: {e}")

    # Send renewal reminders for subs expiring within 7 days
    reminder_qs = TechnologySubscription.objects.filter(
        is_active=True,
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=warning_cutoff,
    ).filter(
        Q(renewal_reminder_at__isnull=True) | Q(renewal_reminder_at__lt=now - timedelta(days=1))
    ).select_related("user", "technology")

    for sub in reminder_qs.iterator(chunk_size=200):
        if not is_tech_subscription_active(sub):
            continue
        days_left = (sub.expires_at - now).days
        amount = float(sub.amount or sub.technology.price or 0)
        renew_url = f"{settings.FRONTEND_URL}/payment?technology={sub.technology.slug}&renew=1"
        profile_url = f"{settings.FRONTEND_URL}/profile"
        expiry_str = sub.expires_at.strftime("%B %d, %Y")

        try:
            create_in_app_notification.delay(
                user_id=sub.user_id,
                notification_type="system",
                title=f"Renew {sub.technology.name} — expires in {days_left} day(s)",
                message=(
                    f"Your subscription expires on {expiry_str}. "
                    "Renew now to keep access to all scenarios."
                ),
                metadata={
                    "technology_slug": sub.technology.slug,
                    "expires_at": sub.expires_at.isoformat(),
                    "needs_renewal": True,
                },
            )
            from apps.notifications.email_helpers import queue_user_email

            queue_user_email(
                sub.user,
                subject=f"FixitLab: Renew your {sub.technology.name} subscription",
                template="emails/subscription_renewal_reminder.html",
                context={
                    "username": sub.user.get_full_name() or sub.user.username,
                    "technology": sub.technology.name,
                    "amount": f"₹{int(amount)}",
                    "expiry_date": expiry_str,
                    "days_remaining": days_left,
                    "renew_url": renew_url,
                    "profile_url": profile_url,
                },
                email_type="subscription",
            )
            sub.renewal_reminder_at = now
            sub.save(update_fields=["renewal_reminder_at"])
            reminder_count += 1
        except Exception as e:
            logger.warning(f"Failed renewal reminder for sub {sub.id}: {e}")

    logger.info(
        f"Subscription expiry: deactivated={expired_count}, reminders_sent={reminder_count}"
    )
    interview_reminders = _process_interview_renewal_reminders(now, warning_cutoff)
    return {
        "expired": expired_count,
        "reminders_sent": reminder_count,
        "interview_reminders_sent": interview_reminders,
    }


def _process_interview_renewal_reminders(now, warning_cutoff):
    """Send renewal reminders for interview plans expiring within RENEWAL_WARNING_DAYS."""
    from django.conf import settings
    from django.db.models import Q
    from apps.interviews.models import InterviewEntitlement
    from apps.notifications.tasks import create_in_app_notification
    from apps.notifications.email_helpers import queue_user_email

    count = 0
    qs = InterviewEntitlement.objects.filter(
        is_active=True,
        period_end__isnull=False,
        period_end__gt=now,
        period_end__lte=warning_cutoff,
        is_complimentary=False,
        is_admin_granted_free=False,
        plan_tier__isnull=False,
    ).filter(
        Q(renewal_reminder_at__isnull=True) | Q(renewal_reminder_at__lt=now - timedelta(days=1))
    ).select_related("user", "plan_tier")

    for ent in qs.iterator(chunk_size=100):
        if not ent.plan_tier or ent.plan_tier.code not in ("pro", "premium"):
            continue
        days_left = (ent.period_end - now).days
        user = ent.user
        plan_name = ent.plan_tier.name
        renew_url = f"{settings.FRONTEND_URL}/interviews#interview-plans"
        expiry_str = ent.period_end.strftime("%B %d, %Y")
        try:
            create_in_app_notification.delay(
                user_id=user.id,
                notification_type="system",
                title=f"Renew {plan_name} — expires in {days_left} day(s)",
                message=f"Your interview plan expires on {expiry_str}. Renew to keep your attempts.",
                metadata={"needs_renewal": True, "url": renew_url},
            )
            queue_user_email(
                user,
                subject=f"FixitLab: Renew your {plan_name} interview plan",
                template="emails/interview_renewal_reminder.html",
                context={
                    "username": user.get_full_name() or user.username,
                    "plan_name": plan_name,
                    "expiry_date": expiry_str,
                    "days_remaining": days_left,
                    "attempts_remaining": ent.interviews_remaining,
                    "renew_url": renew_url,
                    "subscriptions_url": f"{settings.FRONTEND_URL}/subscriptions",
                },
                email_type="subscription",
            )
            ent.renewal_reminder_at = now
            ent.save(update_fields=["renewal_reminder_at"])
            count += 1
        except Exception as exc:
            logger.warning("Interview renewal reminder failed ent=%s: %s", ent.id, exc)
    return count


@shared_task
def deliver_jira_team_reply(
    issue_key: str,
    session_id: str,
    author: str,
    message: str,
    actions: list | None = None,
    scenario_slug: str = "",
):
    """Delayed Jira @team bot reply — applies simulation ops then posts comment."""
    from apps.jira_integration.team_bots import deliver_team_reply_now

    deliver_team_reply_now(
        issue_key,
        session_id,
        author,
        message,
        actions or [],
        scenario_slug,
    )
    logger.info("Jira team reply delivered issue=%s author=%s", issue_key, author)
    return {"issue_key": issue_key, "author": author}


@shared_task
def process_inactive_accounts():
    """Warn and delete accounts with no subscription after INACTIVE_ACCOUNT_MONTHS."""
    from apps.accounts.account_lifecycle import run_account_lifecycle

    result = run_account_lifecycle()
    logger.info("Inactive account lifecycle: %s", result)
    return result


@shared_task
def send_marketing_nurture_emails():
    """
    Daily job: nurture emails every MARKETING_NUDGE_INTERVAL_DAYS (default 5).
    - Sample interview completed → interview subscribe benefits
    - Logged-in users without tech subscription → technology benefits
    """
    from apps.notifications.marketing_service import run_marketing_nudges

    result = run_marketing_nudges()
    logger.info("Marketing nurture emails: %s", result)
    return result


@shared_task
def reset_jira_ticket_after_lab_close(session_id: str) -> dict:
    """Clear simulated Jira comments/history and reopen ticket 2 min after lab ends."""
    from apps.labs.models import LabSession
    from apps.jira_integration.simulated import reset_ticket_to_open, use_simulated_jira
    from apps.jira_integration.models import UserScenarioJiraTicket

    session = LabSession.objects.filter(pk=session_id).select_related("user").first()
    if not session or not session.jira_issue_key:
        return {"skipped": "no_session"}
    if session.status in ("RUNNING", "PROVISIONING"):
        return {"skipped": "lab_active"}

    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user,
        issue_key=session.jira_issue_key,
    ).first()
    if not ticket:
        return {"skipped": "no_ticket"}

    if use_simulated_jira():
        reset_ticket_to_open(ticket)
        logger.info("Jira ticket %s reset to open after lab %s closed", ticket.issue_key, session_id)
        return {"reset": ticket.issue_key}
    return {"skipped": "real_jira"}


# PRODUCTION_AUDIT OBS-02: import the business-signal monitor so its @shared_task
# registers under Celery autodiscovery (which imports each app's tasks.py). The
# task body lives in tasks_monitoring.py to keep this module focused.
from celery_app.tasks_monitoring import check_business_signals  # noqa: E402,F401

