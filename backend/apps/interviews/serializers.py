"""Interview API serializers."""

import logging

from rest_framework import serializers

from apps.interviews.models import (
    AsyncVideoResponse,
    CandidateProfile,
    InterviewCampaign,
    InterviewCertificate,
    InterviewInvitation,
    InterviewMessage,
    InterviewPlanTier,
    InterviewQuestion,
    InterviewReport,
    InterviewRound,
    InterviewTemplate,
)

logger = logging.getLogger(__name__)


def safe_message_data(msg) -> dict | None:
    """Serialize one message without letting a single bad row 500 the interview room."""
    if msg is None:
        return None
    try:
        return InterviewMessageSerializer(msg).data
    except Exception:  # noqa: BLE001
        logger.exception("Failed to serialize interview message %s", getattr(msg, "pk", None))
        created = getattr(msg, "created_at", None)
        return {
            "id": str(getattr(msg, "id", "")),
            "role": getattr(msg, "role", "") or "candidate",
            "content": (getattr(msg, "content", None) or "")[:8000],
            "message_type": getattr(msg, "message_type", "text") or "text",
            "score": getattr(msg, "score", None),
            "metadata": msg.metadata if isinstance(getattr(msg, "metadata", None), dict) else {},
            "practical_config": None,
            "created_at": created.isoformat() if created else None,
        }


def safe_report_data(report) -> dict | None:
    if report is None:
        return None
    try:
        return InterviewReportSerializer(report).data
    except Exception:  # noqa: BLE001
        logger.exception("Failed to serialize interview report %s", getattr(report, "pk", None))
        return None


def safe_round_data(round_obj) -> dict:
    """Full round payload with per-message isolation — never 500 on one bad message."""
    try:
        data = InterviewRoundSerializer(round_obj).data
    except Exception:  # noqa: BLE001
        logger.exception("Failed to serialize interview round %s", getattr(round_obj, "id", None))
        data = {
            "id": str(round_obj.id),
            "campaign_id": str(round_obj.campaign_id),
            "round_number": round_obj.round_number,
            "round_type": round_obj.round_type,
            "title": round_obj.title or "",
            "status": round_obj.status,
            "messages": [],
            "report": None,
        }
    return data


class InterviewPlanTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewPlanTier
        fields = (
            "code", "name", "description", "price_inr", "interviews_per_month",
            "max_rounds", "voice_enabled", "practical_enabled", "certificate_enabled",
        )


class CandidateProfileSerializer(serializers.ModelSerializer):
    primary_technology_name = serializers.CharField(
        source="primary_technology.name", read_only=True, allow_null=True
    )
    has_resume = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = (
            "resume_text", "resume_parsed", "has_resume", "primary_technology", "primary_technology_name",
            "secondary_technologies", "experience_level", "years_experience",
            "current_company", "current_package_lpa", "target_role", "target_companies",
            "voice_id", "voice_locale", "location", "notice_period_days", "updated_at",
        )
        read_only_fields = ("resume_parsed", "updated_at", "has_resume")

    def get_has_resume(self, obj):
        return bool(obj.resume_file or (obj.resume_text or "").strip())


class InterviewMessageSerializer(serializers.ModelSerializer):
    # SHARED API CONTRACT: practical questions expose practical_config so the
    # frontend renders a code editor (kind == "code") or a command terminal
    # (kind == "command"). It already lives inside `metadata` (the engine stamps
    # metadata["practical_config"] when it asks a practical question); we surface
    # it as a top-level field too without removing anything the frontend reads.
    practical_config = serializers.SerializerMethodField()

    class Meta:
        model = InterviewMessage
        fields = (
            "id", "role", "content", "message_type", "score", "metadata",
            "practical_config", "created_at",
        )

    def get_practical_config(self, obj):
        meta = obj.metadata if isinstance(obj.metadata, dict) else {}
        cfg = meta.get("practical_config")
        if not isinstance(cfg, dict) or not cfg:
            return None
        # Normalise the contract keys: kind ("code" | "command") + language.
        kind = cfg.get("kind")
        if not kind:
            kind = "code" if cfg.get("code") else "command"
        out = dict(cfg)
        out["kind"] = kind
        if kind == "code" and not out.get("language"):
            code_spec = cfg.get("code") if isinstance(cfg.get("code"), dict) else {}
            out["language"] = code_spec.get("language") or "python"
        return out


class InterviewReportSerializer(serializers.ModelSerializer):
    recommendation_label = serializers.SerializerMethodField()

    class Meta:
        model = InterviewReport
        fields = (
            "passed", "technical_score", "communication_score", "problem_solving_score",
            "practical_score", "presence_score", "resume_alignment_score", "overall_score",
            "strengths", "improvements", "dressing_notes", "summary", "study_plan",
            "question_breakdown", "recommendation", "recommendation_label",
            "competency_ratings", "confidence_analysis", "generated_at",
        )

    def get_recommendation_label(self, obj):
        from apps.interviews.services.scorecard import RECOMMENDATION_LABELS

        return RECOMMENDATION_LABELS.get(obj.recommendation, "")


class InterviewRoundSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()
    report = serializers.SerializerMethodField()
    is_sample = serializers.BooleanField(source="campaign.is_sample", read_only=True)
    host_state = serializers.SerializerMethodField()

    class Meta:
        model = InterviewRound
        fields = (
            "id", "campaign_id", "round_number", "round_type", "title", "duration_minutes",
            "extension_minutes", "max_extension_minutes", "status", "scheduled_at",
            "schedule_deadline", "started_at", "ended_at", "ends_at", "paused_at", "pass_threshold",
            "overall_score", "persona_name", "persona_voice_id", "invite_token",
            "questions_asked", "difficulty_level", "practical_lab_session_id", "is_sample",
            "mode", "language", "last_practical_submission", "messages", "report", "host_state",
        )

    def get_messages(self, obj):
        try:
            qs = obj.messages.all().order_by("created_at")
        except Exception:  # noqa: BLE001
            return []
        return [m for m in (safe_message_data(msg) for msg in qs) if m is not None]

    def get_report(self, obj):
        try:
            return safe_report_data(obj.report)
        except Exception:  # noqa: BLE001
            return None

    def get_host_state(self, obj):
        try:
            from apps.interviews.services.admin_host import host_state

            return host_state(obj)
        except Exception:  # noqa: BLE001
            return {"joined": False, "ai_enabled": True}


class InterviewCampaignListSerializer(serializers.ModelSerializer):
    primary_technology_name = serializers.CharField(
        source="primary_technology.name", read_only=True, allow_null=True
    )

    class Meta:
        model = InterviewCampaign
        fields = (
            "id", "title", "round_count", "status", "experience_level",
            "primary_technology_name", "current_round_number", "overall_score",
            "is_sample", "mode", "created_at", "completed_at",
        )


class InterviewCampaignDetailSerializer(serializers.ModelSerializer):
    rounds = InterviewRoundSerializer(many=True, read_only=True)
    certificate_id = serializers.CharField(source="certificate.certificate_id", read_only=True, allow_null=True)

    class Meta:
        model = InterviewCampaign
        fields = (
            "id", "title", "round_count", "status", "profile_snapshot",
            "primary_technology", "experience_level", "current_round_number",
            "overall_score", "rounds", "certificate_id", "is_sample", "mode",
            "created_at", "completed_at",
        )


class InterviewQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewQuestion
        fields = (
            "id", "slug", "technology", "technology_tags", "experience_levels",
            "round_types", "category", "difficulty", "question_text", "follow_ups",
            "expected_keywords", "practical_config", "is_active",
        )


class InterviewCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewCertificate
        fields = (
            "certificate_id", "holder_name", "technology_name", "level",
            "rounds_cleared", "overall_score", "issued_at", "expires_at",
            "linkedin_share_text",
        )


class InterviewTemplateSerializer(serializers.ModelSerializer):
    primary_technology_name = serializers.CharField(
        source="primary_technology.name", read_only=True, allow_null=True
    )

    class Meta:
        model = InterviewTemplate
        fields = (
            "id", "slug", "name", "role_title", "description", "primary_technology",
            "primary_technology_name", "technology_tags", "experience_level",
            "round_count", "round_plan", "pass_threshold", "competencies",
            "pinned_question_ids", "is_public", "is_active", "times_used",
            "order", "created_at", "updated_at",
        )
        read_only_fields = ("id", "times_used", "created_at", "updated_at")


class InterviewInvitationSerializer(serializers.ModelSerializer):
    invite_url = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True, allow_null=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = InterviewInvitation
        fields = (
            "id", "token", "invite_url", "template", "template_name", "candidate_email",
            "candidate_name", "role_title", "mode", "message", "status", "campaign",
            "expires_at", "is_expired", "opened_at", "accepted_at", "completed_at",
            "email_sent", "created_at",
        )
        read_only_fields = (
            "id", "token", "status", "campaign", "opened_at", "accepted_at",
            "completed_at", "email_sent", "created_at",
        )

    def get_invite_url(self, obj):
        from apps.interviews.services.invitations import invite_url

        return invite_url(obj)


class AsyncVideoResponseSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = AsyncVideoResponse
        fields = (
            "id", "question_index", "prompt_text", "video_url", "transcript",
            "duration_seconds", "score", "analysis", "created_at",
        )

    def get_video_url(self, obj):
        try:
            return obj.video_file.url if obj.video_file else None
        except Exception:  # noqa: BLE001
            return None
