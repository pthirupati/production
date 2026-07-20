from rest_framework import serializers
from .models import LabSession
from apps.question_bank.serializers import ScenarioListSerializer
from apps.jira_integration.helpers import resolve_jira_issue_url


class LabSessionSerializer(serializers.ModelSerializer):
    scenario_detail = ScenarioListSerializer(source="scenario", read_only=True)
    time_remaining = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    jira_issue_url = serializers.SerializerMethodField()
    host_platform = serializers.SerializerMethodField()
    hosted_as = serializers.SerializerMethodField()

    def get_jira_issue_url(self, obj):
        return resolve_jira_issue_url(obj.jira_issue_key or "")

    def _hosting_from_hosts(self, obj):
        for h in (obj.lab_hosts or []):
            if isinstance(h, dict) and (h.get("host_platform") or h.get("hosted_as")):
                return h.get("host_platform") or "", h.get("hosted_as") or ""
        return "", ""

    def get_host_platform(self, obj):
        platform, _ = self._hosting_from_hosts(obj)
        if platform:
            return platform
        try:
            from apps.labs.provisioner.simulation.hosting_persona import resolve_host_platform
            sc = obj.scenario
            tech = getattr(getattr(sc, "technology", None), "slug", "") or ""
            return resolve_host_platform(
                getattr(sc, "simulation_type", "") or "",
                getattr(sc, "slug", "") or "",
                tech_slug=tech,
            )
        except Exception:
            return "linux"

    def get_hosted_as(self, obj):
        _, line = self._hosting_from_hosts(obj)
        if line:
            return line
        try:
            from apps.labs.provisioner.simulation.hosting_persona import (
                hosted_as_line,
                resolve_host_platform,
            )
            sc = obj.scenario
            tech = getattr(getattr(sc, "technology", None), "slug", "") or ""
            platform = resolve_host_platform(
                getattr(sc, "simulation_type", "") or "",
                getattr(sc, "slug", "") or "",
                tech_slug=tech,
            )
            return hosted_as_line(platform)
        except Exception:
            return "Hosted as: Linux Lab Server (scenario-scoped)"

    class Meta:
        model = LabSession
        fields = [
            "id", "user", "scenario", "scenario_detail", "status",
            "provider", "container_id", "container_name",
            "instance_id", "ssh_host",
            "started_at", "ended_at", "duration_limit",
            "time_remaining", "is_expired",
            "score", "hints_used", "validation_passed",
            "jira_issue_key", "jira_issue_url", "lab_hosts",
            "host_platform", "hosted_as",
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
