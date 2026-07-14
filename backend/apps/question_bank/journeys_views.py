"""Read-only public API for Learning Journeys.

A Learning Journey is a named, role-based track that bundles already-existing
content (a tutorial course + difficulty-ordered scenarios + a capstone project +
a certification track) into one ordered milestone path. These endpoints serve
that catalog data; they never create/mutate anything.

Endpoints (both AllowAny, mounted under ``/api/journeys/`` — NOT behind the
admin-IP gate):

    GET /api/journeys/           -> list active journeys + step summaries
    GET /api/journeys/<slug>/    -> one journey, full ordered steps with each
                                     step's referenced content resolved to a
                                     real title (best-effort).

If an authenticated user makes the request we attach best-effort, non-fatal
per-user progress hints (which referenced scenarios/projects they've completed).
Resolution and progress are wrapped so a missing/renamed reference or a progress
error can never 500 the endpoint — the step just renders with its stored title.
"""

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from .models import LearningJourney, Scenario, Project
from .journeys_serializers import (
    LearningJourneyListSerializer,
    LearningJourneyDetailSerializer,
)


def _base_queryset():
    return (
        LearningJourney.objects.filter(is_active=True)
        .select_related("primary_technology")
        .prefetch_related("steps")
        .order_by("order", "title")
    )


class JourneyListView(ListAPIView):
    """GET /api/journeys/ — active journeys with lightweight step summaries."""

    permission_classes = [AllowAny]
    serializer_class = LearningJourneyListSerializer
    pagination_class = None  # small, curated set — return them all

    def get_queryset(self):
        return _base_queryset()


class JourneyDetailView(RetrieveAPIView):
    """GET /api/journeys/<slug>/ — full ordered steps with resolved titles."""

    permission_classes = [AllowAny]
    serializer_class = LearningJourneyDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return _base_queryset()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Pre-resolve real titles for every referenced slug in ONE pass so the
        # serializer doesn't issue a query per step. Loose refs mean some slugs
        # may resolve to nothing — that's fine, the step keeps its stored title.
        journey = self.get_object()
        scen_slugs, single_slugs = set(), set()
        for step in journey.steps.all():
            if step.kind == "scenarios":
                scen_slugs.update(step.ref_slugs or [])
            elif step.ref_slug:
                single_slugs.add(step.ref_slug)

        scen_titles = dict(
            Scenario.objects.filter(slug__in=scen_slugs).values_list("slug", "title")
        )
        proj_titles = dict(
            Project.objects.filter(slug__in=single_slugs).values_list("slug", "title")
        )
        cert_titles = {}
        try:
            from apps.certifications.models import CertificationTrack

            cert_titles = dict(
                CertificationTrack.objects.filter(slug__in=single_slugs).values_list(
                    "slug", "name"
                )
            )
        except Exception:
            cert_titles = {}

        ctx["scenario_titles"] = scen_titles
        ctx["project_titles"] = proj_titles
        ctx["cert_titles"] = cert_titles
        ctx["completed_scenarios"] = self._completed_scenarios(scen_slugs)
        return ctx

    def _completed_scenarios(self, scen_slugs):
        """Best-effort set of completed scenario slugs for an authed user."""
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False) or not scen_slugs:
            return set()
        try:
            from apps.progress.models import UserScenarioProgress

            return set(
                UserScenarioProgress.objects.filter(
                    user=user, completed=True, scenario__slug__in=scen_slugs
                ).values_list("scenario__slug", flat=True)
            )
        except Exception:
            return set()
