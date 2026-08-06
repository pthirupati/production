"""Read-only public API for Learning Journeys.

A Learning Journey is a named, role-based track that bundles already-existing
content (a tutorial course + difficulty-ordered scenarios + a capstone project +
a certification track) into one ordered milestone path. These endpoints serve
that catalog data; they never create/mutate anything.

Endpoints, mounted under ``/api/journeys/`` — NOT behind the admin-IP gate:

    GET /api/journeys/           -> list active journeys + step summaries
                                    (AllowAny)
    GET /api/journeys/next/      -> the requesting user's in-progress journey
                                    and their next incomplete step (auth only)
    GET /api/journeys/<slug>/    -> one journey, full ordered steps with each
                                     step's referenced content resolved to a
                                     real title (best-effort).  (AllowAny)

If an authenticated user makes the request we attach best-effort, non-fatal
per-user progress hints (which referenced scenarios/projects they've completed).
Resolution and progress are wrapped so a missing/renamed reference or a progress
error can never 500 the endpoint — the step just renders with its stored title.
"""

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
        ctx["course_titles"] = self._course_titles(single_slugs)
        ctx["cert_titles"] = cert_titles
        ctx["completed_scenarios"] = self._completed_scenarios(scen_slugs)
        return ctx

    def _course_titles(self, single_slugs):
        """Map tutorial_course ref_slugs -> the course's display title.

        A "course" isn't its own table: it's the set of Tutorial rows sharing a
        ``course_slug``, each carrying a denormalised ``course_title``. So this
        is one grouped query over the whole slug set, not a query per step.

        ``course_title`` is blank on some rows, so we exclude blanks in the
        query and keep the first remaining row per course. A course whose rows
        are all blank (or all unpublished) simply doesn't appear — an
        unresolvable ref must fall back to the step's stored title, same as
        every other kind here.
        """
        if not single_slugs:
            return {}
        try:
            from apps.tutorials.models import Tutorial

            titles = {}
            rows = (
                Tutorial.objects.filter(
                    is_published=True, course_slug__in=single_slugs
                )
                .exclude(course_title="")
                .values_list("course_slug", "course_title")
            )
            for course_slug, course_title in rows:
                titles.setdefault(course_slug, course_title)
            return titles
        except Exception:
            return {}

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


# ─── "Where was I?" — next incomplete step ───────────────────────────────────
#
# The dashboard needs one question answered: of the journeys this user has
# actually touched, which step should they open next? The detail endpoint has
# the per-user data to answer it but only for one journey at a time and only
# for scenarios, so the dashboard would have to fetch every journey and diff
# them client-side. This does it server-side in a fixed number of queries.


def _journey_refs(journeys):
    """Split every step reference across ``journeys`` by kind, deduplicated."""
    refs = {"scenarios": set(), "tutorial_course": set(), "project": set(), "certification": set()}
    for journey in journeys:
        for step in journey.steps.all():
            if step.kind == "scenarios":
                refs["scenarios"].update(step.ref_slugs or [])
            elif step.ref_slug and step.kind in refs:
                refs[step.kind].add(step.ref_slug)
    return refs


def _course_tutorial_slugs(course_slugs):
    """course_slug -> published tutorial slugs in reading order.

    A "course" is not its own table (see ``_course_titles``), so membership is
    a grouped query over Tutorial. Ordering matters here in a way it doesn't
    for titles: the next step's link points at the first *unread* tutorial, so
    the order must match what the course page shows.
    """
    if not course_slugs:
        return {}
    try:
        from apps.tutorials.models import Tutorial

        courses = {}
        rows = (
            Tutorial.objects.filter(is_published=True, course_slug__in=course_slugs)
            .order_by("course_slug", "module_order", "id")
            .values_list("course_slug", "slug")
        )
        for course_slug, tut_slug in rows:
            courses.setdefault(course_slug, []).append(tut_slug)
        return courses
    except Exception:
        return {}


def _completed_index(user, refs, course_tutorials):
    """Per-kind sets of the slugs this user has finished.

    Every lookup is wrapped: this endpoint degrades to "no progress" rather
    than 500ing, same contract as the rest of the module. Note the asymmetry
    between kinds — completion means a different table for each, and there is
    no single unified progress record to read.
    """
    done = {"scenarios": set(), "tutorials": set(), "project": set(), "certification": set()}

    if refs["scenarios"]:
        try:
            from apps.progress.models import UserScenarioProgress

            done["scenarios"] = set(
                UserScenarioProgress.objects.filter(
                    user=user, completed=True, scenario__slug__in=refs["scenarios"]
                ).values_list("scenario__slug", flat=True)
            )
        except Exception:
            pass

    all_tutorials = {slug for slugs in course_tutorials.values() for slug in slugs}
    if all_tutorials:
        try:
            from apps.tutorials.models import TutorialProgress

            done["tutorials"] = set(
                TutorialProgress.objects.filter(
                    user=user, completed=True, tutorial__slug__in=all_tutorials
                ).values_list("tutorial__slug", flat=True)
            )
        except Exception:
            pass

    if refs["project"]:
        try:
            from .models import UserProjectProgress

            done["project"] = set(
                UserProjectProgress.objects.filter(
                    user=user, status="completed", project__slug__in=refs["project"]
                ).values_list("project__slug", flat=True)
            )
        except Exception:
            pass

    if refs["certification"]:
        try:
            from apps.certifications.models import ExamAttempt

            done["certification"] = set(
                ExamAttempt.objects.filter(
                    user=user, status="passed", track__slug__in=refs["certification"]
                ).values_list("track__slug", flat=True)
            )
        except Exception:
            pass

    return done


def _step_progress(step, done, course_tutorials):
    """(is_complete, pending_slug, item_total, item_done) for one step.

    ``pending_slug`` is the specific piece of content to send the user to —
    the first unfinished item in the step, not the step's own ref. A step with
    nothing measurable behind it (a milestone, or a reference to content that
    was never seeded) reports 0 items and is never counted as complete; the
    caller skips those when choosing where to send the user.
    """
    if step.kind == "scenarios":
        slugs = list(step.ref_slugs or [])
        finished = done["scenarios"]
    elif step.kind == "tutorial_course":
        slugs = course_tutorials.get(step.ref_slug, [])
        finished = done["tutorials"]
    elif step.kind in ("project", "certification") and step.ref_slug:
        slugs = [step.ref_slug]
        finished = done[step.kind]
    else:
        return False, None, 0, 0

    if not slugs:
        return False, None, 0, 0

    pending = [s for s in slugs if s not in finished]
    return (not pending), (pending[0] if pending else None), len(slugs), len(slugs) - len(pending)


# Where each kind of content actually lives in the SPA. ``project`` is absent
# on purpose: the backend has Projects but the frontend has no /projects/<slug>
# route yet, so a capstone step is reported with link=None and the dashboard
# renders it as text rather than a dead link.
_LINK_PREFIX = {
    "scenarios": "/scenarios/",
    "tutorial_course": "/tutorials/",
    "certification": "/certifications/",
}


def _resolve_target(kind, slug):
    """(title, link) for the specific content a step points the user at."""
    prefix = _LINK_PREFIX.get(kind)
    link = f"{prefix}{slug}" if prefix and slug else None
    title = None
    try:
        if kind == "scenarios":
            title = Scenario.objects.filter(slug=slug).values_list("title", flat=True).first()
        elif kind == "tutorial_course":
            from apps.tutorials.models import Tutorial

            title = Tutorial.objects.filter(slug=slug).values_list("title", flat=True).first()
        elif kind == "project":
            title = Project.objects.filter(slug=slug).values_list("title", flat=True).first()
        elif kind == "certification":
            from apps.certifications.models import CertificationTrack

            title = (
                CertificationTrack.objects.filter(slug=slug).values_list("name", flat=True).first()
            )
    except Exception:
        title = None
    return title, link


class JourneyNextStepView(APIView):
    """GET /api/journeys/next/ — resume point for the requesting user.

    Returns the journey the user is furthest into plus the first step they
    haven't finished, or ``{"journey": null, "next_step": null}`` when they
    have not completed anything a journey references.

    "In progress" deliberately requires *completed* content, not merely a
    started lab: every user who browses one scenario would otherwise be
    enrolled in whichever journey happens to mention it. A journey whose
    measurable steps are all finished is also excluded — it is done, not in
    progress, and re-suggesting it would be noise.

    Note this is a suggestion, not enrollment: there is no join table, so
    "their journey" is inferred from content overlap and can change as the
    user works. Ranked by completed items so the inference follows effort.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        journeys = list(_base_queryset())
        if not journeys:
            return Response({"journey": None, "next_step": None})

        refs = _journey_refs(journeys)
        course_tutorials = _course_tutorial_slugs(refs["tutorial_course"])
        done = _completed_index(request.user, refs, course_tutorials)

        best = None
        for journey in journeys:
            steps = sorted(journey.steps.all(), key=lambda s: s.order)
            states = [(s, _step_progress(s, done, course_tutorials)) for s in steps]

            items_done = sum(state[3] for _, state in states)
            if not items_done:
                continue  # untouched — not their journey

            measurable = [(s, st) for s, st in states if st[2] > 0]
            pending = [(s, st) for s, st in measurable if not st[0]]
            if not pending:
                continue  # finished, not in progress

            candidate = {
                "journey": journey,
                "items_done": items_done,
                "completed_steps": sum(1 for _, st in measurable if st[0]),
                "total_steps": len(measurable),
                "next": pending[0],
            }
            # _base_queryset() is already in display order, so a plain > keeps
            # the lowest-ordered journey on a tie.
            if best is None or candidate["items_done"] > best["items_done"]:
                best = candidate

        if best is None:
            return Response({"journey": None, "next_step": None})

        journey = best["journey"]
        step, (_, pending_slug, item_total, item_done) = best["next"]
        target_title, link = _resolve_target(step.kind, pending_slug)

        return Response({
            "journey": {
                "slug": journey.slug,
                "title": journey.title,
                "role_label": journey.role_label,
                "level": journey.level,
                "completed_steps": best["completed_steps"],
                "total_steps": best["total_steps"],
            },
            "next_step": {
                "order": step.order,
                "kind": step.kind,
                "title": step.title,
                "slug": pending_slug,
                # Falls back to the step's stored title when the referenced
                # content can't be resolved — same rule as the detail endpoint.
                "target_title": target_title or step.title,
                "link": link,
                "items_completed": item_done,
                "items_total": item_total,
            },
        })
