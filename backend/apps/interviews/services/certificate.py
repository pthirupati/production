"""Issue interview completion certificates."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.interviews.models import InterviewCampaign, InterviewCertificate


def issue_certificate(campaign: InterviewCampaign) -> InterviewCertificate | None:
    if hasattr(campaign, "certificate"):
        return campaign.certificate

    user = campaign.user
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
