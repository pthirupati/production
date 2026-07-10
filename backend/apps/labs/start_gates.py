"""Shared lab-start eligibility checks (used by StartLabView and interview practical labs)."""

from __future__ import annotations

import os

from django.conf import settings
from django.utils import timezone

from apps.billing.models import TechnologySubscription
from apps.billing.services import can_start_lab, get_user_plan_info
from apps.billing.subscription_utils import (
    is_tech_subscription_active,
    is_tech_subscription_in_grace,
    user_has_complimentary_access,
)
from apps.labs.capacity import at_global_capacity
from apps.labs.infra import lab_infra_type
from apps.labs.models import LabSession


def lab_start_block_reason(user, scenario) -> dict | None:
    """
    Return an error payload dict if the user may not start this scenario's lab,
    or None if start is allowed (staff bypass subscription/daily limits only).
    """
    is_admin = user.is_staff or user.is_superuser

    if not is_admin:
        try:
            from apps.adminpanel.platform_config import is_maintenance_active

            if is_maintenance_active():
                from apps.adminpanel.models import PlatformSettings

                row = PlatformSettings.objects.filter(pk=1).first()
                msg = (row.maintenance_message if row else None) or (
                    "FixitLab is currently under maintenance. Labs are temporarily unavailable."
                )
                return {"error": "maintenance", "message": msg, "code": "MAINTENANCE"}
        except Exception:
            pass

        tech = scenario.technology
        if tech and tech.maintenance_enabled:
            msg = tech.maintenance_message or (
                f"{tech.name} is currently under maintenance and labs are temporarily unavailable."
            )
            return {"error": "tech_maintenance", "message": msg, "technology": tech.name, "code": "TECH_MAINTENANCE"}

    if getattr(scenario.technology, "coming_soon", False):
        return {
            "error": "Technology coming soon",
            "message": f"{scenario.technology.name} is not available yet.",
            "code": "COMING_SOON",
        }

    if not is_admin and not scenario.is_free and not user_has_complimentary_access(user):
        from apps.certifications.services.access import user_has_cert_scenario_access

        cert_ok = user_has_cert_scenario_access(user, scenario)
        sub = TechnologySubscription.objects.filter(
            user=user,
            technology=scenario.technology,
        ).order_by("-created_at").first()
        if sub and is_tech_subscription_in_grace(sub):
            return {
                "error": "Subscription expired",
                "message": (
                    f"Your {scenario.technology.name} subscription expired. "
                    "Renew now to continue labs — grace period allows viewing only."
                ),
                "needs_renewal": True,
                "renew_url": f"/payment?technology={scenario.technology.slug}&renew=1",
                "code": "SUBSCRIPTION_EXPIRED",
            }
        has_sub = sub and is_tech_subscription_active(sub)
        if not has_sub and not cert_ok:
            return {
                "error": "Subscription required. Purchase access to this technology first.",
                "code": "SUBSCRIPTION_REQUIRED",
                "technology": scenario.technology.name,
            }

    if not is_admin:
        today_count = LabSession.objects.filter(
            user=user,
            started_at__date=timezone.now().date(),
        ).exclude(status="FAILED").count()
        if not can_start_lab(user, today_count):
            plan_info = get_user_plan_info(user)
            return {
                "error": "Daily lab limit reached. Upgrade your plan for unlimited access.",
                "code": "LIMIT_REACHED",
                "plan": plan_info["plan"],
                "usage": plan_info["usage"],
            }

    max_concurrent = int(
        os.environ.get(
            "MAX_CONCURRENT_LABS_PER_USER",
            str(getattr(settings, "MAX_CONCURRENT_LABS_PER_USER", 2)),
        )
    )
    active_count = LabSession.objects.filter(
        user=user,
        status__in=["RUNNING", "PROVISIONING"],
    ).count()
    if active_count >= max_concurrent:
        return {
            "error": (
                f"You already have {active_count} active lab(s) running. "
                "Stop an existing lab before starting a new one."
            ),
            "code": "MAX_CONCURRENT",
            "active_labs": active_count,
            "max_concurrent": max_concurrent,
        }

    infra_type = lab_infra_type(scenario)
    if at_global_capacity(infra_type):
        return {
            "error": "All lab engines are at capacity. Please try again in a few minutes.",
            "message": "The platform is temporarily at capacity for new labs. Try again shortly.",
            "code": "CAPACITY_FULL",
        }

    return None


def lab_start_block_http_status(block: dict) -> int:
    """Map a lab_start_block_reason payload to an HTTP status code."""
    from rest_framework import status as drf_status

    code = block.get("code", "")
    if code in ("MAINTENANCE", "TECH_MAINTENANCE", "CAPACITY_FULL"):
        return drf_status.HTTP_503_SERVICE_UNAVAILABLE
    if code == "MAX_CONCURRENT":
        return drf_status.HTTP_429_TOO_MANY_REQUESTS
    return drf_status.HTTP_403_FORBIDDEN


def lab_start_block_http_status(block: dict) -> int:
    """Map a lab_start_block_reason payload to an HTTP status code."""
    from rest_framework import status as drf_status

    code = block.get("code", "")
    if code in ("MAINTENANCE", "TECH_MAINTENANCE", "CAPACITY_FULL"):
        return drf_status.HTTP_503_SERVICE_UNAVAILABLE
    if code == "MAX_CONCURRENT":
        return drf_status.HTTP_429_TOO_MANY_REQUESTS
    return drf_status.HTTP_403_FORBIDDEN
