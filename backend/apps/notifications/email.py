import logging
import re
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template.exceptions import TemplateDoesNotExist
from django.conf import settings

logger = logging.getLogger(__name__)

_E2E_SUFFIXES = getattr(settings, "E2E_TEST_EMAIL_SUFFIXES", ("@fixitlab-test.local",))


def should_skip_real_email(to_email: str) -> bool:
    """Skip outbound delivery for CI/E2E test addresses or when SKIP_EMAIL_TESTS is set."""
    if getattr(settings, "SKIP_EMAIL_TESTS", False):
        return True
    email = (to_email or "").strip().lower()
    return any(email.endswith(suffix) for suffix in _E2E_SUFFIXES)


def _strip_html(html):
    """Convert HTML email to plain text fallback."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def _log_email(subject, to_email, template, status, error=""):
    """Log email to database for monitoring."""
    try:
        from .models import EmailLog
        EmailLog.objects.create(
            subject=subject[:500],
            to_email=to_email,
            template=template,
            status=status,
            error=error[:1000] if error else "",
        )
    except Exception as e:
        logger.debug(f"Could not log email to database: {e}")


def _send_via_sendgrid(subject, to_email, html_content, text_content):
    """Send via SendGrid HTTP API (works when hosting provider blocks SMTP ports)."""
    api_key = getattr(settings, "SENDGRID_API_KEY", "") or ""
    if not api_key:
        return False
    import requests
    from_email = settings.EMAIL_HOST_USER or "no-reply@fixitlab.com"
    if "<" in from_email:
        from_email = from_email.split("<")[-1].rstrip(">")
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_content or subject},
            {"type": "text/html", "value": html_content},
        ],
    }
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"SendGrid HTTP {resp.status_code}: {resp.text[:200]}")
    return True


def _deliver(subject, to_email, html_content, text_content):
    """
    Delivery order (first match wins):
    1. Gmail API (HTTPS) — works on DigitalOcean with your Gmail account
    2. SendGrid API (HTTPS) — optional third-party
    3. SMTP — works locally / on hosts that allow port 587
    """
    from .gmail_api import is_gmail_api_configured, send_via_gmail_api

    if is_gmail_api_configured():
        send_via_gmail_api(subject, to_email, html_content, text_content)
        return "gmail_api"

    if getattr(settings, "SENDGRID_API_KEY", ""):
        _send_via_sendgrid(subject, to_email, html_content, text_content)
        return "sendgrid"

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)
    return "smtp"


def send_email(subject, to_email, template, context=None):
    """
    Send HTML email using a template.
    Falls back gracefully if template is missing or email delivery fails.
    """
    context = context or {}

    try:
        html_content = render_to_string(template, context)
        html_content = (
            html_content.replace("#94a3b8", "#d1d5db")
            .replace("#64748b", "#b0bcc9")
            .replace("#475569", "#94a3b8")
            .replace("color:#8b9cb3", "color:#cbd5e1")
        )
    except TemplateDoesNotExist:
        logger.warning(f"Email template '{template}' not found — skipping email to {to_email}")
        _log_email(subject, to_email, template, "failed", "Template not found")
        return False

    text_content = _strip_html(html_content)

    if should_skip_real_email(to_email):
        logger.info("Skipping real email delivery to %s (test/CI mode)", to_email)
        _log_email(subject, to_email, template, "sent", "skipped:test_mode")
        return True

    try:
        via = _deliver(subject, to_email, html_content, text_content)
        logger.info(f"Email sent via {via}: '{subject}' to {to_email}")
        _log_email(subject, to_email, template, "sent")
        return True
    except Exception as e:
        err = str(e)
        logger.error(f"Email delivery failed to {to_email}: {err}")
        _log_email(subject, to_email, template, "failed", err)
        return False
