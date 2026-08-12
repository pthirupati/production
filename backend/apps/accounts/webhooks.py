import hashlib
import hmac
import json

from celery import shared_task
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


def _sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post_org_webhook(org, event: str, payload: dict, addresses=None) -> bool:
    """POST JSON to org.webhook_url with HMAC signature. Returns True on 2xx.

    ``addresses`` are the IPs that url_safety already vetted for this hostname.
    When present the request is pinned to them, so the resolver never runs a
    second time and there is no DNS-rebinding window between validation and the
    socket. Callers that have validated should always pass them.
    """
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
        # allow_redirects=False is load-bearing, not a preference. validate_outbound_url()
        # only vets the URL we are about to request; requests follows redirects by default,
        # so an org owner could point the webhook at a public host they control and have it
        # answer 302 → http://169.254.169.254/. requests would follow that to instance
        # metadata and the entire SSRF guard would be bypassed without ever storing an
        # unsafe URL. A webhook receiver has no legitimate need to redirect us.
        # It also bounds the pin below: a redirect would target a hostname these
        # addresses were never validated for.
        if addresses:
            from .url_safety import pinned_session

            with pinned_session(addresses) as session:
                resp = session.post(
                    org.webhook_url, data=body, headers=headers, timeout=5,
                    allow_redirects=False,
                )
        else:
            resp = requests.post(
                org.webhook_url, data=body, headers=headers, timeout=5, allow_redirects=False
            )
        if resp.is_redirect or resp.is_permanent_redirect:
            logger.warning(
                "Org webhook %s → %s returned redirect %s; refusing to follow",
                org.slug, event, resp.status_code,
            )
            return False
        if not resp.ok:
            logger.warning("Org webhook %s → %s returned %s", org.slug, event, resp.status_code)
        return resp.ok
    except Exception as exc:
        logger.warning("Org webhook %s → %s failed: %s", org.slug, event, exc)
        return False

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=10,
    acks_late=True,
)
def deliver_org_webhook(self, org_id: str, event: str, payload: dict) -> bool:
    """Deliver an org webhook OFF the request path.

    fire_org_webhook() was previously called synchronously from
    labs/completion.py and accounts/views.py, so every lab completion blocked on
    a 5-second timeout against a URL the org owner controls. That was both a
    latency amplifier and half of an SSRF (the other half being the missing URL
    validation, now in url_safety.py).

    The URL is re-validated here as well as at write time: a hostname that was
    public when it was saved can be repointed at a private address later, and
    this is the last gate before the socket is opened. The addresses this
    validation resolved are handed to the request so the name is not looked up
    again — otherwise the gate and the socket could see different answers.
    """
    from .models import Organization
    from .url_safety import UnsafeURLError, validate_and_resolve

    org = Organization.objects.filter(id=org_id).first()
    if not org or not org.webhook_url:
        return False
    try:
        _, addresses = validate_and_resolve(org.webhook_url)
    except UnsafeURLError as exc:
        # Do not retry — a private target will still be private next time.
        logger.warning(
            "Refusing org webhook for org=%s event=%s: %s", org.slug, event, exc
        )
        return False
    return _post_org_webhook(org, event, payload, addresses=addresses)


def fire_org_webhook(org, event: str, payload: dict) -> bool:
    """Queue an org webhook. Never blocks the caller, never raises.

    Kept as the public entrypoint so the two call sites did not need to change
    shape. Falls back to a synchronous send only if the broker is unreachable,
    matching how the Jira team-reply path degrades.
    """
    if not org or not getattr(org, "webhook_url", ""):
        return False
    try:
        deliver_org_webhook.delay(str(org.id), event, payload)
        return True
    except Exception as exc:
        logger.warning(
            "Broker unavailable for org webhook %s → %s, sending inline: %s",
            getattr(org, "slug", "?"), event, exc,
        )
        try:
            from .url_safety import validate_and_resolve

            _, addresses = validate_and_resolve(org.webhook_url)
        except Exception:
            return False
        return _post_org_webhook(org, event, payload, addresses=addresses)
