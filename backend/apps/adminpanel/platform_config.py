"""Read/write platform settings with env fallbacks."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from common.media_utils import image_specs_for_api

logger = logging.getLogger(__name__)

CONFIG_FILE = Path(getattr(settings, "PLATFORM_CONFIG_FILE", settings.BASE_DIR / "data" / "platform_config.json"))


def get_settings_row():
    from .models import PlatformSettings

    row, _ = PlatformSettings.objects.get_or_create(pk=1)
    return row


def _scheduled_maintenance_active(row) -> bool:
    if not row.maintenance_scheduled_start or not row.maintenance_scheduled_end:
        return False
    now = timezone.now()
    return row.maintenance_scheduled_start <= now <= row.maintenance_scheduled_end


def is_maintenance_active(row=None) -> bool:
    row = row or get_settings_row()
    if row.maintenance_enabled:
        return True
    if _scheduled_maintenance_active(row):
        return True
    return bool(getattr(settings, "MAINTENANCE_MODE", False))


def active_promo_banners(row=None) -> list:
    row = row or get_settings_row()
    now = timezone.now()
    active = []
    for banner in row.promo_banners or []:
        if not banner.get("active", True):
            continue
        start = banner.get("start_at")
        end = banner.get("end_at")
        if start:
            try:
                from django.utils.dateparse import parse_datetime

                if parse_datetime(start) and parse_datetime(start) > now:
                    continue
            except (TypeError, ValueError):
                pass
        if end:
            try:
                from django.utils.dateparse import parse_datetime

                if parse_datetime(end) and parse_datetime(end) < now:
                    continue
            except (TypeError, ValueError):
                pass
        active.append(banner)
    return active


def _normalize_banner_image(url: str) -> str:
    from common.media_utils import public_media_url
    return public_media_url(url or "")


def public_config_payload() -> dict:
    row = get_settings_row()
    maintenance = is_maintenance_active(row)
    message = row.maintenance_message or getattr(settings, "MAINTENANCE_MESSAGE", "")
    promos = active_promo_banners(row) if row.promo_banners_enabled else []
    promos = [
        {**b, "image_url": _normalize_banner_image(b.get("image_url", ""))} if b.get("image_url") else b
        for b in promos
    ]
    return {
        "primary_email": row.primary_email or settings.PRIMARY_EMAIL,
        "support_email": row.support_email or settings.SUPPORT_EMAIL,
        "maintenance_mode": maintenance,
        "maintenance_message": message if maintenance else None,
        "maintenance_banner_enabled": row.maintenance_banner_enabled,
        "promo_banners_enabled": row.promo_banners_enabled,
        "maintenance_banner": {
            "image_url": _normalize_banner_image(row.maintenance_banner_image) if row.maintenance_banner_enabled else "",
            "style": row.maintenance_banner_style or {},
            "scheduled_end": row.maintenance_scheduled_end.isoformat() if row.maintenance_scheduled_end else None,
        },
        "promo_banners": promos,
        "theme_colors": row.theme_colors or {},
        "changelog": row.changelog or [],
        "platform_stats": _platform_stats(),
        "image_upload_specs": image_specs_for_api(),
        **_interview_public_config(),
    }


def _interview_public_config() -> dict:
    try:
        from apps.interviews.services.interview_settings import get_platform_settings
        row = get_platform_settings()
        return {
            "interview_enabled": row.enabled,
            "interview_voice_engine": row.voice_engine or "browser",
        }
    except Exception:
        return {
            "interview_enabled": getattr(settings, "INTERVIEW_ENABLED", True),
            "interview_voice_engine": getattr(settings, "INTERVIEW_VOICE_ENGINE", "browser"),
        }


def _platform_stats() -> dict:
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    from apps.progress.models import UserScenarioProgress
    from apps.question_bank.models import Scenario, Technology

    cached = cache.get("public_platform_stats")
    if cached is not None:
        return cached
    User = get_user_model()
    data = {
        "total_scenarios": Scenario.objects.filter(is_active=True).count(),
        "total_users": User.objects.filter(is_active=True).count(),
        "total_completions": UserScenarioProgress.objects.filter(completed=True).count(),
        "total_technologies": Technology.objects.filter(is_active=True).count(),
    }
    cache.set("public_platform_stats", data, 120)
    return data


def admin_config_payload() -> dict:
    row = get_settings_row()
    return {
        "primary_email": row.primary_email or settings.PRIMARY_EMAIL,
        "payment_email": row.payment_email or settings.PAYMENT_EMAIL,
        "support_email": row.support_email or settings.SUPPORT_EMAIL,
        "admin_display_currency": row.admin_display_currency or "INR",
        "maintenance_mode": is_maintenance_active(row),
        "maintenance_message": row.maintenance_message or settings.MAINTENANCE_MESSAGE,
        "maintenance_enabled": row.maintenance_enabled,
        "maintenance_banner_image": row.maintenance_banner_image,
        "maintenance_banner_style": row.maintenance_banner_style or {},
        "maintenance_scheduled_start": row.maintenance_scheduled_start.isoformat() if row.maintenance_scheduled_start else None,
        "maintenance_scheduled_end": row.maintenance_scheduled_end.isoformat() if row.maintenance_scheduled_end else None,
        "maintenance_notify_users": row.maintenance_notify_users,
        "promo_banners": row.promo_banners or [],
        "promo_banners_enabled": row.promo_banners_enabled,
        "maintenance_banner_enabled": row.maintenance_banner_enabled,
        "theme_colors": row.theme_colors or {},
        "changelog": row.changelog or [],
        "image_upload_specs": image_specs_for_api(),
        "lab_provider": settings.LAB_PROVIDER,
        "max_lab_duration": settings.LAB_MAX_DURATION_MINUTES,
    }


def persist_config_snapshot(row) -> None:
    """Write emails/currency to JSON file for ops backup (mirrors DB)."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "primary_email": row.primary_email,
            "payment_email": row.payment_email,
            "support_email": row.support_email,
            "admin_display_currency": row.admin_display_currency,
            "updated_at": timezone.now().isoformat(),
        }
        CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write platform config file: %s", exc)


def notify_maintenance_users(message: str) -> int:
    from django.contrib.auth import get_user_model

    from apps.notifications.email import send_email

    User = get_user_model()
    sent = 0
    subject = "FixitLab scheduled maintenance"
    for user in User.objects.filter(is_active=True).exclude(email=""):
        try:
            if send_email(
                subject,
                user.email,
                "emails/maintenance_notification.html",
                {"message": message or "FixitLab is entering maintenance.", "username": user.username},
            ):
                sent += 1
        except Exception as exc:
            logger.warning("Maintenance notify failed for %s: %s", user.email, exc)
    return sent
