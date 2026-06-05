"""
Jira Cloud webhook receiver — bidirectional sync (Jira → FixitLab).
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.notifications.models import Notification
from .models import JiraCommentLog, JiraTicketLog, JiraWebhookEvent, UserScenarioJiraTicket

logger = logging.getLogger(__name__)


def _verify_webhook_secret(request) -> bool:
    secret = getattr(settings, "JIRA_WEBHOOK_SECRET", "") or ""
    if not secret:
        return settings.DEBUG
    provided = request.GET.get("secret") or request.headers.get("X-FixitLab-Webhook-Secret", "")
    return provided == secret


def _find_ticket(issue_key: str):
    return UserScenarioJiraTicket.objects.filter(issue_key=issue_key).select_related(
        "user", "scenario", "last_session"
    ).first()


def _extract_comment_text(body) -> str:
    if isinstance(body, str):
        return body
    if not isinstance(body, dict):
        return str(body)
    parts = []
    for block in body.get("content", []):
        for item in block.get("content", []):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
    return "".join(parts) or str(body)


def _notify_user(ticket, title, message, metadata=None):
    Notification.objects.create(
        user=ticket.user,
        type="system",
        title=title,
        message=message,
        metadata=metadata or {},
    )


@csrf_exempt
@require_http_methods(["POST"])
def jira_webhook(request):
    """
    POST /api/jira/webhooks/?secret=YOUR_SECRET

    Configure in Jira: Settings → System → Webhooks
    Events: issue updated, comment created
    """
    if not _verify_webhook_secret(request):
        logger.warning("Jira webhook rejected: invalid secret")
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event_type = data.get("webhookEvent", "")
    issue = data.get("issue", {})
    issue_key = issue.get("key", "")

    JiraWebhookEvent.objects.create(
        webhook_type=event_type or "unknown",
        jira_issue_key=issue_key or "UNKNOWN",
        payload=data,
    )

    if not issue_key:
        return JsonResponse({"status": "ignored", "reason": "no issue key"})

    ticket = _find_ticket(issue_key)
    if not ticket:
        logger.info("Jira webhook for unknown issue %s", issue_key)
        return JsonResponse({"status": "ignored", "reason": "unknown issue"})

    session = ticket.last_session

    if event_type == "jira:issue_updated":
        status_name = issue.get("fields", {}).get("status", {}).get("name", "")
        old_status = ticket.jira_status
        ticket.jira_status = status_name
        ticket.save(update_fields=["jira_status", "updated_at"])

        if session:
            JiraTicketLog.objects.create(
                session=session,
                issue_key=issue_key,
                issue_url=ticket.issue_url,
                action="webhook",
                jira_status=status_name,
                details={"event": event_type, "old_status": old_status},
            )

        if old_status != status_name:
            _notify_user(
                ticket,
                f"Jira {issue_key} updated",
                f"Status changed to: {status_name}",
                {"issue_key": issue_key, "issue_url": ticket.issue_url, "jira_status": status_name},
            )

    elif event_type == "comment_created":
        comment = data.get("comment", {})
        comment_id = str(comment.get("id", ""))
        if comment_id:
            author = comment.get("author", {}).get("displayName", "Unknown")
            text = _extract_comment_text(comment.get("body", ""))
            JiraCommentLog.objects.get_or_create(
                jira_comment_id=comment_id,
                defaults={
                    "session": session,
                    "issue_key": issue_key,
                    "author": author,
                    "text": text,
                    "created_at": timezone.now(),
                },
            )
            _notify_user(
                ticket,
                f"New Jira comment on {issue_key}",
                f"{author}: {text[:120]}",
                {"issue_key": issue_key, "author": author},
            )

    JiraWebhookEvent.objects.filter(
        jira_issue_key=issue_key, processed=False
    ).order_by("-created_at")[:1].update(processed=True)

    return JsonResponse({"status": "ok", "issue_key": issue_key})
