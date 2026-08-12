"""Jira Cloud REST API v3 teaching surface over simulated tickets (audit Y3).

Maps ``/rest/api/3/issue/...`` onto :mod:`apps.jira_integration.simulated` so
curl / api_client labs talk the same shape as Atlassian without needing Cloud.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model

from .helpers import is_jira_closed
from .models import JiraCommentLog, UserScenarioJiraTicket
from .simulated import (
    ALLOWED_TRANSITIONS,
    add_comment,
    ticket_detail_payload,
    transition_ticket,
)

User = get_user_model()


def _adf_text(text: str) -> dict:
    """Minimal Atlassian Document Format document for a plain string."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text or ""}],
            }
        ],
    }


def _issue_json(ticket: UserScenarioJiraTicket) -> dict:
    detail = ticket_detail_payload(ticket)
    status_name = detail.get("jira_status") or "To Do"
    return {
        "id": str(ticket.id),
        "key": ticket.issue_key,
        "self": f"/rest/api/3/issue/{ticket.issue_key}",
        "fields": {
            "summary": detail.get("summary") or "",
            "description": _adf_text(detail.get("description") or ""),
            "status": {
                "name": status_name,
                "statusCategory": {
                    "key": "done" if is_jira_closed(status_name) else "indeterminate",
                    "name": "Done" if is_jira_closed(status_name) else "In Progress",
                },
            },
            "priority": {"name": detail.get("priority") or "Medium"},
            "issuetype": {"name": "Task"},
            "project": {"key": (ticket.issue_key or "KAN").split("-")[0], "name": "FixitLab"},
            "comment": {
                "comments": [
                    {
                        "id": str(i),
                        "author": {"displayName": c.get("author") or "user"},
                        "body": _adf_text(c.get("text") or ""),
                        "created": c.get("created_at"),
                    }
                    for i, c in enumerate(detail.get("comments") or [], start=1)
                ],
                "total": len(detail.get("comments") or []),
            },
        },
    }


def _resolve_ticket(issue_key: str, user=None) -> UserScenarioJiraTicket | None:
    qs = UserScenarioJiraTicket.objects.filter(issue_key=issue_key).select_related(
        "scenario", "user", "last_session"
    )
    if user is not None and not (
        getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
    ):
        qs = qs.filter(user=user)
    return qs.first()


def jira_rest_api(
    url_or_path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    user=None,
) -> tuple[int, Any]:
    """Route a Jira REST v3 path. Returns ``(http_status, json_body)``."""
    method = (method or "GET").upper()
    raw = (url_or_path or "").strip()
    if not raw:
        return 400, {"errorMessages": ["empty URL"], "errors": {}}

    if "://" in raw:
        parsed = urlparse(raw)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query)
    elif "?" in raw:
        path, q = raw.split("?", 1)
        qs = parse_qs(q)
    else:
        path, qs = raw, {}

    norm = path.rstrip("/") or "/"
    # Accept bare /rest/api/3/... or full host paths.
    m = re.search(r"/rest/api/3(/.*)?$", norm)
    if m:
        norm = "/rest/api/3" + (m.group(1) or "")
    body = body if isinstance(body, dict) else {}

    if norm in ("/rest/api/3/myself", "/rest/api/3/serverInfo"):
        return 200, {
            "displayName": getattr(user, "username", None) or "lab-user",
            "accountId": str(getattr(user, "id", "lab")),
            "version": "1001.0.0-fixitlab",
            "deploymentType": "Cloud",
            "serverTitle": "FixitLab Jira",
        }

    # GET /rest/api/3/search?jql=...
    if norm == "/rest/api/3/search" and method == "GET":
        jql = (qs.get("jql") or [""])[0]
        qs_tickets = UserScenarioJiraTicket.objects.all().order_by("-updated_at")
        if user is not None and not getattr(user, "is_staff", False):
            qs_tickets = qs_tickets.filter(user=user)
        # Tiny JQL: key = X  or project = X
        key_m = re.search(r"key\s*=\s*([A-Z]+-\d+)", jql, re.I)
        if key_m:
            qs_tickets = qs_tickets.filter(issue_key__iexact=key_m.group(1))
        issues = [_issue_json(t) for t in qs_tickets[:25]]
        return 200, {"startAt": 0, "maxResults": 25, "total": len(issues), "issues": issues}

    # /rest/api/3/issue/{key}[/comment|/transitions]
    m = re.match(r"^/rest/api/3/issue/([A-Za-z]+-\d+)(?:/(comment|transitions))?$", norm)
    if m:
        key = m.group(1)
        sub = m.group(2)
        ticket = _resolve_ticket(key, user=user)
        if not ticket:
            return 404, {
                "errorMessages": [
                    "Issue does not exist or you do not have permission to see it."
                ],
                "errors": {},
            }

        if sub is None:
            if method == "GET":
                return 200, _issue_json(ticket)
            if method in ("PUT", "PATCH"):
                fields = body.get("fields") or {}
                if "summary" in fields:
                    ticket.summary = str(fields["summary"])
                if "description" in fields:
                    desc = fields["description"]
                    if isinstance(desc, dict):
                        ticket.description = json.dumps(desc)[:4000]
                    else:
                        ticket.description = str(desc)
                ticket.save()
                return 204, {}
            return 405, {"errorMessages": ["method not allowed"], "errors": {}}

        if sub == "comment":
            if method == "GET":
                comments = list(
                    JiraCommentLog.objects.filter(issue_key=ticket.issue_key)
                    .order_by("-created_at")[:50]
                )
                return 200, {
                    "comments": [
                        {
                            "id": str(c.id),
                            "author": {"displayName": c.author},
                            "body": _adf_text(c.text),
                            "created": c.created_at.isoformat(),
                        }
                        for c in comments
                    ],
                    "total": len(comments),
                }
            if method == "POST":
                text = body.get("body")
                if isinstance(text, dict):
                    parts = []
                    for block in text.get("content") or []:
                        for node in block.get("content") or []:
                            if node.get("type") == "text":
                                parts.append(node.get("text") or "")
                    text = "\n".join(parts)
                text = str(text or body.get("text") or "").strip()
                if not text:
                    return 400, {"errorMessages": ["body is required"], "errors": {}}
                add_comment(ticket, user, text, session=ticket.last_session)
                return 201, {"self": f"/rest/api/3/issue/{key}/comment"}
            return 405, {"errorMessages": ["method not allowed"], "errors": {}}

        if sub == "transitions":
            current = ticket.jira_status or "To Do"
            allowed = sorted(ALLOWED_TRANSITIONS.get(current, set()))
            if method == "GET":
                return 200, {
                    "transitions": [
                        {"id": name, "name": name, "to": {"name": name}}
                        for name in allowed
                    ]
                }
            if method == "POST":
                transition = body.get("transition") or {}
                target = (
                    transition.get("id")
                    or transition.get("name")
                    or body.get("status")
                )
                if not target:
                    return 400, {
                        "errorMessages": ["transition.id is required"],
                        "errors": {},
                    }
                try:
                    transition_ticket(
                        ticket,
                        user or ticket.user,
                        str(target),
                        session=ticket.last_session,
                    )
                except ValueError as exc:
                    return 400, {"errorMessages": [str(exc)], "errors": {}}
                return 204, {}
            return 405, {"errorMessages": ["method not allowed"], "errors": {}}

    return 404, {
        "errorMessages": [f"Jira REST API: unknown path {path}"],
        "errors": {},
    }
