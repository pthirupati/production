"""Public, read-only API for the Tutorials section.

Both endpoints are ``AllowAny`` (these are public marketing/SEO pages, like the
blog) and rate-limited per-IP via ``StrictAnonRateThrottle``. They are written
to degrade gracefully — a DB hiccup returns an empty list / 404 rather than a
500 that would blank the public page.
"""

import logging

from django.db.models import Count
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import StrictAnonRateThrottle

from .models import Tutorial
from .serializers import TutorialDetailSerializer, TutorialListSerializer

logger = logging.getLogger(__name__)


class TutorialListView(APIView):
    """GET /api/tutorials/ — published tutorials, optionally filtered by topic."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        try:
            qs = (
                Tutorial.objects.filter(is_published=True)
                .annotate(section_count=Count("sections"))
                .order_by("order", "title")
            )
            topic = (request.query_params.get("topic") or "").strip()
            if topic:
                qs = qs.filter(topic__iexact=topic)

            tutorials = list(qs)
            topics = sorted(
                {t.topic for t in Tutorial.objects.filter(is_published=True) if t.topic}
            )
        except Exception:
            logger.exception("TutorialListView failed — returning empty payload")
            return Response({"tutorials": [], "topics": []})

        return Response(
            {
                "tutorials": TutorialListSerializer(tutorials, many=True).data,
                "topics": topics,
            }
        )


class TutorialCurriculumView(APIView):
    """GET /api/tutorials/curriculum/ — technology-wise learning paths."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        try:
            tutorials = (
                Tutorial.objects.filter(is_published=True)
                .annotate(section_count=Count("sections"))
                .order_by("topic", "order", "title")
            )
            by_topic = {}
            for t in tutorials:
                by_topic.setdefault(t.topic, []).append(TutorialListSerializer(t).data)
            curriculum = [
                {
                    "topic": topic,
                    "tutorial_count": len(items),
                    "total_sections": sum(i.get("section_count", 0) for i in items),
                    "tutorials": items,
                }
                for topic, items in sorted(by_topic.items(), key=lambda x: x[0].lower())
            ]
        except Exception:
            logger.exception("TutorialCurriculumView failed — returning empty payload")
            return Response({"curriculum": []})
        return Response({"curriculum": curriculum})


class TutorialDetailView(APIView):
    """GET /api/tutorials/<slug>/ — a single tutorial with its ordered sections."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request, slug):
        try:
            tutorial = (
                Tutorial.objects.filter(is_published=True)
                .prefetch_related("sections")
                .get(slug=slug)
            )
        except Tutorial.DoesNotExist:
            return Response({"error": "Tutorial not found"}, status=404)
        except Exception:
            logger.exception("TutorialDetailView failed for slug=%s", slug)
            return Response({"error": "Tutorial not found"}, status=404)

        # "Related" cards: same topic, excluding the current tutorial.
        try:
            related = list(
                Tutorial.objects.filter(is_published=True, topic=tutorial.topic)
                .exclude(pk=tutorial.pk)
                .order_by("order", "title")[:4]
            )
        except Exception:
            related = []

        data = TutorialDetailSerializer(tutorial).data
        data["related"] = TutorialListSerializer(related, many=True).data

        # Ordered learning path within the same technology/topic — powers prev/next
        # navigation and the sidebar curriculum on the detail page.
        try:
            siblings = list(
                Tutorial.objects.filter(is_published=True, topic=tutorial.topic)
                .order_by("order", "title")
                .values("slug", "title", "order")
            )
            idx = next((i for i, s in enumerate(siblings) if s["slug"] == tutorial.slug), 0)
            data["curriculum"] = {
                "topic": tutorial.topic,
                "position": idx + 1,
                "total_in_topic": len(siblings),
                "prev": siblings[idx - 1] if idx > 0 else None,
                "next": siblings[idx + 1] if idx < len(siblings) - 1 else None,
                "path": siblings,
            }
        except Exception:
            data["curriculum"] = {
                "topic": tutorial.topic,
                "position": 1,
                "total_in_topic": 1,
                "prev": None,
                "next": None,
                "path": [],
            }

        return Response(data)
