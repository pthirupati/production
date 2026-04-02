import logging
import re
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template.exceptions import TemplateDoesNotExist
from django.conf import settings

logger = logging.getLogger(__name__)


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


def send_email(subject, to_email, template, context=None):
    """
    Send HTML email using a template.
    Falls back gracefully if template is missing or email delivery fails.
    """
    context = context or {}

    try:
        html_content = render_to_string(template, context)
    except TemplateDoesNotExist:
        logger.warning(f"Email template '{template}' not found — skipping email to {to_email}")
        _log_email(subject, to_email, template, "failed", "Template not found")
        return False

    text_content = _strip_html(html_content)

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        logger.info(f"Email sent: '{subject}' to {to_email}")
        _log_email(subject, to_email, template, "sent")
        return True
    except Exception as e:
        logger.error(f"Email delivery failed to {to_email}: {e}")
        _log_email(subject, to_email, template, "failed", str(e))
        return False

