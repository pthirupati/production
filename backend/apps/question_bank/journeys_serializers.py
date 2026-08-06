"""Serializers for the read-only Learning Journeys API."""

from rest_framework import serializers

from .models import LearningJourney, JourneyStep


class JourneyStepSummarySerializer(serializers.ModelSerializer):
    """Lightweight step shape for the list endpoint (no reference resolution)."""

    class Meta:
        model = JourneyStep
        fields = ["order", "kind", "title", "est_minutes"]


class LearningJourneyListSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField()
    primary_technology = serializers.SlugRelatedField(
        slug_field="slug", read_only=True
    )
    step_count = serializers.SerializerMethodField()
    steps = JourneyStepSummarySerializer(many=True, read_only=True)

    class Meta:
        model = LearningJourney
        fields = [
            "slug",
            "title",
            "role_label",
            "description",
            "level",
            "primary_technology",
            "order",
            "step_count",
            "steps",
        ]

    def get_step_count(self, obj):
        return obj.steps.count()


class JourneyStepDetailSerializer(serializers.ModelSerializer):
    """Full step shape: resolves each reference to a real title (best-effort).

    ``refs`` becomes a list of ``{slug, title, completed}`` objects for the
    ``scenarios`` kind; ``ref`` becomes a single ``{slug, title}`` for
    course/project/cert kinds. Resolution uses the maps prebuilt in the view's
    serializer context so there is no per-step query. When a slug can't be
    resolved the step still renders (``title`` falls back to the slug and
    ``resolved`` is False) — a loose reference must never break the journey.
    """

    references = serializers.SerializerMethodField()

    class Meta:
        model = JourneyStep
        fields = [
            "order",
            "kind",
            "title",
            "description",
            "est_minutes",
            "references",
        ]

    def get_references(self, obj):
        ctx = self.context
        if obj.kind == "scenarios":
            titles = ctx.get("scenario_titles", {})
            completed = ctx.get("completed_scenarios", set())
            out = []
            for slug in obj.ref_slugs or []:
                out.append(
                    {
                        "kind": "scenario",
                        "slug": slug,
                        "title": titles.get(slug, slug),
                        "resolved": slug in titles,
                        "completed": slug in completed,
                    }
                )
            return out

        if obj.kind == "milestone" or not obj.ref_slug:
            return []

        slug = obj.ref_slug
        if obj.kind == "project":
            titles = ctx.get("project_titles", {})
            return [{
                "kind": "project", "slug": slug,
                "title": titles.get(slug, slug), "resolved": slug in titles,
            }]
        if obj.kind == "certification":
            titles = ctx.get("cert_titles", {})
            return [{
                "kind": "certification", "slug": slug,
                "title": titles.get(slug, slug), "resolved": slug in titles,
            }]
        if obj.kind == "tutorial_course":
            # course_slug references live in apps.tutorials, which may be seeded
            # by a separate process. The view resolves them best-effort in its
            # single prefetch pass; when the course isn't seeded we keep the
            # step's stored title rather than echoing a raw slug at the user.
            titles = ctx.get("course_titles", {})
            return [{
                "kind": "tutorial_course", "slug": slug,
                "title": titles.get(slug) or obj.title,
                "resolved": slug in titles,
            }]
        return [{"kind": obj.kind, "slug": slug, "title": obj.title, "resolved": None}]


class LearningJourneyDetailSerializer(serializers.ModelSerializer):
    primary_technology = serializers.SlugRelatedField(
        slug_field="slug", read_only=True
    )
    steps = serializers.SerializerMethodField()

    class Meta:
        model = LearningJourney
        fields = [
            "slug",
            "title",
            "role_label",
            "description",
            "level",
            "primary_technology",
            "order",
            "steps",
        ]

    def get_steps(self, obj):
        steps = obj.steps.all().order_by("order")
        return JourneyStepDetailSerializer(steps, many=True, context=self.context).data
