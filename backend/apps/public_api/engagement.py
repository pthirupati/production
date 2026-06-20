"""Engagement-loop endpoints — daily challenge, streak calendar, per-scenario stats.

All of these are FREE (no paid API), reuse existing models/data, and are written
to NEVER 500: every handler wraps its DB work and falls back to safe defaults so
a transient error degrades gracefully instead of breaking the Home/Dashboard page.
"""

from __future__ import annotations

import hashlib
import logging

from django.core.cache import cache
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import StrictAnonRateThrottle

from apps.question_bank.models import Scenario
from apps.question_bank.serializers import ScenarioListSerializer
from apps.progress.models import UserScenarioProgress

logger = logging.getLogger(__name__)


def _deterministic_index(seed: str, n: int) -> int:
    """Stable index in [0, n) from a string seed (date) — same all day, no RNG.

    Uses a hash digest rather than random.seed so the choice is identical across
    processes/workers and cache layers, and never shifts mid-day.
    """
    if n <= 0:
        return 0
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest, 16) % n


class DailyChallengeView(APIView):
    """GET /api/daily-challenge/ — one scenario deterministically chosen by date.

    Public (AllowAny). The same scenario is returned for every user for the whole
    UTC day, so it caches cleanly and is shareable. Authenticated users also get
    a `completed` flag for today's pick. Never 500 — returns {challenge: null} if
    no scenarios exist or anything goes wrong.
    """

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        today = timezone.now().date()
        date_key = today.isoformat()
        cache_key = f"daily_challenge:{date_key}"

        payload = cache.get(cache_key)
        if payload is None:
            payload = self._build_payload(date_key)
            # Cache until well past midnight; a stale-by-minutes pick is harmless.
            cache.set(cache_key, payload, 60 * 60 * 6)  # 6h

        # Overlay per-user completion without busting the shared cache.
        if request.user.is_authenticated and payload.get("challenge"):
            try:
                scen_id = payload["challenge"]["id"]
                payload = {**payload, "completed": UserScenarioProgress.objects.filter(
                    user=request.user, scenario_id=scen_id, completed=True
                ).exists()}
            except Exception:
                payload = {**payload, "completed": False}
        return Response(payload)

    @staticmethod
    def _build_payload(date_key: str) -> dict:
        try:
            # Prefer free + non-coding scenarios so the daily pick is openable by
            # anonymous visitors; fall back to any active scenario.
            base = Scenario.objects.filter(is_active=True).select_related("technology")
            pool_ids = list(
                base.filter(is_free=True).order_by("id").values_list("id", flat=True)
            ) or list(base.order_by("id").values_list("id", flat=True))
            if not pool_ids:
                return {"date": date_key, "challenge": None}

            idx = _deterministic_index(date_key, len(pool_ids))
            scenario = base.filter(pk=pool_ids[idx]).first()
            if scenario is None:
                return {"date": date_key, "challenge": None}

            data = ScenarioListSerializer(scenario).data
            return {"date": date_key, "challenge": data, "completed": False}
        except Exception:
            logger.exception("daily_challenge build failed")
            return {"date": date_key, "challenge": None}


class StreakView(APIView):
    """GET /api/streak/ — current streak + a day-by-day activity calendar.

    Authenticated. Built entirely from existing UserScenarioProgress rows plus
    the Profile streak counters; adds no schema. Returns up to `days` (default
    120, max 365) of {date, count} so the frontend can render a heatmap, and the
    current/longest streak numbers. Never 500 — falls back to zeros.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 120))
        except (TypeError, ValueError):
            days = 120
        days = max(7, min(days, 365))

        try:
            from django.db.models import Count
            from django.db.models.functions import TruncDate
            from apps.progress.services import compute_current_streak

            since = timezone.now() - timezone.timedelta(days=days)
            rows = (
                UserScenarioProgress.objects.filter(
                    user=request.user, completed=True, completed_at__gte=since
                )
                .annotate(day=TruncDate("completed_at"))
                .values("day")
                .annotate(count=Count("id"))
            )
            calendar = {
                r["day"].isoformat(): r["count"]
                for r in rows if r["day"] is not None
            }
            current = compute_current_streak(request.user)

            longest = current
            try:
                from apps.accounts.models import Profile
                profile = Profile.objects.filter(user=request.user).only(
                    "longest_streak", "daily_streak"
                ).first()
                if profile:
                    longest = max(profile.longest_streak, current)
            except Exception:
                pass

            total_active_days = len(calendar)
            return Response({
                "current_streak": current,
                "longest_streak": longest,
                "total_active_days": total_active_days,
                "days": days,
                "calendar": calendar,
            })
        except Exception:
            logger.exception("streak view failed user_id=%s", getattr(request.user, "id", None))
            return Response({
                "current_streak": 0,
                "longest_streak": 0,
                "total_active_days": 0,
                "days": days,
                "calendar": {},
            })


class XpView(APIView):
    """GET /api/xp/ — the user's XP total, level, and progress to next level.

    Authenticated. XP lives on Profile (maintained on completion); this just
    reflects it through the deterministic level curve. Never 500.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from apps.accounts.models import Profile
            from apps.progress.services import compute_level

            profile, _ = Profile.objects.get_or_create(user=request.user)
            return Response(compute_level(profile.xp))
        except Exception:
            logger.exception("xp view failed user_id=%s", getattr(request.user, "id", None))
            from apps.progress.services import compute_level
            return Response(compute_level(0))


class ScenarioStatsView(APIView):
    """GET /api/scenarios/<slug>/stats/ — aggregate solve stats for one scenario.

    Public (AllowAny). Reuses UserScenarioProgress to compute avg solve time,
    fail rate, and average hint usage. Safe defaults; never 500. These power the
    per-scenario stats chip on cards (and seed the admin quality view).
    """

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request, slug):
        cache_key = f"scenario_stats:{slug}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        data = self._safe_defaults(slug)
        try:
            scenario = Scenario.objects.filter(slug=slug, is_active=True).only(
                "id", "slug", "attempts_count", "completions_count"
            ).first()
            if scenario is None:
                return Response(data)

            from django.db.models import Avg, Count, Q

            agg = UserScenarioProgress.objects.filter(scenario=scenario).aggregate(
                learners=Count("id"),
                solved=Count("id", filter=Q(completed=True)),
                avg_time=Avg("best_time", filter=Q(completed=True)),
                avg_hints=Avg("hints_used_best", filter=Q(completed=True)),
            )
            learners = agg["learners"] or 0
            solved = agg["solved"] or 0
            # Fail rate = learners who attempted but never solved / learners.
            fail_rate = round((learners - solved) / learners * 100) if learners else 0
            data = {
                "slug": scenario.slug,
                "learners": learners,
                "solved": solved,
                "completions": scenario.completions_count,
                "avg_solve_seconds": round(agg["avg_time"]) if agg["avg_time"] else None,
                "fail_rate_pct": fail_rate,
                "avg_hints_used": round(agg["avg_hints"], 1) if agg["avg_hints"] is not None else 0,
            }
            cache.set(cache_key, data, 300)  # 5 min
        except Exception:
            logger.exception("scenario_stats failed slug=%s", slug)
            data = self._safe_defaults(slug)
        return Response(data)

    @staticmethod
    def _safe_defaults(slug: str) -> dict:
        return {
            "slug": slug,
            "learners": 0,
            "solved": 0,
            "completions": 0,
            "avg_solve_seconds": None,
            "fail_rate_pct": 0,
            "avg_hints_used": 0,
        }
