"""
Dynamic test catalog — always reads live DB (new techs/scenarios included automatically).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections, connection

from apps.billing.models import Plan, Subscription, TechnologySubscription
from apps.labs.provisioner.docker_provisioner import DockerProvisioner
from apps.question_bank.models import Scenario, Technology

User = get_user_model()
PREFIX = os.environ.get("DOCKER_SCENARIO_IMAGE_PREFIX", "fixitlab/scenario-")
TEST_DOMAIN = "fixitlab-test.local"


def db_refresh():
    close_old_connections()
    connection.ensure_connection()


def image_exists(slug: str) -> bool:
    tag = f"{PREFIX}{slug}:latest"
    try:
        DockerProvisioner().client.images.get(tag)
        return True
    except Exception:
        return False


def discover_catalog():
    """
    Return {technologies: [...], scenarios: [...], by_tech: {slug: [scenarios]}}.
    Only active records — admin additions appear on next test run automatically.
    """
    db_refresh()
    techs = list(Technology.objects.filter(is_active=True).order_by("order", "name"))
    scenarios = list(
        Scenario.objects.filter(is_active=True)
        .select_related("technology")
        .order_by("technology__name", "title")
    )
    by_tech: dict[str, list] = {}
    for sc in scenarios:
        slug = sc.technology.slug if sc.technology_id else "unknown"
        by_tech.setdefault(slug, []).append(sc)

    deployable = []
    missing_images = []
    for sc in scenarios:
        slug = sc.slug or ""
        if sc.technology and getattr(sc.technology, "coming_soon", False):
            continue
        if getattr(sc, "lab_mode", "") == "simulation":
            deployable.append(sc)
            continue
        if image_exists(slug):
            deployable.append(sc)
        else:
            missing_images.append(slug)

    return {
        "technologies": techs,
        "scenarios": scenarios,
        "deployable": deployable,
        "missing_images": missing_images,
        "by_tech": by_tech,
    }


def ensure_test_user(suffix: str, password: str = "E2eLabPass123!"):
    username = f"e2e_lab_{suffix.replace('-', '_')}"
    email = f"{username}@{TEST_DOMAIN}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_active": True},
    )
    if created or not user.check_password(password):
        user.set_password(password)
        user.save()
    return user


def refresh_test_user(user):
    """Re-load test user by username — parallel E2E jobs may delete/recreate accounts."""
    db_refresh()
    username = getattr(user, "username", None)
    if not username:
        raise ValueError("Invalid user object")
    fresh = User.objects.filter(username=username).first()
    if fresh:
        return fresh
    suffix = username.replace("e2e_lab_", "", 1)
    return ensure_test_user(suffix)


def ensure_multi_users(n: int = 3):
    labels = ["user_a", "user_b", "user_c"][:n]
    return [ensure_test_user(lbl) for lbl in labels]


def grant_unlimited_labs(user):
    user = refresh_test_user(user)
    plan, _ = Plan.objects.get_or_create(
        code="e2e-unlimited",
        defaults={
            "name": "E2E Unlimited",
            "price": 0,
            "max_labs_per_day": 9999,
            "max_lab_duration_minutes": 120,
        },
    )
    Subscription.objects.update_or_create(user=user, defaults={"plan": plan, "is_active": True})


def grant_all_technology_subscriptions(user, technologies=None):
    user = refresh_test_user(user)
    cache.clear()
    if technologies is None:
        technologies = Technology.objects.filter(is_active=True)
    for tech in technologies:
        sub_id = f"E2E-{user.username[:16]}-{tech.id}-AUTO"
        sub, _ = TechnologySubscription.objects.update_or_create(
            user=user,
            technology=tech,
            defaults={
                "subscription_id": sub_id,
                "is_active": True,
                "amount": 0,
                "payment_verified": True,
            },
        )
        from apps.billing.subscription_utils import activate_technology_subscription
        activate_technology_subscription(sub, renew=True)


def setup_all_test_users(n: int = 3):
    catalog = discover_catalog()
    users = ensure_multi_users(n)
    for u in users:
        grant_unlimited_labs(u)
        grant_all_technology_subscriptions(u, catalog["technologies"])
    return users, catalog
