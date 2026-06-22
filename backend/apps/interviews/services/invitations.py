"""Candidate invitation flow — shareable interview links.

Parity with aiinterviews.io / TestGorilla candidate-invite links: a recruiter
generates a tokenised invitation (optionally tied to a job-role template); the
invitee opens the public link, signs in, and the interview is provisioned for
them. Notifications use the EXISTING free email pipeline — no paid email service.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.interviews.models import (
    CandidateProfile,
    InterviewCampaign,
    InterviewInvitation,
)
from apps.interviews.serializers import CandidateProfileSerializer


def invite_url(invitation: InterviewInvitation) -> str:
    base = getattr(settings, "FRONTEND_URL", "") or ""
    return f"{base}/interviews/invite/{invitation.token}"


def create_invitation(
    *,
    created_by,
    template=None,
    candidate_email: str = "",
    candidate_name: str = "",
    role_title: str = "",
    mode: str = "live",
    message: str = "",
    expires_in_days: int = 14,
) -> InterviewInvitation:
    expires_at = timezone.now() + timedelta(days=max(1, int(expires_in_days or 14)))
    inv = InterviewInvitation.objects.create(
        created_by=created_by,
        template=template,
        candidate_email=(candidate_email or "").strip(),
        candidate_name=(candidate_name or "").strip(),
        role_title=(role_title or (template.role_title if template else "")).strip(),
        mode=mode if mode in ("live", "async_video") else "live",
        message=message or "",
        expires_at=expires_at,
    )
    return inv


def send_invitation_email(invitation: InterviewInvitation) -> bool:
    """Deliver the invite link over the existing free email pipeline."""
    if not invitation.candidate_email:
        return False
    try:
        from apps.notifications.tasks import send_notification_email

        send_notification_email.delay(
            subject="You're invited to a FixitLab interview",
            to_email=invitation.candidate_email,
            template="emails/interview_invite.html",
            context={
                "round_title": invitation.role_title or "Interview",
                "persona": "your interviewer",
                "scheduled_at": "at your convenience",
                "join_url": invite_url(invitation),
                "duration": 45,
                "message": invitation.message,
            },
        )
        invitation.email_sent = True
        invitation.save(update_fields=["email_sent"])
        return True
    except Exception:  # noqa: BLE001 - email is best-effort
        return False


def mark_opened(invitation: InterviewInvitation) -> None:
    if invitation.status == "pending":
        invitation.status = "opened"
        invitation.opened_at = timezone.now()
        invitation.save(update_fields=["status", "opened_at"])


def accept_invitation(invitation: InterviewInvitation, user) -> InterviewCampaign:
    """The invitee accepts: provision an interview campaign for them, tied to the
    invitation's template/mode. Reuses the template round builder (or the default
    plan). Returns the created (or existing) campaign.
    """
    if invitation.campaign_id and invitation.accepted_by_id == user.id:
        return invitation.campaign

    profile, _ = CandidateProfile.objects.get_or_create(user=user)
    template = invitation.template
    snap = CandidateProfileSerializer(profile).data
    # Let the template's tech/level seed the snapshot when the candidate's own
    # profile is sparse, so generation has something to work with.
    if template:
        snap.setdefault("target_role", template.role_title)
        if not snap.get("experience_level"):
            snap["experience_level"] = template.experience_level
        if template.primary_technology_id and not snap.get("primary_technology_name"):
            snap["primary_technology_name"] = template.primary_technology.name

    title = invitation.role_title or (template.name if template else "Invited interview")
    campaign = InterviewCampaign.objects.create(
        user=user,
        title=title,
        round_count=template.round_count if template else 3,
        status="scheduled",
        profile_snapshot=snap,
        primary_technology=(template.primary_technology if template else profile.primary_technology),
        experience_level=(template.experience_level if template else profile.experience_level),
        template=template,
        mode=invitation.mode,
    )

    if template:
        from apps.interviews.services.templates import create_rounds_from_template

        create_rounds_from_template(campaign, template)
    else:
        from apps.interviews.services.campaign_builder import create_campaign_rounds

        create_campaign_rounds(campaign)
        if invitation.mode == "async_video":
            campaign.rounds.update(mode="async_video")

    invitation.status = "accepted"
    invitation.accepted_by = user
    invitation.accepted_at = timezone.now()
    invitation.campaign = campaign
    invitation.save(update_fields=["status", "accepted_by", "accepted_at", "campaign"])
    return campaign
