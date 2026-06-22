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
        return Response(data)
