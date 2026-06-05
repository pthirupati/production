"""
FixitLab Public API — Full-featured REST endpoints.
Technologies, scenarios, labs, bookmarks, progress, leaderboard.

⚠️ PRODUCTION SECURITY: All endpoints require authentication except whitelisted public endpoints
"""
import logging
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum, F, Exists, OuterRef, Value, BooleanField

from common.throttles import LabStartThrottle
from common.api_security import require_authentication

from apps.question_bank.models import Scenario, Technology, Tag, Bookmark
from apps.question_bank.serializers import (
    TechnologySerializer, ScenarioListSerializer, ScenarioDetailSerializer, TagSerializer
)
from apps.labs.models import LabSession
from apps.labs.serializers import LabSessionSerializer
from apps.labs.provisioner import get_provisioner, DockerProvisioner
from apps.hints.models import Hint
from apps.progress.models import UserScenarioProgress, UserAchievement
from apps.billing.services import can_start_lab
from apps.billing.models import TechnologySubscription
from apps.notifications.tasks import notify_lab_completed, notify_achievement_earned
from apps.jira_integration.sync import (
    sync_lab_started, sync_lab_completed, sync_lab_stopped, sync_lab_in_progress,
    mask_jira_url_for_user,
)

# For PDF certificate generation
import io
import base64
from datetime import datetime

logger = logging.getLogger(__name__)



def _get_subscribed_tech_ids(user):
    """Return set of technology IDs the user has active subscriptions for."""
    if not user or not user.is_authenticated:
        return set()
    if user.is_staff or user.is_superuser:
        return None  # None means "all access"
    return set(
        TechnologySubscription.objects.filter(
            user=user, is_active=True
        ).values_list("technology_id", flat=True)
    )


def _mark_accessible(scenario_data_list, subscribed_tech_ids):
    """Add is_accessible flag to serialized scenario data."""
    for item in scenario_data_list:
        if subscribed_tech_ids is None:
            # Staff/admin — full access
            item["is_accessible"] = True
        elif item.get("is_free"):
            item["is_accessible"] = True
        else:
            tech = item.get("technology")
            tech_id = tech.get("id") if isinstance(tech, dict) else tech
            item["is_accessible"] = tech_id in subscribed_tech_ids


# ─── Public Endpoints ────────────────────────────────────────────────

class PlatformConfigView(APIView):
    """Public platform configuration — emails, maintenance status, etc."""
    permission_classes = [AllowAny]

    def get(self, request):
        from django.conf import settings
        return Response({
            "primary_email": settings.PRIMARY_EMAIL,
            "support_email": settings.SUPPORT_EMAIL,
            "maintenance_mode": settings.MAINTENANCE_MODE,
            "maintenance_message": settings.MAINTENANCE_MESSAGE if settings.MAINTENANCE_MODE else None,
        })


class TechnologiesListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get("technologies_list")
        if cached is not None:
            return Response(cached)
        techs = Technology.objects.filter(is_active=True).annotate(
            scenario_count=Count("scenarios", filter=Q(scenarios__is_active=True))
        )
        serializer = TechnologySerializer(techs, many=True)
        cache.set("technologies_list", serializer.data, 300)  # 5 min
        return Response(serializer.data)


class TechnologyDetailView(APIView):
    """Get a technology with its scenarios."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        tech = get_object_or_404(Technology, slug=slug, is_active=True)
        scenarios = Scenario.objects.filter(
            technology=tech, is_active=True
        ).select_related("technology").prefetch_related("tags")

        # Annotate bookmarks if authed
        if request.user.is_authenticated:
            scenarios = scenarios.annotate(
                is_bookmarked=Exists(
                    Bookmark.objects.filter(user=request.user, scenario=OuterRef("pk"))
                )
            )

        tech_data = TechnologySerializer(tech).data
        tech_data["scenario_count"] = scenarios.count()

        # Group by difficulty
        difficulty_counts = {}
        for d in ["easy", "medium", "hard"]:
            difficulty_counts[d] = scenarios.filter(difficulty=d).count()
        tech_data["difficulty_counts"] = difficulty_counts

        # Categories in this tech
        tech_data["categories"] = list(
            scenarios.values_list("category", flat=True).distinct().order_by("category")
        )

        scenario_data = ScenarioListSerializer(scenarios, many=True).data

        # Overlay progress
        if request.user.is_authenticated:
            progress_map = {
                p.scenario_id: {
                    "completed": p.completed, "attempts": p.attempts,
                    "best_score": p.best_score, "best_time": p.best_time,
                }
                for p in UserScenarioProgress.objects.filter(user=request.user)
            }
            for item in scenario_data:
                item["user_progress"] = progress_map.get(item["id"])

        # Mark subscription access
        subscribed = _get_subscribed_tech_ids(request.user if request.user.is_authenticated else None)
        _mark_accessible(scenario_data, subscribed)

        return Response({"technology": tech_data, "scenarios": scenario_data})


class ScenariosListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Scenario.objects.filter(is_active=True).select_related(
            "technology"
        ).prefetch_related("tags")

        # Filters
        tech_id = request.query_params.get("technology")
        tech_slug = request.query_params.get("technology_slug")
        difficulty = request.query_params.get("difficulty")
        scenario_type = request.query_params.get("type")
        category = request.query_params.get("category")
        tag = request.query_params.get("tag")
        search = request.query_params.get("search")
        is_free = request.query_params.get("free")

        if tech_id:
            qs = qs.filter(technology_id=tech_id)
        if tech_slug:
            qs = qs.filter(technology__slug=tech_slug)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if scenario_type:
            qs = qs.filter(scenario_type=scenario_type)
        if category:
            qs = qs.filter(category__iexact=category)
        if tag:
            qs = qs.filter(tags__slug=tag)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(description__icontains=search) |
                Q(subtitle__icontains=search) | Q(tags__name__icontains=search)
            ).distinct()
        if is_free:
            qs = qs.filter(is_free=True)

        # Annotate bookmarks if authed
        if request.user.is_authenticated:
            qs = qs.annotate(
                is_bookmarked=Exists(
                    Bookmark.objects.filter(user=request.user, scenario=OuterRef("pk"))
                )
            )

        serializer = ScenarioListSerializer(qs, many=True)
        data = serializer.data

        # Overlay user progress
        if request.user.is_authenticated:
            progress_map = {
                p.scenario_id: {
                    "completed": p.completed, "attempts": p.attempts,
                    "best_score": p.best_score, "best_time": p.best_time,
                }
                for p in UserScenarioProgress.objects.filter(user=request.user)
            }
            for item in data:
                item["user_progress"] = progress_map.get(item["id"])

        # Mark subscription access
        subscribed = _get_subscribed_tech_ids(request.user if request.user.is_authenticated else None)
        _mark_accessible(data, subscribed)

        return Response(data)


class ScenarioDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        scenario = get_object_or_404(
            Scenario.objects.select_related("technology").prefetch_related("tags"),
            slug=slug, is_active=True
        )

        # Annotate
        if request.user.is_authenticated:
            is_bookmarked = Bookmark.objects.filter(
                user=request.user, scenario=scenario
            ).exists()
        else:
            is_bookmarked = False

        serializer = ScenarioDetailSerializer(scenario)
        data = serializer.data
        data["hints_count"] = Hint.objects.filter(scenario=scenario, is_active=True).count()
        data["is_bookmarked"] = is_bookmarked

        # Check subscription access
        subscribed = _get_subscribed_tech_ids(request.user if request.user.is_authenticated else None)
        if subscribed is None:
            data["is_accessible"] = True
        elif scenario.is_free:
            data["is_accessible"] = True
        else:
            data["is_accessible"] = scenario.technology_id in subscribed

        # Hide solution unless user completed it
        if request.user.is_authenticated:
            try:
                progress = UserScenarioProgress.objects.get(
                    user=request.user, scenario=scenario
                )
                data["user_progress"] = {
                    "completed": progress.completed,
                    "attempts": progress.attempts,
                    "best_score": progress.best_score,
                    "best_time": progress.best_time,
                    "completed_at": progress.completed_at,
                }
                # Only show solution after solving
                if not progress.completed:
                    data["solution_explanation"] = None
            except UserScenarioProgress.DoesNotExist:
                data["user_progress"] = None
                data["solution_explanation"] = None
        else:
            data["user_progress"] = None
            data["solution_explanation"] = None

        return Response(data)


class CategoriesListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get("categories_list")
        if cached is not None:
            return Response(cached)
        categories = (
            Scenario.objects.filter(is_active=True)
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )
        data = list(categories)
        cache.set("categories_list", data, 300)  # 5 min
        return Response(data)


class TagsListView(APIView):
    """List all tags with scenario counts."""
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get("tags_list")
        if cached is not None:
            return Response(cached)
        tags = Tag.objects.annotate(
            scenario_count=Count("scenarios", filter=Q(scenarios__is_active=True))
        ).filter(scenario_count__gt=0).order_by("-scenario_count")
        serializer = TagSerializer(tags, many=True)
        data = serializer.data
        for item, tag in zip(data, tags):
            item["scenario_count"] = tag.scenario_count
        cache.set("tags_list", data, 300)  # 5 min
        return Response(data)


# ─── Bookmarks ───────────────────────────────────────────────────────

class BookmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's bookmarked scenarios."""
        bookmarks = Bookmark.objects.filter(
            user=request.user
        ).select_related("scenario", "scenario__technology").prefetch_related("scenario__tags")

        data = []
        for bm in bookmarks:
            scenario_data = ScenarioListSerializer(bm.scenario).data
            scenario_data["bookmarked_at"] = bm.created_at
            data.append(scenario_data)
        return Response(data)

    def post(self, request):
        """Toggle bookmark on a scenario."""
        scenario_id = request.data.get("scenario_id")
        scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)

        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user, scenario=scenario
        )
        if not created:
            bookmark.delete()
            return Response({"bookmarked": False})

        return Response({"bookmarked": True}, status=status.HTTP_201_CREATED)


# ─── Lab Endpoints ───────────────────────────────────────────────────

class StartLabView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LabStartThrottle]

    def post(self, request, scenario_id):
        scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)

        # Check subscription access for paid scenarios
        if not scenario.is_free and not request.user.is_staff:
            has_sub = TechnologySubscription.objects.filter(
                user=request.user,
                technology=scenario.technology,
                is_active=True,
            ).exists()
            if not has_sub:
                return Response(
                    {
                        "error": "Subscription required. Purchase access to this technology first.",
                        "code": "SUBSCRIPTION_REQUIRED",
                        "technology": scenario.technology.name,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Check billing limits — only count non-failed sessions
        today_count = LabSession.objects.filter(
            user=request.user,
            started_at__date=timezone.now().date()
        ).exclude(status="FAILED").count()
        if not can_start_lab(request.user, today_count):
            from apps.billing.services import get_user_plan_info
            plan_info = get_user_plan_info(request.user)
            return Response(
                {
                    "error": "Daily lab limit reached. Upgrade your plan for unlimited access.",
                    "code": "LIMIT_REACHED",
                    "plan": plan_info["plan"],
                    "usage": plan_info["usage"],
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Cross-tab sync: resume existing active lab for SAME scenario ──
        # If user opens a new tab and clicks "Start Lab" again for a scenario
        # they're already running, return the existing session so the frontend
        # navigates to it instead of launching a duplicate.
        with transaction.atomic():
            existing_sessions = LabSession.objects.select_for_update().filter(
                user=request.user, status__in=["RUNNING", "PROVISIONING"]
            )

            # Resume: if there's already an active session for THIS scenario, return it
            active_same_scenario = existing_sessions.filter(scenario=scenario).first()
            if active_same_scenario:
                serializer = LabSessionSerializer(
                    active_same_scenario, context={"request": request}
                )
                if active_same_scenario.jira_issue_key:
                    jira_info = {
                        "jira_issue_key": active_same_scenario.jira_issue_key,
                        "jira_issue_url": active_same_scenario.jira_issue_url,
                        "jira_enabled": True,
                    }
                else:
                    jira_info = sync_lab_started(active_same_scenario)
                jira_info = mask_jira_url_for_user(jira_info, request.user)
                return Response(
                    {**serializer.data, "resumed": True, **jira_info},
                    status=status.HTTP_200_OK,
                )

            # Terminate active sessions for OTHER scenarios
            for existing in existing_sessions:
                try:
                    old_provisioner = get_provisioner(existing.provider or "docker")
                    resource_id = existing.container_id or existing.instance_id
                    if resource_id:
                        old_provisioner.terminate(resource_id)
                except Exception as e:
                    logger.warning(f"Failed to terminate existing resource: {e}")
                existing.mark_terminated()
                logger.info(f"Auto-terminated session {existing.id} for new lab start")

            # Determine infrastructure type from scenario
            infra_type = getattr(scenario, "infrastructure_type", "docker") or "docker"

            # Create a fresh session — always, regardless of prior completion
            session = LabSession.objects.create(
                user=request.user,
                scenario=scenario,
                status="PROVISIONING",
                provider=infra_type,
                duration_limit=scenario.time_limit,
            )

        try:
            provisioner = get_provisioner(infra_type)

            if infra_type != "docker":
                # Cloud labs (AWS EC2, DigitalOcean): provision asynchronously
                # Return PROVISIONING status immediately — frontend polls until RUNNING
                from celery_app.tasks import provision_cloud_lab
                provision_cloud_lab.delay(str(session.id))

                # Record attempt eagerly so the user sees it immediately
                progress, _ = UserScenarioProgress.objects.get_or_create(
                    user=request.user, scenario=scenario
                )
                progress.attempts += 1
                progress.completed = False
                progress.completed_at = None
                progress.save()

                Scenario.objects.filter(pk=scenario.pk).update(
                    attempts_count=F("attempts_count") + 1
                )

                serializer = LabSessionSerializer(session, context={"request": request})
                jira_info = mask_jira_url_for_user(sync_lab_started(session), request.user)
                response_data = {**serializer.data, **jira_info}
                return Response(response_data, status=status.HTTP_201_CREATED)

            # Docker labs: provision synchronously (instant)
            resource_id, resource_name = provisioner.provision(session)

            session.container_id = resource_id
            session.container_name = resource_name
            session.status = "RUNNING"
            session.save()

            # Record attempt — reset completed flag so the user must
            # re-solve from scratch on every new lab launch
            progress, _ = UserScenarioProgress.objects.get_or_create(
                user=request.user, scenario=scenario
            )
            progress.attempts += 1
            progress.completed = False     # Reset: user must re-solve
            progress.completed_at = None
            progress.save()

            # Update scenario stats
            Scenario.objects.filter(pk=scenario.pk).update(
                attempts_count=F("attempts_count") + 1
            )

            jira_info = mask_jira_url_for_user(sync_lab_started(session), request.user)
            serializer = LabSessionSerializer(session, context={"request": request})
            response_data = {**serializer.data, **jira_info}
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            session.status = "FAILED"
            session.save()
            logger.error(f"Lab provisioning failed: {e}")
            err_msg = str(e)
            if "Lab image not built" in err_msg or "pull access denied" in err_msg:
                user_msg = (
                    "This lab scenario is not deployed on the server yet. "
                    "Please try another scenario or contact support."
                )
            else:
                user_msg = "Failed to provision lab. Please try again."
            return Response(
                {"error": user_msg, "code": "PROVISION_FAILED", "detail": err_msg[:200]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StopLabView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)

        if session.status not in ("RUNNING", "PROVISIONING"):
            return Response({"error": "Lab is not running"}, status=400)

        # Terminate the resource (container or cloud instance)
        resource_id = session.container_id or session.instance_id
        if resource_id:
            try:
                provisioner = get_provisioner(session.provider or "docker")
                provisioner.terminate(resource_id, session_id=str(session.id))
            except Exception as e:
                logger.error(f"Resource termination error: {e}")
                # Still mark as terminated even if cleanup fails

        session.mark_terminated()
        sync_lab_stopped(session, reason="Lab stopped by user")

        # For cloud labs, return the provider so frontend can decide
        # whether to poll for full termination
        is_cloud = (session.provider or "docker") != "docker"
        return Response({
            "session_id": str(session.id),
            "status": session.status,
            "provider": session.provider or "docker",
            "is_cloud": is_cloud,
            "message": "Lab stopped and resources cleaned up successfully",
        })


class ValidateLabView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )

        resource_id = session.container_id or session.instance_id
        if not resource_id:
            return Response({"error": "No resource for this session"}, status=400)

        provisioner = get_provisioner(session.provider or "docker")

        # Check resource is actually running before validating
        resource_status = provisioner.get_status(resource_id)
        if resource_status not in ("running", "active"):
            return Response(
                {"error": f"Lab environment is not running (status: {resource_status}). Please restart the lab."},
                status=400,
            )

        # Use validation script priority:
        # 1. Check for /opt/fixitlab/check.sh inside the container
        # 2. Use scenario.validation_script from DB
        # 3. Fallback to default check
        validation_script = (
            "if [ -f /opt/fixitlab/check.sh ]; then "
            "  bash /opt/fixitlab/check.sh; "
            "elif [ -f /check.sh ]; then "
            "  bash /check.sh; "
            "else "
            f"  {session.scenario.validation_script or 'echo NO_VALIDATION_SCRIPT && exit 1'}; "
            "fi"
        )

        try:
            passed, output = provisioner.run_validation(
                resource_id, validation_script
            )

            if passed:
                elapsed = (timezone.now() - session.started_at).total_seconds()
                time_bonus = max(0, int(session.time_remaining * 100 / session.duration_limit))
                hint_penalty = session.hints_used * 10
                score = max(10, 100 + time_bonus - hint_penalty)

                session.mark_completed(score=score)
                sync_lab_completed(session, score=score, time_taken=int(elapsed))

                # Update progress and check achievements using centralized service
                from apps.progress.services import record_attempt
                record_attempt(
                    user=request.user,
                    scenario=session.scenario,
                    score=score,
                    completed=True,
                    time_seconds=int(elapsed),
                    hints_used=session.hints_used,
                )

                # Update scenario stats
                Scenario.objects.filter(pk=session.scenario.pk).update(
                    completions_count=F("completions_count") + 1
                )

                # Send completion notification (async)
                try:
                    notify_lab_completed.delay(
                        user_id=request.user.id,
                        scenario_title=session.scenario.title,
                        score=score,
                        time_taken=int(elapsed),
                        hints_used=session.hints_used,
                    )
                except Exception:
                    pass  # Don't block validation response

                # Terminate resource
                provisioner.terminate(resource_id, session_id=str(session.id))

                return Response({
                    "passed": True,
                    "score": score,
                    "output": output,
                    "time_taken": int(elapsed),
                    "message": "Congratulations! Challenge solved!",
                    "solution": session.scenario.solution_explanation or None,
                })
            else:
                return Response({
                    "passed": False,
                    "output": output,
                    "message": "Validation failed. Keep trying!",
                })

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return Response({"error": "Validation failed"}, status=500)


class ActiveLabsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = LabSession.objects.filter(
            user=request.user
        ).select_related(
            "scenario", "scenario__technology"
        ).order_by("-started_at")

        status_filter = request.query_params.get("status")
        if status_filter:
            sessions = sessions.filter(status=status_filter)

        serializer = LabSessionSerializer(
            sessions[:20], many=True, context={"request": request}
        )
        return Response(serializer.data)


class LabSessionStatusView(APIView):
    """
    Lightweight endpoint for polling a single session's status.
    Returns minimal data: id, status, provider, ssh_host, time_remaining.
    Much more efficient than fetching all 20 sessions via ActiveLabsView.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = LabSession.objects.select_related(
                "scenario", "scenario__technology"
            ).get(pk=session_id, user=request.user)
        except LabSession.DoesNotExist:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "id": str(session.id),
            "status": session.status,
            "provider": session.provider or "docker",
            "ssh_host": session.ssh_host or "",
            "instance_id": session.instance_id or "",
            "container_id": session.container_id or "",
            "time_remaining": session.time_remaining,
            "duration_limit": session.duration_limit,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "scenario": {
                "id": session.scenario.id,
                "title": session.scenario.title,
                "slug": session.scenario.slug,
                "difficulty": session.scenario.difficulty,
                "description": session.scenario.description,
                "instructions": getattr(session.scenario, "instructions", "") or "",
                "technology": {
                    "name": session.scenario.technology.name,
                    "slug": session.scenario.technology.slug,
                } if session.scenario.technology else None,
            },
            "score": session.score,
            "hints_used": session.hints_used,
            "validation_passed": session.validation_passed,
            "is_expired": session.is_expired,
            "jira_issue_key": session.jira_issue_key or "",
            "jira_issue_url": (
                session.jira_issue_url or ""
                if request.user.is_staff or request.user.is_superuser
                else ""
            ),
        }
        return Response(data)


class LabHintsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        hints = Hint.objects.filter(scenario=session.scenario, is_active=True).order_by("order")

        revealed = hints[:session.hints_used]
        return Response({
            "revealed": [
                {"order": h.order, "content": h.content, "penalty": h.penalty}
                for h in revealed
            ],
            "next_available": hints.count() > session.hints_used,
            "total_hints": hints.count(),
            "hints_used": session.hints_used,
        })

    def post(self, request, session_id):
        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )
        hints = Hint.objects.filter(
            scenario=session.scenario, is_active=True
        ).order_by("order")

        if session.hints_used >= hints.count():
            return Response({"error": "No more hints available"}, status=400)

        next_hint = hints[session.hints_used]
        session.hints_used += 1
        session.save()

        return Response({
            "hint": {"order": next_hint.order, "content": next_hint.content, "penalty": next_hint.penalty},
            "hints_used": session.hints_used,
            "total_hints": hints.count(),
        })


# ─── Progress + Stats ────────────────────────────────────────────────

class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress = UserScenarioProgress.objects.filter(
            user=request.user
        ).select_related("scenario", "scenario__technology")

        total_scenarios = Scenario.objects.filter(is_active=True).count()
        completed = progress.filter(completed=True).count()
        total_attempts = sum(p.attempts for p in progress)
        avg_score = progress.filter(completed=True).aggregate(avg=Avg("best_score"))["avg"] or 0

        # Per-technology progress
        tech_progress = {}
        for tech in Technology.objects.filter(is_active=True):
            tech_total = Scenario.objects.filter(technology=tech, is_active=True).count()
            tech_completed = progress.filter(scenario__technology=tech, completed=True).count()
            tech_scores = list(
                progress.filter(scenario__technology=tech, completed=True)
                .values_list("best_score", flat=True)
            )
            tech_progress[tech.name] = {
                "total": tech_total,
                "completed": tech_completed,
                "avg_score": round(sum(tech_scores) / len(tech_scores), 1) if tech_scores else 0,
                "slug": tech.slug,
                "icon": tech.icon,
                "color": tech.color,
            }

        # Per-difficulty progress
        diff_progress = {}
        for d in ["easy", "medium", "hard"]:
            diff_total = Scenario.objects.filter(is_active=True, difficulty=d).count()
            diff_completed = progress.filter(scenario__difficulty=d, completed=True).count()
            diff_progress[d] = {"total": diff_total, "completed": diff_completed}

        # Achievements
        achievements = list(
            UserAchievement.objects.filter(user=request.user)
            .values_list("achievement", flat=True)
        )

        # Recent activity
        recent = (
            LabSession.objects.filter(user=request.user)
            .select_related("scenario")
            .order_by("-started_at")[:10]
        )

        return Response({
            "summary": {
                "total_scenarios": total_scenarios,
                "completed": completed,
                "completion_rate": round(completed / total_scenarios * 100, 1) if total_scenarios else 0,
                "total_attempts": total_attempts,
                "average_score": round(avg_score, 1),
            },
            "technology_progress": tech_progress,
            "difficulty_progress": diff_progress,
            "achievements": achievements,
            "recent_activity": [
                {
                    "scenario_title": s.scenario.title,
                    "scenario_id": s.scenario.id,
                    "scenario_slug": s.scenario.slug,
                    "status": s.status,
                    "score": s.score,
                    "started_at": s.started_at.isoformat(),
                }
                for s in recent
            ],
        })


class UserAchievementsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        earned = list(
            UserAchievement.objects.filter(user=request.user)
            .values("achievement", "earned_at")
        )
        all_achievements = [
            {"key": k, "label": v, "earned": False, "earned_at": None}
            for k, v in UserAchievement.ACHIEVEMENT_CHOICES
        ]
        earned_map = {a["achievement"]: a["earned_at"] for a in earned}
        for a in all_achievements:
            if a["key"] in earned_map:
                a["earned"] = True
                a["earned_at"] = earned_map[a["key"]]
        return Response(all_achievements)


class LeaderboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tech_id = request.query_params.get("technology")
        cache_key = f"leaderboard_{tech_id or 'all'}"

        cached_data = cache.get(cache_key)
        if cached_data is None:
            qs = UserScenarioProgress.objects.filter(completed=True)
            if tech_id:
                qs = qs.filter(scenario__technology_id=tech_id)

            leaderboard = (
                qs.values("user__id", "user__username")
                .annotate(
                    total_score=Sum("best_score"),
                    scenarios_completed=Count("id"),
                    avg_time=Avg("best_time"),
                )
                .order_by("-total_score")[:100]
            )

            cached_data = []
            for i, entry in enumerate(leaderboard, 1):
                cached_data.append({
                    "rank": i,
                    "user_id": entry["user__id"],
                    "username": entry["user__username"],
                    "total_score": entry["total_score"],
                    "scenarios_completed": entry["scenarios_completed"],
                    "avg_time": round(entry["avg_time"] or 0),
                })
            cache.set(cache_key, cached_data, 60)  # 1 min

        user_rank = None
        if request.user.is_authenticated:
            for entry in cached_data:
                if entry["username"] == request.user.username:
                    user_rank = entry
                    break

        return Response({
            "leaderboard": cached_data,
            "user_rank": user_rank,
        })


# ─── Platform Stats (public) ────────────────────────────────────────

class PlatformStatsView(APIView):
    """Public stats for the landing page."""
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get("platform_stats")
        if cached is not None:
            return Response(cached)
        from django.contrib.auth import get_user_model
        User = get_user_model()

        data = {
            "total_scenarios": Scenario.objects.filter(is_active=True).count(),
            "total_users": User.objects.filter(is_active=True).count(),
            "total_completions": UserScenarioProgress.objects.filter(completed=True).count(),
            "total_technologies": Technology.objects.filter(is_active=True).count(),
        }
        cache.set("platform_stats", data, 120)  # 2 min
        return Response(data)


# ─── User Plan Info ─────────────────────────────────────────────────

class UserPlanView(APIView):
    """Return the authenticated user's current plan and usage."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.billing.services import get_user_plan_info
        return Response(get_user_plan_info(request.user))


# ─── Command History + Session Replay ────────────────────────────────

class CommandHistoryView(APIView):
    """View command history for a lab session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        from apps.labs.models import CommandHistory
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        commands = CommandHistory.objects.filter(session=session).order_by("timestamp")
        data = [
            {
                "command": c.command,
                "timestamp": c.timestamp.isoformat(),
                "exit_code": c.exit_code,
            }
            for c in commands[:500]  # Limit to 500 commands
        ]
        return Response({
            "session_id": str(session.id),
            "scenario_title": session.scenario.title,
            "commands": data,
            "total_commands": commands.count(),
        })


class SessionReplayView(APIView):
    """Get session recording for replay."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        from apps.labs.models import SessionRecording
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        try:
            recording = SessionRecording.objects.get(session=session)
            return Response({
                "session_id": str(session.id),
                "scenario_title": session.scenario.title,
                "events": recording.events,
                "total_duration": recording.total_duration,
                "created_at": recording.created_at.isoformat(),
            })
        except SessionRecording.DoesNotExist:
            return Response(
                {"error": "No recording available for this session"},
                status=status.HTTP_404_NOT_FOUND,
            )


# ─── Solution on Expiry ─────────────────────────────────────────────

class ExpiredSessionSolutionView(APIView):
    """Get solution explanation for an expired/terminated session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)

        # Show solution for sessions that are done or still running but expired
        if session.status in ("EXPIRED", "TERMINATED", "COMPLETED"):
            pass  # always show
        elif session.status == "RUNNING" and session.is_expired:
            # Auto-expire the session
            resource_id = session.container_id or session.instance_id
            if resource_id:
                try:
                    provisioner = get_provisioner(session.provider or "docker")
                    provisioner.terminate(resource_id, session_id=str(session.id))
                except Exception:
                    pass
            session.status = "EXPIRED"
            session.ended_at = timezone.now()
            session.save()
        else:
            return Response(
                {"error": "Solution only available after session ends"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response({
            "session_id": str(session.id),
            "scenario_title": session.scenario.title,
            "solution_explanation": session.scenario.solution_explanation or "No solution available.",
            "status": session.status,
            "score": session.score,
            "validation_passed": session.validation_passed,
        })


# ─── Achievements Certificate ───────────────────────────────────────

class AchievementsCertificateView(APIView):
    """
    Generate a certificate for a specific technology.
    Requirements:
    - User must have completed ALL scenarios of the technology
    - User must have an active technology subscription (paid)
    - Certificate is generated once per technology
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.billing.models import TechnologySubscription
        from apps.question_bank.models import Technology as Tech

        user = request.user
        tech_slug = request.query_params.get("technology")

        if not tech_slug:
            # Return list of technologies eligible for certificates
            subscribed_techs = TechnologySubscription.objects.filter(
                user=user, is_active=True
            ).select_related("technology")

            eligible = []
            for sub in subscribed_techs:
                total = sub.technology.scenarios.filter(is_active=True).count()
                completed = UserScenarioProgress.objects.filter(
                    user=user,
                    scenario__technology=sub.technology,
                    completed=True,
                ).count()
                eligible.append({
                    "technology": sub.technology.name,
                    "slug": sub.technology.slug,
                    "total_scenarios": total,
                    "completed": completed,
                    "can_generate": completed >= total and total > 0,
                })

            return Response({"eligible_technologies": eligible})

        # Generate certificate for specific technology
        try:
            tech = Tech.objects.get(slug=tech_slug)
        except Tech.DoesNotExist:
            return Response({"error": "Technology not found"}, status=404)

        # Check subscription
        has_sub = TechnologySubscription.objects.filter(
            user=user, technology=tech, is_active=True
        ).exists()

        if not has_sub and not user.is_staff:
            return Response(
                {"error": "Active subscription required for this technology"},
                status=403,
            )

        # Check completion
        total_scenarios = tech.scenarios.filter(is_active=True).count()
        completed = UserScenarioProgress.objects.filter(
            user=user, scenario__technology=tech, completed=True
        ).count()

        if completed < total_scenarios:
            return Response({
                "error": "Complete all scenarios first",
                "total_scenarios": total_scenarios,
                "completed": completed,
                "remaining": total_scenarios - completed,
            }, status=400)

        # Generate certificate data
        total_score = UserScenarioProgress.objects.filter(
            user=user, scenario__technology=tech, completed=True
        ).aggregate(total=Sum("best_score"))["total"] or 0

        cert_id = f"FIXIT-{tech.slug.upper()}-{user.id}-{timezone.now().strftime('%Y%m%d')}"

        cert_data = {
            "certificate_id": cert_id,
            "username": user.get_full_name() or user.username,
            "email": user.email,
            "technology": tech.name,
            "scenarios_completed": completed,
            "total_scenarios": total_scenarios,
            "total_score": total_score,
            "generated_at": timezone.now().isoformat(),
            "completion_percentage": round((completed / total_scenarios) * 100) if total_scenarios > 0 else 0,
        }

        # Send certificate email
        try:
            from apps.notifications.tasks import send_notification_email
            send_notification_email.delay(
                subject=f"FixitLab Certificate - {tech.name} Completed!",
                to_email=user.email,
                template="emails/subscription_confirmation.html",
                context={
                    "username": user.get_full_name() or user.username,
                    "technology": tech.name,
                    "plan_name": "Certificate of Completion",
                    "amount": f"Certificate ID: {cert_id}",
                    "expiry_date": "Lifetime Achievement",
                    "subscription_id": cert_id,
                    "payment_method": f"Completed {completed}/{total_scenarios} scenarios with total score {total_score}",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to send certificate email: {e}")

        return Response(cert_data)


# ─── Public Certificate Verification ────────────────────────────────

class CertificateVerifyView(APIView):
    """
    Public endpoint to verify a FixitLab certificate by ID.
    No authentication required — anyone can verify.
    Certificate ID format: FIXIT-{TECH_SLUG}-{USER_ID}-{YYYYMMDD}
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cert_id = request.query_params.get("certificate_id", "").strip()
        if not cert_id:
            return Response(
                {"error": "certificate_id query parameter is required"},
                status=400,
            )

        # Parse certificate ID
        parts = cert_id.split("-")
        if len(parts) < 4 or parts[0] != "FIXIT":
            return Response({
                "valid": False,
                "error": "Invalid certificate ID format",
            })

        try:
            from django.contrib.auth import get_user_model
            from apps.question_bank.models import Technology as Tech

            # Extract components: FIXIT-TECHSLUG-USERID-DATE
            tech_slug = "-".join(parts[1:-2]).lower()
            user_id = int(parts[-2])
            date_str = parts[-1]

            User = get_user_model()
            user = User.objects.filter(id=user_id).first()
            if not user:
                return Response({"valid": False, "error": "Certificate holder not found"})

            tech = Tech.objects.filter(slug=tech_slug, is_active=True).first()
            if not tech:
                return Response({"valid": False, "error": "Technology not found"})

            # Verify completion
            total_scenarios = tech.scenarios.filter(is_active=True).count()
            completed = UserScenarioProgress.objects.filter(
                user=user, scenario__technology=tech, completed=True
            ).count()

            from apps.billing.models import TechnologySubscription
            has_sub = TechnologySubscription.objects.filter(
                user=user, technology=tech, is_active=True
            ).exists()

            is_valid = completed >= total_scenarios and total_scenarios > 0 and has_sub

            total_score = UserScenarioProgress.objects.filter(
                user=user, scenario__technology=tech, completed=True
            ).aggregate(total=Sum("best_score"))["total"] or 0

            return Response({
                "valid": is_valid,
                "certificate_id": cert_id,
                "holder_name": user.get_full_name() or user.username,
                "technology": tech.name,
                "scenarios_completed": completed,
                "total_scenarios": total_scenarios,
                "total_score": total_score,
                "issued_date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str,
            })

        except (ValueError, IndexError):
            return Response({"valid": False, "error": "Invalid certificate ID format"})
