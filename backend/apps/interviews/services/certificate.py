"""Issue interview completion certificates."""

from __future__ import annotations

import logging

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.interviews.models import InterviewCampaign, InterviewCertificate

logger = logging.getLogger(__name__)


def issue_certificate(campaign: InterviewCampaign) -> InterviewCertificate | None:
    if hasattr(campaign, "certificate"):
        return campaign.certificate

    user = campaign.user

    # Gate on the paid-tier flag.
    #
    # InterviewPlanTier.certificate_enabled is seeded False on Free and True on
    # Pro/Premium, is exposed in the entitlement payload, and is shown in the
    # pricing UI — but nothing ever checked it. _finalize_campaign called this
    # unconditionally, so a Free-tier user received the certificate that Premium
    # (Rs 2,499) is partly sold on. This was the clearest UI-only paywall in the
    # codebase: grep for certificate_enabled and every hit was a serializer,
    # admin, seed or payload — no enforcement site at all.
    #
    # Fails CLOSED on lookup error: better to withhold a certificate (recoverable
    # by re-running once the tier resolves) than to hand out the paid artefact.
    try:
        from apps.interviews.services.entitlements import get_entitlement_payload

        plan = (get_entitlement_payload(user) or {}).get("plan") or {}
        if not plan.get("certificate_enabled"):
            logger.info(
                "Certificate withheld for user=%s campaign=%s — plan %r does not "
                "include certificates",
                user.id, campaign.id, plan.get("code") or "unknown",
            )
            return None
    except Exception as exc:
        logger.warning(
            "Certificate entitlement check failed for user=%s campaign=%s (%s) — "
            "withholding rather than issuing",
            user.id, campaign.id, exc,
        )
        return None

    tech_name = campaign.primary_technology.name if campaign.primary_technology else "Multi-stack"
    date_str = timezone.now().strftime("%Y%m%d")
    cert_id = f"FIXIT-INT-{tech_name.upper().replace(' ', '-')[:12]}-{user.id}-{date_str}"

    holder = user.get_full_name() or user.username or user.email
    overall = campaign.overall_score or 0

    cert = InterviewCertificate.objects.create(
        campaign=campaign,
        user=user,
        certificate_id=cert_id,
        holder_name=holder,
        technology_name=tech_name,
        level=campaign.experience_level,
        rounds_cleared=campaign.round_count,
        overall_score=overall,
        expires_at=timezone.now() + timedelta(days=365),
        linkedin_share_text=(
            f"I cleared {campaign.round_count}-round AI mock interviews on FixitLab "
            f"({tech_name}, {campaign.experience_level} level) with score {overall:.0f}/100. "
            f"Verify: {settings.FRONTEND_URL}/verify-certificate?certificate_id={cert_id}"
        ),
    )

    try:
        from apps.notifications.tasks import send_notification_email
        from apps.interviews.services.notify import notify_certificate_issued

        notify_certificate_issued(campaign, cert)

        send_notification_email.delay(
            subject=f"Interview cleared — certificate {cert_id}",
            to_email=user.email,
            template="emails/interview_certificate.html",
            context={
                "holder_name": holder,
                "certificate_id": cert_id,
                "technology": tech_name,
                "rounds": campaign.round_count,
                "score": f"{overall:.0f}",
                "verify_url": f"{settings.FRONTEND_URL}/verify-certificate?certificate_id={cert_id}",
            },
        )
    except Exception:
        pass

    return cert
