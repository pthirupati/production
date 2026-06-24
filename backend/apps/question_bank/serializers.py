from rest_framework import serializers
from .models import Technology, Scenario, Tag, Bookmark
from .scenario_copy import public_objectives


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class TechnologySerializer(serializers.ModelSerializer):
    scenario_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Technology
        fields = [
            "id", "name", "slug", "icon", "color", "description",
            "price", "is_free", "is_active", "coming_soon", "order", "scenario_count",
            "learning_path", "created_at",
            "maintenance_enabled", "maintenance_message",
            "maintenance_scheduled_start", "maintenance_scheduled_end",
        ]


class ScenarioListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing scenarios"""
    technology = TechnologySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    completion_rate = serializers.IntegerField(read_only=True, required=False)
    is_bookmarked = serializers.BooleanField(read_only=True, required=False, default=False)

    class Meta:
        model = Scenario
        fields = [
            "id", "slug", "title", "subtitle", "category", "difficulty",
            "scenario_type", "technology", "tags", "time_limit", "max_score",
            "is_free", "attempts_count", "completions_count", "completion_rate",
            "is_bookmarked", "blocked_commands",
            "lab_mode", "simulation_type", "dual_terminal", "requires_companion_hosts",
            "interview_mode", "coding_mode", "cross_technology", "vmware_link", "created_at",
        ]


class ScenarioDetailSerializer(serializers.ModelSerializer):
    """Full serializer for scenario detail view (no fix spoilers)."""
    technology = TechnologySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    hints_count = serializers.IntegerField(read_only=True, required=False)
    is_bookmarked = serializers.BooleanField(read_only=True, required=False, default=False)
    objectives = serializers.SerializerMethodField()

    class Meta:
        model = Scenario
        fields = [
            "id", "slug", "title", "subtitle", "category", "difficulty",
            "scenario_type", "technology", "tags", "description", "objectives",
            "initial_state", "time_limit", "max_score",
            "is_free", "attempts_count", "completions_count",
            "avg_completion_time", "hints_count", "is_bookmarked",
            "blocked_commands", "infrastructure_type",
            "lab_mode", "simulation_type", "dual_terminal", "requires_companion_hosts",
            "interview_mode", "coding_mode", "cross_technology", "vmware_link",
            "created_at", "updated_at",
        ]

    def get_objectives(self, scenario):
        return public_objectives(scenario.objectives)


class ScenarioAdminSerializer(serializers.ModelSerializer):
    """Full serializer for admin CRUD"""
    technology_id = serializers.PrimaryKeyRelatedField(
        queryset=Technology.objects.all(), source="technology", write_only=True
    )
    technology = TechnologySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), source="tags", many=True, write_only=True, required=False
    )

    class Meta:
        model = Scenario
        fields = [
            "id", "slug", "title", "subtitle", "category", "difficulty",
            "scenario_type", "technology", "technology_id", "tags", "tag_ids",
            "description", "objectives", "initial_state", "validation_script",
            "solution_explanation", "docker_image",
            "infrastructure_type", "cloud_setup_script", "cloud_ami", "cloud_image",
            "blocked_commands",
            "jira_priority", "jira_issue_template",
            "requires_companion_hosts", "dual_terminal", "lab_mode", "simulation_type",
            "docker_privileged", "coding_mode", "coding_spec",
            "cross_technology", "vmware_link",
            "time_limit", "max_score",
            "definition_path", "is_free", "is_active", "interview_mode",
            "attempts_count", "completions_count", "avg_completion_time",
            "created_at", "updated_at",
        ]


class BookmarkSerializer(serializers.ModelSerializer):
    scenario = ScenarioListSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "scenario", "created_at"]
