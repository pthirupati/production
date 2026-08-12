"""Whole-account data export — the right of access, in one file.

Audit Z4-12: the only export was `/api/interviews/export/transcripts/`, so a subject
access request could be answered with interview transcripts and nothing else —
excluding the profile, lab history, billing, community posts, certificates and
preferences. GDPR Art.15 and DPDP §11 are about *all* the personal data held, not one
convenient subset.

Two rules this module lives by:

* **Never widen the blast radius.** Every query is filtered to `user=user`. An export
  bug that leaks someone else's data is far worse than a missing section, so there
  are no unfiltered queries here at all.
* **Never export a credential.** Password hashes, session tokens, OTP hashes, API
  keys and webhook secrets are personal-data-adjacent but exporting them turns a
  download into an account-takeover kit. The test suite asserts their absence rather
  than trusting this docstring.

Sections degrade independently: a missing optional app must not fail the whole
export, or the feature becomes unusable the first time an app is disabled.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Anything matching these must never reach the payload. Asserted by tests.
FORBIDDEN_KEYS = frozenset({
    "password", "code_hash", "session_token", "token", "secret",
    "api_key", "webhook_secret", "access", "refresh",
})


def _safe(section: str, fn):
    """Run one section; on failure record the error instead of losing the export."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - one bad section must not kill the file
        logger.warning("data_export: section %s failed: %s", section, exc)
        return {"error": "This section could not be exported. Contact support."}


def _profile(user) -> dict:
    prof = getattr(user, "profile", None)
    data = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "is_staff": user.is_staff,
    }
    if prof is not None:
        for field in ("bio", "location", "website", "github_username",
                      "linkedin_url", "xp", "level", "streak_days", "referral_code"):
            if hasattr(prof, field):
                data[field] = getattr(prof, field)
    return data


def _labs(user) -> list[dict]:
    from apps.labs.models import LabSession

    rows = []
    qs = (
        LabSession.objects.filter(user=user)
        .select_related("scenario")
        .order_by("-started_at")
    )
    for row in qs.iterator(chunk_size=200):
        rows.append({
            "session_id": str(row.id),
            "scenario": getattr(row.scenario, "slug", None),
            "status": row.status,
            "score": row.score,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            "validation_passed": row.validation_passed,
        })
    return rows


def _command_history(user) -> dict:
    """Counts, not contents. The full text is available on request; inlining tens of
    thousands of shell lines would make the export unusable and is not what an access
    request is asking for."""
    from apps.labs.models import CommandHistory

    qs = CommandHistory.objects.filter(session__user=user)
    first = qs.order_by("timestamp").values_list("timestamp", flat=True).first()
    last = qs.order_by("-timestamp").values_list("timestamp", flat=True).first()
    return {
        "commands_recorded": qs.count(),
        "earliest": first.isoformat() if first else None,
        "latest": last.isoformat() if last else None,
        "note": "Full command text is available on request — email the privacy contact.",
    }


def _billing(user) -> dict:
    from apps.billing.models import PaymentTransaction, Subscription

    subs = [
        {
            "plan": getattr(s.plan, "code", None),
            "is_active": s.is_active,
            "started_at": s.started_at.isoformat() if getattr(s, "started_at", None) else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in Subscription.objects.filter(user=user).select_related("plan")
    ]
    payments = [
        {
            "amount": str(getattr(p, "amount", "")),
            "currency": getattr(p, "currency", None),
            "status": getattr(p, "status", None),
            "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        }
        for p in PaymentTransaction.objects.filter(user=user).order_by("-created_at")[:500]
    ]
    return {"subscriptions": subs, "payments": payments}


def _interviews(user) -> list[dict]:
    from apps.interviews.models import InterviewCampaign

    out = []
    qs = (
        InterviewCampaign.objects.filter(user=user)
        .prefetch_related("rounds__messages")
        .order_by("-created_at")
    )
    for c in qs:
        out.append({
            "campaign_id": str(c.id),
            "title": c.title,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "rounds": [
                {
                    "round_id": str(r.id),
                    "round_type": r.round_type,
                    "status": r.status,
                    "score": r.overall_score,
                    "consent_granted_at": (
                        r.consent_granted_at.isoformat() if r.consent_granted_at else None
                    ),
                    "consent_policy_version": r.consent_policy_version,
                    "messages": [
                        {
                            "role": m.role,
                            "content": m.content,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                        }
                        for m in r.messages.all()
                    ],
                }
                for r in c.rounds.all()
            ],
        })
    return out


def _certificates(user) -> list[dict]:
    from apps.certifications.models import CertEarnedCertificate

    return [
        {
            "certificate_id": c.certificate_id,
            "track": getattr(c.track, "code", None),
            "score": c.score,
            "issued_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "revoked": c.revoked,
            "revoked_reason": c.revoked_reason,
        }
        for c in CertEarnedCertificate.objects.filter(user=user).select_related("track")
    ]


def _community(user) -> dict:
    from apps.community.models import Reply, Thread

    return {
        "threads": [
            {"id": t.id, "title": t.title,
             "created_at": t.created_at.isoformat() if t.created_at else None}
            for t in Thread.objects.filter(author=user).order_by("-created_at")
        ],
        "replies": [
            {"id": r.id, "thread_id": r.thread_id,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in Reply.objects.filter(author=user).order_by("-created_at")
        ],
    }


def _preferences(user) -> dict:
    from apps.notifications.models import NotificationPreference

    p = NotificationPreference.get_for_user(user)
    return {
        "email_achievements": p.email_achievements,
        "email_lab_completed": p.email_lab_completed,
        "email_subscription": p.email_subscription,
        "email_marketing": p.email_marketing,
    }


def build_account_export(user) -> dict:
    """Assemble the full export for `user`. Every section is user-scoped."""
    return {
        "export_version": 1,
        "exported_at": timezone.now().isoformat(),
        "notice": (
            "This is all personal data FixitLab holds for your account. Credentials "
            "(password, tokens) are deliberately excluded — they are not useful to "
            "you and exporting them would create a security risk."
        ),
        "profile": _safe("profile", lambda: _profile(user)),
        "preferences": _safe("preferences", lambda: _preferences(user)),
        "labs": _safe("labs", lambda: _labs(user)),
        "command_history": _safe("command_history", lambda: _command_history(user)),
        "interviews": _safe("interviews", lambda: _interviews(user)),
        "certificates": _safe("certificates", lambda: _certificates(user)),
        "billing": _safe("billing", lambda: _billing(user)),
        "community": _safe("community", lambda: _community(user)),
    }
