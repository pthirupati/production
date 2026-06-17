#!/usr/bin/env python3
"""Ensure all Jira tickets use in-app simulation (no real Atlassian keys)."""
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from apps.jira_integration.models import UserScenarioJiraTicket
from apps.jira_integration.simulated import _next_issue_key, _ticket_url


def main():
    updated = 0
    for ticket in UserScenarioJiraTicket.objects.all().iterator():
        changed = False
        if not ticket.simulated:
            ticket.simulated = True
            changed = True
        key = (ticket.issue_key or "").strip()
        if not key or not key.upper().startswith("KAN-"):
            ticket.issue_key = _next_issue_key()
            ticket.issue_url = _ticket_url(ticket.issue_key)
            changed = True
        elif ticket.issue_url and "atlassian.net" in ticket.issue_url.lower():
            ticket.issue_url = _ticket_url(ticket.issue_key)
            changed = True
        if changed:
            ticket.save(update_fields=["simulated", "issue_key", "issue_url", "updated_at"])
            updated += 1
    print(f"Migrated {updated} ticket(s) to simulation mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
