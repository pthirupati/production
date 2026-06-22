from rest_framework import serializers

from .models import Tutorial, TutorialSection


class TutorialSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorialSection
        fields = [
            "order",
            "heading",
            "body",
            "code",
            "code_language",
            "code_caption",
        ]


class TutorialListSerializer(serializers.ModelSerializer):
    """Lightweight card payload for the /tutorials index."""

    section_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tutorial
        fields = [
            "slug",
            "title",
            "summary",
            "topic",
            "difficulty",
            "estimated_minutes",
            "playground_slug",
            "scenario_slug",
            "section_count",
        ]


class TutorialDetailSerializer(serializers.ModelSerializer):
    sections = TutorialSectionSerializer(many=True, read_only=True)
    meta_title = serializers.CharField(read_only=True)
    meta_description = serializers.CharField(read_only=True)

    class Meta:
        model = Tutorial
        fields = [
            "slug",
            "title",
            "summary",
            "topic",
            "difficulty",
            "estimated_minutes",
            "playground_slug",
            "scenario_slug",
            "meta_title",
            "meta_description",
            "seo_keywords",
            "sections",
        ]
