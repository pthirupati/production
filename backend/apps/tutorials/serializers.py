from rest_framework import serializers

from .models import Tutorial, TutorialProgress, TutorialSection


from .completeness import enrich_body


class TutorialSectionSerializer(serializers.ModelSerializer):
    quiz = serializers.SerializerMethodField()

    class Meta:
        model = TutorialSection
        fields = [
            "order",
            "heading",
            "body",
            "code",
            "code_language",
            "code_caption",
            "quiz",
        ]

    def get_quiz(self, obj):
        if obj.quiz_json:
            return obj.quiz_json
        heading = (obj.heading or "").lower()
        if not any(k in heading for k in ("assessment", "quiz", "checkpoint", "practice question")):
            return None
        # Generate a real, scored end-of-module quiz (5 questions) keyed to the
        # tutorial's topic + module. Deterministic so it is stable per module.
        from .quiz_bank import build_module_quiz

        tutorial = obj.tutorial
        return build_module_quiz(tutorial.topic, tutorial.title)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        tutorial = instance.tutorial
        data["body"] = enrich_body(tutorial.topic, tutorial.title, instance.body or "")
        return data


class TutorialProgressSerializer(serializers.ModelSerializer):
    tutorial_slug = serializers.CharField(source="tutorial.slug", read_only=True)
    tutorial_title = serializers.CharField(source="tutorial.title", read_only=True)
    topic = serializers.CharField(source="tutorial.topic", read_only=True)
    section_count = serializers.SerializerMethodField()
    progress_pct = serializers.SerializerMethodField()

    class Meta:
        model = TutorialProgress
        fields = [
            "tutorial_slug",
            "tutorial_title",
            "topic",
            "completed_sections",
            "last_section_order",
            "completed",
            "section_count",
            "progress_pct",
            "updated_at",
        ]

    def get_section_count(self, obj):
        return obj.tutorial.sections.count()

    def get_progress_pct(self, obj):
        total = obj.tutorial.sections.count()
        if not total:
            return 100 if obj.completed else 0
        done = len(obj.completed_sections or [])
        return min(100, round((done / total) * 100))


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
            "course_slug",
            "course_title",
            "module_order",
            "level_track",
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
            "course_slug",
            "course_title",
            "module_order",
            "level_track",
            "estimated_minutes",
            "playground_slug",
            "scenario_slug",
            "meta_title",
            "meta_description",
            "seo_keywords",
            "sections",
        ]
