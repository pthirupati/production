"""Certification-track API.

Public reads (list / detail / verify) are ``AllowAny`` + per-IP throttled and
degrade gracefully (empty payload / 404, never a 500 that blanks the page),
mirroring ``apps.tutorials``. Exam actions are owner-scoped.

Per-objective progress and exam grading read ``UserScenarioProgress`` — the
existing single source of truth for scenario completion. For the *timed mock
exam*, only completions recorded DURING the exam window count, so prior lab
completions can't be cashed in for an exam pass.
"""

import logging
import random
from uuid import uuid4

from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.adminpanel.permissions import IsPlatformAdmin
from apps.progress.models import UserScenarioProgress

from common.throttles import StrictAnonRateThrottle
from .models import (
    CertEarnedCertificate,
    CertificationTrack,
    ExamAttempt,
)
from .serializers import (
    AdminTrackSerializer,
    CertificateSerializer,
    TrackListSerializer,
)
from .services.access import effective_cert_prices, user_has_cert_track_access

logger = logging.getLogger(__name__)

# How many scenarios per objective to sample into a timed mock exam.
EXAM_SCENARIOS_PER_OBJECTIVE = 2


def _completed_scenario_ids(user, scenario_ids, since=None):
    """Scenario ids the user has completed (optionally only since a datetime)."""
    if not user or not user.is_authenticated or not scenario_ids:
        return set()
    qs = UserScenarioProgress.objects.filter(
        user=user, completed=True, scenario_id__in=scenario_ids
    )
    if since is not None:
        qs = qs.filter(completed_at__gte=since)
    return set(qs.values_list("scenario_id", flat=True))


def _track_objectives_payload(track, user):
    """Build the per-objective progress payload for a track and (optional) user."""
    objectives = list(
        track.objectives.prefetch_related("track_scenarios__scenario").all()
    )
    all_ids = [
        ts.scenario_id
        for obj in objectives
        for ts in obj.track_scenarios.all()
    ]
    completed_ids = _completed_scenario_ids(user, all_ids)

    obj_payloads = []
    weighted_sum = 0
    weight_total = 0
    for obj in objectives:
        scenarios = []
        completed = 0
        for ts in obj.track_scenarios.all():
            sc = ts.scenario
            is_done = sc.id in completed_ids
            if is_done:
                completed += 1
            scenarios.append(
                {
                    "slug": sc.slug,
                    "title": sc.title,
                    "difficulty": sc.difficulty,
                    "completed": is_done,
                    # Flag so the UI can render these in a dedicated
                    # "Certification scenarios" group, visually separated from
                    # the lab's normal technology listing (the same lab can also
                    # appear under its regular technology — this just marks the
                    # certification context).
                    "is_certification": True,
                    "in_exam_pool": ts.in_exam_pool,
                }
            )
        total = len(scenarios)
        percent = round(100 * completed / total) if total else 0
        weight = obj.weight or 1
        weighted_sum += percent * weight
        weight_total += weight
        obj_payloads.append(
            {
                "code": obj.code,
                "title": obj.title,
                "description": obj.description,
                "weight": weight,
                "order": obj.order,
                "total_scenarios": total,
                "completed_scenarios": completed,
                "percent": percent,
                "scenarios": scenarios,
            }
        )

    overall = round(weighted_sum / weight_total) if weight_total else 0
    return obj_payloads, overall


class TrackListView(APIView):
    """GET /api/certifications/ — active certification tracks."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        try:
            tracks = list(
                CertificationTrack.objects.filter(is_active=True)
                .annotate(
                    objective_count=Count("objectives", distinct=True),
                    scenario_count=Count(
                        "objectives__track_scenarios__scenario", distinct=True
                    ),
                )
                .order_by("order", "name")
            )
        except Exception:
            logger.exception("TrackListView failed — returning empty payload")
            return Response({"tracks": []})
        return Response({"tracks": TrackListSerializer(tracks, many=True).data})


class MyCertDashboardView(APIView):
    """GET /api/certifications/dashboard/ — learner panel: progress + active exams."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tracks = (
            CertificationTrack.objects.filter(is_active=True)
            .select_related("technology")
            .order_by("order", "name")
        )
        rows = []
        for track in tracks:
            objectives, overall = _track_objectives_payload(track, request.user)
            attempt = (
                ExamAttempt.objects.filter(
                    user=request.user, track=track, status="in_progress"
                )
                .order_by("-started_at")
                .first()
            )
            active = None
            if attempt and not attempt.is_expired:
                remaining = int((attempt.expires_at - timezone.now()).total_seconds())
                active = {
                    "id": str(attempt.id),
                    "seconds_remaining": max(0, remaining),
                    "scenario_count": len(attempt.results.get("scenarios", [])),
                }
            cert = (
                CertEarnedCertificate.objects.filter(user=request.user, track=track)
                .order_by("-issued_at")
                .first()
            )
            pricing = effective_cert_prices(track)
            rows.append(
                {
                    "slug": track.slug,
                    "code": track.code,
                    "name": track.name,
                    "vendor": track.vendor,
                    "overall_percent": overall,
                    "passing_score": track.passing_score,
                    "exam_duration_minutes": track.exam_duration_minutes,
                    "is_free": track.is_free,
                    "price": track.price,
                    "addon_price": track.addon_price,
                    **pricing,
                    "has_track_access": user_has_cert_track_access(request.user, track),
                    "active_exam": active,
                    "earned_certificate": (
                        {"certificate_id": cert.certificate_id, "issued_at": cert.issued_at}
                        if cert
                        else None
                    ),
                    "objective_count": len(objectives),
                }
            )
        return Response({"tracks": rows})


class TrackDetailView(APIView):
    """GET /api/certifications/<slug>/ — track + objectives + per-user progress."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request, slug):
        try:
            track = CertificationTrack.objects.get(slug=slug, is_active=True)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Track not found"}, status=404)
        except Exception:
            logger.exception("TrackDetailView failed for slug=%s", slug)
            return Response({"error": "Track not found"}, status=404)

        user = request.user if request.user.is_authenticated else None
        objectives, overall = _track_objectives_payload(track, user)

        active_attempt = None
        earned = None
        if user:
            attempt = (
                ExamAttempt.objects.filter(user=user, track=track, status="in_progress")
                .order_by("-started_at")
                .first()
            )
            if attempt and not attempt.is_expired:
                active_attempt = {
                    "id": str(attempt.id),
                    "expires_at": attempt.expires_at,
                }
            cert = (
                CertEarnedCertificate.objects.filter(user=user, track=track)
                .order_by("-issued_at")
                .first()
            )
            if cert:
                earned = {"certificate_id": cert.certificate_id, "issued_at": cert.issued_at}

        pricing = effective_cert_prices(track)
        has_access = user_has_cert_track_access(user, track) if user else track.is_free

        return Response(
            {
                "slug": track.slug,
                "code": track.code,
                "name": track.name,
                "vendor": track.vendor,
                "description": track.description,
                "exam_duration_minutes": track.exam_duration_minutes,
                "passing_score": track.passing_score,
                "price": track.price,
                "addon_price": track.addon_price,
                "is_free": track.is_free,
                "technology_slug": track.technology.slug if track.technology_id else None,
                "technology_name": track.technology.name if track.technology_id else None,
                **pricing,
                "has_track_access": has_access,
                "maintenance_enabled": track.maintenance_enabled,
                "maintenance_message": track.maintenance_message,
                "overall_percent": overall,
                # The track's scenarios are a DISTINCT, certification-scoped
                # group: every entry under `objectives[].scenarios` is flagged
                # is_certification=True so the UI renders them in their own
                # "Certification scenarios" section, separate from the same
                # labs' normal technology listing.
                "scenario_group": "certification",
                "objectives": objectives,
                "active_attempt": active_attempt,
                "earned_certificate": earned,
            }
        )


class ExamStartView(APIView):
    """POST /api/certifications/<slug>/exam/start/ — begin a timed mock exam."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            track = CertificationTrack.objects.get(slug=slug, is_active=True)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Track not found"}, status=404)

        if track.maintenance_enabled:
            return Response(
                {"error": track.maintenance_message or "This certification track is under maintenance."},
                status=503,
            )

        if not user_has_cert_track_access(request.user, track):
            pricing = effective_cert_prices(track)
            return Response(
                {
                    "error": "Certification track subscription required.",
                    "code": "CERT_SUBSCRIPTION_REQUIRED",
                    "track_slug": track.slug,
                    "standalone_price": pricing["standalone_price"],
                    "addon_price": pricing["addon_price"],
                    "bundled_price": pricing["bundled_price"],
                    "payment_url": f"/payment?cert={track.slug}",
                },
                status=403,
            )

        # Reuse an existing live attempt instead of stacking duplicates.
        existing = (
            ExamAttempt.objects.filter(user=request.user, track=track, status="in_progress")
            .order_by("-started_at")
            .first()
        )
        if existing and not existing.is_expired:
            return Response(self._attempt_payload(existing, resumed=True))
        if existing and existing.is_expired:
            existing.status = "expired"
            existing.save(update_fields=["status"])

        # Sample scenarios per objective into the exam pool.
        snapshot = []
        for obj in track.objectives.prefetch_related("track_scenarios__scenario").all():
            pool = [ts for ts in obj.track_scenarios.all() if ts.in_exam_pool]
            picks = (
                random.sample(pool, EXAM_SCENARIOS_PER_OBJECTIVE)
                if len(pool) > EXAM_SCENARIOS_PER_OBJECTIVE
                else pool
            )
            for ts in picks:
                snapshot.append(
                    {
                        "scenario_id": ts.scenario_id,
                        "slug": ts.scenario.slug,
                        "title": ts.scenario.title,
                        "objective_code": obj.code,
                        "passed": False,
                        "score": 0,
                    }
                )

        if not snapshot:
            return Response({"error": "This track has no exam scenarios yet."}, status=400)

        attempt = ExamAttempt.objects.create(
            user=request.user,
            track=track,
            expires_at=timezone.now() + timezone.timedelta(minutes=track.exam_duration_minutes),
            results={"scenarios": snapshot},
        )
        return Response(self._attempt_payload(attempt), status=201)

    @staticmethod
    def _attempt_payload(attempt, resumed=False):
        remaining = int((attempt.expires_at - timezone.now()).total_seconds())
        return {
            "id": str(attempt.id),
            "track_slug": attempt.track.slug,
            "status": attempt.status,
            "resumed": resumed,
            "started_at": attempt.started_at,
            "expires_at": attempt.expires_at,
            "seconds_remaining": max(0, remaining),
            "score": attempt.score,
            "scenarios": attempt.results.get("scenarios", []),
        }


class ExamDetailView(APIView):
    """GET /api/certifications/exam/<uuid>/ — live attempt state (owner only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({"error": "Attempt not found"}, status=404)
        return Response(ExamStartView._attempt_payload(attempt))


class ExamSubmitView(APIView):
    """POST /api/certifications/exam/<uuid>/submit/ — grade + maybe issue a cert."""

    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.select_related("track").get(
                id=attempt_id, user=request.user
            )
        except ExamAttempt.DoesNotExist:
            return Response({"error": "Attempt not found"}, status=404)

        if attempt.status != "in_progress":
            # Already graded — return the stored result idempotently.
            return Response(self._result_payload(attempt))

        scenarios = attempt.results.get("scenarios", [])
        scenario_ids = [s["scenario_id"] for s in scenarios]
        # Exam integrity: only completions DURING this attempt's window count.
        completed_ids = _completed_scenario_ids(
            request.user, scenario_ids, since=attempt.started_at
        )

        # Re-read objective weights from the DB (don't trust the snapshot) and
        # divide by the FULL track weight, so an untested/failed objective drags
        # the score down — a cert can't be earned on partial objective coverage.
        track_weights = {o.code: (o.weight or 1) for o in attempt.track.objectives.all()}
        by_obj = {}
        for s in scenarios:
            passed = s["scenario_id"] in completed_ids
            s["passed"] = passed
            s["score"] = 100 if passed else 0
            o = by_obj.setdefault(s["objective_code"], {"total": 0, "passed": 0})
            o["total"] += 1
            o["passed"] += 1 if passed else 0

        weighted_sum = sum(
            (o["passed"] / o["total"]) * 100 * track_weights.get(code, 1)
            for code, o in by_obj.items()
            if o["total"]
        )
        weight_total = sum(track_weights.values()) or 1
        overall = round(weighted_sum / weight_total)

        attempt.score = overall
        attempt.submitted_at = timezone.now()
        attempt.results["objective_breakdown"] = by_obj
        expired = attempt.is_expired

        certificate = None
        if expired:
            attempt.status = "expired"
        elif overall >= attempt.track.passing_score:
            attempt.status = "passed"
            certificate = self._issue_certificate(request.user, attempt, overall)
        else:
            attempt.status = "failed"
        attempt.save(update_fields=["score", "submitted_at", "results", "status"])

        return Response(self._result_payload(attempt, certificate))

    @staticmethod
    def _issue_certificate(user, attempt, score):
        track = attempt.track
        # Never expose the user's email on a public certificate.
        holder = (user.get_full_name() or "").strip() or getattr(user, "username", "") or "FixitLab Learner"
        expires = timezone.now() + timezone.timedelta(days=30 * (track.validity_months or 36))
        # One certificate per (user, track); a re-pass at >= the stored score
        # updates it in place. certificate_id carries a random component so it is
        # NOT enumerable from public track code + user id + date.
        cert, created = CertEarnedCertificate.objects.get_or_create(
            user=user,
            track=track,
            defaults={
                "certificate_id": f"FIXIT-{track.code}-{uuid4().hex[:12].upper()}",
                "attempt": attempt,
                "holder_name": holder,
                "score": score,
                "expires_at": expires,
            },
        )
        if not created and score >= cert.score:
            cert.attempt = attempt
            cert.score = score
            cert.holder_name = holder
            cert.issued_at = timezone.now()
            cert.expires_at = expires
            cert.save(update_fields=["attempt", "score", "holder_name", "issued_at", "expires_at"])
        return cert

    @staticmethod
    def _result_payload(attempt, certificate=None):
        if certificate is None and attempt.status == "passed":
            certificate = (
                CertEarnedCertificate.objects.filter(
                    user=attempt.user, track=attempt.track
                ).first()
            )
        return {
            "id": str(attempt.id),
            "status": attempt.status,
            "score": attempt.score,
            "passing_score": attempt.track.passing_score,
            "passed": attempt.status == "passed",
            "expired": attempt.status == "expired",
            "objective_breakdown": attempt.results.get("objective_breakdown", {}),
            "certificate": CertificateSerializer(certificate).data if certificate else None,
        }


class MyCertificatesView(APIView):
    """GET /api/certifications/certificates/ — the current user's earned certs."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        certs = CertEarnedCertificate.objects.filter(user=request.user).select_related("track")
        return Response({"certificates": CertificateSerializer(certs, many=True).data})


# ─── Admin certification-track management ────────────────────────────────
#
# Mirrors how ``adminpanel`` manages ``Technology``: staff (IsPlatformAdmin) can
# list every track (including inactive ones) and edit each track's commercial /
# exam settings — active toggle, maintenance, pricing, free flag, passing score,
# exam duration, coming-soon. These live in the certifications app (not in
# adminpanel) so the cert domain owns its own admin surface.


class AdminTrackListView(APIView):
    """GET /api/certifications/admin/tracks/ — every track, with counts."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        tracks = (
            CertificationTrack.objects.annotate(
                objective_count=Count("objectives", distinct=True),
                scenario_count=Count(
                    "objectives__track_scenarios__scenario", distinct=True
                ),
            )
            .select_related("technology")
            .order_by("order", "name")
        )
        return Response({"tracks": AdminTrackSerializer(tracks, many=True).data})


class AdminTrackDetailView(APIView):
    """GET/PUT /api/certifications/admin/tracks/<pk>/ — read + update settings."""

    permission_classes = [IsPlatformAdmin]

    def _get_track(self, pk):
        return (
            CertificationTrack.objects.annotate(
                objective_count=Count("objectives", distinct=True),
                scenario_count=Count(
                    "objectives__track_scenarios__scenario", distinct=True
                ),
            )
            .select_related("technology")
            .get(pk=pk)
        )

    def get(self, request, pk):
        try:
            track = self._get_track(pk)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response(AdminTrackSerializer(track).data)

    def put(self, request, pk):
        try:
            track = self._get_track(pk)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        serializer = AdminTrackSerializer(track, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Re-read with counts so the response carries the annotated fields.
            return Response(AdminTrackSerializer(self._get_track(pk)).data)
        return Response(serializer.errors, status=400)


class AdminTrackScenariosView(APIView):
    """GET /api/certifications/admin/tracks/<pk>/scenarios/ — the labs mapped
    into a track, grouped by objective (the admin's view of track membership)."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        try:
            track = CertificationTrack.objects.get(pk=pk)
        except CertificationTrack.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        objectives = []
        total = 0
        for obj in track.objectives.prefetch_related(
            "track_scenarios__scenario__technology"
        ).all():
            scenarios = []
            for ts in obj.track_scenarios.all():
                sc = ts.scenario
                scenarios.append(
                    {
                        "slug": sc.slug,
                        "title": sc.title,
                        "difficulty": sc.difficulty,
                        "technology": getattr(sc.technology, "name", "") if sc.technology_id else "",
                        "in_exam_pool": ts.in_exam_pool,
                        "order": ts.order,
                    }
                )
            total += len(scenarios)
            objectives.append(
                {
                    "code": obj.code,
                    "title": obj.title,
                    "weight": obj.weight,
                    "order": obj.order,
                    "scenario_count": len(scenarios),
                    "scenarios": scenarios,
                }
            )
        return Response(
            {
                "track": {"slug": track.slug, "code": track.code, "name": track.name},
                "scenario_count": total,
                "objectives": objectives,
            }
        )


class CertVerifyView(APIView):
    """GET /api/certifications/certificate/verify/?id=... — public verification."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        cert_id = (request.query_params.get("id") or "").strip()
        if not cert_id:
            return Response({"valid": False, "error": "Missing certificate id"}, status=400)
        try:
            cert = CertEarnedCertificate.objects.select_related("track").get(
                certificate_id=cert_id
            )
        except CertEarnedCertificate.DoesNotExist:
            return Response({"valid": False, "error": "Certificate not found"}, status=404)
        return Response(
            {
                "valid": not cert.is_expired,
                "certificate": CertificateSerializer(cert).data,
            }
        )
