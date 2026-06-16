"""Interview API serializers."""

from rest_framework import serializers

from apps.interviews.models import (
    CandidateProfile,
    InterviewCampaign,
    InterviewCertificate,
    InterviewMessage,
    InterviewPlanTier,
    InterviewQuestion,
    InterviewReport,
    InterviewRound,
)


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
    class Meta:
        model = InterviewMessage
        fields = ("id", "role", "content", "message_type", "score", "metadata", "created_at")


class InterviewReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewReport
        fields = (
            "passed", "technical_score", "communication_score", "problem_solving_score",
            "practical_score", "presence_score", "resume_alignment_score", "overall_score",
            "strengths", "improvements", "dressing_notes", "summary", "study_plan",
            "question_breakdown", "generated_at",
        )


class InterviewRoundSerializer(serializers.ModelSerializer):
    messages = InterviewMessageSerializer(many=True, read_only=True)
    report = InterviewReportSerializer(read_only=True)
    is_sample = serializers.BooleanField(source="campaign.is_sample", read_only=True)

    class Meta:
        model = InterviewRound
        fields = (
            "id", "campaign_id", "round_number", "round_type", "title", "duration_minutes",
            "extension_minutes", "max_extension_minutes", "status", "scheduled_at",
            "schedule_deadline", "started_at", "ended_at", "ends_at", "pass_threshold",
            "overall_score", "persona_name", "persona_voice_id", "invite_token",
            "questions_asked", "difficulty_level", "practical_lab_session_id", "is_sample",
            "messages", "report",
        )


class InterviewCampaignListSerializer(serializers.ModelSerializer):
    primary_technology_name = serializers.CharField(
        source="primary_technology.name", read_only=True, allow_null=True
    )

    class Meta:
        model = InterviewCampaign
        fields = (
            "id", "title", "round_count", "status", "experience_level",
            "primary_technology_name", "current_round_number", "overall_score",
            "is_sample", "created_at", "completed_at",
        )


class InterviewCampaignDetailSerializer(serializers.ModelSerializer):
    rounds = InterviewRoundSerializer(many=True, read_only=True)
    certificate_id = serializers.CharField(source="certificate.certificate_id", read_only=True, allow_null=True)

    class Meta:
        model = InterviewCampaign
        fields = (
            "id", "title", "round_count", "status", "profile_snapshot",
            "primary_technology", "experience_level", "current_round_number",
            "overall_score", "rounds", "certificate_id", "is_sample",
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
