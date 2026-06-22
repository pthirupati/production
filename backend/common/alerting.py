"""Lightweight operational alerting (PRODUCTION_AUDIT OBS-02).

Posts a short message to a configurable webhook (Slack / Discord / generic
JSON) and/or sends an email to ``ALERT_EMAIL``. Everything here is **fully
gated** on configuration and is a guaranteed no-op when neither channel is set:

  * ``ALERT_WEBHOOK_URL`` unset  → no HTTP call is made.
  * ``ALERT_EMAIL`` unset        → no email is sent.

With *neither* configured, :func:`send_alert` logs at WARNING and returns
``False`` without performing any network/email I/O, so the default deploy (no
alerting secrets) is behaviour-unchanged. The owner sets ``ALERT_WEBHOOK_URL``
(and optionally ``ALERT_EMAIL``) in Vault/env to turn alerting on.

This module never raises: a webhook/email failure is logged and swallowed so an
alerting outage can never take down the caller (a Celery beat task or a request
path). It deliberately has no Django-model imports at module load so it is safe
to import from anywhere, including ``settings``-adjacent code.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib import error as _urlerror
from urllib import request as _urlrequest

from django.conf import settings

logger = logging.getLogger(__name__)

# How long to wait on the alert webhook before giving up. Alerting must never
# block the caller for long — a slow/unreachable webhook should fail fast.
_WEBHOOK_TIMEOUT_SECONDS = 5


def alerting_enabled() -> bool:
    """True when at least one alert channel (webhook or email) is configured."""
    return bool(
        getattr(settings, "ALERT_WEBHOOK_URL", "")
        or getattr(settings, "ALERT_EMAIL", "")
    )


def _build_webhook_payload(url: str, text: str, level: str) -> bytes:
    """Render a payload that works for Slack, Discord, and generic webhooks.

    Slack expects ``{"text": ...}``; Discord expects ``{"content": ...}``. We
    send both keys plus a structured ``message``/``level`` so a generic
    consumer also gets the data. Sending extra keys is harmless for Slack and
    Discord (they ignore unknown fields).
    """
    payload = {
        "text": text,          # Slack
        "content": text,       # Discord
        "message": text,       # generic
        "level": level,
        "source": "fixitlab",
    }
    return json.dumps(payload).encode("utf-8")


def _post_webhook(url: str, text: str, level: str) -> bool:
    data = _build_webhook_payload(url, text, level)
    req = _urlrequest.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _urlrequest.urlopen(req, timeout=_WEBHOOK_TIMEOUT_SECONDS) as resp:
            # 2xx is success; Slack returns 200 with body "ok", Discord 204.
            status = getattr(resp, "status", 200)
            if 200 <= status < 300:
                return True
            logger.warning("Alert webhook returned HTTP %s", status)
            return False
    except _urlerror.URLError as exc:  # network/DNS/timeout
        logger.warning("Alert webhook POST failed: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001 — alerting must never raise
        logger.warning("Alert webhook unexpected error: %s", exc)
        return False


def _send_email(subject: str, body: str) -> bool:
    recipient = getattr(settings, "ALERT_EMAIL", "")
    if not recipient:
        return False
    try:
        from django.core.mail import send_mail

        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient],
            fail_silently=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — alerting must never raise
        logger.warning("Alert email send failed: %s", exc)
        return False


def send_alert(
    message: str,
    *,
    level: str = "warning",
    title: Optional[str] = None,
) -> bool:
    """Send an operational alert to whatever channels are configured.

    Returns True if at least one channel accepted the alert, else False. When
    no channel is configured this is a no-op (logs at WARNING, returns False)
    — so callers can fire alerts unconditionally without guarding on config.

    Never raises: any transport failure is logged and swallowed.
    """
    prefix = getattr(settings, "ALERT_ENV_PREFIX", "") or ""
    label = f"[{prefix}] " if prefix else ""
    full_title = title or "FixitLab alert"
    text = f"{label}{full_title}: {message}"

    if not alerting_enabled():
        # No channel configured — record locally so the signal is not lost, but
        # perform no network/email I/O. This is the default-deploy path.
        logger.warning("ALERT (no channel configured): %s", text)
        return False

    delivered = False
    webhook_url = getattr(settings, "ALERT_WEBHOOK_URL", "")
    if webhook_url:
        delivered = _post_webhook(webhook_url, text, level) or delivered
    if getattr(settings, "ALERT_EMAIL", ""):
        delivered = _send_email(full_title, text) or delivered

    if not delivered:
        logger.warning("Alert configured but no channel accepted it: %s", text)
    return delivered
