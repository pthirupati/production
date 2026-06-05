from rest_framework import serializers
from .models import LabSession
from apps.question_bank.serializers import ScenarioListSerializer


class LabSessionSerializer(serializers.ModelSerializer):
    scenario_detail = ScenarioListSerializer(source="scenario", read_only=True)
    time_remaining = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = LabSession
        fields = [
            "id", "user", "scenario", "scenario_detail", "status",
            "provider", "container_id", "container_name",
            "instance_id", "ssh_host",
            "started_at", "ended_at", "duration_limit",
            "time_remaining", "is_expired",
            "score", "hints_used", "validation_passed",
            "jira_issue_key", "jira_issue_url",
        ]
        read_only_fields = [
            "id", "user", "status", "container_id", "container_name",
            "instance_id", "ssh_host",
            "started_at", "ended_at", "score", "hints_used", "validation_passed",
        ]


class StartLabSerializer(serializers.Serializer):
    scenario_id = serializers.IntegerField()


class ValidateLabSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
