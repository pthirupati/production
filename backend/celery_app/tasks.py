import logging
import time

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


@shared_task(autoretry_for=(Exception,), retry_backoff=60, retry_kwargs={"max_retries": 2})
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


# Where beat records that it is alive, and how stale that record may be before the
# container is considered unhealthy.
#
# A file rather than Redis: the healthcheck runs inside the beat container with
# `docker exec`, so it must not need a Redis client, credentials, or the network.
# A stale file is also unambiguous — no "is Redis down, or is beat down?".
BEAT_HEARTBEAT_PATH = "/tmp/celerybeat-heartbeat"
BEAT_HEARTBEAT_INTERVAL_SECONDS = 60
# Three missed beats. Tight enough to catch a wedge quickly, loose enough that one
# slow tick under load does not restart a healthy scheduler.
BEAT_HEARTBEAT_MAX_AGE_SECONDS = 200


@shared_task(name="celery_app.tasks.beat_heartbeat", autoretry_for=(OSError,), retry_backoff=5, retry_kwargs={"max_retries": 2})
def beat_heartbeat():
    """Prove celery beat is still scheduling (audit Z5-15).

    The healthcheck previously only confirmed the pidfile existed and the process
    was alive, so a beat that was running but no longer scheduling looked perfectly
    healthy — meaning no expiry cleanup, no orphan cleanup, no retention sweep, and
    **no alert**.

    The tempting alternative is to watch the mtime of beat's own schedule file.
    Measured, that does not work: with the next task an hour away the mtime does not
    advance, so the check would report a healthy beat as dead whenever nothing is
    due — a restart loop in place of a missing alert.

    This proves liveness by beat doing its actual job. If the scheduler stops
    dispatching, this task stops running, the file goes stale, and the healthcheck
    fails. It is deliberately trivial: a heartbeat that can fail for its own reasons
    is a heartbeat that reports false alarms.
    """
    import os
    import tempfile

    payload = f"{time.time():.0f}\n"
    # Written atomically. A healthcheck reading a half-written file would flap, and
    # the whole point of this task is to be the one thing that does not.
    directory = os.path.dirname(BEAT_HEARTBEAT_PATH) or "/tmp"
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".beat-hb-")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
        os.replace(tmp, BEAT_HEARTBEAT_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {"written_at": payload.strip()}


@shared_task(
    name="celery_app.tasks.prune_docker_artifacts",
    queue="provisioning",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 2},
)
def prune_docker_artifacts():
    """Reclaim disk from dangling images, build cache and unused volumes.

    Audit Z5-11. Container and network cleanup was correct and label-scoped, but
    nothing ever ran `image prune`, `builder prune` or `volume prune` — so the lab
    host accumulated every intermediate layer from every scenario image build until
    the disk filled. Anonymous volumes were worse: `container.remove(force=True)`
    omitted `v=True`, so one orphaned on *every* teardown.

    Deliberately conservative, because an over-eager prune on the lab host means
    every subsequent lab start pays a full image pull:

    * images: `dangling=True` only — untagged layers with nothing referencing them.
      A blanket `until=` prune would delete the scenario base images themselves,
      which are large and slow to rebuild.
    * volumes: unused only. Nothing here is stateful; lab state lives in the
      container filesystem and the DB.
    * build cache: aged out rather than emptied, so an incremental rebuild still
      hits warm layers.

    Reports reclaimed bytes so the value is measurable rather than assumed.
    """
    from django.conf import settings

    try:
        import docker
    except Exception as exc:
        return {"status": "docker_unavailable", "error": str(exc)}

    try:
        client = docker.DockerClient(
            base_url=getattr(settings, "DOCKER_SOCKET", "unix:///var/run/docker.sock"),
            timeout=60,
        )
    except Exception as exc:
        # Expected on any node that is not the lab host.
        logger.debug("prune_docker_artifacts: no docker daemon here (%s)", exc)
        return {"status": "not_applicable"}

    reclaimed = {}
    try:
        for label, call in (
            ("images", lambda: client.images.prune(filters={"dangling": True})),
            ("volumes", lambda: client.volumes.prune()),
            ("build_cache", lambda: client.api.prune_builds(filters={"until": "168h"})),
        ):
            try:
                result = call() or {}
                reclaimed[label] = int(result.get("SpaceReclaimed") or 0)
            except Exception as exc:
                # One unsupported prune (older API, rootless daemon) must not stop
                # the others — the disk pressure is usually in a different bucket.
                logger.warning("prune_docker_artifacts: %s prune failed: %s", label, exc)
                reclaimed[label] = None
    finally:
        try:
            client.close()
        except Exception:
            pass

    total = sum(v for v in reclaimed.values() if v)
    logger.info(
        "prune_docker_artifacts: reclaimed %.1f MB (%s)", total / 1_048_576, reclaimed
    )
    return {"status": "ok", "reclaimed_bytes": reclaimed, "total_bytes": total}


@shared_task(autoretry_for=(Exception,), retry_backoff=60, retry_kwargs={"max_retries": 2})
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


@shared_task(autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 2})
def recalculate_leaderboard():
    """
    Recalculate the global leaderboard snapshot from progress data.
    Scheduled daily (see celery_app.beat_schedule) — nothing reads the table yet.

    Delegates to apps.leaderboard.services, which is the single hardened
    implementation. This task used to carry a second, near-identical copy of the
    delete + bulk_create; the copy drifted from the original (audit Z3-7) and only
    one of the two was covered by tests. Two implementations of one invariant means
    the next person to harden it fixes one and misses the other.

    The dropped copy also annotated `completed_count=Count("id")` and then never
    used it — `LeaderboardEntry` has no such field, and the rows it built passed
    only user/scenario/score/rank. Removing it drops a wasted aggregate, not data.
    """
    from apps.leaderboard.models import LeaderboardEntry
    from apps.leaderboard.services import compute_global_leaderboard

    compute_global_leaderboard()

    count = LeaderboardEntry.objects.filter(scenario__isnull=True).count()
    logger.info(f"Leaderboard recalculated: {count} entries")
    return {"entries": count}


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


@shared_task(
    bind=True,
    name="celery_app.tasks.teardown_lab_resource",
    queue="provisioning",
    max_retries=3,
    default_retry_delay=10,
)
def teardown_lab_resource(self, session_id: str):
    """Destroy the container / cloud instance backing an already-terminated session.

    Audit Z5-9. `StartLabView` used to tear the user's previous labs down inline,
    inside the `transaction.atomic()` block that also holds the global capacity
    advisory lock. That is network I/O — SSH to D4, or the docker daemon — executed
    while holding a row lock *and* a lock every other lab start in the platform is
    waiting on. One slow D4 response serialised lab starts for everybody.

    The DB half (marking the session TERMINATED) stays in the transaction, because
    capacity accounting has to be atomic. Only the resource teardown moved here,
    scheduled via `transaction.on_commit` so a rolled-back start never destroys a
    lab the user still has.

    Retried, unlike the old inline version which swallowed every failure into a
    `logger.warning` — a teardown that quietly fails is a container that runs until
    the reaper notices, on a box with a hard capacity cap.
    """
    from apps.labs.models import LabSession
    from apps.labs.provisioner import get_provisioner, terminate_lab_session

    try:
        session = LabSession.objects.get(id=session_id)
    except LabSession.DoesNotExist:
        return {"status": "gone"}

    resource_id = session.container_id or session.instance_id
    if not resource_id:
        return {"status": "no_resource"}

    try:
        terminate_lab_session(get_provisioner(session.provider or "docker"), session)
    except Exception as exc:
        logger.warning("teardown_lab_resource: session %s failed: %s", session_id, exc)
        raise self.retry(exc=exc)
    return {"status": "terminated", "session_id": str(session_id)}


@shared_task(autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 2})
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


@shared_task(autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 2})
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


@shared_task(autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 2})
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


@shared_task(autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 2})
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
    from apps.jira_integration.pending_team_replies import cancel_pending_for_issue
    from apps.jira_integration.team_bots import deliver_team_reply_now

    deliver_team_reply_now(
        issue_key,
        session_id,
        author,
        message,
        actions or [],
        scenario_slug,
    )
    # Celery path won — drop the durable pending row so beat does not double-post.
    try:
        cancel_pending_for_issue(issue_key)
    except Exception:  # pragma: no cover
        pass
    logger.info("Jira team reply delivered issue=%s author=%s", issue_key, author)
    return {"issue_key": issue_key, "author": author}


@shared_task
def sweep_pending_team_replies():
    """Beat sweeper for durable @team replies (audit X2b).

    Re-delivers any pending row whose countdown was lost (worker restart /
    broker drop). Idempotent with the Celery countdown path via cancel-on-deliver.
    """
    from apps.jira_integration.pending_team_replies import deliver_due_pending_team_replies

    result = deliver_due_pending_team_replies()
    if result.get("delivered") or result.get("failed"):
        logger.info("pending team reply sweep: %s", result)
    return result


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

# Same reason as above: deliver_org_webhook lives in apps/accounts/webhooks.py
# (next to the signing/POST helpers it uses) rather than in that app's tasks.py,
# so autodiscovery would not see it. Import it here so the @shared_task registers.
# Without this, fire_org_webhook().delay() raises and silently degrades to a
# synchronous send — which is the latency problem it exists to remove.
from apps.accounts.webhooks import deliver_org_webhook  # noqa: E402,F401


@shared_task(autoretry_for=(Exception,), retry_backoff=60, retry_kwargs={"max_retries": 2})
def purge_expired_personal_data():
    """Enforce the retention periods in settings for the sensitive data classes.

    Audit Z4-2: interview messages (free-text candidate speech), async video,
    resumes (file + parsed text) and CommandHistory had no retention and no purge
    — all plaintext, indefinite, stored alongside employer and current_package_lpa.

    Each period defaults to 0 = REPORT ONLY. The task still counts what it would
    remove and logs it, so the owner picks a retention period against real volumes
    instead of guessing; silently deleting a customer's interview reports because a
    default looked sensible would be worse than the gap being closed. Set the
    matching RETENTION_*_DAYS env var to start actually purging.

    Resumes are cleared field-by-field rather than by deleting CandidateProfile,
    which would cascade away the whole interview history. Assigning None to
    resume_file and saving lets the pre_save handler in common/file_cleanup remove
    the blob from disk too — clearing the DB column alone would orphan the file.
    """
    from django.conf import settings

    from apps.accounts.models import AccountLifecycleEvent
    from apps.interviews.models import AsyncVideoResponse, CandidateProfile, InterviewMessage
    from apps.labs.models import CommandHistory

    now = timezone.now()
    report: dict[str, dict] = {}

    def _sweep(label, days, queryset_for, purge):
        enabled = int(days or 0) > 0
        if not enabled:
            # Still measure, so "how much would we delete?" is answerable.
            days = 365
        cutoff = now - timedelta(days=int(days))
        qs = queryset_for(cutoff)
        count = qs.count()
        if enabled and count:
            purge(qs)
        report[label] = {
            "enabled": enabled,
            "retention_days": int(days),
            "matched": count,
            "purged": count if enabled else 0,
        }
        if count and not enabled:
            logger.info(
                "retention: %s — %d record(s) older than %d days would be purged "
                "(set RETENTION_%s_DAYS to enable)",
                label, count, int(days), label.upper(),
            )
        elif enabled and count:
            logger.info("retention: %s — purged %d record(s)", label, count)

    _sweep(
        "interview_message",
        getattr(settings, "RETENTION_INTERVIEW_MESSAGE_DAYS", 0),
        lambda c: InterviewMessage.objects.filter(created_at__lt=c),
        lambda qs: qs.delete(),
    )
    _sweep(
        "async_video",
        getattr(settings, "RETENTION_ASYNC_VIDEO_DAYS", 0),
        lambda c: AsyncVideoResponse.objects.filter(created_at__lt=c),
        lambda qs: qs.delete(),
    )
    _sweep(
        "command_history",
        getattr(settings, "RETENTION_COMMAND_HISTORY_DAYS", 0),
        lambda c: CommandHistory.objects.filter(timestamp__lt=c),
        lambda qs: qs.delete(),
    )

    def _purge_resumes(qs):
        # Row-by-row: assigning None and saving fires the file_cleanup pre_save
        # handler, so the blob leaves the disk. A bulk update() would skip signals
        # and orphan every file.
        for profile in qs.iterator(chunk_size=200):
            profile.resume_file = None
            profile.resume_text = ""
            profile.resume_parsed = {}
            profile.save(update_fields=["resume_file", "resume_text", "resume_parsed"])

    _sweep(
        "resume",
        getattr(settings, "RETENTION_RESUME_DAYS", 0),
        lambda c: CandidateProfile.objects.filter(updated_at__lt=c).exclude(
            resume_file="", resume_text="",
        ),
        _purge_resumes,
    )

    # Audit Z4-12 leftover: email kept after inactive deletion for anti-abuse.
    # Basis + TTL must be stated (privacy page) and enforced here — unbounded
    # retention of a deleted user's email is the defect, not the retention itself.
    _sweep(
        "account_lifecycle",
        getattr(settings, "RETENTION_ACCOUNT_LIFECYCLE_DAYS", 0),
        lambda c: AccountLifecycleEvent.objects.filter(created_at__lt=c),
        lambda qs: qs.delete(),
    )

    # ── Operational growth (audit Z5-8) ────────────────────────────────────────
    #
    # Different motivation from the four classes above, same discipline. These are
    # not privacy risks; they are the tables that decide backup and restore time.
    # D3 is 2 vCPU with no read replica, `pg_dump` grows linearly and restore is
    # single-threaded, so unbounded growth converts into RTO — at 50 GB, hours.
    # SessionRecording alone stores up to 5,000 I/O events per session in a
    # JSONField (~500 MB/day of JSONB at 1,000 labs/day).
    #
    # Report-only by default for the same reason as above: a guessed default that
    # shipped enabled would delete a customer's session replays the first night it
    # ran. The counts tell the owner what the real volumes are first.
    from apps.billing.models import ProcessedWebhookEvent
    from apps.labs.models import IncidentRun, LabSession, SessionRecording
    from apps.notifications.models import Notification

    _sweep(
        "session_recording",
        getattr(settings, "RETENTION_SESSION_RECORDING_DAYS", 0),
        lambda c: SessionRecording.objects.filter(created_at__lt=c),
        lambda qs: qs.delete(),
    )

    def _clear_snapshots(qs):
        # The snapshot is only meaningful while a lab can still be resumed, but
        # it is kept forever — multi-hundred-KB of JSON per row. Cleared with
        # update() rather than delete(): the LabSession row itself is the
        # completion record that progress, grading and billing all reference.
        #
        # `{}` and not `None`: the column is `JSONField(default=dict)` with no
        # null=True, so nulling it raises IntegrityError. The full suite caught
        # that; the isolated run did not, because the enabling override_settings
        # only exists in a couple of tests.
        qs.update(simulation_snapshot={})

    _sweep(
        "lab_snapshot",
        getattr(settings, "RETENTION_LAB_SNAPSHOT_DAYS", 0),
        # Terminal states only. A PROVISIONING or RUNNING session is live no
        # matter how old its row looks, and clearing its snapshot mid-lab would
        # destroy the learner's work in place.
        lambda c: LabSession.objects.filter(
            ended_at__lt=c,
            status__in=("COMPLETED", "FAILED", "TERMINATED", "EXPIRED"),
        ).exclude(simulation_snapshot={}),
        _clear_snapshots,
    )

    _sweep(
        "webhook_event",
        getattr(settings, "RETENTION_WEBHOOK_EVENT_DAYS", 0),
        # These rows are the durable double-fulfilment guard, so the retention
        # floor is not a preference — it must comfortably exceed any gateway's
        # replay window (Razorpay retries for about a day). The default measure of
        # 365 days is far beyond it; do not set this below ~90.
        lambda c: ProcessedWebhookEvent.objects.filter(created_at__lt=c),
        lambda qs: qs.delete(),
    )

    _sweep(
        "read_notification",
        getattr(settings, "RETENTION_READ_NOTIFICATION_DAYS", 0),
        # Read only. An unread notification is still pending work for the user, so
        # age alone is not a reason to remove it.
        lambda c: Notification.objects.filter(created_at__lt=c, read=True),
        lambda qs: qs.delete(),
    )

    _sweep(
        "incident_run",
        getattr(settings, "RETENTION_INCIDENT_RUN_DAYS", 0),
        # Cascades to Postmortem, which is the point — an orphaned postmortem
        # references a run nobody can look at.
        lambda c: IncidentRun.objects.filter(started_at__lt=c),
        lambda qs: qs.delete(),
    )

    return report
