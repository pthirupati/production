"""
FixitLab Public API — Full-featured REST endpoints.
Technologies, scenarios, labs, bookmarks, progress, leaderboard.

⚠️ PRODUCTION SECURITY: All endpoints require authentication except whitelisted public endpoints
"""
import logging
import os
from django.conf import settings
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import connection, transaction
from django.db.models import Q, Count, Avg, Sum, Max, F, Exists, OuterRef, Value, BooleanField

from common.throttles import LabStartThrottle, StrictAnonRateThrottle
from common.api_security import require_authentication

from apps.question_bank.models import Scenario, Technology, Tag, Bookmark, Project, ProjectTask, UserProjectProgress, UserTaskProgress
from apps.question_bank.serializers import (
    TechnologySerializer, ScenarioListSerializer, ScenarioDetailSerializer, TagSerializer
)
from apps.labs.models import LabSession
from apps.labs.serializers import LabSessionSerializer
from apps.labs.capacity import at_global_capacity
from apps.labs.start_gates import lab_start_block_reason, lab_start_block_http_status
from apps.labs.provisioner import get_provisioner, terminate_lab_session, DockerProvisioner
from apps.labs.completion import finalize_validated_session
from apps.question_bank.scenario_copy import public_objectives
from apps.hints.models import Hint
from apps.progress.models import UserScenarioProgress, UserAchievement
from apps.progress.services import record_attempt_started
from apps.billing.services import can_start_lab
from apps.billing.models import TechnologySubscription
from apps.notifications.tasks import notify_lab_completed, notify_achievement_earned
from apps.jira_integration.sync import (
    sync_lab_started, sync_lab_completed, sync_lab_stopped, sync_lab_in_progress, sync_lab_expired,
    mask_jira_url_for_user,
)
from apps.jira_integration.helpers import resolve_jira_issue_url

# For PDF certificate generation
import io
import base64
from datetime import datetime

logger = logging.getLogger(__name__)

# Friendly payload returned (with HTTP 503) when the single Docker labs engine
# is at the global concurrent-lab ceiling. Distinct "code" so the frontend can
# show a retry-soon message rather than a generic error. (PRODUCTION_AUDIT
# SCALE-01.)
LAB_CAPACITY_FULL_RESPONSE = {
    "error": "All lab capacity is in use right now — please try again in a few minutes.",
    "code": "CAPACITY_FULL",
}


def _enqueue_provisioning(task, session) -> bool:
    """Queue a provisioning task, releasing the capacity slot if the broker is down.

    Audit Z5-18. Both enqueue sites called `.delay()` unguarded, and the failure
    cascaded rather than stopping at a 500:

      1. the LabSession row is created,
      2. `.delay()` raises because the broker is unreachable,
      3. the row stays PROVISIONING and **counts against the global capacity cap**
         (`at_global_capacity` counts live rows, deliberately — see capacity.py),
      4. the beat task that clears stuck sessions cannot run either, because it
         needs the same broker.

    So a broker outage did not merely fail lab starts; it permanently consumed
    capacity that nothing could reclaim until someone noticed and cleared it by
    hand. Marking the session FAILED here is what stops step 3 — the row no longer
    counts, so the platform recovers on its own when the broker returns.

    Returns True when queued. The caller turns False into a 503, not a 500: the
    request was valid and the service is temporarily unable to fulfil it, which is
    also what tells a client it is worth retrying.
    """
    try:
        task.delay(str(session.id))
        return True
    except Exception as exc:
        logger.error(
            "Could not queue provisioning for session %s (%s) — releasing the "
            "capacity slot so a broker outage does not fill the cap with rows "
            "nothing can clear",
            session.id, exc,
        )
        try:
            # `status` only — LabSession has no error_message field, and assigning
            # one here would raise *inside the error handler*, turning a broker
            # outage into an unhandled 500 and leaving the slot held anyway.
            session.status = "FAILED"
            session.save(update_fields=["status"])
        except Exception:
            # If we cannot even mark it, the stuck-session sweep is the backstop —
            # but say so, because that sweep also needs the broker.
            logger.error(
                "Failed to release capacity slot for session %s; it will hold a "
                "slot until the stuck-session sweep runs", session.id,
            )
        return False


QUEUE_UNAVAILABLE_RESPONSE = {
    "error": "Lab provisioning is temporarily unavailable. Please try again in a moment.",
    "code": "QUEUE_UNAVAILABLE",
}


def _schedule_lab_teardown(session):
    """Destroy `session`'s container/instance *after* the current transaction commits.

    Audit Z5-9. Kept out of the atomic block because it is network I/O (SSH to D4 or
    the docker daemon) and the block holds the global capacity advisory lock.

    `transaction.on_commit` rather than a bare `.delay()`: if the surrounding lab
    start rolls back, the user's existing lab is still theirs and must not be torn
    down. Falls back to an inline teardown when the queue is unreachable — the
    alternative is a container that runs until the reaper notices, on a box with a
    hard capacity cap — but still only on commit, and still outside the lock.
    """
    from django.db import transaction as _db_transaction

    session_id = str(session.id)

    def _dispatch():
        try:
            from celery_app.tasks import teardown_lab_resource

            teardown_lab_resource.apply_async(
                args=[session_id], queue="provisioning"
            )
        except Exception as exc:
            logger.warning(
                "Could not queue teardown for session %s (%s); tearing down inline",
                session_id, exc,
            )
            try:
                terminate_lab_session(
                    get_provisioner(session.provider or "docker"), session
                )
            except Exception as inner:
                logger.error(
                    "Inline teardown also failed for session %s: %s", session_id, inner
                )

    _db_transaction.on_commit(_dispatch)


def _get_subscribed_tech_ids(user):
    """Return set of technology IDs the user has active subscriptions for."""
    from apps.billing.subscription_utils import get_subscribed_technology_ids

    if not user or not user.is_authenticated:
        return set()
    return get_subscribed_technology_ids(user)


from apps.labs.infra import lab_infra_type as _lab_infra_type


def _mark_accessible(scenario_data_list, subscribed_tech_ids, user=None):
    """Add is_accessible flag to serialized scenario data.

    `subscribed_tech_ids` is None for staff/admin (full access), or a set of
    technology IDs the user is subscribed to (empty set for anonymous users).
    Defensive against malformed items so listing endpoints never 500.
    """
    from apps.certifications.services.access import user_has_cert_scenario_access
    from apps.question_bank.models import Scenario

    cert_cache = {}

    for item in scenario_data_list or []:
        if not isinstance(item, dict):
            continue
        if subscribed_tech_ids is None:
            # Staff/admin — full access
            item["is_accessible"] = True
        elif item.get("is_free"):
            item["is_accessible"] = True
        else:
            sc_id = item.get("id")
            if sc_id and user:
                if sc_id not in cert_cache:
                    cert_cache[sc_id] = Scenario.objects.filter(id=sc_id).first()
                sc = cert_cache[sc_id]
                if sc and user_has_cert_scenario_access(user, sc):
                    item["is_accessible"] = True
                    continue
            tech = item.get("technology")
            tech_id = tech.get("id") if isinstance(tech, dict) else tech
            item["is_accessible"] = tech_id in subscribed_tech_ids


def _serialize_project_stages(project):
    """Return the ordered stages for a project (empty list for flat projects).

    Additive: flat projects (no ProjectStage rows) return [] so the payload is
    unchanged for them.
    """
    stages = (
        project.stages.all()
        .select_related("stage_technology", "lab_scenario")
        .order_by("order")
    )
    result = []
    for s in stages:
        result.append({
            "id": s.id,
            "order": s.order,
            "title": s.title,
            "description": s.description,
            "stage_technology": s.stage_technology.slug if s.stage_technology_id else None,
            "stage_technology_name": s.stage_technology.name if s.stage_technology_id else None,
            "lab_scenario_id": s.lab_scenario_id,
            "lab_scenario_slug": s.lab_scenario.slug if s.lab_scenario_id else None,
            "handoff_artifact": s.handoff_artifact or {},
            "breakpoint_note": s.breakpoint_note,
        })
    return result


def _serialize_projects(tech, user):
    """Return serialized projects list for a technology, with user progress overlaid."""
    projects = (
        Project.objects.filter(technology=tech, is_active=True)
        .prefetch_related("tasks", "stages__stage_technology", "stages__lab_scenario")
        .order_by("order")
    )
    progress_map = {}
    task_progress_map = {}
    if user and user.is_authenticated:
        for upp in UserProjectProgress.objects.filter(user=user, project__technology=tech):
            progress_map[upp.project_id] = {"status": upp.status, "started_at": str(upp.started_at)}
        for utp in UserTaskProgress.objects.filter(user=user, task__project__technology=tech):
            task_progress_map[utp.task_id] = {"status": utp.status}
    result = []
    for p in projects:
        tasks_data = []
        for t in p.tasks.all():
            task_item = {
                "id": t.id,
                "jira_key": t.jira_key,
                "title": t.title,
                "description": t.description,
                "acceptance_criteria": t.acceptance_criteria,
                "order": t.order,
                "depends_on": t.depends_on_id,
                "stage_id": t.stage_id,
                "validation_scenario_id": t.validation_scenario_id,
                "user_status": task_progress_map.get(t.id, {}).get("status", "todo"),
            }
            tasks_data.append(task_item)
        stages_data = _serialize_project_stages(p)
        result.append({
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "architecture_type": p.architecture_type,
            "description": p.description,
            "objectives": p.objectives,
            "difficulty": p.difficulty,
            "estimated_hours": p.estimated_hours,
            "task_count": len(tasks_data),
            "tasks": tasks_data,
            # Ordered stages when the project is staged; [] for flat projects.
            "stages": stages_data,
            "is_staged": bool(stages_data),
            "user_progress": progress_map.get(p.id),
        })
    return result


# ─── Public Endpoints ────────────────────────────────────────────────

class PlatformConfigView(APIView):
    """Public platform configuration — emails, maintenance status, etc."""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.adminpanel.platform_config import public_config_payload

        cached = cache.get("platform_config_public")
        if cached is not None:
            return Response(cached)
        # Public bootstrap endpoint hit by every page (layout, pricing,
        # changelog). Must never 500 — fall back to safe defaults so pages
        # still render without login if settings can't be read.
        try:
            payload = public_config_payload()
            cache.set("platform_config_public", payload, 60)  # 1 min
        except Exception:
            logger.exception("PlatformConfigView failed — returning safe defaults")
            from django.conf import settings as dj_settings
            payload = {
                "primary_email": getattr(dj_settings, "PRIMARY_EMAIL", ""),
                "support_email": getattr(dj_settings, "SUPPORT_EMAIL", ""),
                "maintenance_mode": False,
                "maintenance_message": None,
                "maintenance_banner_enabled": False,
                "promo_banners_enabled": False,
                "promo_banners": [],
                "theme_colors": {},
                "changelog": [],
                "platform_stats": {},
                "support_bot": {"enabled": True, "name": "FixitLab Assistant"},
                "interview_enabled": True,
            }
        return Response(payload)


class ActiveCampaignsView(APIView):
    """Public: currently-enabled marketing banners for the user's audience.

    AllowAny + must never 500 — returns [] on any error so the layout banner
    fetch is always safe. Anonymous users are treated as the "free" audience.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.adminpanel.campaigns import active_campaigns_for

        placement = request.query_params.get("placement")
        user = request.user if getattr(request.user, "is_authenticated", False) else None
        # Cache the common anon/all slice briefly; audience-specific results are
        # cheap to recompute and small in volume.
        cache_key = None
        if user is None and not placement:
            cache_key = "campaigns_active_anon"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
        try:
            data = active_campaigns_for(user, placement=placement)
        except Exception:
            logger.exception("ActiveCampaignsView failed — returning empty list")
            data = []
        if cache_key is not None:
            cache.set(cache_key, data, 30)
        return Response(data)


class TechnologiesListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "technologies_list_v2"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        # Public bootstrap endpoint — must never 500 the page. On any DB/serialize
        # error, log and return an empty list so the frontend falls back to its
        # static catalog instead of showing "Server error".
        try:
            from apps.certifications.services.scenario_groups import certification_scenario_ids

            cert_ids = certification_scenario_ids()
            count_filter = Q(scenarios__is_active=True) & Q(scenarios__certification_only=False)
            if cert_ids:
                count_filter &= ~Q(scenarios__id__in=cert_ids)
            techs = Technology.objects.filter(is_active=True).annotate(
                scenario_count=Count("scenarios", filter=count_filter)
            ).order_by("order", "name")
            data = TechnologySerializer(techs, many=True).data
            cache.set(cache_key, data, 300)  # 5 min
            return Response(data)
        except Exception:
            logger.exception("TechnologiesListView failed — returning empty list")
            return Response([])


class TechnologyDetailView(APIView):
    """Get a technology with its scenarios."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        tech = get_object_or_404(Technology, slug=slug, is_active=True)
        if tech.coming_soon:
            tech_data = TechnologySerializer(tech).data
            tech_data["scenario_count"] = 0
            tech_data["difficulty_counts"] = {"easy": 0, "medium": 0, "hard": 0, "expert": 0}
            tech_data["categories"] = []
            if request.user.is_authenticated:
                from apps.progress.learning_path import get_learning_path_progress
                tech_data["learning_path_progress"] = get_learning_path_progress(request.user, tech)
            return Response({"technology": tech_data, "scenarios": [], "projects": [], "coming_soon": True})

        # Cache the anonymous scenario list (metadata only, no per-user data)
        cache_key = f"tech_detail_anon:{slug}"
        base = cache.get(cache_key)
        if base is None:
            from apps.certifications.services.scenario_groups import certification_scenario_ids

            cert_ids = certification_scenario_ids()
            scenarios = Scenario.objects.filter(
                technology=tech, is_active=True, certification_only=False,
            ).exclude(id__in=cert_ids).select_related("technology").prefetch_related("tags").order_by(
                "-is_free", "difficulty", "title"
            )

            # Audit Z5-13: this block used to issue 6 queries against `scenarios`
            # — .count(), one .filter().count() per difficulty, a DISTINCT on
            # category, and finally the serializer's own SELECT. Every one of them
            # re-ran the same filter/exclude over the same rows.
            #
            # We need the full row set anyway (the serializer below fetches it), so
            # evaluate the queryset ONCE and derive the aggregates in Python. This
            # is exact rather than approximate: the counts are computed from the
            # identical row set that gets serialised, so they cannot drift from the
            # filters (is_active, certification_only=False, cert_ids excluded) the
            # way a separately-filtered aggregate could.
            scenario_list = list(scenarios)

            tech_data = TechnologySerializer(tech).data
            tech_data["scenario_count"] = len(scenario_list)

            difficulty_counts = {"easy": 0, "medium": 0, "hard": 0, "expert": 0}
            for s in scenario_list:
                if s.difficulty in difficulty_counts:
                    difficulty_counts[s.difficulty] += 1
            tech_data["difficulty_counts"] = difficulty_counts

            # sorted() matches the previous .distinct().order_by("category").
            tech_data["categories"] = sorted(
                {s.category for s in scenario_list if s.category is not None}
            )

            scenario_data = ScenarioListSerializer(scenario_list, many=True).data
            subscribed_anon = _get_subscribed_tech_ids(None)
            _mark_accessible(scenario_data, subscribed_anon, user=None)

            base = {"technology": tech_data, "scenarios": scenario_data}
            cache.set(cache_key, base, 60)  # 60s for anonymous base

        from apps.certifications.models import CertificationTrack
        cert_tracks = list(
            CertificationTrack.objects.filter(technology=tech, is_active=True)
            .values("slug", "name", "vendor", "code", "is_free")
        )

        if not request.user.is_authenticated:
            return Response({**base, "projects": _serialize_projects(tech, None), "cert_tracks": cert_tracks})

        # Copy before overlaying per-user fields.
        #
        # Audit Z5-13 flagged the copy.deepcopy() this replaces. Worth recording
        # WHY the one-level copy below is safe, because the audit's stated reason
        # for keeping the deepcopy ("a shallow copy silently corrupts the shared
        # cache entry and leaks one user's progress to everyone") does not hold
        # here — measured, not assumed:
        #
        #   Both cache backends serialise. Redis in prod obviously does, and
        #   LocMemCache pickles on set and unpickles on every get, so two
        #   cache.get() calls never return the same object graph and a mutation
        #   made after the get is never written back. On the cache-MISS branch
        #   above, `base` is the freshly-built local object and cache.set() has
        #   already stored a snapshot of it. Either way, mutating `base` cannot
        #   reach another request.
        #
        # So the deepcopy was never load-bearing for cross-user isolation — it was
        # pure cost: a full recursive clone of every nested tags/technology dict on
        # every authenticated request. We still copy, because the overlay must not
        # corrupt `base` within THIS request (the anonymous branch just above
        # returns `base` directly), and one level is exactly enough: the overlay
        # only ever writes top-level keys — `is_accessible` (all _mark_accessible
        # assigns), plus `user_progress` and `is_bookmarked` in the loop below.
        # Nested values stay shared, which is safe precisely because nothing here
        # mutates them.
        tech_data = dict(base["technology"])
        scenario_data = [dict(item) for item in base["scenarios"]]

        # Overlay per-user: bookmarks, progress, learning path
        from apps.progress.learning_path import get_learning_path_progress
        tech_data["learning_path_progress"] = get_learning_path_progress(request.user, tech)

        progress_map = {
            p.scenario_id: {
                "completed": p.completed, "attempts": p.attempts,
                "best_score": p.best_score, "best_time": p.best_time,
            }
            for p in UserScenarioProgress.objects.filter(user=request.user, scenario__technology=tech)
        }
        bookmark_ids = set(
            Bookmark.objects.filter(user=request.user, scenario__technology=tech)
            .values_list("scenario_id", flat=True)
        )
        subscribed = _get_subscribed_tech_ids(request.user)
        _mark_accessible(scenario_data, subscribed, user=request.user if request.user.is_authenticated else None)

        for item in scenario_data:
            item["user_progress"] = progress_map.get(item["id"])
            item["is_bookmarked"] = item["id"] in bookmark_ids

        # Include projects
        projects = _serialize_projects(tech, request.user if request.user.is_authenticated else None)
        return Response({"technology": tech_data, "scenarios": scenario_data, "projects": projects, "cert_tracks": cert_tracks})


# Trigram similarity below this is treated as "not a match" for typo fallback.
# 0.3 is Postgres' historical pg_trgm.similarity_threshold default and works
# well for catching one/two-character typos in short lab titles.
_TRGM_SIMILARITY_THRESHOLD = 0.3


def _apply_scenario_search(qs, search):
    """Filter/rank a Scenario queryset by a free-text query.

    Postgres: weighted full-text search (title A > subtitle B > category C >
    description D) via ``websearch`` query parsing, OR'd with a pg_trgm
    similarity match on ``title`` for typo tolerance. Results are annotated with
    ``search_rank`` (full-text SearchRank, boosted by title trigram similarity)
    so the caller can order by relevance. Both the FTS expression and the trgm
    match are backed by the GIN indexes created in question_bank migration 0023.

    Any other backend (SQLite in local/offline tests): falls back to the
    original case-insensitive icontains match across title/subtitle/description
    and tag names. ``search_rank`` is not annotated on this path — the caller
    only orders by it under ``connection.vendor == 'postgresql'``.
    """
    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import (
            SearchQuery,
            SearchRank,
            SearchVector,
            TrigramSimilarity,
        )

        # NOTE: this vector MUST match the functional GIN index expression in
        # question_bank migration 0023 (scenario_fts_gin) for it to be used.
        vector = (
            SearchVector("title", weight="A", config="english")
            + SearchVector("subtitle", weight="B", config="english")
            + SearchVector("category", weight="C", config="english")
            + SearchVector("description", weight="D", config="english")
        )
        query = SearchQuery(search, search_type="websearch", config="english")
        title_similarity = TrigramSimilarity("title", search)

        return (
            qs.annotate(
                _fts_rank=SearchRank(vector, query),
                _title_sim=title_similarity,
            )
            # Full-text hit OR a close-enough title (handles typos the FTS
            # lexer would otherwise miss, e.g. "kubenetes" -> "kubernetes").
            .filter(
                Q(_fts_rank__gt=0)
                | Q(_title_sim__gt=_TRGM_SIMILARITY_THRESHOLD)
            )
            # Blend FTS rank with title similarity so a strong fuzzy title match
            # still ranks even when the full-text lexer scored it zero.
            .annotate(
                search_rank=(F("_fts_rank") + F("_title_sim")),
            )
            .distinct()
        )

    # Non-Postgres fallback (SQLite): original naive substring search.
    return qs.filter(
        Q(title__icontains=search)
        | Q(description__icontains=search)
        | Q(subtitle__icontains=search)
        | Q(tags__name__icontains=search)
    ).distinct()


class ScenariosListView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        # Cache anonymous list responses for 2 minutes to avoid hammering the DB
        if not request.user.is_authenticated:
            params = request.query_params
            cache_key = (
                f"scenarios_anon_{params.get('technology','')}_{params.get('technology_slug','')}_{params.get('difficulty','')}_{params.get('type','')}_{params.get('category','')}_{params.get('tag','')}_{params.get('search','')}_{params.get('free','')}_{params.get('gradeable','')}_{params.get('page',1)}_{params.get('page_size',50)}"
            )
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

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
            # `technology` is an integer PK filter. Frontends sometimes pass a
            # slug here by mistake — treat a non-numeric value as a slug instead
            # of letting Django raise ValueError (which would 500 the endpoint).
            tech_id_str = str(tech_id).strip()
            if tech_id_str.isdigit():
                qs = qs.filter(technology_id=int(tech_id_str))
            elif tech_id_str:
                qs = qs.filter(technology__slug=tech_id_str)
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
            qs = _apply_scenario_search(qs, search)
        # `free` is a tri-state query flag: 1/true → free only; 0/false → paid only.
        # A bare truthy string check wrongly treated free=0 as free-only.
        free_raw = (is_free or "").strip().lower()
        if free_raw in ("1", "true", "yes"):
            qs = qs.filter(is_free=True)
        elif free_raw in ("0", "false", "no"):
            qs = qs.filter(is_free=False)

        # Authed-only progress filter: completed=1 → solved; completed=0 → unsolved.
        completed_raw = (request.query_params.get("completed") or "").strip().lower()
        if completed_raw in ("1", "true", "yes", "0", "false", "no") and request.user.is_authenticated:
            solved = Exists(
                UserScenarioProgress.objects.filter(
                    user=request.user,
                    scenario_id=OuterRef("pk"),
                    completed=True,
                )
            )
            if completed_raw in ("1", "true", "yes"):
                qs = qs.filter(solved)
            else:
                qs = qs.exclude(solved)

        # Tri-state gradeable filter (audit §X7b residual): 1 → auto-checkable;
        # 0 → stub/missing validation. Uses coding_mode + sim resolve + trivial check.
        gradeable_raw = (request.query_params.get("gradeable") or "").strip().lower()
        if gradeable_raw in ("1", "true", "yes", "0", "false", "no"):
            from apps.labs.provisioner.simulation.validation import scenario_is_gradeable

            want = gradeable_raw in ("1", "true", "yes")
            gradeable_ids = [
                sid
                for sid, slug, coding, lab_mode, script in qs.values_list(
                    "id", "slug", "coding_mode", "lab_mode", "validation_script",
                )
                if scenario_is_gradeable(
                    slug=slug or "",
                    coding_mode=bool(coding),
                    lab_mode=lab_mode or "",
                    validation_script=script or "",
                ) == want
            ]
            qs = qs.filter(id__in=gradeable_ids)

        # Certification labs are listed under /certifications only unless explicitly requested.
        scenario_group = (request.query_params.get("scenario_group") or "").strip().lower()
        from apps.certifications.services.scenario_groups import certification_scenario_ids

        cert_ids = certification_scenario_ids()
        if scenario_group == "certification":
            qs = qs.filter(id__in=cert_ids)
        elif request.query_params.get("include_cert") not in ("1", "true", "yes"):
            qs = qs.exclude(id__in=cert_ids).filter(certification_only=False)
        if request.user.is_authenticated:
            qs = qs.annotate(
                is_bookmarked=Exists(
                    Bookmark.objects.filter(user=request.user, scenario=OuterRef("pk"))
                )
            )

        # When a Postgres full-text search ran, rank the most relevant labs
        # first; free/difficulty/title stay as tie-breakers. Otherwise keep the
        # historical stable ordering (also the SQLite icontains path).
        if search and connection.vendor == "postgresql":
            qs = qs.order_by("-search_rank", "-is_free", "difficulty", "title")
        else:
            qs = qs.order_by("-is_free", "difficulty", "title")

        # Pagination
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        try:
            page_size = int(request.query_params.get("page_size", 50))
        except (TypeError, ValueError):
            page_size = 50
        paginator.page_size = max(1, min(page_size, 200))
        paginator.page_size_query_param = "page_size"
        paginator.max_page_size = 200
        try:
            page = paginator.paginate_queryset(qs, request)
        except Exception:
            # Bad `page` query param (e.g. non-numeric / out of range) must not 500.
            page = None
        if page is None:
            page = list(qs)
            paginator = None

        serializer = ScenarioListSerializer(page, many=True)
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
        _mark_accessible(data, subscribed, user=request.user if request.user.is_authenticated else None)

        if paginator is not None:
            response = paginator.get_paginated_response(data)
            payload = response.data
        else:
            # No pagination applied — still return the paginated envelope shape
            # the frontend expects (results/count) so the response is consistent.
            payload = {"count": len(data), "next": None, "previous": None, "results": data}

        # Cache anonymous list result to reduce DB load on repeated browses
        if not request.user.is_authenticated:
            cache.set(cache_key, payload, 120)  # 2 min

        return Response(payload)


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
        tech = scenario.technology  # may be None for orphaned rows
        if getattr(tech, "coming_soon", False):
            data["is_accessible"] = False
            data["coming_soon"] = True
        elif subscribed is None:
            data["is_accessible"] = True
        elif scenario.is_free:
            data["is_accessible"] = True
        else:
            from apps.certifications.services.access import user_has_cert_scenario_access

            if request.user.is_authenticated and user_has_cert_scenario_access(request.user, scenario):
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

        if not data.get("is_accessible", True):
            data["initial_state"] = None

        try:
            from apps.tutorials.models import Tutorial
            from apps.tutorials.serializers import TutorialListSerializer

            related_tutorials = list(
                Tutorial.objects.filter(is_published=True, scenario_slug=scenario.slug)
                .order_by("order", "title")[:4]
            )
            # Prefer the scenario's linked_tutorial course (§C1) over a vague
            # technology-topic fallback — that was returning unrelated lessons.
            course_slug = (getattr(scenario, "linked_tutorial", None) or "").strip()
            if not related_tutorials and course_slug:
                related_tutorials = list(
                    Tutorial.objects.filter(
                        is_published=True, course_slug=course_slug,
                    ).order_by("module_order", "order", "title")[:4]
                )
            if not related_tutorials and scenario.technology:
                related_tutorials = list(
                    Tutorial.objects.filter(is_published=True, topic__iexact=scenario.technology.name)
                    .order_by("order", "title")[:4]
                )
            data["related_tutorials"] = TutorialListSerializer(related_tutorials, many=True).data
            data["linked_tutorial"] = course_slug
        except Exception:
            data["related_tutorials"] = []
            data["linked_tutorial"] = getattr(scenario, "linked_tutorial", "") or ""

        return Response(data)


def _solution_unlock_allowed(session) -> bool:
    """Solution is shown only after genuine completion or exhaustion — not on early stop."""
    if session.status == "COMPLETED":
        return True
    if session.status == "EXPIRED":
        return True
    if session.status == "FAILED":
        return True
    if session.status == "TERMINATED":
        if session.validation_passed:
            return True
        if session.is_expired:
            return True
        from apps.hints.models import Hint
        total_hints = Hint.objects.filter(scenario=session.scenario).count()
        if total_hints > 0 and session.hints_used >= total_hints:
            return True
        return False
    if session.status == "RUNNING" and session.is_expired:
        return True
    return False


class CategoriesListView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

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
    throttle_classes = [StrictAnonRateThrottle]

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

        block = lab_start_block_reason(request.user, scenario)
        if block:
            return Response(block, status=lab_start_block_http_status(block))

        infra_type = _lab_infra_type(scenario)
        max_concurrent = int(os.environ.get(
            "MAX_CONCURRENT_LABS_PER_USER",
            str(getattr(settings, "MAX_CONCURRENT_LABS_PER_USER", 2)),
        ))

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

            # ── Re-check limits under the row-level lock (TOCTOU guard) ──
            # By the time we acquired the lock, another concurrent request may
            # have already created a session.  Re-evaluate both limits using the
            # now-locked queryset so we don't exceed them under load.

            # Re-check concurrent-session limit using the locked queryset
            locked_active_count = existing_sessions.count()
            if locked_active_count >= max_concurrent:
                return Response(
                    {
                        "error": f"You already have {locked_active_count} active lab(s) running. "
                                 f"Stop an existing lab before starting a new one.",
                        "active_labs": locked_active_count,
                        "max_concurrent": max_concurrent,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Re-check daily billing limit (requires a separate query — not
            # covered by the RUNNING/PROVISIONING lock above)
            locked_today_count = LabSession.objects.filter(
                user=request.user,
                started_at__date=timezone.now().date()
            ).exclude(status="FAILED").count()
            if not can_start_lab(request.user, locked_today_count):
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

            # ── Re-check global capacity race-safely under the advisory lock ──
            # (PRODUCTION_AUDIT SCALE-01) The unlocked pre-check above can race:
            # N concurrent starts could all read "under cap" then all insert,
            # overshooting the single engine. at_global_capacity() takes a
            # transaction-scoped advisory lock and re-counts live engine-backed
            # sessions under it; because we hold that lock through the INSERT
            # below, "count < cap ⇒ create" is atomic and cannot overshoot.
            # Done BEFORE terminating the user's other sessions so a rejection
            # has no destructive side effect (we don't kill their running lab
            # just to refuse a new one). The user's own swap can transiently sit
            # one over the global count, which is safe and self-corrects.
            if at_global_capacity(infra_type):
                return Response(
                    LAB_CAPACITY_FULL_RESPONSE,
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Terminate active sessions for OTHER scenarios.
            #
            # Audit Z5-9: this used to call `terminate_lab_session` inline — SSH to
            # D4, or a round trip to the docker daemon — *inside* this
            # `transaction.atomic()` block, which holds both the session row lock and
            # the global capacity advisory lock that every other lab start on the
            # platform is queued behind. One slow D4 response serialised lab starts
            # for everybody.
            #
            # The DB half stays here: capacity accounting must be atomic with the
            # INSERT below, or two concurrent starts could both see room. Only the
            # resource teardown is deferred, and via `transaction.on_commit` rather
            # than a bare `.delay()` — a start that rolls back after this point must
            # not destroy a lab the user still has running.
            for existing in existing_sessions:
                existing.mark_terminated()
                logger.info(f"Auto-terminated session {existing.id} for new lab start")
                _schedule_lab_teardown(existing)

            # Create a fresh session — always, regardless of prior completion
            session = LabSession.objects.create(
                user=request.user,
                scenario=scenario,
                status="PROVISIONING",
                provider=infra_type,
                # Never allow a 0/None limit — that expires the lab in ~1s and
                # redirects learners back to a previous scenario after stop/start.
                duration_limit=max(int(scenario.time_limit or 900), 60),
            )

        try:
            provisioner = get_provisioner(infra_type)

            if infra_type != "docker" and infra_type != "simulation":
                # Cloud labs (AWS EC2, DigitalOcean): provision asynchronously
                # Return PROVISIONING status immediately — frontend polls until RUNNING
                from celery_app.tasks import provision_cloud_lab
                if not _enqueue_provisioning(provision_cloud_lab, session):
                    return Response(
                        QUEUE_UNAVAILABLE_RESPONSE,
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )

                # Record attempt eagerly so the user sees it immediately
                record_attempt_started(request.user, scenario)

                Scenario.objects.filter(pk=scenario.pk).update(
                    attempts_count=F("attempts_count") + 1
                )

                serializer = LabSessionSerializer(session, context={"request": request})
                jira_info = mask_jira_url_for_user(sync_lab_started(session), request.user)
                response_data = {**serializer.data, **jira_info}
                return Response(response_data, status=status.HTTP_201_CREATED)

            # Docker and simulation labs: provision asynchronously via Celery
            from celery_app.tasks import provision_docker_lab
            if not _enqueue_provisioning(provision_docker_lab, session):
                return Response(
                    QUEUE_UNAVAILABLE_RESPONSE,
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Record attempt eagerly so the user sees it immediately
            record_attempt_started(request.user, scenario)

            Scenario.objects.filter(pk=scenario.pk).update(
                attempts_count=F("attempts_count") + 1
            )

            serializer = LabSessionSerializer(session, context={"request": request})
            jira_info = mask_jira_url_for_user(sync_lab_started(session), request.user)
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

        if session.status == "TERMINATED":
            return Response({
                "session_id": str(session.id),
                "status": session.status,
                "message": "Lab already stopped",
            })

        if session.status not in ("RUNNING", "PROVISIONING", "COMPLETED"):
            return Response({"error": "Lab is not running"}, status=400)

        # Terminate the resource (container or cloud instance)
        resource_id = session.container_id or session.instance_id
        if resource_id:
            try:
                provisioner = get_provisioner(session.provider or "docker")
                terminate_lab_session(provisioner, session)
            except Exception as e:
                logger.error(f"Resource termination error: {e}")
                # Still mark as terminated even if cleanup fails

        session.mark_terminated()
        sync_lab_stopped(session, reason="Lab stopped by user")
        try:
            from apps.jira_integration.simulated import schedule_jira_reset_after_lab_close
            schedule_jira_reset_after_lab_close(session)
        except Exception as e:
            logger.warning(f"Jira reset schedule failed: {e}")

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


class ExtendLabView(APIView):
    """POST /api/labs/<session_id>/extend/ — add 30 min (quota: 2/day)."""
    permission_classes = [IsAuthenticated]

    EXTENSION_SECONDS = 1800  # 30 minutes
    DAILY_QUOTA = 2

    def post(self, request, session_id):
        from datetime import date, timedelta
        session = get_object_or_404(LabSession, pk=session_id, user=request.user, status="RUNNING")

        today = date.today()
        if session.last_extension_date == today:
            used = session.extensions_used
        else:
            used = 0

        if used >= self.DAILY_QUOTA:
            return Response(
                {"error": f"Daily extension limit reached ({self.DAILY_QUOTA}/day). Resets at midnight."},
                status=429,
            )

        session.duration_limit += self.EXTENSION_SECONDS
        session.extensions_used = used + 1
        session.last_extension_date = today
        session.save(update_fields=["duration_limit", "expires_at", "extensions_used", "last_extension_date"])

        return Response({
            "session_id": str(session.id),
            "extensions_used": session.extensions_used,
            "extensions_remaining": self.DAILY_QUOTA - session.extensions_used,
            "new_expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "time_remaining": session.time_remaining,
        })


class RestartLabView(APIView):
    """POST /api/labs/<session_id>/restart/ — restart a crashed/stuck lab container."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [LabStartThrottle]

    def post(self, request, session_id):
        session = get_object_or_404(
            LabSession.objects.select_related("scenario"),
            id=session_id,
            user=request.user,
        )

        if session.status not in ("RUNNING", "FAILED"):
            return Response(
                {"error": f"Cannot restart a lab in '{session.status}' status. Stop the lab first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Terminate old container
        try:
            provisioner = DockerProvisioner()
            provisioner.terminate(session)
        except Exception as exc:
            logger.warning("Restart: terminate old container failed (may already be gone): %s", exc)

        # Re-provision
        session.container_id = None
        session.status = "PROVISIONING"
        session.save(update_fields=["container_id", "status"])

        try:
            provisioner = DockerProvisioner()
            provisioner.provision(session)
            session.status = "RUNNING"
            session.save(update_fields=["status"])
        except Exception as exc:
            session.status = "FAILED"
            session.save(update_fields=["status"])
            logger.error("Lab restart failed for session %s: %s", session_id, exc)
            return Response(
                {"error": "Lab restart failed. Please stop and start a new session."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"status": "restarted", "session_id": str(session.id)})


class ValidateLabView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LabStartThrottle]

    def post(self, request, session_id):
        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )

        scenario = session.scenario
        spec = scenario.coding_spec or {}
        if getattr(scenario, "coding_mode", False) and spec.get("kind") == "prompt":
            return Response({
                "passed": False,
                "message": "Use Submit in the Prompt Playground to grade this lab.",
                "output": "PROMPT_PLAYGROUND_REQUIRED",
            })

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

        is_simulation = (session.provider or "") == "simulation"
        db_script = (session.scenario.validation_script or "").strip()

        try:
            if is_simulation:
                passed, output = provisioner.run_validation(
                    resource_id, db_script, scenario_slug=session.scenario.slug or "",
                )
            else:
                file_check_cmd = (
                    "if [ -x /opt/fixitlab/check.sh ]; then bash /opt/fixitlab/check.sh; "
                    "elif [ -x /check.sh ]; then bash /check.sh; "
                    "else exit 127; fi"
                )
                exit_code, output = provisioner.execute_command(resource_id, file_check_cmd)
                if exit_code == 127:
                    if not db_script:
                        return Response({
                            "passed": False,
                            "output": "NO_VALIDATION_SCRIPT",
                            "message": "Validation failed. Keep trying!",
                        })
                    passed, output = provisioner.run_validation(resource_id, db_script)
                else:
                    passed = exit_code == 0

            if passed:
                # Single shared completion path — see apps.labs.completion.
                from apps.labs.acceptance_checklist import build_acceptance_checklist
                from apps.labs.completion import finalize_validated_session
                from apps.question_bank.scenario_copy import public_objectives
                payload = finalize_validated_session(session, request.user, provisioner)
                payload["output"] = output
                payload["checklist"] = build_acceptance_checklist(
                    public_objectives(session.scenario.objectives),
                    passed=True,
                    output=output or "",
                )
                return Response(payload)
            else:
                from apps.labs.acceptance_checklist import build_acceptance_checklist
                from apps.question_bank.scenario_copy import public_objectives
                return Response({
                    "passed": False,
                    "output": output,
                    "message": "Validation failed. Keep trying!",
                    "checklist": build_acceptance_checklist(
                        public_objectives(session.scenario.objectives),
                        passed=False,
                        output=output or "",
                    ),
                })

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return Response({"error": "Validation failed"}, status=500)


def _step_failure_message(step, output="", exit_code=None):
    """Explain WHY a guided step did not pass, without handing over the answer.

    The old messages were three fixed strings ("Apply the documented fix, then
    verify this step again.") that said nothing about which assertion failed, so
    a stuck learner had no signal to act on (audit L2335).

    Only fields the learner can ALREADY see are echoed: ``title`` and
    ``expected_output`` are rendered in the guided panel next to this step. The
    scenario's ``solution``, ``validation_script`` and any hidden test source are
    never touched here.

    Validator ``output`` is NOT interpolated into ``message``. It stays in its
    own response field (as before) and LabRunner renders it below the
    explanation, so raw check output stays attributable to the check rather than
    reading as platform guidance. Previously ``output or <generic>`` meant a
    validator that echoed the expected value became the whole message.
    """
    step = step or {}
    title = str(step.get("title") or "").strip()
    expected = str(step.get("expected_output") or "").strip()

    what = f"'{title}' did not pass" if title else "This step did not pass"
    if exit_code is not None and exit_code != 0:
        what += f" (command exited {exit_code})"

    parts = [f"{what}."]
    if expected:
        # Truncated: expected_output is a short human phrase in every seeded
        # scenario, but nothing enforces that, and this string lands in a toast.
        parts.append(f"Still looking for: {expected[:200]}.")
    if str(output or "").strip():
        parts.append("See the check output below for what the lab actually found.")
    else:
        parts.append("Apply the fix, then verify this step again.")
    return " ".join(parts)


class ValidateGuidedStepView(APIView):
    """Verify a single guided-mode step against live simulation state."""

    permission_classes = [IsAuthenticated]

    _MANUAL_CMDS = frozenset({
        "open playground", "draft prompt", "submit", "bash check.sh", "./check.sh",
    })

    def post(self, request, session_id):
        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )
        step_index = request.data.get("step_index")
        if step_index is None:
            return Response({"error": "step_index required"}, status=400)
        try:
            step_index = int(step_index)
        except (TypeError, ValueError):
            return Response({"error": "step_index must be an integer"}, status=400)

        scenario = session.scenario
        guided = (scenario.guided_mode or {}) if hasattr(scenario, "guided_mode") else {}
        steps = guided.get("steps") or []
        if step_index < 0 or step_index >= len(steps):
            return Response({"error": "Invalid step_index"}, status=400)

        step = steps[step_index]
        cmd = (step.get("command") or "").strip()
        spec = scenario.coding_spec or {}
        is_prompt = getattr(scenario, "coding_mode", False) and spec.get("kind") == "prompt"

        resource_id = session.container_id or session.instance_id
        if not resource_id:
            return Response({"error": "No resource for this session"}, status=400)

        provisioner = get_provisioner(session.provider or "docker")
        resource_status = provisioner.get_status(resource_id)
        if resource_status not in ("running", "active"):
            return Response(
                {"error": f"Lab environment is not running (status: {resource_status})"},
                status=400,
            )

        # Prompt Playground steps — step 2 can verify live rubric score from submissions.
        if is_prompt and cmd.lower() == "draft prompt":
            from apps.labs.prompt_eval import evaluate_course
            submissions = request.data.get("submissions") or {}
            if not isinstance(submissions, dict) or not submissions:
                return Response({
                    "passed": False,
                    "message": "Write your prompt in the playground and score 80+ before verifying this step.",
                })
            verdict = evaluate_course(spec.get("prompt_config", {}) or {}, submissions)
            if verdict.get("all_passed"):
                return Response({"passed": True, "message": "Rubric passed — advance to submit."})
            return Response({
                "passed": False,
                "message": verdict.get("summary") or "Prompt rubric not met yet — refine and try again.",
            })

        # Other prompt/coding manual steps — acknowledge without terminal execution.
        if cmd.lower() in self._MANUAL_CMDS or step.get("next_on") == "manual":
            return Response({"passed": True, "message": "Step acknowledged — continue to the next goal."})

        is_simulation = (session.provider or "") == "simulation"
        db_script = (scenario.validation_script or "").strip()

        try:
            if cmd.startswith("#") or not cmd:
                if is_simulation and db_script:
                    passed, output = provisioner.run_validation(
                        resource_id, db_script, scenario_slug=scenario.slug or "",
                    )
                    if passed:
                        return Response({"passed": True, "message": "Fix verified — advancing.", "output": output})
                    return Response({
                        "passed": False,
                        "message": _step_failure_message(step, output=output),
                        "output": output,
                    })
                return Response({
                    "passed": False,
                    "message": _step_failure_message(step),
                })

            if is_simulation:
                code, output = provisioner.execute_command(resource_id, cmd)
            else:
                code, output = provisioner.execute_command(resource_id, cmd)

            if code == 0:
                return Response({"passed": True, "message": "Command succeeded.", "output": output})
            return Response({
                "passed": False,
                "message": _step_failure_message(step, output=output, exit_code=code),
                "output": output,
            })
        except Exception as e:
            logger.error(f"Guided step validation error: {e}")
            return Response({"error": "Step validation failed"}, status=500)


def public_coding_spec(scenario):
    """Return a coding_spec safe to send to the browser (HIDDEN tests stripped).

    The browser gets starter files, the entrypoint, the language, and the
    VISIBLE test cases (names + code, since they run client-side). HIDDEN test
    source is NEVER included — only the count, so the UI can say "N hidden
    tests". Hidden tests run exclusively on the backend.
    """
    spec = dict(scenario.coding_spec or {})
    visible = spec.get("visible_tests") or []
    hidden = spec.get("hidden_tests") or []
    from apps.labs.code_exec import resolve_runtime

    language = spec.get("language", "python")
    payload = {
        "language": language,
        # §Y2c — authoring label vs gradeable runtime. IDE uses language for
        # chrome/grammar; Check grades against runtime.
        "runtime": resolve_runtime(spec),
        "files": spec.get("files", []),
        "entrypoint": spec.get("entrypoint", ""),
        "instructions": spec.get("instructions", "") or scenario.description,
        "visible_tests": [
            {"name": t.get("name", f"test_{i}"), "code": t.get("code", "")}
            for i, t in enumerate(visible)
        ],
        "hidden_test_count": len(hidden),
        "starter_note": spec.get("starter_note", ""),
    }
    if isinstance(spec.get("preview"), dict):
        payload["preview"] = spec["preview"]
    # Prompt Engineering scenarios reuse coding_mode to open a custom in-browser
    # surface (PromptPlayground) instead of the code editor. The whole
    # prompt_config is purely educational content (lessons, rubric, exercises) —
    # there are no hidden answers or secrets to strip, so it is sent as-is so the
    # client can render the guided, rule-based AI practice simulator offline.
    kind = spec.get("kind")
    if kind:
        payload["kind"] = kind
    if kind == "prompt":
        payload["prompt_config"] = spec.get("prompt_config", {}) or {}
    from apps.labs.api_client_mock import public_api_client_spec

    ac = public_api_client_spec(spec.get("api_client") if isinstance(spec.get("api_client"), dict) else None)
    if ac:
        payload["api_client"] = ac
    return payload


class CodingSpecView(APIView):
    """Serve the coding-IDE spec for a running session (hidden tests stripped)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        scenario = session.scenario
        if not getattr(scenario, "coding_mode", False):
            return Response({"error": "Not a coding scenario"}, status=400)
        snap = session.simulation_snapshot if isinstance(session.simulation_snapshot, dict) else {}
        ide_draft = snap.get("ide_draft") if isinstance(snap.get("ide_draft"), dict) else None
        return Response({
            "coding_mode": True,
            "scenario": {
                "slug": scenario.slug,
                "title": scenario.title,
                "description": scenario.description,
                "objectives": public_objectives(scenario.objectives),
                "difficulty": scenario.difficulty,
            },
            "spec": public_coding_spec(scenario),
            "status": session.status,
            "validation_passed": session.validation_passed,
            "ide_draft": ide_draft,
        })


class IdeDraftView(APIView):
    """GET/PUT server-side coding IDE draft (survives browser clear / device switch).

    Stored under LabSession.simulation_snapshot['ide_draft'] — no migration.
    localStorage remains a fast cache; this is the durable copy.
    """

    permission_classes = [IsAuthenticated]
    MAX_FILES = 80
    MAX_BYTES = 1_500_000  # ~1.5 MB total payload

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        snap = session.simulation_snapshot if isinstance(session.simulation_snapshot, dict) else {}
        draft = snap.get("ide_draft") if isinstance(snap.get("ide_draft"), dict) else None
        return Response({"draft": draft})

    def put(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        if session.status not in ("RUNNING", "PROVISIONING", "COMPLETED"):
            return Response({"error": "Session is not writable"}, status=400)
        files = request.data.get("files")
        if not isinstance(files, dict):
            return Response({"error": "files map required"}, status=400)
        if len(files) > self.MAX_FILES:
            return Response({"error": f"Too many files (max {self.MAX_FILES})"}, status=400)
        clean = {}
        total = 0
        for path, content in files.items():
            if not isinstance(path, str) or not path.strip() or len(path) > 260:
                continue
            if not isinstance(content, str):
                continue
            total += len(content.encode("utf-8", errors="ignore"))
            if total > self.MAX_BYTES:
                return Response({"error": "Draft too large"}, status=400)
            clean[path] = content
        from django.utils import timezone
        draft = {
            "files": clean,
            "ts": int(timezone.now().timestamp() * 1000),
            "updated_at": timezone.now().isoformat(),
        }
        snap = session.simulation_snapshot if isinstance(session.simulation_snapshot, dict) else {}
        snap = dict(snap)
        snap["ide_draft"] = draft
        session.simulation_snapshot = snap
        session.save(update_fields=["simulation_snapshot"])
        return Response({"ok": True, "draft": draft})


class ApiClientDraftView(APIView):
    """GET/PUT server-side API client panel draft (merge with localStorage).

    Stored under LabSession.simulation_snapshot['api_client_draft'] — no migration.
    """

    permission_classes = [IsAuthenticated]
    MAX_BYTES = 200_000
    ALLOWED_KEYS = (
        "method", "url", "headersText", "bodyText", "varsText",
        "preRequest", "testScript", "authType", "authToken", "authUser",
        "authPass", "authKey", "authValue", "history", "ts",
    )

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        snap = session.simulation_snapshot if isinstance(session.simulation_snapshot, dict) else {}
        draft = snap.get("api_client_draft") if isinstance(snap.get("api_client_draft"), dict) else None
        return Response({"draft": draft})

    def put(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        if session.status not in ("RUNNING", "PROVISIONING", "COMPLETED"):
            return Response({"error": "Session is not writable"}, status=400)
        raw = request.data.get("draft") if isinstance(request.data.get("draft"), dict) else request.data
        if not isinstance(raw, dict):
            return Response({"error": "draft object required"}, status=400)
        clean = {}
        total = 0
        for key in self.ALLOWED_KEYS:
            if key not in raw:
                continue
            val = raw[key]
            if key == "history":
                if not isinstance(val, list):
                    continue
                clean[key] = val[:20]
            elif isinstance(val, (str, int, float, bool)) or val is None:
                clean[key] = val
            else:
                continue
            total += len(str(val).encode("utf-8", errors="ignore"))
            if total > self.MAX_BYTES:
                return Response({"error": "Draft too large"}, status=400)
        from django.utils import timezone
        clean["ts"] = int(clean.get("ts") or timezone.now().timestamp() * 1000)
        clean["updated_at"] = timezone.now().isoformat()
        snap = session.simulation_snapshot if isinstance(session.simulation_snapshot, dict) else {}
        snap = dict(snap)
        snap["api_client_draft"] = clean
        session.simulation_snapshot = snap
        session.save(update_fields=["simulation_snapshot"])
        return Response({"ok": True, "draft": clean})


class ApiClientSendView(APIView):
    """Interactive API-client send — in-process mock router only (no sockets).

    Audit Y3 / api_client interactive surface. Graded fetch mock is residual.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        from apps.labs.api_client_mock import dispatch_mock_request, evaluate_assertions

        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        if session.status not in ("RUNNING", "PROVISIONING", "COMPLETED"):
            return Response({"error": "Session is not active"}, status=400)
        method = request.data.get("method") or "GET"
        url = request.data.get("url") or ""
        if not isinstance(url, str) or not url.strip():
            return Response({"error": "url required"}, status=400)
        headers = request.data.get("headers") if isinstance(request.data.get("headers"), dict) else {}
        variables = request.data.get("variables") if isinstance(request.data.get("variables"), dict) else {}
        body = request.data.get("body")
        result = dispatch_mock_request(
            method=method,
            url=url,
            headers=headers,
            body=body,
            variables=variables,
        )
        assertions = request.data.get("assertions")
        if assertions is None:
            spec = getattr(session.scenario, "coding_spec", None) or {}
            ac = spec.get("api_client") if isinstance(spec, dict) else None
            assertions = (ac or {}).get("assertions") if isinstance(ac, dict) else None
        if assertions:
            result["assertions"] = evaluate_assertions(result, assertions)
        return Response(result)


class CodeValidateView(APIView):
    """Grade a coding submission against HIDDEN tests on the backend.

    Integrity (the platform's #1 rule): clicking Check NEVER auto-completes a
    scenario. We run the user's real code against the scenario's hidden +
    visible tests in a sandboxed subprocess (apps.labs.code_exec). Only when
    EVERY required test genuinely passes do we mark the session complete — via
    the SAME finalize_validated_session() path as the terminal validator. If a
    language can't be safely auto-graded, we return needs_review, never a pass.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        from apps.labs.code_exec import grade_submission, resolve_runtime

        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )
        scenario = session.scenario
        if not getattr(scenario, "coding_mode", False):
            return Response({"error": "Not a coding scenario"}, status=400)

        spec = scenario.coding_spec or {}
        # Client may still send the authoring language; grade on resolved runtime
        # so language: html / react still hit the JS harness (audit §Y2c).
        language_hint = (
            request.data.get("runtime")
            or request.data.get("language")
            or spec.get("language")
            or "python"
        )
        runtime = resolve_runtime(spec, language_override=str(language_hint).lower())

        # Accept either a single concatenated source string, or a {path: content}
        # map of files. We grade the entrypoint file's content (multi-file
        # projects concatenate non-entry files first so helpers are in scope).
        user_code = self._resolve_user_code(request.data, spec)
        if not user_code.strip():
            return Response({"error": "No code submitted"}, status=400)

        visible = spec.get("visible_tests") or []
        hidden = spec.get("hidden_tests") or []
        # Run BOTH visible and hidden tests on the backend for the authoritative
        # verdict. The browser may have run visible tests already, but the
        # backend re-runs everything so the pass decision is never client-trusted.
        all_tests = (
            [{"name": t.get("name", f"v{i}"), "code": t.get("code", ""), "hidden": False}
             for i, t in enumerate(visible)]
            + [{"name": t.get("name", f"h{i}"), "code": t.get("code", ""), "hidden": True}
               for i, t in enumerate(hidden)]
        )

        result = grade_submission(
            runtime,
            user_code,
            all_tests,
            timeout=int(spec.get("timeout", 8)),
            api_client=spec.get("api_client") if isinstance(spec.get("api_client"), dict) else None,
            authoring_language=spec.get("language") or "",
        )

        # Reveal hidden test names only once the scenario is already solved.
        already_solved = session.validation_passed
        payload = result.public_dict(reveal_hidden_names=already_solved)

        if result.needs_review:
            payload["passed"] = False
            payload["message"] = (
                result.error
                or "This submission needs manual review and was not auto-graded."
            )
            return Response(payload)

        if result.all_passed:
            provisioner = None
            try:
                provisioner = get_provisioner(session.provider or "simulation")
            except Exception:
                provisioner = None
            completion = finalize_validated_session(session, request.user, provisioner)
            payload.update(completion)
            payload["passed"] = True
            payload["message"] = "All tests passed! " + completion.get("message", "")
            return Response(payload)

        payload["passed"] = False
        payload["message"] = (
            "Some tests failed — your code ran but did not pass every check."
            if result.ran else
            (result.error or "Your code did not run.")
        )
        return Response(payload)

    @staticmethod
    def _resolve_user_code(data, spec) -> str:
        """Build the single source string to grade from the request payload."""
        from apps.labs.code_exec import compose_user_code_from_files

        code = data.get("code")
        if isinstance(code, str) and code.strip():
            return code

        files = data.get("files")
        if isinstance(files, dict) and files:
            entrypoint = data.get("entrypoint") or spec.get("entrypoint") or ""
            return compose_user_code_from_files(files, entrypoint)
        return ""


class CodeMentorView(APIView):
    """Rule-based AI Mentor for the coding IDE — FREE, no paid LLM.

    Given the learner's current code plus the latest run/test output, returns
    plain-language guidance (explain errors/stack traces, explain a failing test
    *conceptually*, teach the concept, suggest style/complexity/security
    improvements). See apps.labs.ide_mentor — it is pure pattern matching with
    NO model call and NO network.

    Integrity: this endpoint NEVER returns the reference solution. The mentor's
    only inputs are the user's own code + public run output, so there is nothing
    to leak. The reference walkthrough is exposed ONLY when the client POSTs
    `unlock_reference: true` (the UI gates that behind an explicit confirm), and
    even then it comes from the separate reference_payload() path — analysis and
    the answer never travel together by accident.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        from apps.labs.ide_mentor import analyze, reference_payload

        # Accept any non-terminal session the user owns (mentor stays useful even
        # right after solving). It does not mutate session state.
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        scenario = session.scenario
        if not getattr(scenario, "coding_mode", False):
            return Response({"error": "Not a coding scenario"}, status=400)

        spec = scenario.coding_spec or {}
        language = (request.data.get("language") or spec.get("language") or "python").lower()
        code = request.data.get("code") or ""
        if isinstance(code, dict):  # tolerate a {path: content} map
            code = "\n\n".join(v for v in code.values() if isinstance(v, str))
        output = request.data.get("output") or ""
        error = request.data.get("error") or ""
        test_results = request.data.get("test_results") or request.data.get("tests") or []
        if not isinstance(test_results, list):
            test_results = []
        requested = request.data.get("requested") or "all"

        # Explicit, confirmed unlock is the ONLY way the answer is returned.
        unlock = bool(request.data.get("unlock_reference"))
        if unlock and not _solution_unlock_allowed(session):
            return Response(
                {"error": "Reference solution only available after session ends or giving up."},
                status=status.HTTP_403_FORBIDDEN,
            )

        report = analyze(
            language=language,
            code=str(code)[:20000],
            output=str(output)[:20000],
            error=str(error)[:20000],
            test_results=test_results[:50],
            requested=str(requested),
        ).to_dict()

        report["reference"] = reference_payload(scenario, unlocked=unlock)
        return Response(report)


class PromptValidateView(APIView):
    """Grade a Prompt Engineering ("prompt") scenario — rule-based, FREE.

    Prompt scenarios reuse the coding_mode flag to open the browser
    PromptPlayground instead of the code editor. There is NO LLM call here — the
    simulator and grader are pure lexical heuristics (see apps.labs.prompt_eval),
    and the code is honest that it's a guided practice tool, not a real model.

    Integrity (same rule as code grading): the browser's feedback is advisory;
    completion is decided ONLY by re-checking the user's submitted prompts on the
    server against the scenario's embedded rubric, then finalizing through the
    SAME finalize_validated_session() path as every other lab type.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [LabStartThrottle]

    def post(self, request, session_id):
        from apps.labs.prompt_eval import evaluate_course

        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )
        scenario = session.scenario
        spec = scenario.coding_spec or {}
        if not getattr(scenario, "coding_mode", False) or spec.get("kind") != "prompt":
            return Response({"error": "Not a prompt scenario"}, status=400)

        submissions = request.data.get("submissions") or {}
        if not isinstance(submissions, dict):
            return Response(
                {"error": "submissions must be an object of {exercise_id: prompt}"},
                status=400,
            )

        verdict = evaluate_course(spec.get("prompt_config", {}) or {}, submissions)

        if verdict["all_passed"]:
            provisioner = None
            try:
                provisioner = get_provisioner(session.provider or "simulation")
            except Exception:
                provisioner = None
            completion = finalize_validated_session(session, request.user, provisioner)
            verdict.update(completion)
            verdict["passed"] = True
            verdict["message"] = "Lesson complete! " + completion.get("message", "")
            return Response(verdict)

        verdict["passed"] = False
        remaining = verdict["total"] - verdict["passed_count"]
        verdict["message"] = (
            f"{verdict['passed_count']}/{verdict['total']} exercises cleared — "
            f"{remaining} to go. Refine the prompts the playground flags."
        )
        return Response(verdict)


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
            "ssh_user": session.ssh_user or "root",
            "lab_hosts": session.lab_hosts or [],
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
                # Expected-outcome objectives drive the right-hand panel in both
                # the terminal sidebar and the coding IDE. Without them the panel
                # rendered empty for running labs (the status endpoint omitted
                # them while the detail serializer included them).
                "objectives": public_objectives(session.scenario.objectives),
                "lab_mode": session.scenario.lab_mode,
                "simulation_type": session.scenario.simulation_type,
                "coding_mode": bool(getattr(session.scenario, "coding_mode", False)),
                # Cross-technology flags so the LabRunner surfaces the "Open VMware"
                # link for a shared-server scenario (e.g. add a disk in VMware that
                # then appears in this terminal after a rescan/reboot).
                "cross_technology": bool(getattr(session.scenario, "cross_technology", False)),
                "vmware_link": bool(getattr(session.scenario, "vmware_link", False)),
                # ITSM (ServiceNow-style) ticket flow — tells the LabRunner to
                # mount the ITSM ticket panel (open ticket + raise sub-tickets to
                # other teams) for this scenario.
                "itsm_enabled": bool(getattr(session.scenario, "itsm_enabled", False)),
                "itsm_ticket_type": getattr(session.scenario, "itsm_ticket_type", "") or "incident",
                # coding_kind lets the frontend route coding_mode scenarios to the
                # right surface without fetching the full spec — "prompt" opens the
                # PromptPlayground, anything else opens the code IDE.
                "coding_kind": (session.scenario.coding_spec or {}).get("kind", ""),
                # Surfaced so the terminal can warn before sending a disallowed
                # command (the consumer also enforces this server-side).
                "blocked_commands": session.scenario.blocked_commands or [],
                "dual_terminal": bool(getattr(session.scenario, "dual_terminal", False)),
                "technology": {
                    "name": session.scenario.technology.name,
                    "slug": session.scenario.technology.slug,
                } if session.scenario.technology else None,
            },
            "score": session.score,
            "hints_used": session.hints_used,
            "validation_passed": session.validation_passed,
            "is_expired": session.is_expired,
            "interview_mode": bool(getattr(session.scenario, "interview_mode", False)),
            "jira_issue_key": session.jira_issue_key or "",
            "jira_issue_url": resolve_jira_issue_url(
                session.jira_issue_key or "",
                session.jira_issue_url or "",
            ),
        }
        return Response(data)


class LabHintsView(APIView):
    permission_classes = [IsAuthenticated]

    TIER_LABELS = {
        1: ("Hint 1: Where to look", "Investigation strategy"),
        2: ("Hint 2: Step-by-step guide", "Diagnostic steps"),
        3: ("Hint 3: Full solution", "Exact fix + verification"),
    }
    TIER_XP_COSTS = {1: 0, 2: 25, 3: 50}

    @classmethod
    def _hint_payload(cls, hint, revealed: bool, unlocked: bool) -> dict:
        label, title = cls.TIER_LABELS.get(
            int(hint.order),
            (f"Hint {hint.order}", "Additional guidance"),
        )
        return {
            "order": hint.order,
            "label": label,
            "title": title,
            "content": hint.content if revealed else "",
            "penalty": hint.penalty,
            "xp_cost": cls.TIER_XP_COSTS.get(int(hint.order), hint.penalty),
            "revealed": revealed,
            "unlocked": unlocked,
            "locked": not unlocked,
        }

    @classmethod
    def _standard_response(cls, session, hints, *, interview_mode: bool = False) -> dict:
        total = hints.count()
        hints_used = min(session.hints_used, total)
        if interview_mode:
            return {
                "revealed": [],
                "tiers": [],
                "next_available": False,
                "total_hints": total,
                "hints_used": session.hints_used,
                "interview_mode": True,
                "ai_hints_available": True,
                "message": "Interview mode: standard hints are disabled. Use AI coaching hints instead.",
            }
        tier_items = [
            cls._hint_payload(
                hint,
                revealed=hint.order <= hints_used,
                unlocked=hint.order <= hints_used + 1,
            )
            for hint in hints
        ]
        return {
            "revealed": [t for t in tier_items if t["revealed"]],
            "tiers": tier_items,
            "next_available": total > hints_used,
            "total_hints": total,
            "hints_used": hints_used,
            "interview_mode": False,
        }

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        interview_mode = bool(getattr(session.scenario, "interview_mode", False))
        hints = Hint.objects.filter(scenario=session.scenario, is_active=True).order_by("order")

        if interview_mode:
            return Response(self._standard_response(session, hints, interview_mode=True))

        return Response(self._standard_response(session, hints))

    def post(self, request, session_id):
        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )
        if getattr(session.scenario, "interview_mode", False):
            return Response(
                {
                    "error": "Standard hints are disabled in interview mode.",
                    "code": "INTERVIEW_MODE",
                    "interview_mode": True,
                    "ai_hint_url": f"/api/labs/{session_id}/ai-hint/",
                },
                status=403,
            )

        hints = Hint.objects.filter(
            scenario=session.scenario, is_active=True
        ).order_by("order")

        if session.hints_used >= hints.count():
            return Response({"error": "No more hints available"}, status=400)

        next_hint = hints[session.hints_used]
        session.hints_used += 1
        session.save()

        payload = self._standard_response(session, hints)
        return Response({
            "hint": self._hint_payload(next_hint, revealed=True, unlocked=True),
            "tiers": payload["tiers"],
            "hints_used": session.hints_used,
            "total_hints": hints.count(),
            "next_available": payload["next_available"],
        })


class LabAiHintView(APIView):
    """FREE rule-based AI coaching for ANY lab scenario (and interview mode).

    Powered by apps.labs.ai_hint_service — no paid/OpenAI APIs. Returns
    progressive coaching hints that never reveal the stored solution. Optionally
    accepts a typed ``question`` for a context-aware coaching answer instead of
    the next ladder hint. This is the endpoint the lab "Ask AI" button calls.
    """
    permission_classes = [IsAuthenticated]

    MAX_AI_HINTS = 12

    def post(self, request, session_id):
        from apps.labs.ai_hint_service import answer_lab_question, generate_lab_hint

        session = get_object_or_404(
            LabSession, pk=session_id, user=request.user, status="RUNNING"
        )
        scenario = session.scenario
        interview_mode = bool(getattr(scenario, "interview_mode", False))

        # Recent commands give the coach context on what the learner already tried.
        try:
            recent_commands = list(
                session.command_history.order_by("-timestamp").values_list("command", flat=True)[:8]
            )
            recent_commands.reverse()
        except Exception:
            recent_commands = []

        # A typed question returns a coaching answer and does NOT consume a hint
        # credit (it's conversational), so learners can ask freely.
        question = (request.data.get("question") or "").strip()
        if question:
            result = answer_lab_question(scenario, question, recent_commands)
            return Response({
                "answer": result["content"],
                "ai_generated": True,
                "hints_used": session.hints_used,
                "total_hints": self.MAX_AI_HINTS,
                "interview_mode": interview_mode,
            })

        if session.hints_used >= self.MAX_AI_HINTS:
            return Response({"error": "Maximum AI coaching hints reached for this session."}, status=400)

        session.hints_used += 1
        session.save(update_fields=["hints_used"])
        order = session.hints_used

        hint = generate_lab_hint(scenario, order, recent_commands)
        hint["penalty"] = 15

        return Response({
            "hint": hint,
            "hints_used": session.hints_used,
            "total_hints": self.MAX_AI_HINTS,
            "interview_mode": interview_mode,
        })


class LabAiReviewView(APIView):
    """GET/POST /api/labs/<session_id>/ai-review/ — command-pattern feedback, no external API."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        review = session.metadata.get("ai_review")
        if not review:
            return Response({"review": None})
        return Response({"review": review})

    def post(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)
        if session.status not in ("COMPLETED", "TERMINATED", "EXPIRED", "FAILED"):
            return Response({"error": "Review only available after session ends."}, status=400)

        if session.metadata.get("ai_review"):
            return Response({"review": session.metadata["ai_review"]})

        commands = list(
            session.command_history.order_by("timestamp").values_list("command", "exit_code")
        )

        total = len(commands)
        errors = sum(1 for _, code in commands if code not in (None, 0))
        hints = session.hints_used
        solved = session.validation_passed

        # Pattern analysis
        used_sudo = any("sudo" in cmd for cmd, _ in commands)
        used_systemctl = any("systemctl" in cmd for cmd, _ in commands)
        used_journalctl = any("journalctl" in cmd for cmd, _ in commands)
        used_tail_logs = any(("tail" in cmd or "cat" in cmd) and "log" in cmd for cmd, _ in commands)
        used_grep = any("grep" in cmd for cmd, _ in commands)
        used_man = any(cmd.strip().startswith("man ") for cmd, _ in commands)

        strengths = []
        improvements = []

        if solved:
            strengths.append("Successfully resolved the scenario — well done.")
        if used_journalctl:
            strengths.append("Used `journalctl` for structured log analysis.")
        elif used_tail_logs:
            strengths.append("Checked logs to diagnose the issue.")
        if used_grep:
            strengths.append("Used `grep` to filter relevant output efficiently.")
        if used_man:
            strengths.append("Consulted `man` pages — good habit for unfamiliar options.")
        if errors < total * 0.2 and total > 3:
            strengths.append("Low error rate — commands were accurate and purposeful.")

        if errors > total * 0.4 and total > 3:
            improvements.append("High command error rate. Review syntax before running.")
        if hints >= 3:
            improvements.append("Used many hints. Try to diagnose from logs before requesting help.")
        if not used_journalctl and not used_tail_logs and total > 3:
            improvements.append("Log inspection was minimal. Start with `journalctl -xe` or check /var/log/.")
        if not used_grep and total > 5:
            improvements.append("Adding `grep` to filter command output speeds up root-cause identification.")
        if not solved:
            improvements.append("The scenario wasn't fully resolved. Review the solution to understand the fix.")

        overall = (
            "Excellent work!" if solved and hints <= 1
            else "Good effort!" if solved
            else "Solid attempt — check the solution for the final steps."
        )

        review = {
            "overall": overall,
            "stats": {"total_commands": total, "error_commands": errors, "hints_used": hints, "solved": solved},
            "strengths": strengths or ["Engaged with the scenario — keep practicing."],
            "improvements": improvements or ["Strong performance — nothing significant to flag."],
        }

        session.metadata["ai_review"] = review
        session.save(update_fields=["metadata"])

        return Response({"review": review})


# ─── Progress + Stats ────────────────────────────────────────────────

class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = f"user_progress:{request.user.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        try:
            progress = UserScenarioProgress.objects.filter(
                user=request.user
            ).select_related("scenario", "scenario__technology")

            total_scenarios = Scenario.objects.filter(is_active=True).count()
            completed = progress.filter(completed=True).count()
            total_attempts = progress.aggregate(total=Sum("attempts"))["total"] or 0
            avg_score = progress.filter(completed=True).aggregate(avg=Avg("best_score"))["avg"] or 0

            # Per-technology progress — single annotated query instead of N+1 loop
            techs_qs = Technology.objects.filter(is_active=True).annotate(
                tech_total=Count(
                    "scenarios",
                    filter=Q(scenarios__is_active=True),
                    distinct=True,
                ),
            )
            # Build completed count and avg_score per tech from already-loaded progress queryset
            user_progress_by_tech: dict[int, list] = {}
            for p in progress.filter(completed=True).select_related("scenario__technology"):
                tid = p.scenario.technology_id
                user_progress_by_tech.setdefault(tid, []).append(p.best_score)

            tech_progress = {}
            for tech in techs_qs:
                scores = user_progress_by_tech.get(tech.id, [])
                tech_progress[tech.name] = {
                    "total": tech.tech_total,
                    "completed": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                    "slug": tech.slug,
                    "icon": tech.icon,
                    "color": tech.color,
                }

            # Per-difficulty — two annotated aggregations instead of 6 queries
            diff_totals = {
                row["difficulty"]: row["cnt"]
                for row in Scenario.objects.filter(is_active=True)
                .values("difficulty")
                .annotate(cnt=Count("id"))
            }
            diff_done = {
                row["scenario__difficulty"]: row["cnt"]
                for row in progress.filter(completed=True)
                .values("scenario__difficulty")
                .annotate(cnt=Count("id"))
            }
            diff_progress = {
                d: {
                    "total": diff_totals.get(d, 0),
                    "completed": diff_done.get(d, 0),
                }
                for d in ["easy", "medium", "hard", "expert"]
            }

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

            # Difficulty auto-progression recommendations
            completed_slugs = set(progress.filter(completed=True).values_list("scenario__slug", flat=True))
            recommended = []
            for tech in Technology.objects.filter(is_active=True).prefetch_related("scenarios"):
                easy_s = [s for s in tech.scenarios.filter(is_active=True, difficulty="easy")]
                medium_s = [s for s in tech.scenarios.filter(is_active=True, difficulty="medium")]
                hard_s = [s for s in tech.scenarios.filter(is_active=True, difficulty="hard")]
                easy_done = sum(1 for s in easy_s if s.slug in completed_slugs)
                medium_done = sum(1 for s in medium_s if s.slug in completed_slugs)
                if easy_s and medium_s and easy_done >= len(easy_s) * 0.8 > 0:
                    target_pool = hard_s if (medium_done >= len(medium_s) * 0.8) else medium_s
                else:
                    target_pool = easy_s or medium_s
                # Emit a STABLE next-step: within the chosen difficulty tier, order
                # by the catalog's academy-sequence/slug key so the recommendation
                # is deterministic (DB row order is not guaranteed).
                try:
                    from apps.question_bank.technology_catalog import _slug_sort_key as _next_sort_key
                except Exception:
                    def _next_sort_key(slug):  # noqa: ANN001 — simple fallback
                        return (slug,)
                target_pool = sorted(target_pool, key=lambda s: _next_sort_key(s.slug))
                for s in target_pool:
                    if s.slug not in completed_slugs:
                        recommended.append({
                            "id": s.id, "slug": s.slug, "title": s.title,
                            "difficulty": s.difficulty, "technology": tech.name,
                            "technology_slug": tech.slug,
                        })
                        break  # one per tech

            # Streak + XP/level — reflect the dormant Profile counters so the
            # dashboard can render the streak + level widgets from one call.
            from apps.progress.services import compute_current_streak, compute_level
            current_streak = compute_current_streak(request.user)
            xp_total = 0
            longest_streak = current_streak
            try:
                from apps.accounts.models import Profile
                profile = Profile.objects.filter(user=request.user).only(
                    "xp", "longest_streak"
                ).first()
                if profile:
                    xp_total = profile.xp
                    longest_streak = max(profile.longest_streak, current_streak)
            except Exception:
                pass
            level_info = compute_level(xp_total)

            result = {
                "summary": {
                    "total_scenarios": total_scenarios,
                    "completed": completed,
                    "completion_rate": round(completed / total_scenarios * 100, 1) if total_scenarios else 0,
                    "total_attempts": total_attempts,
                    "average_score": round(avg_score, 1),
                    "current_streak": current_streak,
                    "longest_streak": longest_streak,
                    "xp": xp_total,
                    "level": level_info["level"],
                    "level_progress_pct": level_info["progress_pct"],
                    "xp_into_level": level_info["xp_into_level"],
                    "xp_for_next_level": level_info["xp_for_next_level"],
                },
                "technology_progress": tech_progress,
                "difficulty_progress": diff_progress,
                "achievements": achievements,
                "recommended_scenarios": recommended[:8],
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
                    if s.scenario_id is not None and s.scenario is not None
                ],
            }
            cache.set(cache_key, result, 60)
            return Response(result)
        except Exception:
            logger.exception("user_progress_failed user_id=%s", request.user.id)
            return Response(
                {"error": "Could not load progress"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        tech_id = request.query_params.get("technology")
        # scope: "all" (lifetime best, default) | "weekly" (last 7 days of solves)
        scope = (request.query_params.get("scope") or "all").lower()
        if scope not in ("all", "weekly"):
            scope = "all"
        cache_key = f"leaderboard_{scope}_{tech_id or 'all'}"

        cached_data = cache.get(cache_key)
        if cached_data is None:
            if scope == "weekly":
                cached_data = self._build_weekly(tech_id)
            else:
                cached_data = self._build_all_time(tech_id)
            cache.set(cache_key, cached_data, 300)  # 5 min

        user_rank = None
        if request.user.is_authenticated:
            for entry in cached_data:
                if entry["username"] == request.user.username:
                    user_rank = entry
                    break

        # Tolerate garbage page / page_size params without 500ing.
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = max(1, min(int(request.query_params.get("page_size", 20)), 100))
        except (TypeError, ValueError):
            page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        paginated = cached_data[start:end]

        return Response({
            "leaderboard": paginated,
            "user_rank": user_rank,
            "scope": scope,
            "count": len(cached_data),
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (len(cached_data) + page_size - 1) // page_size),
        })

    @staticmethod
    def _coerce_tech_id(tech_id):
        """Accept an int PK or a slug; return a kwargs dict for filtering.

        A garbage value must never 500 — it simply yields no tech filter.
        """
        if not tech_id:
            return {}
        s = str(tech_id).strip()
        if s.isdigit():
            return {"scenario__technology_id": int(s)}
        # Treat any non-numeric value as a slug (mirrors ScenariosListView).
        return {"scenario__technology__slug": s}

    @staticmethod
    def _build_all_time(tech_id):
        """Lifetime leaderboard from best-ever scenario scores."""
        qs = UserScenarioProgress.objects.filter(completed=True)
        qs = qs.filter(**LeaderboardView._coerce_tech_id(tech_id))
        rows = (
            qs.values("user__id", "user__username")
            .annotate(
                total_score=Sum("best_score"),
                scenarios_completed=Count("id"),
                avg_time=Avg("best_time"),
            )
            .order_by("-total_score")[:100]
        )
        return [
            {
                "rank": i,
                "user_id": r["user__id"],
                "username": r["user__username"],
                "total_score": r["total_score"] or 0,
                "scenarios_completed": r["scenarios_completed"],
                "avg_time": round(r["avg_time"] or 0),
            }
            for i, r in enumerate(rows, 1)
        ]

    @staticmethod
    def _build_weekly(tech_id):
        """Last-7-days leaderboard from validated lab sessions.

        UserScenarioProgress only keeps lifetime bests, so the weekly board reads
        from completed LabSessions (which carry a per-session score + ended_at).
        """
        since = timezone.now() - timezone.timedelta(days=7)
        qs = LabSession.objects.filter(
            validation_passed=True, ended_at__gte=since, scenario__isnull=False
        )
        qs = qs.filter(**LeaderboardView._coerce_tech_id(tech_id))
        # ANTI-GRIND: sum each scenario's BEST score once per user, not every
        # session. This was Sum("score") over all sessions in the window, so
        # re-solving one 30-second lab 200 times added 200 scores and topped the
        # weekly board. The all-time board already uses per-scenario bests
        # (UserScenarioProgress.best_score); this brings weekly in line.
        #
        # The tell that it was wrong was visible in the output: scenarios_completed
        # used distinct=True, so a grinder showed "1 scenario" beside an enormous
        # total. Nothing rejected it.
        # Two-level aggregation. Django cannot Sum() over an aggregate annotation
        # in one chain (Sum("best") where best=Max(...) raises), so the per-user
        # roll-up happens in Python. The input is bounded: one row per
        # (user, scenario) pair that had a validated session in a 7-day window.
        per_scenario = (
            qs.values("user__id", "user__username", "scenario")
            .annotate(best=Max("score"))
        )
        totals = {}
        for row in per_scenario.iterator(chunk_size=2000):
            key = row["user__id"]
            entry = totals.get(key)
            if entry is None:
                entry = totals[key] = {
                    "user__id": key,
                    "user__username": row["user__username"],
                    "total_score": 0,
                    "scenarios_completed": 0,
                }
            entry["total_score"] += row["best"] or 0
            entry["scenarios_completed"] += 1
        rows = sorted(
            totals.values(), key=lambda r: r["total_score"], reverse=True
        )[:100]
        return [
            {
                "rank": i,
                "user_id": r["user__id"],
                "username": r["user__username"],
                "total_score": r["total_score"] or 0,
                "scenarios_completed": r["scenarios_completed"],
                "avg_time": 0,
            }
            for i, r in enumerate(rows, 1)
        ]


# ─── Platform Stats (public) ────────────────────────────────────────

class PlatformStatsView(APIView):
    """Public stats for the landing page."""
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        cached = cache.get("platform_stats")
        if cached is not None:
            return Response(cached)
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Public landing/about stats — never 500. On any DB error return zeros;
        # the About page already overlays sensible display defaults.
        try:
            data = {
                "total_scenarios": Scenario.objects.filter(is_active=True).count(),
                "total_users": User.objects.filter(is_active=True).count(),
                "total_completions": UserScenarioProgress.objects.filter(completed=True).count(),
                "total_technologies": Technology.objects.filter(is_active=True).count(),
            }
            cache.set("platform_stats", data, 120)  # 2 min
        except Exception:
            logger.exception("PlatformStatsView failed — returning zeros")
            data = {
                "total_scenarios": 0,
                "total_users": 0,
                "total_completions": 0,
                "total_technologies": 0,
            }
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
            recording, _ = SessionRecording.objects.get_or_create(
                session=session,
                defaults={"events": [], "total_duration": 0},
            )
            return Response({
                "session_id": str(session.id),
                "scenario_title": session.scenario.title,
                "events": recording.events,
                "total_duration": recording.total_duration,
                "created_at": recording.created_at.isoformat(),
            })


# ─── Solution on Expiry ─────────────────────────────────────────────

class ExpiredSessionSolutionView(APIView):
    """Get solution explanation for an expired/terminated session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LabSession, pk=session_id, user=request.user)

        if session.status == "RUNNING" and session.is_expired:
            # Auto-expire the session
            resource_id = session.container_id or session.instance_id
            if resource_id:
                try:
                    provisioner = get_provisioner(session.provider or "docker")
                    terminate_lab_session(provisioner, session)
                except Exception:
                    pass
            session.status = "EXPIRED"
            session.ended_at = timezone.now()
            session.save()
        elif not _solution_unlock_allowed(session):
            return Response(
                {"error": "Solution only available after session ends, time expires, or hints are exhausted"},
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
        issued_at = timezone.now()
        expires_at = issued_at + timezone.timedelta(days=365)

        from apps.billing.models import UserCertificate

        cert_record, _ = UserCertificate.objects.update_or_create(
            user=user,
            technology=tech,
            defaults={
                "certificate_id": cert_id,
                "issued_at": issued_at,
                "expires_at": expires_at,
            },
        )

        cert_data = {
            "certificate_id": cert_record.certificate_id,
            "username": user.get_full_name() or user.username,
            "email": user.email,
            "technology": tech.name,
            "scenarios_completed": completed,
            "total_scenarios": total_scenarios,
            "total_score": total_score,
            "generated_at": issued_at.isoformat(),
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "completion_percentage": round((completed / total_scenarios) * 100) if total_scenarios > 0 else 0,
        }

        # Send certificate email
        try:
            from apps.notifications.tasks import send_notification_email
            from django.conf import settings as dj_settings

            verify_url = f"{dj_settings.FRONTEND_URL}/verify-certificate"
            send_notification_email.delay(
                subject=f"FixitLab Certificate — {tech.name} Completed!",
                to_email=user.email,
                template="emails/certificate_issued.html",
                context={
                    "username": user.get_full_name() or user.username,
                    "technology": tech.name,
                    "certificate_id": cert_record.certificate_id,
                    "scenarios_completed": completed,
                    "total_score": total_score,
                    "expires_at": expires_at.strftime("%B %d, %Y"),
                    "verify_url": verify_url,
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
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        cert_id = request.query_params.get("certificate_id", "").strip()
        if not cert_id:
            return Response(
                {"error": "certificate_id query parameter is required"},
                status=400,
            )

        if cert_id.startswith("FIXIT-INT-"):
            from apps.interviews.models import InterviewCertificate
            from django.utils import timezone as tz

            icert = InterviewCertificate.objects.filter(certificate_id=cert_id).first()
            if not icert:
                return Response({"valid": False, "error": "Certificate not found"})
            if icert.expires_at < tz.now():
                return Response({"valid": False, "error": "Certificate expired", "certificate_id": cert_id})
            return Response({
                "valid": True,
                "type": "interview",
                "certificate_id": icert.certificate_id,
                "holder_name": icert.holder_name,
                "technology": icert.technology_name,
                "level": icert.level,
                "rounds_cleared": icert.rounds_cleared,
                "overall_score": icert.overall_score,
                "issued_date": icert.issued_at.strftime("%Y-%m-%d"),
            })

        from apps.billing.subscription_utils import TEST_CERTIFICATE_ID

        if cert_id == TEST_CERTIFICATE_ID:
            return Response({
                "valid": True,
                "certificate_id": cert_id,
                "holder_name": "FixitLab Admin (Test Certificate)",
                "technology": "All Technologies",
                "scenarios_completed": 0,
                "total_scenarios": 0,
                "total_score": 0,
                "issued_date": "2026-01-01",
                "is_test_certificate": True,
            })

        # ── Certification-track certificates (apps.certifications) ──
        # Resolved strictly by the stored opaque id (which carries a random
        # component, so it is not enumerable). Lets the shared verify page work
        # for track certs too.
        from apps.certifications.models import CertEarnedCertificate

        track_cert = (
            CertEarnedCertificate.objects.select_related("track")
            .filter(certificate_id=cert_id)
            .first()
        )
        if track_cert:
            # ``is_valid`` (not just expiry) is the single source of truth --
            # revocation beats expiry, and this is the endpoint the shared verify
            # page hits, so an expiry-only check here means an employer following
            # a shared link is told a withdrawn certificate still stands.
            payload = {
                "valid": track_cert.is_valid,
                "type": "certification",
                "certificate_id": track_cert.certificate_id,
                "holder_name": track_cert.holder_name,
                "technology": track_cert.track.name,
                "level": track_cert.track.code,
                "overall_score": track_cert.score,
                "total_score": track_cert.score,
                "issued_date": track_cert.issued_at.strftime("%Y-%m-%d"),
            }
            if track_cert.revoked:
                # Say "revoked", not "not found" -- a bare miss is
                # indistinguishable from a typo and invites the holder to assume a
                # bug rather than a withdrawal. Holder/score stay in the payload
                # for the same reason the expired path below keeps them: the
                # opaque id genuinely identifies this holder's certificate, and
                # the withdrawal is unambiguous alongside ``valid: false``.
                # Mirrors CertVerifyView (apps/certifications/views.py).
                payload["revoked"] = True
                payload["revoked_at"] = track_cert.revoked_at
                payload["revoked_reason"] = track_cert.revoked_reason
                payload["error"] = "Certificate has been revoked"
                if track_cert.revoked_reason:
                    payload["error"] += f": {track_cert.revoked_reason}"
            elif track_cert.is_expired:
                payload["is_expired"] = True
                payload["error"] = (
                    "Certificate is out of date. Please renew your certification."
                )
            return Response(payload)

        # ── Look up STRICTLY by the stored opaque certificate id ──
        # (PRODUCTION_AUDIT PRIV-01) Certificate ids embed a user id
        # (FIXIT-<tech>-<USERID>-<DATE>), but we must NEVER derive the holder
        # from client-supplied input — doing so let an attacker enumerate every
        # user's name/stats by incrementing the id. Instead we resolve the
        # certificate only via the unique, issued ``UserCertificate.certificate_id``
        # row and read the holder/technology from that authoritative row. Any id
        # that does not match a genuinely issued certificate gets a flat
        # ``valid: false`` with no PII, so enumeration reveals nothing.
        if not cert_id.startswith("FIXIT-"):
            return Response({
                "valid": False,
                "error": "Invalid certificate ID format",
            })

        from apps.billing.models import UserCertificate

        cert_record = (
            UserCertificate.objects.select_related("user", "technology")
            .filter(certificate_id=cert_id)
            .first()
        )
        if not cert_record:
            # No issued certificate with this id. Return nothing identifying —
            # this is the response for every non-matching / probed id.
            return Response({
                "valid": False,
                "error": "Certificate not found. Check the ID and try again.",
            })

        user = cert_record.user
        tech = cert_record.technology
        holder_name = user.get_full_name() or user.username
        issued_date = cert_record.issued_at.strftime("%Y-%m-%d")
        expires_date = cert_record.expires_at.strftime("%Y-%m-%d")

        # Expired certificate: the id genuinely identifies this holder's cert,
        # so showing their name + the renew prompt is expected (this is the
        # legitimate "your certificate is out of date" path).
        if cert_record.is_expired:
            return Response({
                "valid": False,
                "certificate_id": cert_id,
                "holder_name": holder_name,
                "technology": tech.name,
                "error": "Certificate is out of date. Please renew your certification with the latest scenarios and technologies.",
                "issued_date": issued_date,
                "expires_date": expires_date,
                "is_expired": True,
            })

        # Stats are computed from the certificate's own (DB-derived) holder and
        # technology — never from client input.
        total_scenarios = tech.scenarios.filter(is_active=True).count()
        completed = UserScenarioProgress.objects.filter(
            user=user, scenario__technology=tech, completed=True
        ).count()
        total_score = UserScenarioProgress.objects.filter(
            user=user, scenario__technology=tech, completed=True
        ).aggregate(total=Sum("best_score"))["total"] or 0

        return Response({
            "valid": True,
            "certificate_id": cert_id,
            "holder_name": holder_name,
            "technology": tech.name,
            "scenarios_completed": completed,
            "total_scenarios": total_scenarios,
            "total_score": total_score,
            "issued_date": issued_date,
            "expires_date": expires_date,
        })


# ─── Blog (public CMS) ───────────────────────────────────────────────

class BlogListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Public marketing page — must NEVER 500. The frontend ships a static
        # fallback catalog, so on any DB error we return an empty list and let
        # the client render its built-in posts instead of a "Server error".
        try:
            from apps.adminpanel.models import BlogPost

            posts = list(
                BlogPost.objects.filter(is_published=True)
                .order_by("-published_at", "-created_at")[:50]
            )
        except Exception:
            logger.exception("BlogListView failed — returning empty list")
            return Response([])

        return Response([
            {
                "slug": p.slug,
                "title": p.title,
                "excerpt": p.excerpt,
                "category": p.category,
                "author": p.author_name,
                "date": (p.published_at or p.created_at).strftime("%B %d, %Y"),
                "readTime": f"{p.read_minutes} min read",
                "featured": i == 0,
            }
            for i, p in enumerate(posts)
        ])


class BlogDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        # Public marketing page — must NEVER 500. A missing post (or any DB
        # error) returns 404 so the client falls back to its static article
        # catalog rather than showing a server-error toast.
        try:
            from apps.adminpanel.models import BlogPost

            post = BlogPost.objects.get(slug=slug, is_published=True)
        except Exception as exc:
            from apps.adminpanel.models import BlogPost as _BP
            if not isinstance(exc, _BP.DoesNotExist):
                logger.exception("BlogDetailView failed for slug=%s", slug)
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "slug": post.slug,
            "title": post.title,
            "excerpt": post.excerpt,
            "content": post.content,
            "category": post.category,
            "author": post.author_name,
            "date": (post.published_at or post.created_at).strftime("%B %d, %Y"),
            "readTime": f"{post.read_minutes} min read",
        })


# ─── Projects API ─────────────────────────────────────────────────────────────

def _current_project_stage(project, user):
    """Return the current ProjectStage for a staged project, or None if flat.

    The current stage is the first stage (by ``order``) that is not yet complete.
    A stage is complete when all of its tasks are done for this user. When a
    project has stages but they are all complete, the last stage is returned so
    "Start/Resume" still opens a valid lab. Returns None for a flat project (no
    stages) so callers fall back to the single ``project.lab_scenario``.
    """
    stages = list(project.stages.all().select_related("lab_scenario").order_by("order"))
    if not stages:
        return None
    done_task_ids = set(
        UserTaskProgress.objects.filter(
            user=user, task__project=project, status="done"
        ).values_list("task_id", flat=True)
    )
    for stage in stages:
        stage_task_ids = list(stage.tasks.values_list("id", flat=True))
        # A stage with no tasks is treated as immediately complete (skip it).
        if stage_task_ids and not all(tid in done_task_ids for tid in stage_task_ids):
            return stage
    # Everything complete — return the last stage so Start still opens a lab.
    return stages[-1]


def _user_passed_scenario(user, scenario) -> bool:
    """True when the user has a validated (passed) lab session for `scenario`.

    Reuses the SAME completion signal that ValidateLabView / CodeValidateView
    write via apps.labs.completion.finalize_validated_session — a LabSession with
    validation_passed=True. This is the single source of truth for "the scenario
    validator passed", so a project task can gate on it without re-running the
    validator here.
    """
    if scenario is None:
        return False
    return LabSession.objects.filter(
        user=user, scenario=scenario, validation_passed=True
    ).exists()


class ProjectsListView(APIView):
    """GET /api/projects/ — catalog index for capstone projects (audit §C3).

    Projects historically lived only under TechnologyDetail. Journeys and the
    dashboard need a top-level browse surface with stable /projects/:slug links.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        qs = (
            Project.objects.filter(is_active=True)
            .select_related("technology", "lab_scenario")
            .annotate(task_count=Count("tasks"))
            .order_by("technology__order", "order", "title")
        )
        tech_slug = (request.query_params.get("technology") or "").strip()
        if tech_slug:
            qs = qs.filter(technology__slug=tech_slug)
        items = []
        for p in qs:
            items.append({
                "id": p.id,
                "slug": p.slug,
                "title": p.title,
                "description": p.description,
                "difficulty": p.difficulty,
                "estimated_hours": p.estimated_hours,
                "architecture_type": p.architecture_type,
                "technology": {
                    "slug": p.technology.slug,
                    "name": p.technology.name,
                },
                "task_count": p.task_count,
                "has_lab": bool(p.lab_scenario_id),
                "lab_scenario_slug": p.lab_scenario.slug if p.lab_scenario_id else None,
            })
        return Response({"projects": items, "count": len(items)})


class ProjectDetailView(APIView):
    """GET /api/projects/<slug>/ — single project for the /projects/:slug page."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        project = get_object_or_404(
            Project.objects.select_related("technology", "lab_scenario")
            .prefetch_related("tasks", "stages__stage_technology", "stages__lab_scenario"),
            slug=slug,
            is_active=True,
        )
        # Reuse the technology serializer shape so Start + task UI stay consistent
        # with TechnologyDetail's projects tab.
        serialized = _serialize_projects(project.technology, request.user if request.user.is_authenticated else None)
        match = next((p for p in serialized if p["slug"] == project.slug), None)
        if not match:
            return Response({"error": "Project not found"}, status=404)
        match["technology"] = {
            "slug": project.technology.slug,
            "name": project.technology.name,
        }
        match["has_lab"] = bool(project.lab_scenario_id)
        match["lab_scenario_slug"] = project.lab_scenario.slug if project.lab_scenario_id else None
        return Response(match)


class ProjectStartView(APIView):
    """POST — start or resume a project; returns the project with tasks and current user progress.

    For a *flat* project (no stages) this opens the single ``project.lab_scenario``
    exactly as before. For a *staged* project it opens the CURRENT stage's
    ``lab_scenario`` (the first stage whose tasks are not all done), so the learner
    lands in the right lab for wherever they are in the staged workflow.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, is_active=True)
        progress, _ = UserProjectProgress.objects.get_or_create(
            user=request.user, project=project,
            defaults={"status": "in_progress"},
        )
        # Ensure a UserTaskProgress row exists for every task
        for task in project.tasks.all():
            UserTaskProgress.objects.get_or_create(user=request.user, task=task)

        # Default to the flat project's single lab_scenario (unchanged behavior).
        lab_scenario = project.lab_scenario
        current_stage = None
        try:
            current_stage = _current_project_stage(project, request.user)
        except Exception as e:
            # Never fail Start because of stage resolution — fall back to flat.
            logger.warning(f"Stage resolution failed for project {project.id}: {e}")
            current_stage = None
        # A staged project opens the current stage's lab. If that stage has no
        # lab of its own (e.g. a postmortem/doc stage), fall back to the
        # project-level lab_scenario so Start still yields a workspace.
        if current_stage is not None and current_stage.lab_scenario_id:
            lab_scenario = current_stage.lab_scenario

        payload = {
            "status": progress.status,
            "started_at": str(progress.started_at),
            "project_id": project.id,
            # The lab the frontend should launch so the user gets a working
            # environment (terminal / sim / IDE / VMware / Grafana) for the project.
            "lab_scenario_id": lab_scenario.id if lab_scenario else None,
            "lab_scenario_slug": lab_scenario.slug if lab_scenario else None,
            "is_staged": current_stage is not None,
        }
        if current_stage is not None:
            payload["current_stage"] = {
                "id": current_stage.id,
                "order": current_stage.order,
                "title": current_stage.title,
                "stage_technology": (
                    current_stage.stage_technology.slug
                    if current_stage.stage_technology_id else None
                ),
                "handoff_artifact": current_stage.handoff_artifact or {},
                "breakpoint_note": current_stage.breakpoint_note,
            }
        return Response(payload)


class ProjectTaskUpdateView(APIView):
    """POST — update a task's status and optionally attach a screenshot."""
    permission_classes = [IsAuthenticated]
    parser_classes_lazy = ["rest_framework.parsers.MultiPartParser", "rest_framework.parsers.JSONParser"]

    def post(self, request, project_id, task_id):
        from django.utils import timezone as tz
        task = get_object_or_404(ProjectTask, id=task_id, project_id=project_id)
        utp, _ = UserTaskProgress.objects.get_or_create(user=request.user, task=task)

        new_status = request.data.get("status", utp.status)
        if new_status not in ("todo", "in_progress", "done"):
            return Response({"error": "Invalid status"}, status=400)

        # ── Optional real validation gate ──────────────────────────────────
        # If this task (or its stage's lab) has a configured validator, the user
        # must have PASSED that scenario's lab (a validated LabSession) before we
        # let them mark the task done and unlock its dependents. This reuses the
        # exact completion signal ValidateLabView writes. If NO validator is
        # configured, we preserve today's self-attest behavior. Any error here
        # falls back to self-attest — it must never 500.
        if new_status == "done":
            try:
                validator_scenario = task.validation_scenario
                if validator_scenario is None and task.stage_id:
                    stage_lab = task.stage.lab_scenario
                    # Only gate on the stage lab if it actually has a validator.
                    if stage_lab and (stage_lab.validation_script or "").strip():
                        validator_scenario = stage_lab
                if validator_scenario is not None and not _user_passed_scenario(
                    request.user, validator_scenario
                ):
                    return Response({
                        "error": "validation_required",
                        "message": (
                            f"Complete and pass the lab '{validator_scenario.slug}' "
                            "before marking this task done — the next ticket unlocks "
                            "on a passing validation."
                        ),
                        "validation_scenario_slug": validator_scenario.slug,
                    }, status=409)
            except Exception as e:
                # Never block on a validation-lookup failure — fall back to the
                # historical self-attest behavior with the change still applied.
                logger.warning(f"Task validation gate errored for task {task.id}: {e}")

        utp.status = new_status
        utp.notes = request.data.get("notes", utp.notes)
        if new_status == "done" and not utp.completed_at:
            utp.completed_at = tz.now()
        screenshot = request.FILES.get("screenshot")
        if screenshot:
            if screenshot.content_type not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
                return Response({'error': 'Screenshot must be PNG, JPEG, WebP, or GIF'}, status=400)
            if screenshot.size > 5 * 1024 * 1024:
                return Response({'error': 'Screenshot must be under 5 MB'}, status=400)
        if screenshot:
            utp.screenshot = screenshot
        utp.save()

        # Check if all tasks done → mark project completed
        project = task.project
        all_done = not project.tasks.exclude(
            id__in=UserTaskProgress.objects.filter(user=request.user, status="done").values_list("task_id", flat=True)
        ).exists()
        if all_done:
            UserProjectProgress.objects.filter(user=request.user, project=project).update(
                status="completed", completed_at=tz.now()
            )

        return Response({
            "task_id": task.id,
            "status": utp.status,
            "screenshot_url": utp.screenshot.url if utp.screenshot else None,
        })


class ProjectJiraBotView(APIView):
    """POST — ask the Jira bot about a project task; supports optional screenshot context."""
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id, task_id):
        task = get_object_or_404(ProjectTask, id=task_id, project_id=project_id)
        message = (request.data.get("message") or "").strip()
        has_screenshot = bool(request.FILES.get("screenshot"))

        # Free contextual answer based on task data — no external API
        lines = [
            f"**{task.jira_key}: {task.title}**",
            "",
            task.description,
        ]
        if task.acceptance_criteria:
            lines += ["", "**Acceptance criteria:**", task.acceptance_criteria]
        if task.hint:
            lines += ["", f"**Hint:** {task.hint}"]
        if has_screenshot:
            # Save screenshot to UserTaskProgress
            utp, _ = UserTaskProgress.objects.get_or_create(user=request.user, task=task)
            utp.screenshot = request.FILES["screenshot"]
            utp.save(update_fields=["screenshot"])
            lines += ["", "Screenshot received — I can see you've shared your progress. Based on the task above, check the acceptance criteria and make sure all steps are completed."]
        if message:
            # Simple keyword matching for contextual hints
            msg_lower = message.lower()
            if any(w in msg_lower for w in ("stuck", "help", "how", "what", "where", "hint")):
                lines += ["", f"**Next step:** {task.hint or 'Re-read the acceptance criteria and check your work step by step.'}"]
            elif any(w in msg_lower for w in ("done", "finished", "complete", "verify")):
                lines += ["", "Mark the task as **Done** using the status button. The next ticket will unlock once this one is completed."]

        return Response({"answer": "\n".join(lines), "task": {"id": task.id, "jira_key": task.jira_key}})
