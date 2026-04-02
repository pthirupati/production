from .models import AuditLog

def export_audit_logs(format="json"):
    logs = AuditLog.objects.all().order_by("-created_at")

    if format == "json":
        return [
            {
                "user": log.user_id,
                "action": log.action,
                "resource": log.resource,
                "metadata": log.metadata,
                "timestamp": log.created_at.isoformat(),
            }
            for log in logs
        ]

    raise ValueError("Unsupported export format")

