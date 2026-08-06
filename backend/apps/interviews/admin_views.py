"""Admin API for Interview Studio — full control, analytics, pricing."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from apps.adminpanel.permissions import IsPlatformAdmin
from apps.interviews.models import (
    InterviewCampaign,
    InterviewCertificate,
    InterviewEntitlement,
    InterviewInvitation,
    InterviewPlanTier,
    InterviewPlatformSettings,
    InterviewQuestion,
    InterviewReport,
    InterviewRound,
    InterviewTemplate,
    InterviewVoiceOption,
)
from apps.interviews.serializers import (
    InterviewInvitationSerializer,
    InterviewPlanTierSerializer,
    InterviewQuestionSerializer,
    InterviewTemplateSerializer,
)
from apps.interviews.billing_views import activate_interview_plan
from apps.interviews.services.interview_settings import get_platform_settings, settings_payload
from apps.notifications.models import MarketingEmailLog


def _interview_funnel_metrics(days: int) -> dict:
    """Sample interview → paid subscribe conversion funnel."""
    since = timezone.now() - timedelta(days=days)

    sample_campaigns = InterviewCampaign.objects.filter(is_sample=True, created_at__gte=since)
    sample_started = sample_campaigns.count()
    sample_completed = sample_campaigns.filter(status="completed").count()

    completed_user_ids = list(
        sample_campaigns.filter(status="completed")
        .values_list("user_id", flat=True)
        .distinct()
    )

    paid_conversions = 0
    conversion_days = []
    for uid in completed_user_ids:
        sample = (
            InterviewCampaign.objects.filter(user_id=uid, is_sample=True, status="completed")
            .order_by("-completed_at")
            .first()
        )
        if not sample or not sample.completed_at:
            continue
        ent = InterviewEntitlement.objects.filter(user_id=uid).select_related("plan_tier").first()
        if not ent or ent.is_complimentary or ent.is_admin_granted_free:
            continue
        if not ent.plan_tier or ent.plan_tier.code not in ("pro", "premium"):
            continue
        if not ent.period_start or ent.period_start <= sample.completed_at:
            continue
        paid_conversions += 1
        conversion_days.append((ent.period_start - sample.completed_at).days)

    nudges_sent = MarketingEmailLog.objects.filter(
        campaign__in=(
            "interview_sample_nudge",
            "combined_subscribe_nudge",
        ),
        sent_at__gte=since,
    ).count()

    median_days = 0
    if conversion_days:
        conversion_days.sort()
        mid = len(conversion_days) // 2
        median_days = conversion_days[mid]

    rate = round(100 * paid_conversions / sample_completed, 1) if sample_completed else 0

    daily = list(
        sample_campaigns.filter(status="completed", completed_at__isnull=False)
        .annotate(day=TruncDate("completed_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    return {
        "sample_started": sample_started,
        "sample_completed": sample_completed,
        "paid_conversions": paid_conversions,
        "conversion_rate_pct": rate,
        "median_days_to_convert": median_days,
        "nudges_sent": nudges_sent,
        "daily_sample_completions": [
            {"date": row["day"].isoformat() if row["day"] else None, "count": row["count"]}
            for row in daily
        ],
    }


class AdminInterviewOverviewView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)
        campaigns = InterviewCampaign.objects.filter(created_at__gte=since)
        rounds = InterviewRound.objects.filter(created_at__gte=since)
        reports = InterviewReport.objects.filter(generated_at__gte=since)
        return Response({
            **settings_payload(),
            "days": days,
            "campaigns_total": campaigns.count(),
            "campaigns_completed": campaigns.filter(status="completed").count(),
            "campaigns_failed": campaigns.filter(status="failed").count(),
            "campaigns_in_progress": campaigns.filter(status="in_progress").count(),
            "rounds_total": rounds.count(),
            "rounds_in_progress": rounds.filter(status="in_progress").count(),
            "rounds_scheduled": rounds.filter(status__in=("scheduled", "ready", "schedulable")).count(),
            "rounds_passed": rounds.filter(status="passed").count(),
            "rounds_failed": rounds.filter(status="failed").count(),
            "avg_round_score": rounds.filter(overall_score__isnull=False).aggregate(avg=Avg("overall_score"))["avg"] or 0,
            "pass_rate": _pass_rate(rounds),
            "certificates_issued": InterviewCertificate.objects.filter(issued_at__gte=since).count(),
            "active_entitlements": InterviewEntitlement.objects.filter(is_active=True).count(),
            "complimentary_users": InterviewEntitlement.objects.filter(
                Q(is_complimentary=True) | Q(is_admin_granted_free=True)
            ).count(),
            "questions_in_bank": InterviewQuestion.objects.filter(is_active=True).count(),
            "reports_generated": reports.count(),
            "by_level": list(
                campaigns.values("experience_level").annotate(count=Count("id")).order_by("-count")
            ),
            "by_round_type": list(
                rounds.values("round_type").annotate(count=Count("id")).order_by("-count")
            ),
            "funnel": _interview_funnel_metrics(days),
        })


def _pass_rate(rounds):
    done = rounds.filter(status__in=("passed", "failed"))
    if not done.exists():
        return 0
    return round(100 * done.filter(status="passed").count() / done.count(), 1)


class AdminInterviewSettingsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response(settings_payload())

    def put(self, request):
        row = get_platform_settings()
        for field in (
            "enabled", "staff_free_by_default", "free_campaigns_per_month",
            "sample_enabled", "sample_duration_minutes",
            "av_grace_seconds", "schedule_window_hours", "default_pass_threshold",
            "allow_admin_observer", "voice_engine",
        ):
            if field in request.data:
                setattr(row, field, request.data[field])
        row.save()
        return Response(settings_payload())


class AdminInterviewCampaignsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_filter = request.query_params.get("status")
        qs = InterviewCampaign.objects.select_related("user", "primary_technology").order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs[:300]
        data = []
        for c in qs:
            active_round = c.rounds.filter(status="in_progress").first()
            data.append({
                "id": str(c.id),
                "title": c.title,
                "user": {"id": c.user_id, "email": c.user.email, "username": c.user.username},
                "status": c.status,
                "round_count": c.round_count,
                "experience_level": c.experience_level,
                "technology": c.primary_technology.name if c.primary_technology else "",
                "overall_score": c.overall_score,
                "created_at": c.created_at.isoformat(),
                "active_round_id": str(active_round.id) if active_round else None,
            })
        return Response({"campaigns": data})


class AdminInterviewQuestionsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = InterviewQuestion.objects.all().order_by("-created_at")[:500]
        return Response({"questions": InterviewQuestionSerializer(qs, many=True).data})

    def post(self, request):
        ser = InterviewQuestionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        q = ser.save()
        return Response(InterviewQuestionSerializer(q).data, status=201)


class AdminInterviewQuestionDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        q = InterviewQuestion.objects.get(pk=pk)
        ser = InterviewQuestionSerializer(q, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        InterviewQuestion.objects.filter(pk=pk).delete()
        return Response(status=204)


class AdminInterviewAnswerCorpusView(APIView):
    """List / upload reference-answer text files per technology."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.interviews.models import InterviewAnswerCorpus

        tech_id = request.query_params.get("technology")
        qs = InterviewAnswerCorpus.objects.select_related("technology").order_by("-updated_at")
        if tech_id:
            qs = qs.filter(technology_id=tech_id)
        data = [
            {
                "id": c.id,
                "technology_id": c.technology_id,
                "technology_name": c.technology.name if c.technology_id else "",
                "technology_slug": c.technology.slug if c.technology_id else "",
                "title": c.title,
                "entry_count": len(c.entries or []),
                "is_active": c.is_active,
                "uploaded_at": c.uploaded_at,
                "updated_at": c.updated_at,
            }
            for c in qs[:100]
        ]
        return Response({"corpora": data})

    def post(self, request):
        from apps.interviews.models import InterviewAnswerCorpus
        from apps.interviews.services.answer_corpus import parse_answer_text
        from apps.question_bank.models import Technology

        tech_id = request.data.get("technology_id") or request.data.get("technology")
        if not tech_id:
            return Response({"error": "technology_id is required"}, status=400)
        try:
            tech = Technology.objects.get(pk=tech_id)
        except Technology.DoesNotExist:
            return Response({"error": "Technology not found"}, status=404)

        raw = ""
        upload = request.FILES.get("file")
        if upload:
            raw = upload.read().decode("utf-8", errors="replace")
        else:
            raw = request.data.get("raw_text") or request.data.get("content") or ""

        if not raw.strip():
            return Response({"error": "Upload a .txt file or paste raw_text"}, status=400)

        entries = parse_answer_text(raw)
        title = (request.data.get("title") or upload.name if upload else "") or f"{tech.name} answers"
        corpus = InterviewAnswerCorpus.objects.create(
            technology=tech,
            title=title[:200],
            raw_text=raw,
            entries=entries,
            is_active=True,
        )
        return Response(
            {
                "id": corpus.id,
                "title": corpus.title,
                "entry_count": len(entries),
                "technology_slug": tech.slug,
            },
            status=201,
        )


class AdminInterviewAnswerCorpusDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def delete(self, request, pk):
        from apps.interviews.models import InterviewAnswerCorpus

        InterviewAnswerCorpus.objects.filter(pk=pk).delete()
        return Response(status=204)

    def put(self, request, pk):
        from apps.interviews.models import InterviewAnswerCorpus

        corpus = InterviewAnswerCorpus.objects.get(pk=pk)
        if "is_active" in request.data:
            corpus.is_active = bool(request.data["is_active"])
        if "title" in request.data:
            corpus.title = str(request.data["title"])[:200]
        corpus.save()
        return Response({"id": corpus.id, "is_active": corpus.is_active, "title": corpus.title})


class AdminInterviewTiersView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        tiers = InterviewPlanTier.objects.all()
        return Response({"tiers": InterviewPlanTierSerializer(tiers, many=True).data})

    def post(self, request):
        ser = InterviewPlanTierSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tier = InterviewPlanTier.objects.create(**ser.validated_data)
        return Response(InterviewPlanTierSerializer(tier).data, status=201)


class AdminInterviewTierDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        tier = InterviewPlanTier.objects.get(pk=pk)
        for field in (
            "name", "description", "price_inr", "interviews_per_month", "max_rounds",
            "voice_enabled", "practical_enabled", "certificate_enabled", "is_active", "order",
        ):
            if field in request.data:
                setattr(tier, field, request.data[field])
        tier.save()
        return Response(InterviewPlanTierSerializer(tier).data)


class AdminInterviewEntitlementsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = InterviewEntitlement.objects.select_related("user", "plan_tier").order_by("-updated_at")[:300]
        rows = []
        for e in qs:
            rows.append({
                "user_id": e.user_id,
                "email": e.user.email,
                "plan": e.plan_tier.code if e.plan_tier else None,
                "interviews_remaining": e.interviews_remaining,
                "is_active": e.is_active,
                "is_complimentary": e.is_complimentary,
                "is_admin_granted_free": e.is_admin_granted_free,
                "period_end": e.period_end.isoformat() if e.period_end else None,
            })
        return Response({"entitlements": rows})

    def post(self, request):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        email = request.data.get("email", "").strip()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "User not found"}, status=404)

        grant_free = bool(request.data.get("grant_free", False))
        if grant_free:
            ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
            premium = InterviewPlanTier.objects.filter(code="premium", is_active=True).first()
            ent.plan_tier = premium
            ent.is_active = True
            ent.is_complimentary = True
            ent.is_admin_granted_free = True
            ent.interviews_remaining = int(request.data.get("interviews_remaining", 999))
            ent.period_end = timezone.now() + timedelta(days=3650)
            ent.save()
            _audit_entitlement_grant(
                request, user,
                event="interview_grant_free",
                detail={
                    "plan": "premium",
                    "interviews_remaining": ent.interviews_remaining,
                    "period_end": ent.period_end.isoformat() if ent.period_end else None,
                    "complimentary": True,
                },
            )
            return Response({"ok": True, "user_id": user.id, "grant_free": True})

        tier_code = request.data.get("plan_code", "pro")
        tier = InterviewPlanTier.objects.filter(code=tier_code).first()
        if not tier:
            return Response({"error": "Plan not found"}, status=404)
        activate_interview_plan(user, tier)
        ent = InterviewEntitlement.objects.get(user=user)
        ent.is_complimentary = bool(request.data.get("complimentary", False))
        ent.save(update_fields=["is_complimentary"])
        _audit_entitlement_grant(
            request, user,
            event="interview_plan_activated",
            detail={"plan": tier_code, "complimentary": ent.is_complimentary},
        )
        return Response({"ok": True, "user_id": user.id})



def _audit_entitlement_grant(request, user, *, event: str, detail: dict) -> None:
    """Record who granted whose interview access, and what (audit Z1-15).

    The billing admin's bulk actions were audited under Z1-15; this is the same
    class of change on a different surface. Granting a 10-year premium entitlement
    with 999 interviews is the single most valuable thing an operator can hand out
    here, and it left no record of who did it or for whom.

    Best-effort — support must stay able to act on a live problem — but logged
    loudly, because an unrecorded grant is the entire defect.
    """
    try:
        from apps.audit.models import AuditLog

        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action="admin_action",
            resource=f"/admin/interviews/entitlement/{user.id}",
            metadata={
                "event": event,
                "target_user_id": user.id,
                "target_email": getattr(user, "email", ""),
                "target_username": getattr(user, "username", ""),
                **detail,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Interview entitlement grant for user=%s was NOT audited (%s) — paid "
            "access changed without a record.", getattr(user, "id", "?"), exc,
        )


class AdminInterviewVoicesView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        voices = InterviewVoiceOption.objects.all()
        return Response({
            "voices": [
                {
                    "id": v.id,
                    "code": v.code,
                    "label": v.label,
                    "locale": v.locale,
                    "gender": v.gender,
                    "region": v.region,
                    "browser_voice_hint": v.browser_voice_hint,
                    "pitch": v.pitch,
                    "rate": v.rate,
                    "is_default": v.is_default,
                    "is_active": v.is_active,
                    "order": v.order,
                }
                for v in voices
            ]
        })

    def post(self, request):
        if request.data.get("is_default"):
            InterviewVoiceOption.objects.update(is_default=False)
        v = InterviewVoiceOption.objects.create(
            code=request.data["code"],
            label=request.data["label"],
            locale=request.data.get("locale", "en-IN"),
            gender=request.data.get("gender", "female"),
            region=request.data.get("region", "india"),
            browser_voice_hint=request.data.get("browser_voice_hint", ""),
            pitch=float(request.data.get("pitch", 1.0)),
            rate=float(request.data.get("rate", 0.95)),
            is_default=bool(request.data.get("is_default", False)),
            is_active=bool(request.data.get("is_active", True)),
            order=int(request.data.get("order", 0)),
        )
        return Response({"id": v.id, "code": v.code}, status=201)


class AdminInterviewVoiceDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        v = InterviewVoiceOption.objects.get(pk=pk)
        if request.data.get("is_default"):
            InterviewVoiceOption.objects.exclude(pk=pk).update(is_default=False)
        for field in (
            "label", "locale", "gender", "region", "browser_voice_hint",
            "pitch", "rate", "is_default", "is_active", "order",
        ):
            if field in request.data:
                setattr(v, field, request.data[field])
        v.save()
        return Response({"ok": True})

    def delete(self, request, pk):
        InterviewVoiceOption.objects.filter(pk=pk).delete()
        return Response(status=204)


# ---------------------------------------------------------------------------
# Parity admin: interview templates (job-role library + question-set builder),
# invitations overview, and recruiter candidate comparison.
# ---------------------------------------------------------------------------

class AdminInterviewTemplatesView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.interviews.services.templates import ensure_default_templates

        ensure_default_templates()
        qs = InterviewTemplate.objects.all()
        return Response({"templates": InterviewTemplateSerializer(qs, many=True).data})

    def post(self, request):
        from django.utils.text import slugify

        data = dict(request.data)
        if not data.get("slug") and data.get("name"):
            data["slug"] = slugify(data["name"])[:140]
        ser = InterviewTemplateSerializer(data=data)
        ser.is_valid(raise_exception=True)
        tmpl = ser.save(created_by=request.user)
        return Response(InterviewTemplateSerializer(tmpl).data, status=201)


class AdminInterviewTemplateDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        tmpl = InterviewTemplate.objects.get(pk=pk)
        ser = InterviewTemplateSerializer(tmpl, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        InterviewTemplate.objects.filter(pk=pk).delete()
        return Response(status=204)


class AdminInterviewInvitationsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = InterviewInvitation.objects.select_related("template", "created_by").order_by("-created_at")[:300]
        return Response({"invitations": InterviewInvitationSerializer(qs, many=True).data})


class AdminInterviewComparisonView(APIView):
    """Recruiter candidate comparison/ranking across all completed campaigns."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.interviews.services.analytics import recruiter_comparison

        template_id = request.query_params.get("template_id") or None
        technology_id = request.query_params.get("technology_id") or None
        return Response(recruiter_comparison(template_id=template_id, technology_id=technology_id))
