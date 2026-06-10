#!/usr/bin/env python3
"""
Remove all data created by automated E2E / lab validation tests.

Run inside backend container after tests:
  python /scripts/cleanup-test-data.py

Identifies test users by:
  - email @fixitlab-test.local
  - username prefixes: e2e, e2e-concurrent, labval_
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.cache import cache

User = get_user_model()

TEST_EMAIL_DOMAIN = "fixitlab-test.local"
TEST_USERNAME_PREFIXES = ("e2e", "e2e-concurrent", "e2e_lab_", "labval_")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
PROTECTED_EMAIL = (os.environ.get("SUPERUSER_EMAIL") or "").strip().lower()


def is_test_user(user) -> bool:
    email = (user.email or "").lower()
    username = (user.username or "").lower()

    if PROTECTED_EMAIL and email == PROTECTED_EMAIL:
        return False
    if user.is_superuser and not email.endswith(f"@{TEST_EMAIL_DOMAIN}"):
        return False
    if user.is_staff and not email.endswith(f"@{TEST_EMAIL_DOMAIN}"):
        return False

    if email.endswith(f"@{TEST_EMAIL_DOMAIN}"):
        return True
    if any(username.startswith(p) for p in TEST_USERNAME_PREFIXES):
        return True
    if re.match(r"^e2e(-concurrent)?-", email):
        return True
    return False


def cleanup_lab_sessions(user_ids):
    from apps.labs.models import LabSession
    from apps.labs.cleanup import cleanup_lab

    sessions = LabSession.objects.filter(
        user_id__in=user_ids,
        status__in=("PROVISIONING", "RUNNING"),
    )
    stopped = 0
    for session in sessions.iterator():
        if DRY_RUN:
            stopped += 1
            continue
        try:
            cleanup_lab(session)
            stopped += 1
        except Exception as exc:
            print(f"  WARN lab cleanup {session.id}: {exc}")
    return stopped


def cleanup_docker_containers(usernames):
    """Remove leftover lab containers for test usernames."""
    removed = 0
    try:
        from apps.labs.provisioner.docker_provisioner import DockerProvisioner

        client = DockerProvisioner().client
        for container in client.containers.list(all=True):
            name = (container.name or "").lower()
            if not name.startswith("fixitlab-"):
                continue
            for username in usernames:
                uname = username.lower()
                if f"fixitlab-{uname}-" in name or name == f"fixitlab-{uname}":
                    if DRY_RUN:
                        removed += 1
                        break
                    try:
                        container.remove(force=True)
                        removed += 1
                    except Exception as exc:
                        print(f"  WARN container {name}: {exc}")
                    break
    except Exception as exc:
        print(f"  WARN docker scan: {exc}")
    return removed


def cleanup_jira_issues(issue_keys):
    """Best-effort delete of test Jira issues (requires delete permission)."""
    if not issue_keys:
        return 0
    deleted = 0
    try:
        from apps.jira_integration.client import JiraClient, JiraClientError

        client = JiraClient()
        if not client.enabled:
            return 0
        for key in sorted(set(issue_keys)):
            if DRY_RUN:
                deleted += 1
                continue
            try:
                client._request("DELETE", f"/issue/{key}")
                deleted += 1
            except JiraClientError:
                pass
    except Exception as exc:
        print(f"  WARN jira cleanup: {exc}")
    return deleted


def cleanup_test_data() -> dict:
    from apps.accounts.models import ContactMessage, EmailVerificationOTP
    from apps.billing.models import PaymentTransaction
    from apps.jira_integration.models import UserScenarioJiraTicket, JiraWebhookEvent

    stats = {
        "users": 0,
        "labs_stopped": 0,
        "containers": 0,
        "jira_issues": 0,
        "otps": 0,
        "contacts": 0,
        "webhooks": 0,
        "threads": 0,
        "tags": 0,
    }

    test_users = list(User.objects.filter(is_active=True).iterator())
    test_users = [u for u in test_users if is_test_user(u)]

    if not test_users:
        print("No test users to clean up.")
        return stats

    user_ids = [u.id for u in test_users]
    usernames = [u.username for u in test_users]

    print(f"Cleaning {len(test_users)} test user(s)...")
    for u in test_users:
        print(f"  - {u.username} <{u.email}>")

    stats["labs_stopped"] = cleanup_lab_sessions(user_ids)

    issue_keys = list(
        UserScenarioJiraTicket.objects.filter(user_id__in=user_ids)
        .values_list("issue_key", flat=True)
        .distinct()
    )
    stats["jira_issues"] = cleanup_jira_issues(issue_keys)

    email_q = Q(email__iendswith=f"@{TEST_EMAIL_DOMAIN}") | Q(email__istartswith="e2e-")
    if not DRY_RUN:
        stats["otps"] = EmailVerificationOTP.objects.filter(email_q).delete()[0]
        stats["contacts"] = ContactMessage.objects.filter(
            Q(email__iendswith=f"@{TEST_EMAIL_DOMAIN}") | Q(email__istartswith="e2e")
        ).delete()[0]
        stats["webhooks"] = JiraWebhookEvent.objects.filter(jira_issue_key__startswith="E2E-").delete()[0]
        # Community threads/replies from E2E (before user cascade)
        from apps.community.models import Thread
        stats["threads"] = Thread.objects.filter(
            Q(title__icontains="E2E") | Q(body__icontains="Automated E2E")
        ).delete()[0]
        from apps.question_bank.models import Tag
        stats["tags"] = Tag.objects.filter(name__istartswith="E2E-Cleanup-").delete()[0]
        PaymentTransaction.objects.filter(user_id__in=user_ids).delete()
        stats["users"] = User.objects.filter(id__in=user_ids).delete()[0]
        cache.delete("admin_overview_v1")
    else:
        stats["otps"] = EmailVerificationOTP.objects.filter(email_q).count()
        stats["contacts"] = ContactMessage.objects.filter(
            Q(email__iendswith=f"@{TEST_EMAIL_DOMAIN}") | Q(email__istartswith="e2e")
        ).count()
        stats["users"] = len(test_users)

    stats["containers"] = cleanup_docker_containers(usernames)
    return stats


def main():
    print("=== FixitLab test data cleanup ===")
    if DRY_RUN:
        print("DRY_RUN=1 — no changes will be made")
    stats = cleanup_test_data()
    print(
        f"Done: users={stats['users']} labs_stopped={stats['labs_stopped']} "
        f"containers={stats['containers']} jira={stats['jira_issues']} "
        f"otps={stats['otps']} contacts={stats['contacts']} threads={stats['threads']} tags={stats.get('tags', 0)}"
    )


if __name__ == "__main__":
    main()
