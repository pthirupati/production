"""
Send email via Gmail API over HTTPS (port 443).

Use this on VPS providers (e.g. DigitalOcean) that block outbound SMTP ports 587/465.
Requires a one-time OAuth setup — see docs/EMAIL_AND_LABS.md and scripts/setup-gmail-oauth.py
"""
import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def is_gmail_api_configured() -> bool:
    return bool(
        getattr(settings, "GMAIL_OAUTH_CLIENT_ID", "")
        and getattr(settings, "GMAIL_OAUTH_CLIENT_SECRET", "")
        and getattr(settings, "GMAIL_OAUTH_REFRESH_TOKEN", "")
        and getattr(settings, "EMAIL_HOST_USER", "")
    )


def verify_gmail_credentials() -> tuple[bool, str]:
    """Refresh OAuth token without sending mail — for health checks."""
    if not is_gmail_api_configured():
        return False, "Gmail API not configured (missing GMAIL_OAUTH_* or EMAIL_HOST_USER)"
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=settings.GMAIL_OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GMAIL_OAUTH_CLIENT_ID,
            client_secret=settings.GMAIL_OAUTH_CLIENT_SECRET,
            scopes=[GMAIL_SEND_SCOPE],
        )
        if not creds.valid:
            creds.refresh(Request())
        return True, "Gmail OAuth token refresh OK"
    except Exception as exc:
        err = str(exc)
        logger.error("Gmail OAuth verification failed: %s", err)
        return False, err


def send_via_gmail_api(subject: str, to_email: str, html_content: str,
                       text_content: str, headers: dict | None = None) -> None:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_OAUTH_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_OAUTH_CLIENT_ID,
        client_secret=settings.GMAIL_OAUTH_CLIENT_SECRET,
        scopes=[GMAIL_SEND_SCOPE],
    )
    try:
        if not creds.valid:
            creds.refresh(Request())
    except Exception as exc:
        logger.error(
            "Gmail OAuth refresh failed (check GMAIL_OAUTH_REFRESH_TOKEN and client credentials): %s",
            exc,
        )
        raise RuntimeError(f"Gmail OAuth refresh failed: {exc}") from exc

    from_email = settings.EMAIL_HOST_USER
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.DEFAULT_FROM_EMAIL or from_email
    msg["To"] = to_email
    # Extra RFC headers (List-Unsubscribe / List-Unsubscribe-Post — audit Z6-4).
    for key, value in (headers or {}).items():
        if value:
            msg[key] = value
    if text_content:
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as exc:
        logger.error("Gmail API send failed for %s: %s", to_email, exc)
        raise RuntimeError(f"Gmail API send failed: {exc}") from exc
    logger.info("Gmail API: sent '%s' to %s", subject, to_email)
