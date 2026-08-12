import logging

from django.db.models import Avg, Count, Q
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Rating
from .serializers import RatingSerializer
from common.throttles import RatingWriteThrottle, StrictAnonRateThrottle

logger = logging.getLogger(__name__)

# Below this many ratings the average is statistically meaningless and is
# suppressed rather than displayed (audit Z3-10). One 5★ rendered as "5.0 ★"
# exactly like a thousand 5★ ratings, which flatters new content and lets a
# single hostile rating define a scenario's score forever.
MIN_RATINGS_FOR_AVERAGE = 3

# Reviews are shown publicly, so an unbounded TextField is a defacement surface.
MAX_REVIEW_LENGTH = 2000


class RateView(APIView):
    """Submit or update a rating for a scenario or the platform.

    Audit Z3-10. Previously: no throttle, no completion gate, `int(score)` on
    unvalidated input (a non-numeric score was a 500, not a 400), and an
    unvalidated `scenario_id` (a nonexistent id was a database error surfacing as
    a 500). A fresh account could 1★ every scenario on the platform in a loop.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [RatingWriteThrottle]

    def post(self, request):
        rating_type = request.data.get("rating_type", "platform")
        scenario_id = request.data.get("scenario")
        review = (request.data.get("review") or "").strip()

        if rating_type not in ("scenario", "platform"):
            return Response(
                {"error": "rating_type must be 'scenario' or 'platform'."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # `int(score)` on the raw value raised ValueError → 500 for any
        # non-numeric input, and `not score` treated 0 and "" identically.
        try:
            score = int(request.data.get("score"))
        except (TypeError, ValueError):
            return Response(
                {"error": "Score must be a whole number between 1 and 5."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= score <= 5:
            return Response(
                {"error": "Score must be between 1 and 5"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if len(review) > MAX_REVIEW_LENGTH:
            return Response(
                {"error": f"Review must be {MAX_REVIEW_LENGTH} characters or fewer."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if rating_type == "platform":
            rating, created = Rating.objects.update_or_create(
                user=request.user,
                rating_type="platform",
                defaults={"score": score, "review": review, "scenario": None},
            )
            return self._respond(rating, created)

        if not scenario_id:
            return Response(
                {"error": "Scenario ID required for scenario ratings"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        from apps.question_bank.models import Scenario

        # Was passed straight to `scenario_id=`: a nonexistent or non-integer id
        # became a database error and a 500.
        try:
            scenario = Scenario.objects.get(pk=int(scenario_id))
        except (TypeError, ValueError, Scenario.DoesNotExist):
            return Response(
                {"error": "That scenario does not exist."},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Completion gate. Without it a rating carries no information: a fresh
        # account can 1★ every scenario on the platform without opening one, and
        # those scores are indistinguishable from the ones left by people who did
        # the work. Staff are exempt so the catalog can be spot-checked.
        if not request.user.is_staff and not self._has_completed(request.user, scenario):
            return Response(
                {
                    "error": "Complete this lab before rating it.",
                    "error_code": "not_completed",
                },
                status=http_status.HTTP_403_FORBIDDEN,
            )

        rating, created = Rating.objects.update_or_create(
            user=request.user,
            rating_type="scenario",
            scenario=scenario,
            defaults={"score": score, "review": review},
        )
        return self._respond(rating, created)

    @staticmethod
    def _has_completed(user, scenario) -> bool:
        """Whether ``user`` finished ``scenario`` at least once.

        `completion_finalized` rather than `status="COMPLETED"`: the status can be
        set while grading is still in flight, and it is the *finalized* flag that
        means progress was actually recorded.
        """
        from apps.labs.models import LabSession

        return LabSession.objects.filter(
            user=user, scenario=scenario, completion_finalized=True
        ).exists()

    @staticmethod
    def _respond(rating, created):
        serializer = RatingSerializer(rating)
        return Response(
            serializer.data,
            status=http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK,
        )


class RatingsListView(APIView):
    """Get ratings summary and recent reviews."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        rating_type = request.query_params.get("type", "platform")
        scenario_id = request.query_params.get("scenario")

        if rating_type not in ("scenario", "platform"):
            return Response(
                {"error": "type must be 'scenario' or 'platform'."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        filters = Q(rating_type=rating_type)
        if scenario_id:
            try:
                filters &= Q(scenario_id=int(scenario_id))
            except (TypeError, ValueError):
                return Response(
                    {"error": "scenario must be a numeric id."},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

        ratings = Rating.objects.filter(filters)

        # One aggregate query instead of the previous 7 (a `.count()` per star in
        # a loop, plus two). The conditional Counts evaluate in the same pass.
        stats = ratings.aggregate(
            average_score=Avg("score"),
            total_ratings=Count("id"),
            **{f"star_{i}": Count("id", filter=Q(score=i)) for i in range(1, 6)},
        )
        total = stats["total_ratings"] or 0
        distribution = {str(i): stats[f"star_{i}"] for i in range(1, 6)}

        # Suppress the average below the sample floor rather than publishing a
        # number derived from one or two opinions. `average_score` stays in the
        # payload as null so existing clients do not KeyError; `has_enough_ratings`
        # is what a caller should branch on.
        has_enough = total >= MIN_RATINGS_FOR_AVERAGE
        average = (
            round(stats["average_score"], 1)
            if (has_enough and stats["average_score"])
            else None
        )

        recent = (
            ratings.filter(review__gt="")
            .select_related("user")
            .order_by("-created_at")[:10]
        )

        return Response({
            "average_score": average,
            "has_enough_ratings": has_enough,
            "min_ratings_for_average": MIN_RATINGS_FOR_AVERAGE,
            "total_ratings": total,
            "distribution": distribution,
            "recent_reviews": RatingSerializer(recent, many=True).data,
        })
