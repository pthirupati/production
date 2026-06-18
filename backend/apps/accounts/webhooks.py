import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


def _sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def fire_org_webhook(org, event: str, payload: dict) -> bool:
    """POST JSON to org.webhook_url with HMAC signature. Returns True on 2xx."""
    if not org.webhook_url:
        return False

    data = {
        "event": event,
        "org": org.slug,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        **payload,
    }
    body = json.dumps(data, default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "X-FixitLab-Event": event,
        "X-FixitLab-Org": org.slug,
    }
    if org.webhook_secret:
        headers["X-FixitLab-Signature"] = _sign_payload(org.webhook_secret, body)

    try:
        resp = requests.post(org.webhook_url, data=body, headers=headers, timeout=5)
        if not resp.ok:
            logger.warning("Org webhook %s → %s returned %s", org.slug, event, resp.status_code)
        return resp.ok
    except Exception as exc:
        logger.warning("Org webhook %s → %s failed: %s", org.slug, event, exc)
        return False
