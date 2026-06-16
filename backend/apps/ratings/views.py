import logging
from django.db.models import Avg, Count, Q
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Rating
from .serializers import RatingSerializer
from common.throttles import StrictAnonRateThrottle

logger = logging.getLogger(__name__)


class RateView(APIView):
    """Submit or update a rating for a scenario or the platform."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        rating_type = request.data.get("rating_type", "platform")
        scenario_id = request.data.get("scenario")
        score = request.data.get("score")
        review = request.data.get("review", "")

        if not score or int(score) < 1 or int(score) > 5:
            return Response(
                {"error": "Score must be between 1 and 5"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if rating_type == "scenario" and not scenario_id:
            return Response(
                {"error": "Scenario ID required for scenario ratings"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Update or create
        if rating_type == "scenario":
            rating, created = Rating.objects.update_or_create(
                user=request.user,
                rating_type="scenario",
                scenario_id=scenario_id,
                defaults={"score": score, "review": review},
            )
        else:
            rating, created = Rating.objects.update_or_create(
                user=request.user,
                rating_type="platform",
                defaults={"score": score, "review": review, "scenario": None},
            )

        serializer = RatingSerializer(rating)
        status_code = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
        return Response(serializer.data, status=status_code)


class RatingsListView(APIView):
    """Get ratings summary and recent reviews."""
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        rating_type = request.query_params.get("type", "platform")
        scenario_id = request.query_params.get("scenario")

        filters = Q(rating_type=rating_type)
        if scenario_id:
            filters &= Q(scenario_id=scenario_id)

        ratings = Rating.objects.filter(filters)

        # Aggregate stats
        stats = ratings.aggregate(
            average_score=Avg("score"),
            total_ratings=Count("id"),
        )

        # Distribution
        distribution = {}
        for i in range(1, 6):
            distribution[str(i)] = ratings.filter(score=i).count()

        # Recent reviews (with text)
        recent = ratings.filter(review__gt="").select_related("user").order_by("-created_at")[:10]
        recent_data = RatingSerializer(recent, many=True).data

        return Response({
            "average_score": round(stats["average_score"] or 0, 1),
            "total_ratings": stats["total_ratings"],
            "distribution": distribution,
            "recent_reviews": recent_data,
        })
