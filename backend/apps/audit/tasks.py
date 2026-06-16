from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name="audit.create_log",
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    retry_backoff=True,
)
def create_audit_log(user_id, action, resource, metadata, ip_address, user_agent):
    """Write an audit log entry asynchronously so it does not block the request."""
    from apps.audit.models import AuditLog
    try:
        AuditLog.objects.create(
            user_id=user_id,
            action=action,
            resource=resource,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)
        raise  # allow Celery to retry
