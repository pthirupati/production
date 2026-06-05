#!/usr/bin/env python3
"""
Validate scenario Docker images and multi-user lab provisioning on production.

Run inside backend container:
  docker exec fixitlab-backend-1 python /scripts/validate-scenario-labs.py

Env:
  E2E_SKIP_LAB=1  — only check images exist
  LAB_SAMPLE=10   — max scenarios to start labs for (default: all with images)
"""
from __future__ import annotations

import os
import sys
import time
import uuid

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_production")

import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.question_bank.models import Scenario
from apps.public_api.views import StartLabView
from apps.labs.models import LabSession
from apps.labs.provisioner.docker_provisioner import DockerProvisioner
from apps.billing.models import TechnologySubscription

User = get_user_model()
SKIP_LAB = os.environ.get("E2E_SKIP_LAB", "0") == "1"
SAMPLE = int(os.environ.get("LAB_SAMPLE", "0") or "0")
PREFIX = os.environ.get("DOCKER_SCENARIO_IMAGE_PREFIX", "fixitlab/scenario-")


def image_exists(slug: str) -> bool:
    tag = f"{PREFIX}{slug}:latest"
    try:
        DockerProvisioner().client.images.get(tag)
        return True
    except Exception:
        return False


def ensure_user(suffix: str):
    email = f"labval-{suffix}@fixitlab-test.local"
    user, created = User.objects.get_or_create(
        username=email,
        defaults={"email": email, "is_active": True},
    )
    if created:
        user.set_password("LabValPass123!")
        user.save()
    return user


def grant_subscriptions(user, scenarios):
    """Ensure test user can start labs for all technologies in the sample."""
    from django.core.cache import cache
    cache.clear()
    tech_ids = {sc.technology_id for sc in scenarios}
    for tech_id in tech_ids:
        sub_id = f"TECH-{user.username[:20]}-{tech_id}-LABVAL"
        TechnologySubscription.objects.get_or_create(
            user=user,
            technology_id=tech_id,
            defaults={
                "subscription_id": sub_id,
                "is_active": True,
                "amount": 0,
                "payment_verified": True,
            },
        )


def start_lab(user, scenario_id):
    factory = APIRequestFactory()
    req = factory.post(f"/api/labs/{scenario_id}/start/")
    force_authenticate(req, user=user)
    resp = StartLabView.as_view()(req, scenario_id=scenario_id)
    data = getattr(resp, "data", {}) or {}
    return resp.status_code, data


def wait_running(session_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        session = LabSession.objects.filter(id=session_id).first()
        if not session:
            return None, "missing"
        if session.status == "RUNNING":
            return session, "RUNNING"
        if session.status in ("FAILED", "TERMINATED"):
            return session, session.status
        time.sleep(3)
    session = LabSession.objects.filter(id=session_id).first()
    return session, session.status if session else "timeout"


def main():
    scenarios = list(Scenario.objects.filter(is_active=True).order_by("id"))
    missing_images = []
    present = []

    for sc in scenarios:
        slug = sc.slug or sc.docker_image.replace(f"{PREFIX}", "").replace(":latest", "")
        if image_exists(slug):
            present.append(sc)
        else:
            missing_images.append(slug)

    print(f"Images: {len(present)}/{len(scenarios)} present")
    if missing_images:
        print(f"Missing ({len(missing_images)}): {', '.join(missing_images[:20])}" +
              (" ..." if len(missing_images) > 20 else ""))

    if SKIP_LAB:
        print("E2E_SKIP_LAB=1 — skipping lab starts")
        sys.exit(1 if missing_images else 0)

    user_a = ensure_user("user-a")
    user_b = ensure_user("user-b")
    to_test = present[:SAMPLE] if SAMPLE else present
    grant_subscriptions(user_a, to_test)
    grant_subscriptions(user_b, to_test)

    ok = 0
    fail = 0
    for sc in to_test:
        print(f"\n--- {sc.slug} ---")
        st_a, data_a = start_lab(user_a, sc.id)
        st_b, data_b = start_lab(user_b, sc.id)
        sid_a = data_a.get("session_id") or data_a.get("id")
        sid_b = data_b.get("session_id") or data_b.get("id")

        if st_a not in (200, 201, 202) or not sid_a:
            print(f"  FAIL user_a start: {st_a} {data_a.get('error', data_a)}")
            fail += 1
            continue
        if st_b not in (200, 201, 202) or not sid_b:
            print(f"  FAIL user_b start: {st_b} {data_b.get('error', data_b)}")
            fail += 1
            continue
        if str(sid_a) == str(sid_b):
            print("  FAIL same session id for two users")
            fail += 1
            continue

        sess_a, status_a = wait_running(sid_a)
        sess_b, status_b = wait_running(sid_b)
        jira_a = data_a.get("jira_issue_key") or (sess_a.jira_issue_key if sess_a else "")
        jira_b = data_b.get("jira_issue_key") or (sess_b.jira_issue_key if sess_b else "")

        if status_a != "RUNNING":
            print(f"  FAIL user_a status={status_a} err={getattr(sess_a, 'error_message', '')[:80]}")
            fail += 1
            continue
        if status_b != "RUNNING":
            print(f"  FAIL user_b status={status_b} err={getattr(sess_b, 'error_message', '')[:80]}")
            fail += 1
            continue
        if jira_a and jira_b and jira_a == jira_b:
            print(f"  FAIL shared Jira ticket {jira_a}")
            fail += 1
            continue

        print(f"  PASS — sessions {sid_a} / {sid_b}, Jira {jira_a or 'n/a'} / {jira_b or 'n/a'}")
        ok += 1

        # Stop labs to free resources
        for sid in (sid_a, sid_b):
            try:
                from apps.public_api.views import StopLabView
                req = APIRequestFactory().post(f"/api/labs/{sid}/stop/")
                force_authenticate(req, user=user_a if sid == sid_a else user_b)
                StopLabView.as_view()(req, session_id=sid)
            except Exception:
                pass

    print(f"\nLab validation: {ok} passed, {fail} failed, {len(missing_images)} missing images")
    sys.exit(0 if fail == 0 and not missing_images else 1)


if __name__ == "__main__":
    main()
