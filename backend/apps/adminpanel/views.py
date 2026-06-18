"""
Complete Admin Panel API - Full CRUD for scenarios, technologies, users,
lab sessions, system monitoring, platform settings, and data exports.
"""
import csv
import logging
import os
from io import StringIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Avg, Sum, F
from django.http import HttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.db.models.functions import TruncDate
from datetime import timedelta

from apps.question_bank.models import Scenario, Technology, Tag
from apps.question_bank.serializers import ScenarioAdminSerializer, TechnologySerializer
from apps.labs.models import LabSession
from apps.labs.provisioner import get_provisioner, DockerProvisioner, terminate_lab_session
from apps.leaderboard.models import LeaderboardEntry
from apps.progress.models import UserScenarioProgress
from apps.billing.models import Plan, Subscription, TechnologySubscription
from apps.hints.models import Hint
from apps.community.models import Thread, Reply
from .permissions import IsPlatformAdmin

User = get_user_model()
logger = logging.getLogger(__name__)


class AdminOverviewView(APIView):
    permission_classes = [IsPlatformAdmin]
    CACHE_KEY = "admin_overview_v1"
    CACHE_TTL = 60

    def get(self, request):
        if request.query_params.get("refresh") != "1":
            cached = cache.get(self.CACHE_KEY)
            if cached is not None:
                return Response(cached)

        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        inactive_threshold = now - timedelta(days=90)

        # Revenue from technology subscriptions
        from apps.adminpanel.platform_config import get_settings_row
        from common.currency import get_usd_to_inr_rate, get_price_in_currency

        display_currency = request.query_params.get("currency", "").upper()
        if not display_currency:
            display_currency = (get_settings_row().admin_display_currency or "INR").upper()

        total_revenue_inr = TechnologySubscription.objects.filter(
            is_active=True
        ).aggregate(total=Sum("amount"))["total"] or 0

        revenue_display = get_price_in_currency(total_revenue_inr, display_currency)
        exchange_rate = float(get_usd_to_inr_rate()) if display_currency == "USD" else None

        # Paid subscribers count
        paid_subscribers = TechnologySubscription.objects.filter(
            is_active=True
        ).values("user").distinct().count()

        # Inactive users (90+ days)
        inactive_users = User.objects.filter(
            Q(last_login__lt=inactive_threshold) | Q(last_login__isnull=True)
        ).count()

        payload = {
            "users": {
                "total": User.objects.count(),
                "active_24h": User.objects.filter(last_login__gte=last_24h).count(),
                "new_7d": User.objects.filter(date_joined__gte=last_7d).count(),
                "new_30d": User.objects.filter(date_joined__gte=last_30d).count(),
                "inactive_90d": inactive_users,
                "paid_subscribers": paid_subscribers,
            },
            "revenue": {
                "total": float(revenue_display["amount"]),
                "currency": revenue_display["currency"],
                "symbol": revenue_display.get("symbol", "₹" if display_currency == "INR" else "$"),
                "total_inr": float(total_revenue_inr),
                "exchange_rate": exchange_rate,
                "subscriptions_count": TechnologySubscription.objects.filter(is_active=True).count(),
            },
            "scenarios": {
                "total": Scenario.objects.count(),
                "active": Scenario.objects.filter(is_active=True).count(),
                "draft": Scenario.objects.filter(is_active=False).count(),
            },
            "technologies": {
                "total": Technology.objects.count(),
                "active": Technology.objects.filter(is_active=True).count(),
            },
            "labs": {
                "running": LabSession.objects.filter(status="RUNNING").count(),
                "completed_24h": LabSession.objects.filter(
                    status="COMPLETED", ended_at__gte=last_24h
                ).count(),
                "total": LabSession.objects.count(),
                "avg_score": LabSession.objects.filter(
                    status="COMPLETED"
                ).aggregate(avg=Avg("score"))["avg"] or 0,
            },
            "community": {
                "threads": Thread.objects.filter(is_deleted=False).count(),
                "replies": Reply.objects.filter(is_deleted=False).count(),
            },
            "completion_rate": self._get_completion_rate(),
            "maintenance_mode": __import__(
                "apps.adminpanel.platform_config", fromlist=["is_maintenance_active"]
            ).is_maintenance_active(),
            "cached_at": now.isoformat(),
        }
        cache.set(self.CACHE_KEY, payload, self.CACHE_TTL)
        return Response(payload)

    def _get_completion_rate(self):
        total = LabSession.objects.filter(
            status__in=["COMPLETED", "TERMINATED", "FAILED"]
        ).count()
        completed = LabSession.objects.filter(status="COMPLETED").count()
        return round(completed / total * 100, 1) if total else 0


# ─── Technology Management ───────────────────────────────────────────

class AdminTechnologiesView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        techs = Technology.objects.annotate(
            scenario_count=Count("scenarios"),
            active_scenarios=Count("scenarios", filter=Q(scenarios__is_active=True)),
            subscriber_count=Count("subscriptions", filter=Q(subscriptions__is_active=True)),
        ).order_by("name")
        data = []
        for t in techs:
            data.append({
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "icon": t.icon,
                "color": t.color,
                "description": t.description,
                "price": str(t.price),
                "order": t.order,
                "is_active": t.is_active,
                "coming_soon": t.coming_soon,
                "maintenance_enabled": t.maintenance_enabled,
                "scenario_count": t.scenario_count,
                "active_scenarios": t.active_scenarios,
                "subscriber_count": t.subscriber_count,
                "created_at": t.created_at.isoformat(),
            })
        return Response(data)

    def post(self, request):
        """Create a new technology."""
        serializer = TechnologySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            from apps.question_bank.cache_utils import invalidate_technologies_cache
            invalidate_technologies_cache()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminTechnologyDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        try:
            tech = Technology.objects.get(pk=pk)
        except Technology.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        serializer = TechnologySerializer(tech, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            from apps.question_bank.cache_utils import invalidate_technologies_cache
            invalidate_technologies_cache()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        try:
            tech = Technology.objects.get(pk=pk)
        except Technology.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        cascade = str(request.data.get("cascade", request.query_params.get("cascade", ""))).lower() in (
            "1", "true", "yes",
        )
        force = str(request.data.get("force", request.query_params.get("force", ""))).lower() in (
            "1", "true", "yes",
        )
        confirm_name = request.data.get("confirm_name", "").strip()

        # Check active subscribers
        active_sub_count = TechnologySubscription.objects.filter(
            technology=tech, is_active=True
        ).count()
        if active_sub_count > 0 and not force:
            return Response(
                {
                    "error": "subscribers_active",
                    "message": f"This technology has {active_sub_count} active subscriber(s). Force-delete requires typing the technology name to confirm.",
                    "active_subscriber_count": active_sub_count,
                    "technology_name": tech.name,
                },
                status=409,
            )
        if active_sub_count > 0 and force:
            if confirm_name != tech.name:
                return Response(
                    {"error": "Name confirmation does not match. Type the exact technology name to confirm force-delete."},
                    status=400,
                )

        scenario_count = tech.scenarios.count()
        if scenario_count and not cascade:
            return Response(
                {
                    "error": (
                        f"Technology has {scenario_count} scenario(s). "
                        "Send cascade=true to delete the technology and all its scenarios."
                    ),
                    "scenario_count": scenario_count,
                },
                status=400,
            )

        deleted_scenarios = 0
        if scenario_count:
            deleted_scenarios = scenario_count
            tech.scenarios.all().delete()

        tech_name = tech.name
        tech.delete()
        from apps.question_bank.cache_utils import invalidate_technologies_cache
        invalidate_technologies_cache()
        return Response({
            "message": "Technology deleted",
            "technology": tech_name,
            "scenarios_deleted": deleted_scenarios,
        })


# ─── Tag Management ──────────────────────────────────────────────────

class AdminTagsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        tags = Tag.objects.annotate(
            scenario_count=Count("scenarios"),
        ).order_by("name")
        data = [
            {"id": t.id, "name": t.name, "slug": t.slug, "scenario_count": t.scenario_count}
            for t in tags
        ]
        return Response(data)

    def post(self, request):
        name = request.data.get("name")
        if not name:
            return Response({"error": "Name is required"}, status=400)
        if Tag.objects.filter(name__iexact=name).exists():
            return Response({"name": ["Tag with this name already exists."]}, status=400)
        tag = Tag.objects.create(name=name)
        return Response({"id": tag.id, "name": tag.name, "slug": tag.slug}, status=201)


class AdminTagDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        try:
            tag = Tag.objects.get(pk=pk)
        except Tag.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        name = request.data.get("name", tag.name)
        tag.name = name
        tag.save()
        return Response({"id": tag.id, "name": tag.name, "slug": tag.slug})

    def delete(self, request, pk):
        try:
            tag = Tag.objects.get(pk=pk)
        except Tag.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        tag.delete()
        return Response({"message": "Tag deleted"})


# ─── Technology Maintenance & Subscriber Management ──────────────────

class AdminTechnologyMaintenanceView(APIView):
    """Toggle maintenance mode and set message/schedule for a single technology."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        try:
            tech = Technology.objects.get(pk=pk)
        except Technology.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response({
            "maintenance_enabled": tech.maintenance_enabled,
            "maintenance_message": tech.maintenance_message,
            "maintenance_scheduled_start": tech.maintenance_scheduled_start.isoformat() if tech.maintenance_scheduled_start else None,
            "maintenance_scheduled_end": tech.maintenance_scheduled_end.isoformat() if tech.maintenance_scheduled_end else None,
        })

    def post(self, request, pk):
        from django.utils.dateparse import parse_datetime
        try:
            tech = Technology.objects.get(pk=pk)
        except Technology.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        was_enabled = tech.maintenance_enabled
        tech.maintenance_enabled = bool(request.data.get("enabled", tech.maintenance_enabled))
        if "message" in request.data:
            tech.maintenance_message = request.data["message"]
        if "scheduled_start" in request.data:
            val = request.data["scheduled_start"]
            tech.maintenance_scheduled_start = parse_datetime(val) if val else None
        if "scheduled_end" in request.data:
            val = request.data["scheduled_end"]
            tech.maintenance_scheduled_end = parse_datetime(val) if val else None
        tech.save()

        from apps.question_bank.cache_utils import invalidate_technologies_cache
        invalidate_technologies_cache()

        # Notify subscribers if maintenance just turned on
        if tech.maintenance_enabled and not was_enabled:
            _notify_tech_maintenance(tech)

        return Response({
            "maintenance_enabled": tech.maintenance_enabled,
            "maintenance_message": tech.maintenance_message,
            "maintenance_scheduled_start": tech.maintenance_scheduled_start.isoformat() if tech.maintenance_scheduled_start else None,
            "maintenance_scheduled_end": tech.maintenance_scheduled_end.isoformat() if tech.maintenance_scheduled_end else None,
        })


def _notify_tech_maintenance(tech):
    """Send maintenance email to all active subscribers of this technology."""
    try:
        from apps.notifications.email_dispatch import dispatch_notification_email
        subs = TechnologySubscription.objects.filter(
            technology=tech, is_active=True
        ).select_related("user")
        msg = tech.maintenance_message or f"{tech.name} is currently undergoing maintenance. Labs will be unavailable during this period."
        for sub in subs:
            dispatch_notification_email(
                subject=f"[FixitLab] {tech.name} Maintenance Notice",
                to_email=sub.user.email,
                template="emails/maintenance_notice.html",
                context={
                    "user": sub.user,
                    "technology": tech.name,
                    "maintenance_message": msg,
                    "maintenance_scheduled_start": tech.maintenance_scheduled_start,
                    "maintenance_scheduled_end": tech.maintenance_scheduled_end,
                },
            )
    except Exception:
        pass


class AdminTechnologySubscribersView(APIView):
    """List all subscribers for a specific technology with stats."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        try:
            tech = Technology.objects.get(pk=pk)
        except Technology.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        from django.utils import timezone as tz
        from apps.billing.subscription_utils import is_tech_subscription_active
        now = tz.now()

        subs = TechnologySubscription.objects.filter(
            technology=tech
        ).select_related("user").order_by("-created_at")

        total_revenue = 0
        active_count = 0
        data = []
        for sub in subs:
            active = is_tech_subscription_active(sub)
            if active:
                active_count += 1
                total_revenue += float(sub.amount)
            data.append({
                "id": str(sub.id),
                "subscription_id": sub.subscription_id,
                "user": {
                    "id": sub.user.id,
                    "username": sub.user.username,
                    "email": sub.user.email,
                    "full_name": sub.user.get_full_name(),
                    "date_joined": sub.user.date_joined.isoformat(),
                },
                "amount": str(sub.amount),
                "amount_display": f"₹{int(float(sub.amount))}",
                "payment_verified": sub.payment_verified,
                "is_active": active,
                "subscribed_at": sub.created_at.isoformat(),
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "days_remaining": max(0, (sub.expires_at - now).days) if sub.expires_at and active else None,
            })

        # Scenario progress stats per subscriber
        from apps.progress.models import UserScenarioProgress
        scenario_ids = list(tech.scenarios.values_list("id", flat=True))
        progress_qs = UserScenarioProgress.objects.filter(
            scenario_id__in=scenario_ids, completed=True
        ).values("user_id").annotate(completed=Count("id"))
        progress_map = {p["user_id"]: p["completed"] for p in progress_qs}
        for entry in data:
            entry["completed_scenarios"] = progress_map.get(entry["user"]["id"], 0)

        return Response({
            "technology": {"id": tech.id, "name": tech.name, "slug": tech.slug},
            "total_subscribers": len(data),
            "active_count": active_count,
            "total_revenue": total_revenue,
            "subscribers": data,
        })


class AdminTechnologyEmailView(APIView):
    """Send / draft an email campaign to all active subscribers of a technology."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        try:
            tech = Technology.objects.get(pk=pk)
        except Technology.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        subject = request.data.get("subject", "").strip()
        body = request.data.get("body", "").strip()
        send_now = request.data.get("send_now", True)

        if not subject or not body:
            return Response({"error": "subject and body are required"}, status=400)

        subs = TechnologySubscription.objects.filter(
            technology=tech, is_active=True
        ).select_related("user")

        if not send_now:
            return Response({"status": "draft_saved", "recipient_count": subs.count()})

        sent = 0
        failed = 0
        try:
            from apps.notifications.email_dispatch import dispatch_notification_email
            for sub in subs:
                try:
                    dispatch_notification_email(
                        subject=subject,
                        to_email=sub.user.email,
                        template="emails/admin_campaign.html",
                        context={
                            "user": sub.user,
                            "technology": tech.name,
                            "subject": subject,
                            "body": body,
                        },
                    )
                    sent += 1
                except Exception:
                    failed += 1
        except Exception:
            failed += subs.count()

        return Response({
            "status": "sent",
            "sent": sent,
            "failed": failed,
            "recipient_count": subs.count(),
        })


class AdminTechnologyStatsView(APIView):
    """Per-technology revenue and subscriber stats for the subscriptions overview."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from django.utils import timezone as tz
        from apps.billing.subscription_utils import is_tech_subscription_active
        from apps.labs.models import LabSession
        from django.contrib.auth import get_user_model
        User = get_user_model()
        now = tz.now()

        techs = Technology.objects.annotate(
            total_subs=Count("subscriptions"),
            active_subs=Count(
                "subscriptions",
                filter=Q(subscriptions__is_active=True),
            ),
        ).order_by("order", "name")

        result = []
        for tech in techs:
            revenue = TechnologySubscription.objects.filter(
                technology=tech, is_active=True
            ).aggregate(total=Sum("amount"))["total"] or 0
            paid_user_ids = TechnologySubscription.objects.filter(
                technology=tech, is_active=True
            ).values_list("user_id", flat=True)
            free_users = (
                User.objects.filter(lab_sessions__scenario__technology=tech)
                .exclude(id__in=paid_user_ids)
                .distinct()
                .count()
            )
            complimentary_users = User.objects.filter(
                profile__complimentary_access=True,
                lab_sessions__scenario__technology=tech,
            ).distinct().count()
            free_user_total = free_users + complimentary_users
            result.append({
                "id": tech.id,
                "name": tech.name,
                "slug": tech.slug,
                "color": tech.color,
                "price": str(tech.price),
                "is_active": tech.is_active,
                "maintenance_enabled": tech.maintenance_enabled,
                "total_subscribers": tech.total_subs,
                "active_subscribers": tech.active_subs,
                "free_users": free_users,
                "complimentary_users": complimentary_users,
                "free_user_total": free_user_total,
                "revenue_inr": float(revenue),
                "revenue_display": f"₹{int(float(revenue))}",
            })

        total_revenue = sum(r["revenue_inr"] for r in result)
        total_active = sum(r["active_subscribers"] for r in result)
        maintenance_count = sum(1 for r in result if r.get("maintenance_enabled"))
        coming_soon_count = Technology.objects.filter(coming_soon=True).count()
        total_unique_users = (
            TechnologySubscription.objects.filter(is_active=True)
            .values("user_id")
            .distinct()
            .count()
        )
        total_free_users = User.objects.filter(profile__complimentary_access=True).count()

        return Response({
            "technologies": result,
            "total_revenue_inr": total_revenue,
            "total_active_subscribers": total_active,
            "total_unique_subscribers": total_unique_users,
            "total_free_users": total_free_users,
            "maintenance_technologies": maintenance_count,
            "coming_soon_technologies": coming_soon_count,
        })


class AdminInterviewMaintenanceView(APIView):
    """Toggle interview maintenance mode."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.interviews.models import InterviewPlatformSettings
        settings_row, _ = InterviewPlatformSettings.objects.get_or_create(pk=1)
        return Response({
            "maintenance_enabled": settings_row.maintenance_enabled,
            "maintenance_message": settings_row.maintenance_message,
            "maintenance_scheduled_start": settings_row.maintenance_scheduled_start.isoformat() if settings_row.maintenance_scheduled_start else None,
            "maintenance_scheduled_end": settings_row.maintenance_scheduled_end.isoformat() if settings_row.maintenance_scheduled_end else None,
        })

    def post(self, request):
        from django.utils.dateparse import parse_datetime
        from apps.interviews.models import InterviewPlatformSettings
        settings_row, _ = InterviewPlatformSettings.objects.get_or_create(pk=1)
        if "enabled" in request.data:
            settings_row.maintenance_enabled = bool(request.data["enabled"])
        if "message" in request.data:
            settings_row.maintenance_message = request.data["message"]
        if "scheduled_start" in request.data:
            val = request.data["scheduled_start"]
            settings_row.maintenance_scheduled_start = parse_datetime(val) if val else None
        if "scheduled_end" in request.data:
            val = request.data["scheduled_end"]
            settings_row.maintenance_scheduled_end = parse_datetime(val) if val else None
        settings_row.save()
        return Response({
            "maintenance_enabled": settings_row.maintenance_enabled,
            "maintenance_message": settings_row.maintenance_message,
            "maintenance_scheduled_start": settings_row.maintenance_scheduled_start.isoformat() if settings_row.maintenance_scheduled_start else None,
            "maintenance_scheduled_end": settings_row.maintenance_scheduled_end.isoformat() if settings_row.maintenance_scheduled_end else None,
        })


# ─── Scenario Management ────────────────────────────────────────────

class AdminScenariosView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Scenario.objects.select_related("technology").prefetch_related("tags").annotate(
            total_attempts=Count("lab_sessions"),
            completions=Count("lab_sessions", filter=Q(lab_sessions__status="COMPLETED")),
        ).order_by("-created_at")

        # Filters
        tech_id = request.query_params.get("technology")
        difficulty = request.query_params.get("difficulty")
        is_active = request.query_params.get("is_active")
        search = request.query_params.get("search")

        if tech_id:
            qs = qs.filter(technology_id=tech_id)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(slug__icontains=search))

        data = []
        for s in qs:
            data.append({
                "id": s.id,
                "title": s.title,
                "slug": s.slug,
                "subtitle": s.subtitle,
                "scenario_type": s.scenario_type,
                "technology": {"id": s.technology.id, "name": s.technology.name},
                "category": s.category,
                "difficulty": s.difficulty,
                "description": s.description,
                "objectives": s.objectives,
                "validation_script": s.validation_script,
                "solution_explanation": s.solution_explanation,
                "definition_path": s.definition_path,
                "infrastructure_type": s.infrastructure_type,
                "lab_mode": s.lab_mode,
                "simulation_type": s.simulation_type,
                "requires_companion_hosts": s.requires_companion_hosts,
                "dual_terminal": s.dual_terminal,
                "docker_privileged": s.docker_privileged,
                "initial_state": s.initial_state,
                "cloud_setup_script": s.cloud_setup_script,
                "jira_priority": s.jira_priority,
                "jira_issue_template": s.jira_issue_template,
                "blocked_commands": s.blocked_commands or [],
                "is_active": s.is_active,
                "is_free": s.is_free,
                "time_limit": s.time_limit,
                "max_score": s.max_score,
                "tags": [{"id": t.id, "name": t.name} for t in s.tags.all()],
                "total_attempts": s.total_attempts,
                "completions": s.completions,
                "created_at": s.created_at.isoformat(),
            })
        return Response(data)

    def post(self, request):
        """Create a new scenario."""
        serializer = ScenarioAdminSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminScenarioDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        try:
            scenario = Scenario.objects.select_related("technology").prefetch_related("tags").get(pk=pk)
        except Scenario.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        hints = Hint.objects.filter(scenario=scenario).order_by("order").values(
            "id", "order", "content", "penalty", "is_active"
        )

        serializer = ScenarioAdminSerializer(scenario)
        data = serializer.data
        data["hints"] = list(hints)
        return Response(data)

    def put(self, request, pk):
        try:
            scenario = Scenario.objects.get(pk=pk)
        except Scenario.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        serializer = ScenarioAdminSerializer(scenario, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        try:
            scenario = Scenario.objects.get(pk=pk)
        except Scenario.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        # Soft delete - deactivate instead
        scenario.is_active = False
        scenario.save()
        return Response({"message": "Scenario deactivated"})


# ─── Hint Management ────────────────────────────────────────────────

class AdminHintsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, scenario_id):
        """Add a hint to a scenario."""
        try:
            scenario = Scenario.objects.get(pk=scenario_id)
        except Scenario.DoesNotExist:
            return Response({"error": "Scenario not found"}, status=404)

        content = request.data.get("content")
        penalty = request.data.get("penalty", 10)
        if not content:
            return Response({"error": "Content is required"}, status=400)

        # Auto-assign order
        max_order = Hint.objects.filter(scenario=scenario).count()
        hint = Hint.objects.create(
            scenario=scenario,
            order=max_order + 1,
            content=content,
            penalty=penalty,
        )
        return Response({
            "id": hint.id, "order": hint.order,
            "content": hint.content, "penalty": hint.penalty,
        }, status=201)


class AdminHintDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        try:
            hint = Hint.objects.get(pk=pk)
        except Hint.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        hint.content = request.data.get("content", hint.content)
        hint.penalty = request.data.get("penalty", hint.penalty)
        hint.is_active = request.data.get("is_active", hint.is_active)
        hint.save()
        return Response({"id": hint.id, "content": hint.content, "penalty": hint.penalty})

    def delete(self, request, pk):
        try:
            hint = Hint.objects.get(pk=pk)
        except Hint.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        hint.delete()
        return Response({"message": "Hint deleted"})


# ─── User Management ────────────────────────────────────────────────

class AdminUsersView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = User.objects.all().order_by("-date_joined")

        search = request.query_params.get("search")
        is_active = request.query_params.get("is_active")
        is_staff = request.query_params.get("is_staff")

        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        if is_staff is not None:
            qs = qs.filter(is_staff=is_staff.lower() == "true")

        # Annotate with stats
        qs = qs.annotate(
            labs_completed=Count(
                "lab_sessions", filter=Q(lab_sessions__status="COMPLETED")
            ),
            total_labs=Count("lab_sessions"),
            active_subscriptions=Count(
                "tech_subscriptions",
                filter=Q(tech_subscriptions__is_active=True),
            ),
        ).select_related("profile")

        data = []
        for u in qs[:100]:
            phone_number = None
            country = ""
            try:
                phone_number = u.profile.phone_number
                country = u.profile.country or ""
            except Exception:
                pass

            is_inactive_90d = False
            if u.last_login:
                from django.utils import timezone as tz
                is_inactive_90d = (tz.now() - u.last_login).days >= 90

            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone_number": phone_number,
                "country": country,
                "is_active": u.is_active,
                "is_staff": u.is_staff,
                "is_superuser": u.is_superuser,
                "complimentary_access": getattr(u.profile, "complimentary_access", False) if hasattr(u, "profile") else False,
                "is_paid": u.active_subscriptions > 0 or getattr(u.profile, "complimentary_access", False) if hasattr(u, "profile") else u.active_subscriptions > 0,
                "active_subscriptions": u.active_subscriptions,
                "is_inactive_90d": is_inactive_90d,
                "date_joined": u.date_joined.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "labs_completed": u.labs_completed,
                "total_labs": u.total_labs,
            })
        return Response(data)

    def post(self, request):
        """Create a new user (admin-created)."""
        email = request.data.get("email")
        password = request.data.get("password")
        is_staff = request.data.get("is_staff", False)
        phone_number = request.data.get("phone_number")

        if not email or not password:
            return Response({"error": "Email and password are required"}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already exists"}, status=400)

        user = User.objects.create_user(
            username=email, email=email, password=password, is_staff=is_staff
        )

        # Create profile with phone number
        from apps.accounts.models import Profile
        Profile.objects.update_or_create(
            user=user,
            defaults={"phone_number": phone_number or None},
        )

        return Response({"id": user.id, "email": user.email}, status=201)


class AdminUserDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        """Get detailed user info including progress and activity."""
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        # Profile info
        phone_number = None
        complimentary_access = False
        try:
            phone_number = user.profile.phone_number
            complimentary_access = user.profile.complimentary_access
        except Exception:
            pass

        # Lab stats
        labs = LabSession.objects.filter(user=user)
        completed_labs = labs.filter(status="COMPLETED")
        total_score = completed_labs.aggregate(total=Sum("score"))["total"] or 0

        # Progress stats
        progress = UserScenarioProgress.objects.filter(user=user)
        completed_scenarios = progress.filter(completed=True).count()
        total_attempts = sum(p.attempts for p in progress)

        # Recent labs
        recent_labs = labs.select_related("scenario").order_by("-started_at")[:10]

        jira_tickets = []
        try:
            from apps.jira_integration.models import UserScenarioJiraTicket
            from apps.jira_integration.helpers import is_jira_closed

            for t in UserScenarioJiraTicket.objects.filter(user=user, issue_key__gt="").select_related("scenario"):
                jira_tickets.append({
                    "issue_key": t.issue_key,
                    "issue_url": t.issue_url,
                    "jira_status": t.jira_status,
                    "is_closed": is_jira_closed(t.jira_status),
                    "run_count": t.run_count,
                    "scenario": {"id": t.scenario_id, "slug": t.scenario.slug, "title": t.scenario.title},
                    "updated_at": t.updated_at.isoformat(),
                })
        except Exception:
            pass

        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone_number": phone_number,
            "complimentary_access": complimentary_access,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "date_joined": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "stats": {
                "total_labs": labs.count(),
                "labs_completed": completed_labs.count(),
                "total_score": total_score,
                "scenarios_completed": completed_scenarios,
                "total_attempts": total_attempts,
                "avg_score": round(
                    completed_labs.aggregate(avg=Avg("score"))["avg"] or 0, 1
                ),
            },
            "recent_labs": [
                {
                    "id": str(lab.id),
                    "scenario": lab.scenario.title,
                    "status": lab.status,
                    "score": lab.score,
                    "started_at": lab.started_at.isoformat(),
                }
                for lab in recent_labs
            ],
            "jira_tickets": jira_tickets,
        })

    def put(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        if "is_active" in request.data:
            user.is_active = request.data["is_active"]
        if "is_staff" in request.data:
            if not request.user.is_superuser:
                return Response({"error": "Only superusers can modify admin privileges"}, status=403)
            user.is_staff = request.data["is_staff"]

        # Admin can reset user password
        new_password = request.data.get("new_password")
        if new_password:
            if len(new_password) < 8:
                return Response({"error": "Password must be at least 8 characters"}, status=400)
            user.set_password(new_password)

        user.save()

        # Update phone number if provided
        phone_number = request.data.get("phone_number")
        if phone_number is not None:
            from apps.accounts.models import Profile
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone_number = phone_number or None
            profile.save()

        if "complimentary_access" in request.data:
            from apps.billing.subscription_utils import grant_complimentary_access
            grant_complimentary_access(
                user, bool(request.data["complimentary_access"]), granted_by=request.user
            )

        return Response({
            "id": user.id,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "message": "User updated successfully",
        })

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        if user.is_superuser:
            return Response({"error": "Cannot delete superuser"}, status=403)

        try:
            user.delete()
            return Response({"message": "User deleted"})
        except Exception as e:
            logger.error(f"Failed to delete user {pk}: {e}")
            return Response(
                {"error": "Failed to delete user. They may have related data that cannot be removed."},
                status=500,
            )


# ─── Bulk User Operations ───────────────────────────────────────────

class AdminBulkUsersView(APIView):
    """Bulk delete or update users."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        action = request.data.get("action")
        user_ids = request.data.get("user_ids", [])

        if not user_ids or not isinstance(user_ids, list):
            return Response({"error": "user_ids must be a non-empty list"}, status=400)

        if not action:
            return Response({"error": "action is required"}, status=400)

        users = User.objects.filter(id__in=user_ids).exclude(is_superuser=True)
        count = users.count()

        if count == 0:
            return Response({"error": "No eligible users found (superusers are protected)"}, status=400)

        if action == "delete":
            try:
                users.delete()
                return Response({"message": f"{count} user(s) deleted", "count": count})
            except Exception as e:
                logger.error(f"Bulk delete failed: {e}")
                return Response({"error": "Bulk delete failed"}, status=500)

        elif action == "activate":
            updated = users.update(is_active=True)
            return Response({"message": f"{updated} user(s) activated", "count": updated})

        elif action == "deactivate":
            updated = users.update(is_active=False)
            return Response({"message": f"{updated} user(s) deactivated", "count": updated})

        elif action == "make_staff":
            if not request.user.is_superuser:
                return Response({"error": "Only superusers can grant admin privileges"}, status=403)
            updated = users.update(is_staff=True)
            return Response({"message": f"{updated} user(s) granted admin", "count": updated})

        elif action == "remove_staff":
            if not request.user.is_superuser:
                return Response({"error": "Only superusers can revoke admin privileges"}, status=403)
            updated = users.update(is_staff=False)
            return Response({"message": f"{updated} user(s) had admin removed", "count": updated})

        elif action == "grant_free":
            from apps.billing.subscription_utils import grant_complimentary_access
            count = 0
            for u in users:
                grant_complimentary_access(u, True, granted_by=request.user)
                count += 1
            return Response({"message": f"{count} user(s) granted free access", "count": count})

        elif action == "revoke_free":
            from apps.billing.subscription_utils import grant_complimentary_access
            count = 0
            for u in users:
                grant_complimentary_access(u, False, granted_by=request.user)
                count += 1
            return Response({"message": f"{count} user(s) had free access revoked", "count": count})

        else:
            return Response(
                {"error": f"Unknown action: {action}. Valid: delete, activate, deactivate, make_staff, remove_staff, grant_free, revoke_free"},
                status=400,
            )


# ─── Active Labs Management ─────────────────────────────────────────

class AdminActiveLabsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        include_expired = request.query_params.get("include_expired") == "1"
        status_filter = request.query_params.get("status", "running")
        qs = LabSession.objects.select_related("user", "scenario").order_by("-started_at")
        if status_filter == "all":
            qs = qs.filter(status__in=["RUNNING", "PROVISIONING"])
        else:
            qs = qs.filter(status="RUNNING")

        data = []
        for lab in qs:
            expired = lab.is_expired if lab.status == "RUNNING" else False
            if not include_expired and expired:
                continue
            resource_id = lab.container_id or lab.instance_id or ""
            data.append({
                "id": str(lab.id),
                "user": lab.user.username,
                "scenario": lab.scenario.title,
                "provider": lab.provider,
                "infrastructure_type": lab.provider,
                "resource_id": resource_id[:12] if resource_id else None,
                "container_id": lab.container_id[:12] if lab.container_id else None,
                "full_container_id": lab.container_id,
                "instance_id": lab.instance_id[:12] if lab.instance_id else None,
                "ssh_host": lab.ssh_host or None,
                "time_remaining": lab.time_remaining,
                "started_at": lab.started_at.isoformat(),
                "status": lab.status,
                "is_expired": expired,
            })
        return Response(data)


class AdminTerminateLabView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, session_id):
        try:
            session = LabSession.objects.get(pk=session_id)
        except LabSession.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        resource_id = session.container_id or session.instance_id
        if resource_id:
            try:
                provisioner = get_provisioner(session.provider or "docker")
                terminate_lab_session(provisioner, session)
            except Exception as e:
                logger.error(f"Admin terminate error: {e}")

        session.mark_terminated()
        return Response({"message": "Lab terminated"})


class AdminTerminateAllIdleLabsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        """Terminate all labs that have exceeded their time limit."""
        expired = LabSession.objects.filter(status="RUNNING")
        terminated = 0
        for lab in expired:
            if lab.is_expired:
                resource_id = lab.container_id or lab.instance_id
                if resource_id:
                    try:
                        provisioner = get_provisioner(lab.provider or "docker")
                        terminate_lab_session(provisioner, lab)
                    except Exception:
                        pass
                lab.status = "EXPIRED"
                lab.ended_at = timezone.now()
                lab.save()
                terminated += 1

        return Response({"terminated": terminated})


def _admin_terminate_session(session) -> bool:
    try:
        provisioner = get_provisioner(session.provider or "docker")
        terminate_lab_session(provisioner, session)
    except Exception as exc:
        logger.error("Admin terminate error for %s: %s", session.id, exc)
    if session.is_expired and session.status == "RUNNING":
        session.status = "EXPIRED"
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])
        return True
    session.mark_terminated()
    return True


class AdminBulkLabsView(APIView):
    """Bulk terminate selected labs or all expired running labs."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        action = request.data.get("action", "terminate")
        session_ids = request.data.get("session_ids", [])
        terminate_expired_only = request.data.get("terminate_expired_only", False)

        if action == "terminate_expired":
            labs = LabSession.objects.filter(status="RUNNING")
            terminated = 0
            for lab in labs:
                if lab.is_expired:
                    _admin_terminate_session(lab)
                    terminated += 1
            cache.delete(AdminOverviewView.CACHE_KEY)
            return Response({"terminated": terminated, "message": f"{terminated} expired lab(s) terminated"})

        if not session_ids or not isinstance(session_ids, list):
            return Response({"error": "session_ids must be a non-empty list"}, status=400)

        labs = LabSession.objects.filter(id__in=session_ids, status__in=["RUNNING", "PROVISIONING"])
        terminated = 0
        for lab in labs:
            if terminate_expired_only and not lab.is_expired:
                continue
            _admin_terminate_session(lab)
            terminated += 1

        cache.delete(AdminOverviewView.CACHE_KEY)
        return Response({"terminated": terminated, "message": f"{terminated} lab(s) terminated"})


# ─── Analytics ───────────────────────────────────────────────────────

class AdminAnalyticsView(APIView):
    permission_classes = [IsPlatformAdmin]
    CACHE_KEY = "admin_analytics_v1"
    CACHE_TTL = 120

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        cache_key = f"{self.CACHE_KEY}:{days}"
        if request.query_params.get("refresh") != "1":
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        now = timezone.now()
        start_date = now - timedelta(days=days)

        daily_rows = (
            LabSession.objects.filter(started_at__gte=start_date)
            .annotate(day=TruncDate("started_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        daily_labs = [
            {"date": row["day"].strftime("%Y-%m-%d"), "count": row["count"]}
            for row in daily_rows
        ]

        # Top scenarios
        top_scenarios = (
            Scenario.objects.annotate(
                attempt_count=Count("lab_sessions"),
                completion_count=Count("lab_sessions", filter=Q(lab_sessions__status="COMPLETED")),
            )
            .order_by("-attempt_count")[:10]
            .values("title", "attempt_count", "completion_count")
        )

        # Difficulty distribution
        difficulty_stats = (
            Scenario.objects.filter(is_active=True)
            .values("difficulty")
            .annotate(count=Count("id"))
        )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        new_users = User.objects.filter(date_joined__gte=start_date).count()
        active_users = User.objects.filter(last_login__gte=start_date).count()
        completed_labs = LabSession.objects.filter(
            started_at__gte=start_date, status="COMPLETED"
        ).count()
        try:
            from apps.interviews.models import InterviewCampaign
            interview_campaigns = InterviewCampaign.objects.filter(created_at__gte=start_date).count()
        except Exception:
            interview_campaigns = 0
        try:
            new_subs = TechnologySubscription.objects.filter(created_at__gte=start_date, is_active=True).count()
            revenue_inr = TechnologySubscription.objects.filter(
                created_at__gte=start_date, is_active=True, payment_verified=True,
            ).aggregate(total=Sum("amount"))["total"] or 0
        except Exception:
            new_subs = 0
            revenue_inr = 0

        total_starts = sum(d["count"] for d in daily_labs)
        completion_rate = round((completed_labs / total_starts * 100), 1) if total_starts else 0

        top_technologies = list(
            LabSession.objects.filter(started_at__gte=start_date)
            .values("scenario__technology__name", "scenario__technology__slug")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )

        payload = {
            "daily_labs": daily_labs,
            "top_scenarios": list(top_scenarios),
            "difficulty_distribution": list(difficulty_stats),
            "top_technologies": top_technologies,
            "summary": {
                "new_users": new_users,
                "active_users": active_users,
                "completed_labs": completed_labs,
                "interview_campaigns": interview_campaigns,
                "new_subscriptions": new_subs,
                "total_lab_starts": total_starts,
                "revenue_inr": float(revenue_inr),
                "completion_rate_pct": completion_rate,
            },
            "cached_at": now.isoformat(),
        }
        cache.set(cache_key, payload, self.CACHE_TTL)
        return Response(payload)


# ─── System Health ───────────────────────────────────────────────────

class AdminSystemHealthView(APIView):
    permission_classes = [IsPlatformAdmin]

    CACHE_KEY = "admin_system_health_v2"
    CACHE_TTL = 90

    def get(self, request):
        from django.core.cache import cache

        force = request.query_params.get("refresh") == "1"
        if not force:
            cached = cache.get(self.CACHE_KEY)
            if cached:
                return Response(cached)

        health = {
            "database": self._check_db(),
            "redis": self._check_redis(),
            "docker": self._check_docker(),
            "email": self._check_email(),
            "rabbitmq": self._check_rabbitmq(),
            "celery": self._check_celery(),
            "vault": self._check_vault(),
        }

        # Cloud provider health (optional — does not affect core overall)
        health["cloud_providers"] = self._check_cloud_providers()

        # Container-level health (platform services only)
        health["containers"] = self._check_containers()

        # Email statistics
        health["email_stats"] = self._get_email_stats()
        try:
            from apps.notifications.email_health import email_delivery_health

            health["email_delivery_alert"] = email_delivery_health(window_minutes=15)
        except Exception:
            health["email_delivery_alert"] = {"alert": False}

        # Cloud lab usage
        health["cloud_labs"] = self._get_cloud_lab_stats()

        # Overall health — core services only (not cloud providers or lab containers)
        core_services = ["database", "redis", "docker", "email", "rabbitmq", "celery"]
        health["overall"] = all(
            health.get(svc, {}).get("status") == "healthy" for svc in core_services
        )
        health["cached_at"] = timezone.now().isoformat()
        cache.set(self.CACHE_KEY, health, self.CACHE_TTL)
        return Response(health)

    def _check_db(self):
        try:
            from django.db import connection
            connection.ensure_connection()
            user_count = User.objects.count()
            return {"status": "healthy", "details": f"{user_count} users"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_redis(self):
        try:
            from django.core.cache import cache
            cache.set("health_check", "ok", 10)
            if cache.get("health_check") == "ok":
                return {"status": "healthy"}
            return {"status": "unhealthy", "error": "Cache read/write failed"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_docker(self):
        try:
            provisioner = DockerProvisioner()
            provisioner.client.ping()
            info = provisioner.client.info()
            return {
                "status": "healthy",
                "details": f"{info.get('Containers', 0)} containers, {info.get('Images', 0)} images",
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_email(self):
        """Check email delivery path (Gmail API in prod, SMTP in dev)."""
        try:
            from apps.notifications.gmail_api import is_gmail_api_configured

            if is_gmail_api_configured():
                sender = getattr(settings, "EMAIL_HOST_USER", "")
                if settings.GMAIL_OAUTH_REFRESH_TOKEN and settings.GMAIL_OAUTH_CLIENT_ID:
                    return {
                        "status": "healthy",
                        "details": f"Gmail API configured → {sender or 'default sender'}",
                        "provider": "gmail_api",
                    }
                return {"status": "unhealthy", "error": "Gmail OAuth credentials incomplete"}

            import smtplib

            host = settings.EMAIL_HOST
            port = settings.EMAIL_PORT
            use_tls = getattr(settings, "EMAIL_USE_TLS", False)

            # MailHog / dev SMTP — skip strict check if no credentials
            if host in ("mailhog", "localhost", "127.0.0.1") and not getattr(settings, "EMAIL_HOST_USER", ""):
                return {"status": "healthy", "details": f"Dev SMTP ({host}:{port})", "provider": "smtp_dev"}

            # Production SMTP without live network probe (avoids false unhealthy in restricted egress)
            user = getattr(settings, "EMAIL_HOST_USER", "")
            if user and host not in ("mailhog", "localhost", "127.0.0.1"):
                return {
                    "status": "healthy",
                    "details": f"SMTP configured ({host}:{port})",
                    "provider": "smtp",
                }

            if use_tls:
                server = smtplib.SMTP(host, port, timeout=5)
                server.starttls()
            else:
                server = smtplib.SMTP(host, port, timeout=5)

            password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
            if user and password:
                server.login(user, password)
            server.quit()
            return {"status": "healthy", "details": f"{host}:{port}", "provider": "smtp"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_rabbitmq(self):
        """Check RabbitMQ connectivity via Celery's broker."""
        try:
            from celery_app.celery import app
            conn = app.connection()
            conn.ensure_connection(max_retries=1, timeout=3)
            conn.close()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_celery(self):
        """Check if Celery workers are responding."""
        try:
            from celery_app.celery import app
            inspector = app.control.inspect(timeout=3)
            active = inspector.active()
            if active:
                worker_count = len(active)
                task_count = sum(len(tasks) for tasks in active.values())
                return {
                    "status": "healthy",
                    "details": f"{worker_count} worker(s), {task_count} active task(s)",
                }
            return {"status": "unhealthy", "error": "No workers responding"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_vault(self):
        """HashiCorp Vault container + secrets integration status."""
        vault_enabled = str(getattr(settings, "VAULT_ENABLED", "") or os.environ.get("VAULT_ENABLED", "")).lower() in ("1", "true", "yes", "on")
        secrets_loaded = False

        # Check whether vault_loader already injected secrets this process startup
        try:
            from config.vault_loader import _VAULT_LOADED
            secrets_loaded = _VAULT_LOADED
        except Exception:
            pass

        if not vault_enabled:
            return {
                "status": "healthy",
                "details": "Vault disabled — using env file for secrets",
                "optional": True,
                "secrets_loaded": False,
            }

        try:
            import subprocess

            status = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", "fixitlab_vault"],
                capture_output=True, text=True, timeout=8,
            )
            if status.returncode != 0:
                return {"status": "unhealthy", "error": "Vault container not found", "secrets_loaded": secrets_loaded}
            state = (status.stdout or "").strip()
            if state != "running":
                return {"status": "unhealthy", "error": f"Vault container {state}", "secrets_loaded": secrets_loaded}

            # Try live Vault API check via hvac
            try:
                import hvac
                vault_addr = os.environ.get("VAULT_ADDR", "http://vault:8200")
                client = hvac.Client(url=vault_addr, timeout=3)
                sys_health = client.sys.read_health_status(method="GET")
                initialized = sys_health.get("initialized", False)
                sealed = sys_health.get("sealed", False)
                if not initialized:
                    status_str = "degraded"
                    detail = "Vault not initialized — run sync-production-env.sh"
                elif sealed:
                    status_str = "degraded"
                    detail = "Vault is sealed — run: vault operator unseal (or re-deploy to auto-unseal)"
                else:
                    status_str = "healthy"
                    detail = "Vault unsealed and ready"
                return {
                    "status": status_str,
                    "details": detail,
                    "secrets_loaded": secrets_loaded,
                    "initialized": initialized,
                    "sealed": sealed,
                }
            except Exception:
                pass

            # Fallback: container running but API unreachable — if env file has secrets this is non-critical
            env_file_ok = bool(os.environ.get("DJANGO_SECRET_KEY"))
            return {
                "status": "healthy" if env_file_ok else "degraded",
                "details": "Vault API unreachable — running in env file mode" if env_file_ok else "Vault container running but API unreachable",
                "secrets_loaded": env_file_ok,
                "optional": True,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "secrets_loaded": secrets_loaded}

    def _check_containers(self):
        """Get health status of platform Docker containers (not ephemeral lab containers)."""
        try:
            import docker
            client = docker.from_env()
            all_containers = client.containers.list(all=True)
            result = []
            skip_names = ("mailhog",)

            for c in all_containers:
                labels = c.labels or {}
                # Skip ephemeral lab containers
                if labels.get("fixitlab.session_id"):
                    continue
                name_lower = c.name.lower()
                if any(skip in name_lower for skip in skip_names):
                    continue

                project = labels.get("com.docker.compose.project", "")
                # Include containers from any fixitlab compose project (hyphenated or underscore names)
                is_platform = (
                    project in ("fixitlab-main", "fixitlab")
                    or c.name.startswith("fixitlab_")
                    or c.name.startswith("fixitlab-")
                    or c.name in ("fixitlab_db", "fixitlab_redis", "fixitlab_rabbitmq", "fixitlab_vault")
                )
                if not is_platform:
                    continue

                state = c.attrs.get("State", {})
                health_obj = state.get("Health", {})
                health_status = health_obj.get("Status", "none")
                restart_count = c.attrs.get("RestartCount", 0)
                exit_code = state.get("ExitCode", 0)

                # Lightweight memory snapshot (no blocking stream)
                mem_mb = None
                try:
                    if c.status == "running":
                        raw = c.stats(stream=False)
                        mem = raw.get("memory_stats", {})
                        usage = mem.get("usage", 0)
                        cache = mem.get("stats", {}).get("cache", 0)
                        mem_mb = round((usage - cache) / (1024 * 1024), 1)
                except Exception:
                    pass

                result.append({
                    "name": c.name,
                    "status": c.status,
                    "health": health_status,
                    "image": c.image.tags[0] if c.image.tags else str(c.image.id)[:20],
                    "up_since": state.get("StartedAt", ""),
                    "restart_count": restart_count,
                    "exit_code": exit_code if c.status != "running" else None,
                    "mem_mb": mem_mb,
                })
            return sorted(result, key=lambda x: x["name"])
        except Exception as e:
            return [{"name": "error", "status": "unknown", "error": str(e)}]

    def _get_email_stats(self):
        """Get email sending statistics."""
        try:
            from apps.notifications.models import EmailLog
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)

            total = EmailLog.objects.count()
            sent_24h = EmailLog.objects.filter(status="sent", created_at__gte=last_24h).count()
            failed_24h = EmailLog.objects.filter(status="failed", created_at__gte=last_24h).count()
            sent_7d = EmailLog.objects.filter(status="sent", created_at__gte=last_7d).count()
            failed_7d = EmailLog.objects.filter(status="failed", created_at__gte=last_7d).count()

            last_email = EmailLog.objects.first()  # ordered by -created_at
            last_sent_at = last_email.created_at.isoformat() if last_email else None

            recent = list(
                EmailLog.objects.values("subject", "to_email", "status", "created_at")[:10]
            )
            # Convert datetimes to iso strings
            for r in recent:
                r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None

            return {
                "total": total,
                "sent_24h": sent_24h,
                "failed_24h": failed_24h,
                "sent_7d": sent_7d,
                "failed_7d": failed_7d,
                "last_sent_at": last_sent_at,
                "recent": recent,
            }
        except Exception:
            return {
                "total": 0, "sent_24h": 0, "failed_24h": 0,
                "sent_7d": 0, "failed_7d": 0,
                "last_sent_at": None, "recent": [],
            }

    def _check_cloud_providers(self):
        """Check which cloud providers are configured and their status."""
        providers = {}

        # AWS EC2
        aws_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
        if aws_key:
            try:
                from apps.labs.provisioner.aws_provisioner import EC2Provisioner
                prov = EC2Provisioner()
                prov.ec2_client.describe_regions(RegionNames=[settings.AWS_REGION])
                providers["aws_ec2"] = {
                    "configured": True,
                    "status": "healthy",
                    "region": settings.AWS_REGION,
                    "instance_type": getattr(settings, "AWS_LAB_INSTANCE_TYPE", "t3.micro"),
                }
            except Exception as e:
                providers["aws_ec2"] = {
                    "configured": True,
                    "status": "unhealthy",
                    "error": str(e),
                }
        else:
            providers["aws_ec2"] = {"configured": False, "status": "not_configured"}

        # DigitalOcean
        do_token = getattr(settings, "DO_API_TOKEN", "")
        if do_token:
            try:
                import requests as req
                resp = req.get(
                    "https://api.digitalocean.com/v2/account",
                    headers={"Authorization": f"Bearer {do_token}"},
                    timeout=5,
                )
                if resp.status_code == 200:
                    providers["digitalocean"] = {
                        "configured": True,
                        "status": "healthy",
                        "region": getattr(settings, "DO_REGION", "nyc1"),
                        "size": getattr(settings, "DO_SIZE", "s-1vcpu-1gb"),
                    }
                elif resp.status_code == 401:
                    providers["digitalocean"] = {
                        "configured": True,
                        "status": "auth_error",
                        "optional": True,
                        "error": "Invalid or expired DO_API_TOKEN — update .env.production",
                    }
                else:
                    providers["digitalocean"] = {
                        "configured": True,
                        "status": "unhealthy",
                        "optional": True,
                        "error": f"API returned {resp.status_code}",
                    }
            except Exception as e:
                providers["digitalocean"] = {
                    "configured": True,
                    "status": "unhealthy",
                    "error": str(e),
                }
        else:
            providers["digitalocean"] = {"configured": False, "status": "not_configured"}

        return providers

    def _get_cloud_lab_stats(self):
        """Get statistics about cloud-based lab sessions."""
        try:
            now = timezone.now()
            last_24h = now - timedelta(hours=24)

            stats = {
                "active_docker": LabSession.objects.filter(status="RUNNING", provider="docker").count(),
                "active_aws": LabSession.objects.filter(status="RUNNING", provider="aws_ec2").count(),
                "active_do": LabSession.objects.filter(status="RUNNING", provider="digitalocean").count(),
                "total_cloud_24h": LabSession.objects.filter(
                    provider__in=["aws_ec2", "digitalocean"],
                    started_at__gte=last_24h,
                ).count(),
                "cloud_scenarios": Scenario.objects.filter(
                    infrastructure_type__in=["aws_ec2", "digitalocean"],
                    is_active=True,
                ).count(),
            }
            return stats
        except Exception:
            return {
                "active_docker": 0, "active_aws": 0, "active_do": 0,
                "total_cloud_24h": 0, "cloud_scenarios": 0,
            }


# ─── Audit Log Viewer ───────────────────────────────────────────────

class AdminAuditLogView(APIView):
    """View audit logs with filtering."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.audit.models import AuditLog
        qs = AuditLog.objects.select_related("user").order_by("-created_at")

        # Filters
        action = request.query_params.get("action")
        user_id = request.query_params.get("user_id")
        days = int(request.query_params.get("days", 7))

        if action:
            qs = qs.filter(action=action)
        if user_id:
            qs = qs.filter(user_id=user_id)

        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=since)

        logs = []
        for log in qs[:200]:
            logs.append({
                "id": log.id,
                "action": log.action,
                "resource": log.resource,
                "user": log.user.username if log.user else None,
                "user_id": log.user_id,
                "ip_address": log.ip_address,
                "metadata": log.metadata,
                "created_at": log.created_at.isoformat(),
            })

        # Summary stats
        all_actions = AuditLog.objects.filter(created_at__gte=since)
        stats = list(all_actions.values("action").annotate(count=Count("id")).order_by("-count"))

        return Response({
            "logs": logs,
            "stats": stats,
            "total": qs.count(),
        })


# ─── Recent Activity Feed ───────────────────────────────────────────

class AdminActivityFeedView(APIView):
    """Get recent platform activity for the admin dashboard."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        activities = []

        # Recent registrations
        new_users = User.objects.filter(
            date_joined__gte=last_24h
        ).order_by("-date_joined")[:10]
        for u in new_users:
            activities.append({
                "type": "registration",
                "icon": "user-plus",
                "message": f"New user registered: {u.username}",
                "email": u.email,
                "timestamp": u.date_joined.isoformat(),
            })

        # Recent lab starts
        recent_labs = LabSession.objects.filter(
            started_at__gte=last_24h
        ).select_related("user", "scenario").order_by("-started_at")[:10]
        for lab in recent_labs:
            activities.append({
                "type": "lab_start",
                "icon": "play",
                "message": f"{lab.user.username if lab.user else 'Unknown'} started {lab.scenario.title if lab.scenario else 'a lab'}",
                "timestamp": lab.started_at.isoformat(),
            })

        # Recent completions
        completed_labs = LabSession.objects.filter(
            status="COMPLETED", ended_at__gte=last_24h
        ).select_related("user", "scenario").order_by("-ended_at")[:10]
        for lab in completed_labs:
            activities.append({
                "type": "lab_completed",
                "icon": "check-circle",
                "message": f"{lab.user.username if lab.user else 'Unknown'} completed {lab.scenario.title if lab.scenario else 'a lab'} (Score: {lab.score or 0})",
                "timestamp": lab.ended_at.isoformat(),
            })

        # Recent failed labs
        failed_labs = LabSession.objects.filter(
            status="FAILED", ended_at__gte=last_24h
        ).select_related("user", "scenario").order_by("-ended_at")[:5]
        for lab in failed_labs:
            activities.append({
                "type": "lab_failed",
                "icon": "x-circle",
                "message": f"{lab.user.username if lab.user else 'Unknown'}'s lab expired: {lab.scenario.title if lab.scenario else 'a lab'}",
                "timestamp": lab.ended_at.isoformat(),
            })

        # Sort all activities by timestamp descending
        activities.sort(key=lambda x: x["timestamp"], reverse=True)

        return Response(activities[:30])


# ─── CSV Exports ─────────────────────────────────────────────────────

class AdminExportUsersView(APIView):
    """Export all users as CSV."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        users = User.objects.annotate(
            total_labs=Count("lab_sessions"),
            completed_labs=Count("lab_sessions", filter=Q(lab_sessions__status="COMPLETED")),
        ).order_by("-date_joined")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="users_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(["ID", "Username", "Email", "Active", "Staff", "Total Labs", "Completed", "Joined", "Last Login"])
        for u in users:
            writer.writerow([
                u.id, u.username, u.email, u.is_active, u.is_staff,
                u.total_labs, u.completed_labs,
                u.date_joined.strftime("%Y-%m-%d %H:%M"),
                u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never",
            ])
        return response


class AdminExportLabsView(APIView):
    """Export lab sessions as CSV."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)
        labs = LabSession.objects.filter(
            started_at__gte=since
        ).select_related("user", "scenario").order_by("-started_at")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="labs_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(["Session ID", "User", "Scenario", "Status", "Score", "Started", "Ended", "Duration (min)"])
        for lab in labs:
            duration = ""
            if lab.started_at and lab.ended_at:
                duration = round((lab.ended_at - lab.started_at).total_seconds() / 60, 1)
            writer.writerow([
                str(lab.id), lab.user.username if lab.user else "—",
                lab.scenario.title if lab.scenario else "—",
                lab.status, lab.score or 0,
                lab.started_at.strftime("%Y-%m-%d %H:%M"),
                lab.ended_at.strftime("%Y-%m-%d %H:%M") if lab.ended_at else "—",
                duration,
            ])
        return response


class AdminExportProgressView(APIView):
    """Export user progress as CSV."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        progress = UserScenarioProgress.objects.select_related(
            "user", "scenario"
        ).order_by("user__username", "scenario__title")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="progress_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(["User", "Scenario", "Best Score", "Attempts", "Completed", "Last Attempt"])
        for p in progress:
            writer.writerow([
                p.user.username, p.scenario.title if p.scenario else "—",
                p.best_score or 0, p.attempts or 0,
                "Yes" if p.completed else "No",
                p.last_attempt_at.strftime("%Y-%m-%d %H:%M") if hasattr(p, "last_attempt_at") and p.last_attempt_at else "—",
            ])
        return response


# ─── New Admin Features ──────────────────────────────────────────────

class AdminMaintenanceModeView(APIView):
    """Toggle maintenance mode and message."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.adminpanel.platform_config import admin_config_payload, get_settings_row

        row = get_settings_row()
        payload = admin_config_payload()
        return Response({
            "maintenance_mode": payload["maintenance_mode"],
            "maintenance_message": payload["maintenance_message"],
            "maintenance_enabled": row.maintenance_enabled,
            "maintenance_banner_image": row.maintenance_banner_image,
            "maintenance_banner_style": row.maintenance_banner_style,
            "maintenance_scheduled_start": payload["maintenance_scheduled_start"],
            "maintenance_scheduled_end": payload["maintenance_scheduled_end"],
            "maintenance_notify_users": row.maintenance_notify_users,
        })

    def post(self, request):
        from apps.adminpanel.platform_config import (
            get_settings_row,
            notify_maintenance_users,
            persist_config_snapshot,
        )

        row = get_settings_row()
        was_active = row.maintenance_enabled
        if "enabled" in request.data:
            row.maintenance_enabled = bool(request.data.get("enabled"))
        if "message" in request.data:
            row.maintenance_message = request.data.get("message", "")
        if "banner_image" in request.data:
            row.maintenance_banner_image = request.data.get("banner_image", "")
        if "banner_style" in request.data:
            row.maintenance_banner_style = request.data.get("banner_style") or {}
        if "scheduled_start" in request.data:
            from django.utils.dateparse import parse_datetime
            val = request.data.get("scheduled_start")
            row.maintenance_scheduled_start = parse_datetime(val) if val else None
        if "scheduled_end" in request.data:
            from django.utils.dateparse import parse_datetime
            val = request.data.get("scheduled_end")
            row.maintenance_scheduled_end = parse_datetime(val) if val else None
        if "notify_users" in request.data:
            row.maintenance_notify_users = bool(request.data.get("notify_users"))
        row.save()
        persist_config_snapshot(row)
        settings.MAINTENANCE_MODE = row.maintenance_enabled
        settings.MAINTENANCE_MESSAGE = row.maintenance_message
        cache.delete(AdminOverviewView.CACHE_KEY)

        notified = 0
        if row.maintenance_enabled and not was_active and row.maintenance_notify_users:
            notified = notify_maintenance_users(row.maintenance_message)

        from apps.adminpanel.platform_config import admin_config_payload

        payload = admin_config_payload()
        payload["users_notified"] = notified
        return Response(payload)


class AdminInactiveUsersView(APIView):
    """List users inactive for 90+ days (excludes never-logged-in users registered recently)."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        days = int(request.query_params.get("days", 90))
        threshold = timezone.now() - timedelta(days=days)
        join_threshold = timezone.now() - timedelta(days=days)

        # Inactive = last_login older than threshold
        # OR never logged in AND joined more than 'days' ago
        users = User.objects.filter(
            Q(last_login__lt=threshold) |
            Q(last_login__isnull=True, date_joined__lt=join_threshold)
        ).exclude(
            is_staff=True  # Exclude admin/staff users
        ).order_by("last_login")[:100]

        data = [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "date_joined": u.date_joined.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "days_inactive": (timezone.now() - u.last_login).days if u.last_login else "Never logged in",
        } for u in users]

        return Response({"inactive_users": data, "count": len(data)})


class AdminSubscriptionLogsView(APIView):
    """View subscription logs with filters, currency conversion, and revenue details."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from django.db.models import Q
        from common.currency import get_usd_to_inr_rate

        # Filters
        tech_filter = request.query_params.get("technology", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        user_filter = request.query_params.get("user", "").strip()
        date_from = request.query_params.get("date_from", "").strip()
        date_to = request.query_params.get("date_to", "").strip()
        display_currency = request.query_params.get("currency", "INR").upper()

        subs = TechnologySubscription.objects.all().select_related(
            "user", "technology"
        ).order_by("-created_at")

        if tech_filter:
            subs = subs.filter(technology__name__icontains=tech_filter)
        if status_filter == "active":
            from django.utils import timezone as tz
            now = tz.now()
            subs = subs.filter(is_active=True).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            )
        elif status_filter == "expired":
            from django.utils import timezone as tz
            now = tz.now()
            subs = subs.filter(Q(is_active=False) | Q(expires_at__lte=now))
        if user_filter:
            subs = subs.filter(
                Q(user__username__icontains=user_filter) |
                Q(user__email__icontains=user_filter)
            )
        if date_from:
            try:
                from datetime import datetime as dt
                subs = subs.filter(created_at__date__gte=dt.strptime(date_from, "%Y-%m-%d").date())
            except ValueError:
                pass
        if date_to:
            try:
                from datetime import datetime as dt
                subs = subs.filter(created_at__date__lte=dt.strptime(date_to, "%Y-%m-%d").date())
            except ValueError:
                pass

        subs = subs[:500]

        # Exchange rate
        exchange_rate = None
        if display_currency == "USD":
            try:
                exchange_rate = float(get_usd_to_inr_rate())
            except Exception:
                exchange_rate = 83.50

        # Build response
        total_inr = 0
        active_count = 0
        data = []
        for sub in subs:
            amount_inr = float(sub.amount)
            from apps.billing.subscription_utils import is_tech_subscription_active
            if is_tech_subscription_active(sub):
                total_inr += amount_inr
                active_count += 1

            if display_currency == "USD" and exchange_rate:
                amt_converted = round(amount_inr / exchange_rate, 2)
                amount_str = f"${amt_converted}"
            else:
                amount_str = f"₹{int(amount_inr)}"

            from apps.billing.subscription_utils import subscription_status_payload
            status = subscription_status_payload(sub)

            data.append({
                "id": str(sub.id),
                "subscription_id": sub.subscription_id,
                "user": {
                    "id": sub.user.id,
                    "username": sub.user.username,
                    "email": sub.user.email,
                    "full_name": sub.user.get_full_name(),
                },
                "technology": sub.technology.name,
                "amount": str(sub.amount),
                "amount_display": amount_str,
                "payment_verified": sub.payment_verified,
                "created_at": sub.created_at.isoformat(),
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                **status,
            })

        total_display = total_inr
        if display_currency == "USD" and exchange_rate:
            total_display = round(total_inr / exchange_rate, 2)

        interview_logs = []
        try:
            from apps.interviews.models import InterviewEntitlement

            ents = InterviewEntitlement.objects.select_related("user", "plan_tier").order_by("-updated_at")
            if user_filter:
                ents = ents.filter(
                    Q(user__username__icontains=user_filter) |
                    Q(user__email__icontains=user_filter)
                )
            for ent in ents[:200]:
                tier = ent.plan_tier
                amount_inr = float(tier.price_inr) if tier else 0
                interview_logs.append({
                    "id": str(ent.id),
                    "subscription_id": f"INT-{ent.user_id}",
                    "product_type": "interview",
                    "user": {
                        "id": ent.user.id,
                        "username": ent.user.username,
                        "email": ent.user.email,
                        "full_name": ent.user.get_full_name(),
                    },
                    "technology": f"Interview — {tier.name if tier else 'Free'}",
                    "plan_code": tier.code if tier else "free",
                    "amount": str(amount_inr),
                    "amount_display": f"₹{int(amount_inr)}" if amount_inr else "—",
                    "payment_verified": ent.is_active and not ent.is_complimentary,
                    "interviews_remaining": ent.interviews_remaining,
                    "admin_granted": ent.is_admin_granted_free or ent.is_complimentary,
                    "created_at": ent.period_start.isoformat() if ent.period_start else ent.updated_at.isoformat(),
                    "expires_at": ent.period_end.isoformat() if ent.period_end else None,
                    "is_active": ent.is_active,
                })
        except Exception:
            pass

        return Response({
            "logs": data,
            "interview_logs": interview_logs,
            "total_revenue": total_display,
            "total_revenue_inr": total_inr,
            "display_currency": display_currency,
            "exchange_rate": exchange_rate,
            "total_count": len(data),
            "active_count": active_count,
            "interview_active_count": sum(1 for l in interview_logs if l.get("is_active")),
        })


class AdminInvoicesView(APIView):
    """Admin: list all payment invoices with filters."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.billing.models import SubscriptionInvoice, PaymentTransaction
        from apps.billing.invoice_service import create_invoice_for_transaction, invoice_list_payload
        from django.db.models import Q

        user_filter = request.query_params.get("user", "").strip()
        qs = SubscriptionInvoice.objects.select_related("user", "payment_transaction").order_by("-created_at")

        if user_filter:
            qs = qs.filter(
                Q(user__email__icontains=user_filter) |
                Q(user__username__icontains=user_filter) |
                Q(invoice_number__icontains=user_filter)
            )

        # Backfill missing invoices from successful payments
        if qs.count() < 50:
            missing = PaymentTransaction.objects.filter(status="success", invoice__isnull=True).select_related(
                "user", "tech_subscription", "tech_subscription__technology", "plan"
            )[:200]
            for tx in missing:
                create_invoice_for_transaction(tx)

        invoices = qs[:500]
        data = []
        for inv in invoices:
            row = invoice_list_payload(inv)
            row["user"] = {
                "id": inv.user_id,
                "username": inv.user.username,
                "email": inv.user.email,
            }
            data.append(row)

        total_inr = sum(float(i.amount) for i in invoices if i.currency == "INR")
        return Response({
            "invoices": data,
            "total_count": len(data),
            "total_revenue_inr": total_inr,
        })


class AdminThreadModerationView(APIView):
    """Moderate community threads — delete inappropriate content."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request, thread_id=None):
        if thread_id:
            return self._get_thread_detail(thread_id)

        threads = Thread.objects.filter(
            is_deleted=False
        ).select_related("author", "technology").order_by("-created_at")[:100]

        data = [{
            "id": str(t.id),
            "title": t.title,
            "body": t.body[:200],
            "author": t.author.username,
            "technology": t.technology.name if t.technology else None,
            "is_pinned": t.is_pinned,
            "is_locked": t.is_locked,
            "reply_count": t.reply_count,
            "upvotes": t.upvotes,
            "created_at": t.created_at.isoformat(),
        } for t in threads]

        return Response({"threads": data})

    def _get_thread_detail(self, thread_id):
        try:
            thread = Thread.objects.select_related("author", "technology").get(
                id=thread_id, is_deleted=False
            )
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=status.HTTP_404_NOT_FOUND)

        replies = Reply.objects.filter(thread=thread, is_deleted=False).select_related(
            "author"
        ).order_by("created_at")

        return Response({
            "id": str(thread.id),
            "title": thread.title,
            "body": thread.body,
            "author": thread.author.username,
            "technology": thread.technology.name if thread.technology else None,
            "is_pinned": thread.is_pinned,
            "is_locked": thread.is_locked,
            "reply_count": thread.reply_count,
            "upvotes": thread.upvotes,
            "created_at": thread.created_at.isoformat(),
            "replies": [
                {
                    "id": str(r.id),
                    "body": r.body,
                    "author": r.author.username,
                    "upvotes": r.upvotes,
                    "created_at": r.created_at.isoformat(),
                }
                for r in replies
            ],
        })

    def post(self, request, thread_id):
        """Admin reply to a thread (works even when locked)."""
        try:
            thread = Thread.objects.get(id=thread_id, is_deleted=False)
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=status.HTTP_404_NOT_FOUND)

        body = (request.data.get("body") or "").strip()
        if not body:
            return Response({"error": "Reply body required"}, status=status.HTTP_400_BAD_REQUEST)

        reply = Reply.objects.create(author=request.user, thread=thread, body=body)
        Thread.objects.filter(id=thread_id).update(reply_count=F("reply_count") + 1)
        logger.info(f"Admin {request.user.username} replied to thread {thread_id}")

        return Response({
            "id": str(reply.id),
            "body": reply.body,
            "author": reply.author.username,
            "created_at": reply.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, thread_id):
        """Soft-delete a thread."""
        try:
            thread = Thread.objects.get(id=thread_id)
            thread.is_deleted = True
            thread.save(update_fields=["is_deleted"])
            logger.info(f"Thread {thread_id} deleted by admin {request.user.username}")
            return Response({"status": "deleted"})
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, thread_id):
        """Pin/lock a thread."""
        try:
            thread = Thread.objects.get(id=thread_id)
            if "is_pinned" in request.data:
                thread.is_pinned = request.data["is_pinned"]
            if "is_locked" in request.data:
                thread.is_locked = request.data["is_locked"]
            thread.save()
            return Response({"status": "updated"})
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=status.HTTP_404_NOT_FOUND)


class AdminJiraTicketsView(APIView):
    """List all user Jira tickets for admin dashboard."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.jira_integration.models import UserScenarioJiraTicket
        from apps.jira_integration.client import JiraClient
        from apps.jira_integration.helpers import is_jira_closed
        from apps.jira_integration.views import _sync_ticket_status

        qs = UserScenarioJiraTicket.objects.filter(
            issue_key__gt=""
        ).select_related("user", "scenario").order_by("-updated_at")

        user_id = request.query_params.get("user_id")
        scenario_id = request.query_params.get("scenario_id")
        if user_id:
            qs = qs.filter(user_id=user_id)
        if scenario_id:
            qs = qs.filter(scenario_id=scenario_id)

        client = JiraClient()
        live_sync = request.query_params.get("sync") == "1" and client.enabled
        tickets = []
        for t in qs[:300]:
            status_name = _sync_ticket_status(t, client) if live_sync else (t.jira_status or "")
            tickets.append({
                "issue_key": t.issue_key,
                "issue_url": t.issue_url,
                "jira_status": status_name,
                "is_closed": is_jira_closed(status_name),
                "run_count": t.run_count,
                "user": {
                    "id": t.user_id,
                    "username": t.user.username,
                    "email": t.user.email,
                },
                "scenario": {
                    "id": t.scenario_id,
                    "slug": t.scenario.slug,
                    "title": t.scenario.title,
                },
                "updated_at": t.updated_at.isoformat(),
                "created_at": t.created_at.isoformat(),
            })

        open_count = sum(1 for t in tickets if not t["is_closed"])
        return Response({
            "tickets": tickets,
            "count": len(tickets),
            "open_count": open_count,
            "closed_count": len(tickets) - open_count,
            "jira_enabled": client.enabled,
            "live_sync": live_sync,
        })


class AdminJiraCreateView(APIView):
    """Create or ensure a Jira ticket for a user+scenario."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        from apps.jira_integration.sync import ensure_scenario_ticket

        user_id = request.data.get("user_id")
        scenario_id = request.data.get("scenario_id")
        if not user_id or not scenario_id:
            return Response(
                {"error": "user_id and scenario_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id)
            scenario = Scenario.objects.get(pk=scenario_id, is_active=True)
        except (User.DoesNotExist, Scenario.DoesNotExist):
            return Response({"error": "User or scenario not found"}, status=status.HTTP_404_NOT_FOUND)

        result = ensure_scenario_ticket(user, scenario)
        if not result.get("jira_enabled"):
            return Response(
                {"error": result.get("jira_error", "Jira integration disabled")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        from apps.jira_integration.models import UserScenarioJiraTicket
        ticket = UserScenarioJiraTicket.objects.get(user=user, scenario=scenario)
        return Response({
            "issue_key": ticket.issue_key,
            "issue_url": ticket.issue_url,
            "jira_status": ticket.jira_status,
            "jira_created": result.get("jira_created", False),
        }, status=status.HTTP_201_CREATED if result.get("jira_created") else status.HTTP_200_OK)


class AdminConfigView(APIView):
    """Get/update platform configuration for admin."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.adminpanel.platform_config import admin_config_payload

        return Response(admin_config_payload())

    def post(self, request):
        from apps.adminpanel.platform_config import get_settings_row, persist_config_snapshot, admin_config_payload

        if request.data.get("reset_defaults"):
            row = get_settings_row()
            row.primary_email = getattr(settings, "PRIMARY_EMAIL", "") or ""
            row.payment_email = getattr(settings, "PAYMENT_EMAIL", "") or ""
            row.support_email = getattr(settings, "SUPPORT_EMAIL", "") or ""
            row.admin_display_currency = "INR"
            row.maintenance_enabled = False
            row.maintenance_message = ""
            row.promo_banners = []
            row.promo_banners_enabled = True
            row.maintenance_banner_enabled = True
            row.theme_colors = {"cyan": "#06b6d4", "purple": "#a855f7", "amber": "#f59e0b", "green": "#22c55e"}
            row.support_bot_enabled = True
            row.support_bot_name = "FixitLab Assistant"
            row.support_bot_welcome_message = ""
            row.support_bot_quick_topics = []
            row.support_bot_custom_faq = []
            row.support_bot_typing_delay_ms = 1200
            row.save()
            persist_config_snapshot(row)
            settings.MAINTENANCE_MODE = False
            cache.delete(AdminOverviewView.CACHE_KEY)
            cache.delete("public_platform_stats")
            return Response({**admin_config_payload(), "reset": True})

        row = get_settings_row()
        for field, key in (
            ("primary_email", "primary_email"),
            ("payment_email", "payment_email"),
            ("support_email", "support_email"),
            ("admin_display_currency", "admin_display_currency"),
        ):
            if key in request.data:
                setattr(row, field, request.data.get(key) or "")
        if "promo_banners" in request.data:
            row.promo_banners = request.data.get("promo_banners") or []
        if "promo_banners_enabled" in request.data:
            row.promo_banners_enabled = bool(request.data.get("promo_banners_enabled"))
        if "maintenance_banner_enabled" in request.data:
            row.maintenance_banner_enabled = bool(request.data.get("maintenance_banner_enabled"))
        if "theme_colors" in request.data:
            row.theme_colors = request.data.get("theme_colors") or {}
        if "changelog" in request.data:
            row.changelog = request.data.get("changelog") or []
        if "support_bot_enabled" in request.data:
            row.support_bot_enabled = bool(request.data.get("support_bot_enabled"))
        if "support_bot_name" in request.data:
            row.support_bot_name = (request.data.get("support_bot_name") or "")[:80]
        if "support_bot_welcome_message" in request.data:
            row.support_bot_welcome_message = request.data.get("support_bot_welcome_message") or ""
        if "support_bot_quick_topics" in request.data:
            row.support_bot_quick_topics = request.data.get("support_bot_quick_topics") or []
        if "support_bot_custom_faq" in request.data:
            row.support_bot_custom_faq = request.data.get("support_bot_custom_faq") or []
        if "support_bot_typing_delay_ms" in request.data:
            try:
                row.support_bot_typing_delay_ms = max(300, min(5000, int(request.data.get("support_bot_typing_delay_ms") or 1200)))
            except (TypeError, ValueError):
                row.support_bot_typing_delay_ms = 1200
        row.save()
        persist_config_snapshot(row)
        cache.delete("public_platform_stats")
        if row.primary_email:
            settings.PRIMARY_EMAIL = row.primary_email
        if row.payment_email:
            settings.PAYMENT_EMAIL = row.payment_email
        if row.support_email:
            settings.SUPPORT_EMAIL = row.support_email
        cache.delete(AdminOverviewView.CACHE_KEY)
        return Response(admin_config_payload())


class AdminUploadView(APIView):
    """Upload banner/promo images (admin) — images only, fixed dimensions per purpose."""
    permission_classes = [IsPlatformAdmin]
    MAX_BYTES = 5 * 1024 * 1024

    PURPOSE_MAP = {
        "platform": "promo_banner",
        "promo": "promo_banner",
        "maintenance": "maintenance_banner",
    }

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"error": "No file uploaded"}, status=400)
        if upload.size > self.MAX_BYTES:
            return Response({"error": "File too large (max 5MB)"}, status=400)

        from common.media_utils import validate_image_upload, image_specs_for_api, public_media_url
        from django.core.files.storage import default_storage

        folder = request.data.get("folder", "platform")
        purpose = request.data.get("purpose") or self.PURPOSE_MAP.get(folder, "promo_banner")
        try:
            width, height = validate_image_upload(upload, purpose)
        except ValueError as exc:
            return Response({"error": str(exc), "spec": image_specs_for_api().get(purpose)}, status=400)

        safe_name = upload.name.replace("..", "").replace("/", "_")[-120:]
        path = default_storage.save(f"{folder}/{safe_name}", upload)
        url = public_media_url(settings.MEDIA_URL + path)
        return Response({"url": url, "path": path, "width": width, "height": height})


# ─── Container Monitoring ─────────────────────────────────────────────

class AdminMonitoringContainersView(APIView):
    """List FixitLab lab + platform Docker containers with health summary."""
    permission_classes = [IsPlatformAdmin]

    SYSTEM_NAME_HINTS = (
        "backend", "frontend", "gateway", "redis", "postgres", "database",
        "rabbitmq", "celery", "certbot", "nginx", "vault", "pgbouncer", "flower",
        "fixitlab_vault", "fixitlab_db", "fixitlab_redis", "fixitlab_rabbitmq",
    )

    def get(self, request):
        try:
            client = DockerProvisioner().client
        except Exception as exc:
            return Response({"error": str(exc), "containers": []}, status=503)

        kind_filter = request.query_params.get("kind", "all")
        containers = []
        seen = set()

        def add_container(c, kind):
            if c.id in seen:
                return
            seen.add(c.id)
            labels = c.labels or {}
            state = c.attrs.get("State", {})
            containers.append({
                "id": c.short_id,
                "full_id": c.id,
                "name": c.name,
                "kind": kind,
                "status": c.status,
                "health": state.get("Health", {}).get("Status") or ("running" if c.status == "running" else c.status),
                "session_id": labels.get("fixitlab.session_id", ""),
                "scenario": labels.get("fixitlab.scenario", ""),
                "user": labels.get("fixitlab.user", ""),
                "host_role": labels.get("fixitlab.host_role", ""),
                "created": c.attrs.get("Created", ""),
                "restart_count": c.attrs.get("RestartCount", 0),
                "exit_code": state.get("ExitCode", 0) if c.status != "running" else None,
                "up_since": state.get("StartedAt", ""),
            })

        for c in client.containers.list(all=True, filters={"label": "fixitlab.session_id"}):
            add_container(c, "lab")

        for c in client.containers.list(all=True):
            name = (c.name or "").lower()
            try:
                image_str = " ".join(c.image.tags or [str(c.image.id)[:12]]).lower()
            except Exception:
                image_str = ""
            is_system = any(h in name for h in self.SYSTEM_NAME_HINTS)
            # Also catch vault by image (hashicorp/vault)
            if not is_system and "vault" in image_str:
                is_system = True
            if is_system:
                add_container(c, "system")

        if kind_filter != "all":
            containers = [x for x in containers if x["kind"] == kind_filter]

        running = sum(1 for x in containers if x["status"] == "running")
        return Response({
            "containers": containers,
            "total": len(containers),
            "running": running,
            "lab_count": sum(1 for x in containers if x["kind"] == "lab"),
            "system_count": sum(1 for x in containers if x["kind"] == "system"),
        })


class AdminMonitoringContainerDetailView(APIView):
    """Container metrics and metadata."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request, container_id):
        try:
            client = DockerProvisioner().client
            container = client.containers.get(container_id)
        except Exception as exc:
            return Response({"error": str(exc)}, status=404)

        stats = None
        try:
            raw = container.stats(stream=False)
            cpu = raw.get("cpu_stats", {})
            mem = raw.get("memory_stats", {})
            usage = mem.get("usage", 0)
            limit = mem.get("limit", 1) or 1
            stats = {
                "cpu_usage_percent": round(
                    (cpu.get("cpu_usage", {}).get("total_usage", 0) or 0) / 1e9, 2
                ),
                "memory_usage_mb": round(usage / (1024 * 1024), 1),
                "memory_limit_mb": round(limit / (1024 * 1024), 1),
                "memory_percent": round(100 * usage / limit, 1),
            }
        except Exception as exc:
            stats = {"error": str(exc)}

        return Response({
            "id": container.short_id,
            "full_id": container.id,
            "name": container.name,
            "status": container.status,
            "labels": container.labels,
            "attrs": {
                "image": container.image.tags,
                "created": container.attrs.get("Created"),
                "started": container.attrs.get("State", {}).get("StartedAt"),
            },
            "stats": stats,
        })


class AdminMonitoringContainerLogsView(APIView):
    """Tail container logs with optional filters."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request, container_id):
        tail = min(int(request.query_params.get("tail", 200)), 2000)
        since = request.query_params.get("since", "")
        log_type = request.query_params.get("type", "all")
        search = request.query_params.get("q", "").strip().lower()
        live = request.query_params.get("live") == "1"

        try:
            client = DockerProvisioner().client
            container = client.containers.get(container_id)
            kwargs = {"timestamps": True, "tail": tail}
            if since:
                kwargs["since"] = since
            if log_type == "stderr":
                kwargs["stderr"] = True
                kwargs["stdout"] = False
            elif log_type == "stdout":
                kwargs["stdout"] = True
                kwargs["stderr"] = False
            raw = container.logs(**kwargs)
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            lines = text.splitlines()
            if search:
                lines = [ln for ln in lines if search in ln.lower()]
            return Response({
                "container_id": container.short_id,
                "lines": lines,
                "live": live,
                "tail": tail,
                "type": log_type,
            })
        except Exception as exc:
            return Response({"error": str(exc), "lines": []}, status=404)


# ─── Coupon Management ────────────────────────────────────────────────

class AdminCouponsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.billing.models import CouponCode

        coupons = CouponCode.objects.all().order_by("-created_at")
        data = [
            {
                "id": c.id,
                "code": c.code,
                "description": c.description,
                "discount_type": c.discount_type,
                "discount_value": str(c.discount_value),
                "is_active": c.is_active,
                "max_uses": c.max_uses,
                "used_count": c.used_count,
                "valid_from": c.valid_from.isoformat() if c.valid_from else None,
                "valid_until": c.valid_until.isoformat() if c.valid_until else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in coupons
        ]
        return Response({"coupons": data})

    def post(self, request):
        from apps.billing.models import CouponCode
        from apps.billing.coupon_service import normalize_coupon_code

        code = normalize_coupon_code(request.data.get("code", ""))
        if not code:
            return Response({"error": "code is required"}, status=400)
        if CouponCode.objects.filter(code__iexact=code).exists():
            return Response({"error": "Coupon code already exists"}, status=400)

        coupon = CouponCode.objects.create(
            code=code,
            description=request.data.get("description", ""),
            discount_type=request.data.get("discount_type", "percent"),
            discount_value=request.data.get("discount_value", 0),
            is_active=request.data.get("is_active", True),
            max_uses=request.data.get("max_uses") or None,
            valid_from=request.data.get("valid_from") or None,
            valid_until=request.data.get("valid_until") or None,
        )
        return Response({"id": coupon.id, "code": coupon.code}, status=201)


class AdminCouponDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, pk):
        from apps.billing.models import CouponCode

        try:
            coupon = CouponCode.objects.get(pk=pk)
        except CouponCode.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        for field in ("description", "discount_type", "discount_value", "is_active", "max_uses", "valid_from", "valid_until"):
            if field in request.data:
                setattr(coupon, field, request.data[field])
        coupon.save()
        return Response({"message": "Updated"})

    def delete(self, request, pk):
        from apps.billing.models import CouponCode

        CouponCode.objects.filter(pk=pk).delete()
        return Response({"message": "Deleted"})


# ─── Organization / Team Management ───────────────────────────────────

class AdminOrganizationsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.accounts.models import Organization, OrganizationMember, OrganizationTechnologyGrant
        from apps.question_bank.models import Technology

        orgs = Organization.objects.select_related("owner").order_by("-created_at")
        data = []
        for org in orgs:
            grants = OrganizationTechnologyGrant.objects.filter(organization=org, is_active=True).select_related("technology")
            members = list(
                OrganizationMember.objects.filter(organization=org)
                .select_related("user")
                .values("user__username", "user__email", "role")
            )
            data.append({
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "owner": org.owner.username,
                "owner_email": org.owner.email,
                "seat_limit": org.seat_limit,
                "member_count": org.members.count(),
                "members": members,
                "is_active": org.is_active,
                "billing_email": org.billing_email,
                "technologies": [g.technology.name for g in grants if g.is_valid_now()],
                "created_at": org.created_at.isoformat(),
            })
        return Response({"organizations": data, "technologies": list(Technology.objects.filter(is_active=True).values("id", "name"))})

    def post(self, request):
        from django.contrib.auth import get_user_model
        from django.utils.text import slugify
        from apps.accounts.models import Organization, OrganizationMember, OrganizationTechnologyGrant
        from apps.billing.subscription_utils import subscription_expires_at
        from apps.question_bank.models import Technology

        User = get_user_model()
        name = (request.data.get("name") or "").strip()
        owner_id = request.data.get("owner_id")
        seat_limit = int(request.data.get("seat_limit") or 10)
        tech_ids = request.data.get("technology_ids") or []

        if not name or not owner_id:
            return Response({"error": "name and owner_id are required"}, status=400)
        try:
            owner = User.objects.get(pk=owner_id)
        except User.DoesNotExist:
            return Response({"error": "Owner user not found"}, status=404)

        base_slug = slugify(name)[:60] or "team"
        slug = base_slug
        n = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{n}"
            n += 1

        org = Organization.objects.create(
            name=name,
            slug=slug,
            owner=owner,
            seat_limit=seat_limit,
            billing_email=request.data.get("billing_email") or owner.email,
            notes=request.data.get("notes", ""),
        )
        OrganizationMember.objects.create(organization=org, user=owner, role="owner")
        expires = subscription_expires_at()
        for tid in tech_ids:
            try:
                tech = Technology.objects.get(pk=tid, is_active=True)
                OrganizationTechnologyGrant.objects.create(
                    organization=org,
                    technology=tech,
                    expires_at=expires,
                    is_active=True,
                )
            except Technology.DoesNotExist:
                continue

        return Response({"id": str(org.id), "slug": org.slug}, status=201)


class AdminOrganizationDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, org_id):
        """Add member to organization by email."""
        from django.contrib.auth import get_user_model
        from apps.accounts.models import Organization, OrganizationMember

        User = get_user_model()
        try:
            org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found"}, status=404)

        if org.members.count() >= org.seat_limit:
            return Response({"error": "Seat limit reached"}, status=400)

        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"error": "email is required"}, status=400)
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User not found — they must register first"}, status=404)
        if OrganizationMember.objects.filter(organization=org, user=user).exists():
            return Response({"error": "User is already a member"}, status=409)

        role = request.data.get("role", "member")
        OrganizationMember.objects.create(organization=org, user=user, role=role, invited_email=email)
        return Response({"message": f"Added {user.username} to {org.name}"})

    def patch(self, request, org_id):
        """Update org settings: webhook_url, webhook_secret, logo_url, primary_color, custom_domain, seat_limit."""
        from apps.accounts.models import Organization
        try:
            org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found"}, status=404)

        allowed = ("webhook_url", "webhook_secret", "logo_url", "primary_color", "custom_domain", "seat_limit", "notes", "billing_email")
        update_fields = []
        for field in allowed:
            if field in request.data:
                setattr(org, field, request.data[field])
                update_fields.append(field)

        if update_fields:
            org.save(update_fields=update_fields)

        return Response({"message": "Organization updated", "updated": update_fields})

    def delete(self, request, org_id):
        from apps.accounts.models import Organization
        Organization.objects.filter(pk=org_id).update(is_active=False)
        return Response({"message": "Organization deactivated"})


# ─── Security Metrics ─────────────────────────────────────────────────

class AdminSecurityMetricsView(APIView):
    """Aggregate security-related audit events for admin dashboard."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from datetime import timedelta
        from django.db.models import Count
        from apps.audit.models import AuditLog
        from apps.billing.models import PaymentTransaction

        days = int(request.query_params.get("days", 7))
        since = timezone.now() - timedelta(days=days)

        login_failed = AuditLog.objects.filter(action="login_failed", created_at__gte=since).count()
        login_success = AuditLog.objects.filter(action="login", created_at__gte=since).count()
        lab_resets = AuditLog.objects.filter(action="lab_reset", created_at__gte=since).count()
        payment_failed = AuditLog.objects.filter(action="payment_failed", created_at__gte=since).count()
        security_alerts = AuditLog.objects.filter(action="security_alert", created_at__gte=since).count()

        failed_payments = PaymentTransaction.objects.filter(status="failed", created_at__gte=since).count()

        # Brute-force heuristic: IPs with 5+ failed logins in window
        from django.db.models.functions import TruncDate

        suspicious_ips = list(
            AuditLog.objects.filter(action="login_failed", created_at__gte=since, ip_address__isnull=False)
            .values("ip_address")
            .annotate(count=Count("id"))
            .filter(count__gte=5)
            .order_by("-count")[:20]
        )

        recent_events = list(
            AuditLog.objects.filter(
                action__in=["login_failed", "payment_failed", "security_alert", "lab_reset"],
                created_at__gte=since,
            )
            .select_related("user")
            .order_by("-created_at")[:50]
            .values("action", "resource", "ip_address", "metadata", "created_at", "user__username")
        )

        email_stats = {}
        email_failed_count = 0
        try:
            from apps.notifications.models import EmailLog
            from datetime import timedelta as td

            email_since = timezone.now() - td(days=days)
            email_stats = {
                "sent": EmailLog.objects.filter(status="sent", created_at__gte=email_since).count(),
                "failed": EmailLog.objects.filter(status="failed", created_at__gte=email_since).count(),
                "gmail_configured": __import__(
                    "apps.notifications.gmail_api", fromlist=["is_gmail_api_configured"]
                ).is_gmail_api_configured(),
            }
            ok, msg = __import__(
                "apps.notifications.gmail_api", fromlist=["verify_gmail_credentials"]
            ).verify_gmail_credentials()
            email_stats["gmail_ok"] = ok
            email_stats["gmail_message"] = msg[:200] if msg else ""
            from apps.notifications.email_health import email_delivery_health

            health = email_delivery_health(window_minutes=15)
            email_stats["delivery_health"] = health
            if health.get("alert"):
                security_alerts += 1
            email_failed_count = email_stats.get("failed", 0)
        except Exception:
            email_stats = {"sent": 0, "failed": 0, "gmail_configured": False, "gmail_ok": False}
            email_failed_count = 0

        otp_failed = AuditLog.objects.filter(action="otp_failed", created_at__gte=since).count()

        detail = request.query_params.get("detail")
        if detail:
            if detail == "email_failed":
                from apps.notifications.models import EmailLog
                rows = list(
                    EmailLog.objects.filter(status="failed", created_at__gte=since)
                    .order_by("-created_at")[:100]
                    .values("id", "to_email", "subject", "error", "created_at", "status", "template")
                )
                return Response({"detail": "email_failed", "rows": rows})
            action_map = {
                "login_failed": "login_failed",
                "login_success": "login",
                "otp_failed": "otp_failed",
                "payment_failed": "payment_failed",
                "lab_resets": "lab_reset",
                "security_alerts": "security_alert",
                "email_failed": "email_failed",
                "rate_limit_hits": "security_alert",
            }
            action = action_map.get(detail)
            if action:
                rows = list(
                    AuditLog.objects.filter(action=action, created_at__gte=since)
                    .select_related("user")
                    .order_by("-created_at")[:100]
                    .values("id", "action", "resource", "ip_address", "metadata", "created_at", "user__username", "user__email")
                )
                return Response({"detail": detail, "rows": rows})

        from apps.adminpanel.security_helpers import get_blocked_ips, get_blocked_countries

        rate_limit_hits = AuditLog.objects.filter(
            action="security_alert", created_at__gte=since,
            metadata__contains="rate_limit",
        ).count()

        return Response({
            "period_days": days,
            "login_failed": login_failed,
            "login_success": login_success,
            "lab_resets": lab_resets,
            "payment_failed": payment_failed + failed_payments,
            "security_alerts": security_alerts,
            "otp_failed": otp_failed,
            "email_failed": email_failed_count,
            "rate_limit_hits": rate_limit_hits,
            "email_stats": email_stats,
            "suspicious_ips": suspicious_ips,
            "recent_events": recent_events,
            "blocked_ips": get_blocked_ips(),
            "blocked_countries": get_blocked_countries(),
        })


class AdminSecurityActionView(APIView):
    """Block/unblock IPs or countries from admin Security panel."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        from apps.adminpanel.security_helpers import (
            block_ip, unblock_ip, block_country, unblock_country,
            get_blocked_ips, get_blocked_countries,
        )
        action = request.data.get("action", "")
        ip = request.data.get("ip", "")
        country = request.data.get("country", "")

        if action == "block_ip":
            block_ip(ip)
        elif action == "unblock_ip":
            unblock_ip(ip)
        elif action == "block_country":
            block_country(country)
        elif action == "unblock_country":
            unblock_country(country)
        elif action == "block_user":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            uid = request.data.get("user_id")
            email = (request.data.get("email") or "").strip().lower()
            qs = User.objects.all()
            if uid:
                qs = qs.filter(pk=uid)
            elif email:
                qs = qs.filter(email__iexact=email)
            else:
                return Response({"error": "user_id or email required"}, status=400)
            updated = qs.update(is_active=False)
            if not updated:
                return Response({"error": "User not found"}, status=404)
        elif action == "unblock_user":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            uid = request.data.get("user_id")
            email = (request.data.get("email") or "").strip().lower()
            qs = User.objects.all()
            if uid:
                qs = qs.filter(pk=uid)
            elif email:
                qs = qs.filter(email__iexact=email)
            else:
                return Response({"error": "user_id or email required"}, status=400)
            updated = qs.update(is_active=True)
            if not updated:
                return Response({"error": "User not found"}, status=404)
        elif action == "clear_email_failures":
            from apps.notifications.models import EmailLog
            deleted, _ = EmailLog.objects.filter(status="failed").delete()
            return Response({"cleared": deleted, "blocked_ips": get_blocked_ips(), "blocked_countries": get_blocked_countries()})
        else:
            return Response({"error": "Unknown action"}, status=400)

        return Response({
            "blocked_ips": get_blocked_ips(),
            "blocked_countries": get_blocked_countries(),
        })


class AdminTestEmailView(APIView):
    """Send a test email to verify Gmail/SMTP delivery."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        from apps.notifications.email_dispatch import send_email_now

        to_email = (request.data.get("to_email") or request.user.email or "").strip()
        if not to_email:
            return Response({"error": "to_email is required"}, status=status.HTTP_400_BAD_REQUEST)

        ok = send_email_now(
            "FixitLab test email",
            to_email,
            "emails/welcome.html",
            {"username": request.user.get_full_name() or request.user.username},
        )
        if ok:
            return Response({"sent": True, "to_email": to_email})
        return Response({"sent": False, "error": "Email delivery failed — check Gmail OAuth or SMTP settings."}, status=502)


class AdminSyncScenariosView(APIView):
    """Reload scenario YAML/check.sh from repo into the database."""
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        from io import StringIO

        from django.core.cache import cache
        from django.core.management import call_command

        buf = StringIO()
        try:
            call_command("sync_scenarios", stdout=buf)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        cache.delete("platform_stats")
        cache.delete("public_platform_stats")
        output = buf.getvalue()
        return Response({
            "synced": True,
            "message": "Scenarios synced from repository",
            "output_tail": output[-4000:] if output else "",
        })


class AdminBlogPostsView(APIView):
    """CRUD list/create for blog posts."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from apps.adminpanel.models import BlogPost

        posts = BlogPost.objects.all().order_by("-published_at", "-created_at")
        return Response([
            {
                "id": str(p.id),
                "slug": p.slug,
                "title": p.title,
                "excerpt": p.excerpt,
                "category": p.category,
                "author_name": p.author_name,
                "read_minutes": p.read_minutes,
                "is_published": p.is_published,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in posts
        ])

    def post(self, request):
        from apps.adminpanel.models import BlogPost
        from django.utils.text import slugify

        title = (request.data.get("title") or "").strip()
        if not title:
            return Response({"error": "title is required"}, status=status.HTTP_400_BAD_REQUEST)
        slug = (request.data.get("slug") or slugify(title))[:120]
        post = BlogPost.objects.create(
            slug=slug,
            title=title,
            excerpt=request.data.get("excerpt") or "",
            content=request.data.get("content") or "",
            author_name=request.data.get("author_name") or "FixitLab Team",
            category=request.data.get("category") or "Product",
            read_minutes=int(request.data.get("read_minutes") or 5),
            is_published=bool(request.data.get("is_published", True)),
            published_at=timezone.now() if request.data.get("is_published", True) else None,
        )
        return Response({"id": str(post.id), "slug": post.slug}, status=status.HTTP_201_CREATED)


class AdminBlogPostDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, post_id):
        from apps.adminpanel.models import BlogPost

        try:
            post = BlogPost.objects.get(pk=post_id)
        except BlogPost.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        for field in ("title", "excerpt", "content", "author_name", "category", "slug"):
            if field in request.data:
                setattr(post, field, request.data[field])
        if "read_minutes" in request.data:
            post.read_minutes = int(request.data["read_minutes"])
        if "is_published" in request.data:
            post.is_published = bool(request.data["is_published"])
            if post.is_published and not post.published_at:
                post.published_at = timezone.now()
        post.save()
        return Response({"updated": True, "slug": post.slug})

    def delete(self, request, post_id):
        from apps.adminpanel.models import BlogPost

        deleted, _ = BlogPost.objects.filter(pk=post_id).delete()
        if not deleted:
            return Response({"error": "Not found"}, status=404)
        return Response({"deleted": True})


class AdminCertificatesView(APIView):
    """List user technology certificates, interview certificates, and achievements."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from django.utils import timezone

        from apps.billing.models import UserCertificate
        from apps.interviews.models import InterviewCertificate
        from apps.progress.models import UserAchievement

        now = timezone.now()
        email_q = request.query_params.get("email", "").strip()

        tech_qs = UserCertificate.objects.select_related("user", "technology").order_by("-issued_at")
        interview_qs = InterviewCertificate.objects.select_related("user").order_by("-issued_at")
        achievement_qs = UserAchievement.objects.select_related("user").order_by("-earned_at")

        if email_q:
            tech_qs = tech_qs.filter(user__email__icontains=email_q)
            interview_qs = interview_qs.filter(user__email__icontains=email_q)
            achievement_qs = achievement_qs.filter(user__email__icontains=email_q)

        tech_certs = [
            {
                "type": "technology",
                "certificate_id": c.certificate_id,
                "user_email": c.user.email,
                "user_id": c.user_id,
                "technology": c.technology.name,
                "technology_slug": c.technology.slug,
                "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "is_expired": bool(c.expires_at and c.expires_at <= now),
            }
            for c in tech_qs[:500]
        ]

        interview_certs = [
            {
                "type": "interview",
                "certificate_id": c.certificate_id,
                "user_email": c.user.email,
                "user_id": c.user_id,
                "technology": c.technology_name or "Interview Studio",
                "level": c.level,
                "rounds_cleared": c.rounds_cleared,
                "overall_score": c.overall_score,
                "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "is_expired": bool(c.expires_at and c.expires_at <= now),
            }
            for c in interview_qs[:500]
        ]

        achievements = [
            {
                "user_email": a.user.email,
                "user_id": a.user_id,
                "achievement": a.get_achievement_display(),
                "achievement_code": a.achievement,
                "earned_at": a.earned_at.isoformat() if a.earned_at else None,
            }
            for a in achievement_qs[:500]
        ]

        return Response({
            "technology_certificates": tech_certs,
            "interview_certificates": interview_certs,
            "achievements": achievements,
            "counts": {
                "technology": len(tech_certs),
                "interview": len(interview_certs),
                "achievements": len(achievements),
            },
        })


# ─── Platform Environment & Vault Sync ───────────────────────────────────────

_MANAGED_ENV_VARS = [
    {
        "key": "DJANGO_SECRET_KEY",
        "label": "Django Secret Key",
        "category": "security",
        "rotation_days": 365,
        "description": "Signs sessions and CSRF tokens.",
    },
    {
        "key": "POSTGRES_PASSWORD",
        "label": "Database Password",
        "category": "database",
        "rotation_days": 90,
        "description": "PostgreSQL connection password.",
    },
    {
        "key": "REDIS_PASSWORD",
        "label": "Redis Password",
        "category": "cache",
        "rotation_days": 90,
        "description": "Redis auth password (cache + channels).",
    },
    {
        "key": "STRIPE_SECRET_KEY",
        "label": "Stripe Secret Key",
        "category": "payments",
        "rotation_days": 365,
        "description": "Stripe payments secret key.",
    },
    {
        "key": "RAZORPAY_KEY_SECRET",
        "label": "Razorpay Key Secret",
        "category": "payments",
        "rotation_days": 365,
        "description": "Razorpay payments secret.",
    },
    {
        "key": "SMTP_PASSWORD",
        "label": "SMTP Password",
        "category": "email",
        "rotation_days": 365,
        "description": "Email server password.",
    },
    {
        "key": "ANTHROPIC_API_KEY",
        "label": "Anthropic API Key",
        "category": "ai",
        "rotation_days": 365,
        "description": "Claude AI API key.",
    },
    {
        "key": "OPENAI_API_KEY",
        "label": "OpenAI API Key",
        "category": "ai",
        "rotation_days": 365,
        "description": "OpenAI API key (if used).",
    },
]

_SUSPECT_VALUE_PATTERNS = (
    "change-me", "changeme", "secret", "password", "test", "dev-", "local-",
    "example", "placeholder", "replace-this", "your-key",
)


def _mask_secret(value: str) -> str:
    """Show last 4 characters only."""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def _is_suspect(value: str) -> bool:
    v = (value or "").lower()
    if len(v) < 16:
        return True
    return any(p in v for p in _SUSPECT_VALUE_PATTERNS)


def _vault_secret_metadata():
    """Return (secrets_dict, created_time_iso | None) from Vault KV, or ({}, None)."""
    vault_enabled = os.environ.get("VAULT_ENABLED", "").lower() in ("1", "true", "yes", "on")
    if not vault_enabled:
        return {}, None
    try:
        import hvac
        role_id = os.environ.get("VAULT_ROLE_ID", "").strip()
        secret_id = os.environ.get("VAULT_SECRET_ID", "").strip()
        vault_addr = os.environ.get("VAULT_ADDR", "http://vault:8200")
        if "127.0.0.1" in vault_addr and os.path.exists("/.dockerenv"):
            vault_addr = "http://vault:8200"
        kv_path = os.environ.get("VAULT_KV_PATH", "secret/fixitlab/config")
        client = hvac.Client(url=vault_addr, timeout=5)
        client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        parts = kv_path.split("/", 1)
        mount = parts[0] if len(parts) > 1 else "secret"
        path = parts[1] if len(parts) > 1 else kv_path
        resp = client.secrets.kv.v2.read_secret_version(
            path=path, mount_point=mount, raise_on_deleted_version=True
        )
        data = resp["data"]
        secrets = data.get("data", {})
        created_time = data.get("metadata", {}).get("created_time")
        return secrets, created_time
    except Exception:
        return {}, None


def _vault_write_secrets(updates: dict) -> bool:
    """Write updated secrets dict to Vault KV. Returns True on success."""
    vault_enabled = os.environ.get("VAULT_ENABLED", "").lower() in ("1", "true", "yes", "on")
    if not vault_enabled:
        return False
    try:
        import hvac
        role_id = os.environ.get("VAULT_ROLE_ID", "").strip()
        secret_id = os.environ.get("VAULT_SECRET_ID", "").strip()
        vault_addr = os.environ.get("VAULT_ADDR", "http://vault:8200")
        if "127.0.0.1" in vault_addr and os.path.exists("/.dockerenv"):
            vault_addr = "http://vault:8200"
        kv_path = os.environ.get("VAULT_KV_PATH", "secret/fixitlab/config")
        client = hvac.Client(url=vault_addr, timeout=5)
        client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        parts = kv_path.split("/", 1)
        mount = parts[0] if len(parts) > 1 else "secret"
        path = parts[1] if len(parts) > 1 else kv_path
        # Read current state, merge updates, write back
        try:
            resp = client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=mount, raise_on_deleted_version=True
            )
            current = resp["data"]["data"]
        except Exception:
            current = {}
        merged = {**current, **updates}
        client.secrets.kv.v2.create_or_update_secret(
            path=path, mount_point=mount, secret=merged
        )
        return True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Vault write failed: %s", exc)
        return False


class AdminEnvSecretsView(APIView):
    """Read/update platform environment secrets with Vault sync."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        vault_secrets, vault_created_time = _vault_secret_metadata()
        vault_enabled = bool(os.environ.get("VAULT_ENABLED", "").lower() in ("1", "true", "yes", "on"))

        age_days = None
        if vault_created_time:
            try:
                from datetime import datetime, timezone as dt_timezone
                created = datetime.fromisoformat(vault_created_time.rstrip("Z")).replace(tzinfo=dt_timezone.utc)
                age_days = (timezone.now() - created).days
            except Exception:
                pass

        items = []
        for spec in _MANAGED_ENV_VARS:
            key = spec["key"]
            # Prefer Vault value if available; fall back to os.environ
            value = vault_secrets.get(key) or os.environ.get(key, "")
            is_set = bool(value.strip())
            masked = _mask_secret(value) if is_set else ""
            suspect = _is_suspect(value)
            rotation_days = spec["rotation_days"]
            over_age = age_days is not None and age_days > rotation_days
            needs_rotation = not is_set or suspect or over_age
            reasons = []
            if not is_set:
                reasons.append("Not configured")
            if suspect:
                reasons.append("Weak or default value detected")
            if over_age:
                reasons.append(f"Last updated {age_days}d ago (recommend every {rotation_days}d)")
            items.append({
                "key": key,
                "label": spec["label"],
                "category": spec["category"],
                "description": spec["description"],
                "is_set": is_set,
                "masked": masked,
                "needs_rotation": needs_rotation,
                "rotation_reason": "; ".join(reasons) if reasons else None,
                "rotation_days": rotation_days,
            })

        return Response({
            "vault_enabled": vault_enabled,
            "vault_secret_age_days": age_days,
            "vault_last_updated": vault_created_time,
            "secrets": items,
        })

    def post(self, request):
        """Sync updated secret values to Vault and apply to running process."""
        updates = request.data.get("updates", {})
        if not isinstance(updates, dict) or not updates:
            return Response({"error": "updates dict required"}, status=400)

        # Validate keys — only allow managed vars
        allowed = {s["key"] for s in _MANAGED_ENV_VARS}
        invalid = [k for k in updates if k not in allowed]
        if invalid:
            return Response({"error": f"Unknown keys: {invalid}"}, status=400)

        # Strip empty values — don't overwrite with blanks
        clean = {k: v.strip() for k, v in updates.items() if v and v.strip()}
        if not clean:
            return Response({"error": "No non-empty values provided"}, status=400)

        vault_ok = _vault_write_secrets(clean)

        # Apply to running process immediately (best-effort)
        for k, v in clean.items():
            os.environ[k] = v
        # Update Django settings for values it reads from env
        for k, v in clean.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
        # Clear all caches so components re-read settings
        try:
            cache.clear()
        except Exception:
            pass

        import logging
        logging.getLogger(__name__).info(
            "Env secrets updated by %s: %s (vault_ok=%s)",
            request.user.email, list(clean.keys()), vault_ok,
        )

        return Response({
            "synced_keys": list(clean.keys()),
            "vault_updated": vault_ok,
            "applied_to_process": True,
            "note": "Changes applied immediately. Workers will use new values on next startup." if not vault_ok else "Changes saved to Vault and applied to all running workers.",
        })
