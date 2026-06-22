"""Certification-track API.

Public reads (list / detail / verify) are ``AllowAny`` + per-IP throttled and
degrade gracefully (empty payload / 404, never a 500 that blanks the page),
mirroring ``apps.tutorials``. Exam actions are owner-scoped.

Per-objective progress and exam grading both read ``UserScenarioProgress`` —
the existing single source of truth for scenario completion — so the cert layer
adds no parallel progress bookkeeping.
"""

import logging
import random

from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.progress.models import UserScenarioProgress

from common.throttles import StrictAnonRateThrottle
from .models import (
    CertEarnedCertificate,
    CertificationTrack,
    ExamAttempt,
)
from .serializers import CertificateSerializer, TrackListSerializer

logger = logging.getLogger(__name__)

# How many scenarios per objective to sample into a timed mock exam.
EXAM_SCENARIOS_PER_OBJECTIVE = 2


def _completed_scenario_ids(user, scenario_ids):
    """Set of scenario ids the user has completed, restricted to scenario_ids."""
    if not user or not user.is_authenticated or not scenario_ids:
        return set()
    return set(
        UserScenarioProgress.objects.filter(
            user=user, completed=True, scenario_id__in=scenario_ids
        ).values_list("scenario_id", flat=True)
    )


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
                .annotate(objective_count=Count("objectives", distinct=True))
                .order_by("order", "name")
            )
            # scenario_count = distinct scenarios mapped across the track's objectives
            for t in tracks:
                t.scenario_count = (
                    t.objectives.values("track_scenarios__scenario").distinct().count()
                )
        except Exception:
            logger.exception("TrackListView failed — returning empty payload")
            return Response({"tracks": []})
        return Response({"tracks": TrackListSerializer(tracks, many=True).data})


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

        return Response(
            {
                "slug": track.slug,
                "code": track.code,
                "name": track.name,
                "vendor": track.vendor,
                "description": track.description,
                "exam_duration_minutes": track.exam_duration_minutes,
                "passing_score": track.passing_score,
                "overall_percent": overall,
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

        # Reuse an existing live attempt instead of stacking duplicates.
        existing = (
            ExamAttempt.objects.filter(user=request.user, track=track, status="in_progress")
            .order_by("-started_at")
            .first()
        )
        if existing and not existing.is_expired:
            return Response(self._attempt_payload(existing))
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
                        "weight": obj.weight or 1,
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
    def _attempt_payload(attempt):
        remaining = int((attempt.expires_at - timezone.now()).total_seconds())
        return {
            "id": str(attempt.id),
            "track_slug": attempt.track.slug,
            "status": attempt.status,
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

        if attempt.status not in ("in_progress",):
            # Already graded — return the stored result idempotently.
            return Response(self._result_payload(attempt))

        scenarios = attempt.results.get("scenarios", [])
        scenario_ids = [s["scenario_id"] for s in scenarios]
        completed_ids = _completed_scenario_ids(request.user, scenario_ids)
        best_scores = dict(
            UserScenarioProgress.objects.filter(
                user=request.user, scenario_id__in=scenario_ids
            ).values_list("scenario_id", "best_score")
        )

        # Per-objective + overall weighted score.
        by_obj = {}
        for s in scenarios:
            passed = s["scenario_id"] in completed_ids
            s["passed"] = passed
            s["score"] = best_scores.get(s["scenario_id"], 100 if passed else 0)
            o = by_obj.setdefault(s["objective_code"], {"weight": s["weight"], "total": 0, "passed": 0})
            o["total"] += 1
            o["passed"] += 1 if passed else 0

        weighted_sum = sum((o["passed"] / o["total"]) * 100 * o["weight"] for o in by_obj.values() if o["total"])
        weight_total = sum(o["weight"] for o in by_obj.values() if o["total"])
        overall = round(weighted_sum / weight_total) if weight_total else 0

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
        holder = (user.get_full_name() or "").strip() or getattr(user, "email", "") or f"User {user.id}"
        cert_id = f"FIXIT-{track.code}-{user.id}-{timezone.now():%Y%m%d}"
        cert, _ = CertEarnedCertificate.objects.get_or_create(
            certificate_id=cert_id,
            defaults={
                "user": user,
                "track": track,
                "attempt": attempt,
                "holder_name": holder,
                "score": score,
                "expires_at": timezone.now()
                + timezone.timedelta(days=30 * (track.validity_months or 36)),
            },
        )
        return cert

    @staticmethod
    def _result_payload(attempt, certificate=None):
        if certificate is None:
            certificate = (
                CertEarnedCertificate.objects.filter(attempt=attempt).first()
                if attempt.status == "passed"
                else None
            )
        return {
            "id": str(attempt.id),
            "status": attempt.status,
            "score": attempt.score,
            "passing_score": attempt.track.passing_score,
            "passed": attempt.status == "passed",
            "objective_breakdown": attempt.results.get("objective_breakdown", {}),
            "certificate": CertificateSerializer(certificate).data if certificate else None,
        }


class MyCertificatesView(APIView):
    """GET /api/certifications/certificates/ — the current user's earned certs."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        certs = CertEarnedCertificate.objects.filter(user=request.user).select_related("track")
        return Response({"certificates": CertificateSerializer(certs, many=True).data})


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
