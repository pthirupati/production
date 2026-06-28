"""Public, read-only API for the Tutorials section.

Both endpoints are ``AllowAny`` (these are public marketing/SEO pages, like the
blog) and rate-limited per-IP via ``StrictAnonRateThrottle``. They are written
to degrade gracefully — a DB hiccup returns an empty list / 404 rather than a
500 that would blank the public page.

Authenticated users can persist tutorial read progress via
``/api/tutorials/progress/`` and ``/api/tutorials/<slug>/progress/``.
"""

import logging

from django.db.models import Count
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import StrictAnonRateThrottle

from .models import Tutorial, TutorialProgress
from .serializers import (
    TutorialDetailSerializer,
    TutorialListSerializer,
    TutorialProgressSerializer,
)

logger = logging.getLogger(__name__)


def _scenario_brief(scenario_slug: str) -> dict | None:
    if not scenario_slug:
        return None
    try:
        from apps.question_bank.models import Scenario

        sc = Scenario.objects.filter(slug=scenario_slug, is_active=True).only(
            "slug", "title", "difficulty", "technology_id"
        ).select_related("technology").first()
        if not sc:
            return None
        return {
            "slug": sc.slug,
            "title": sc.title,
            "difficulty": sc.difficulty,
            "technology": sc.technology.name if sc.technology else "",
            "technology_slug": sc.technology.slug if sc.technology else "",
        }
    except Exception:
        return None


def _quiz_section_orders(tutorial: Tutorial) -> set[int]:
    """Sections that require an explicit quiz pass, not just reading/scrolling."""
    orders: set[int] = set()
    for section in tutorial.sections.all():
        heading = (section.heading or "").lower()
        if section.quiz_json or any(k in heading for k in ("assessment", "quiz", "checkpoint", "practice question")):
            orders.add(int(section.order))
    return orders


def _linked_lab_completed(user, tutorial: Tutorial) -> bool:
    """Return whether the tutorial's primary scenario has been solved by the user."""
    if not tutorial.scenario_slug:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        from apps.progress.models import UserScenarioProgress
        from apps.question_bank.models import Scenario

        scenario = Scenario.objects.filter(slug=tutorial.scenario_slug).only("id").first()
        if not scenario:
            return False
        return UserScenarioProgress.objects.filter(
            user=user,
            scenario=scenario,
            completed=True,
        ).exists()
    except Exception:
        logger.exception("Could not evaluate linked lab completion for tutorial=%s", tutorial.slug)
        return False


def _completion_requirements(tutorial: Tutorial, user, completed_sections=None) -> dict:
    completed = {int(x) for x in (completed_sections or []) if str(x).isdigit()}
    quiz_orders = sorted(_quiz_section_orders(tutorial))
    lab_required = bool(tutorial.scenario_slug)
    lab_completed = _linked_lab_completed(user, tutorial) if lab_required else True
    section_orders = {int(o) for o in tutorial.sections.values_list("order", flat=True)}
    return {
        "all_sections_read": bool(section_orders) and section_orders.issubset(completed),
        "quiz_required": bool(quiz_orders),
        "quiz_orders": quiz_orders,
        "quiz_passed": all(o in completed for o in quiz_orders),
        "linked_lab_required": lab_required,
        "linked_lab_slug": tutorial.scenario_slug or "",
        "linked_lab_completed": lab_completed,
    }


def _requirements_met(requirements: dict) -> bool:
    return (
        requirements.get("all_sections_read")
        and (not requirements.get("quiz_required") or requirements.get("quiz_passed"))
        and (not requirements.get("linked_lab_required") or requirements.get("linked_lab_completed"))
    )


class TutorialListView(APIView):
    """GET /api/tutorials/ — published tutorials, optionally filtered by topic."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        try:
            qs = (
                Tutorial.objects.filter(is_published=True)
                .annotate(section_count=Count("sections"))
                .order_by("order", "title")
            )
            topic = (request.query_params.get("topic") or "").strip()
            if topic:
                qs = qs.filter(topic__iexact=topic)

            tutorials = list(qs)
            topics = sorted(
                {t.topic for t in Tutorial.objects.filter(is_published=True) if t.topic}
            )
        except Exception:
            logger.exception("TutorialListView failed — returning empty payload")
            return Response({"tutorials": [], "topics": []})

        return Response(
            {
                "tutorials": TutorialListSerializer(tutorials, many=True).data,
                "topics": topics,
            }
        )


class TutorialCurriculumView(APIView):
    """GET /api/tutorials/curriculum/ — technology-wise learning paths."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        try:
            tutorials = (
                Tutorial.objects.filter(is_published=True)
                .annotate(section_count=Count("sections"))
                .order_by("topic", "order", "title")
            )
            by_topic = {}
            courses_map = {}
            for t in tutorials:
                item = TutorialListSerializer(t).data
                by_topic.setdefault(t.topic, []).append(item)
                if t.course_slug:
                    courses_map.setdefault(
                        t.course_slug,
                        {
                            "course_slug": t.course_slug,
                            "course_title": t.course_title or t.course_slug.replace("-", " ").title(),
                            "topic": t.topic,
                            "modules": [],
                        },
                    )
                    courses_map[t.course_slug]["modules"].append(item)
            curriculum = [
                {
                    "topic": topic,
                    "tutorial_count": len(items),
                    "total_sections": sum(i.get("section_count", 0) for i in items),
                    "tutorials": items,
                }
                for topic, items in sorted(by_topic.items(), key=lambda x: x[0].lower())
            ]
            courses = []
            for slug, course in sorted(courses_map.items()):
                course["modules"].sort(key=lambda m: (m.get("module_order", 0), m.get("order", 0)))
                course["module_count"] = len(course["modules"])
                course["total_sections"] = sum(m.get("section_count", 0) for m in course["modules"])
                courses.append(course)
        except Exception:
            logger.exception("TutorialCurriculumView failed — returning empty payload")
            return Response({"curriculum": [], "courses": []})
        return Response({"curriculum": curriculum, "courses": courses})


class TutorialDetailView(APIView):
    """GET /api/tutorials/<slug>/ — a single tutorial with its ordered sections."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request, slug):
        try:
            tutorial = (
                Tutorial.objects.filter(is_published=True)
                .prefetch_related("sections")
                .get(slug=slug)
            )
        except Tutorial.DoesNotExist:
            return Response({"error": "Tutorial not found"}, status=404)
        except Exception:
            logger.exception("TutorialDetailView failed for slug=%s", slug)
            return Response({"error": "Tutorial not found"}, status=404)

        try:
            related = list(
                Tutorial.objects.filter(is_published=True, topic=tutorial.topic)
                .exclude(pk=tutorial.pk)
                .order_by("order", "title")[:4]
            )
        except Exception:
            related = []

        data = TutorialDetailSerializer(tutorial).data
        data["related"] = TutorialListSerializer(related, many=True).data
        data["linked_scenario"] = _scenario_brief(tutorial.scenario_slug)

        if tutorial.scenario_slug:
            try:
                data["related_scenarios"] = [
                    b for b in [_scenario_brief(tutorial.scenario_slug)] if b
                ]
            except Exception:
                data["related_scenarios"] = []
        else:
            data["related_scenarios"] = []

        try:
            if tutorial.course_slug:
                siblings = list(
                    Tutorial.objects.filter(is_published=True, course_slug=tutorial.course_slug)
                    .order_by("module_order", "order", "title")
                    .values("slug", "title", "order", "module_order", "level_track")
                )
                path_label = tutorial.course_title or tutorial.course_slug
            else:
                siblings = list(
                    Tutorial.objects.filter(is_published=True, topic=tutorial.topic)
                    .order_by("order", "title")
                    .values("slug", "title", "order", "module_order", "level_track")
                )
                path_label = tutorial.topic
            idx = next((i for i, s in enumerate(siblings) if s["slug"] == tutorial.slug), 0)
            data["curriculum"] = {
                "topic": path_label,
                "course_slug": tutorial.course_slug or "",
                "position": idx + 1,
                "total_in_topic": len(siblings),
                "prev": siblings[idx - 1] if idx > 0 else None,
                "next": siblings[idx + 1] if idx < len(siblings) - 1 else None,
                "path": siblings,
            }
        except Exception:
            data["curriculum"] = {
                "topic": tutorial.topic,
                "position": 1,
                "total_in_topic": 1,
                "prev": None,
                "next": None,
                "path": [],
            }

        if request.user.is_authenticated:
            try:
                prog = TutorialProgress.objects.filter(user=request.user, tutorial=tutorial).first()
                if prog:
                    data["user_progress"] = TutorialProgressSerializer(prog).data
            except Exception:
                pass

        completed_sections = []
        if data.get("user_progress"):
            completed_sections = data["user_progress"].get("completed_sections") or []
        data["completion_requirements"] = _completion_requirements(tutorial, request.user, completed_sections)

        return Response(data)


class TutorialProgressListView(APIView):
    """GET /api/tutorials/progress/ — current user's tutorial progress rows."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rows = (
                TutorialProgress.objects.filter(user=request.user)
                .select_related("tutorial")
                .prefetch_related("tutorial__sections")
                .order_by("-updated_at")[:50]
            )
            return Response({
                "progress": TutorialProgressSerializer(rows, many=True).data,
            })
        except Exception:
            logger.exception("TutorialProgressListView failed")
            return Response({"progress": []})


class TutorialContinueView(APIView):
    """GET /api/tutorials/progress/continue/ — in-progress tutorials to resume."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rows = (
                TutorialProgress.objects.filter(user=request.user, completed=False)
                .select_related("tutorial")
                .prefetch_related("tutorial__sections")
                .order_by("-updated_at")[:6]
            )
            return Response({
                "continue": TutorialProgressSerializer(rows, many=True).data,
            })
        except Exception:
            logger.exception("TutorialContinueView failed")
            return Response({"continue": []})


class TutorialProgressUpdateView(APIView):
    """POST /api/tutorials/<slug>/progress/ — update section progress."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            tutorial = Tutorial.objects.filter(is_published=True).prefetch_related("sections").get(slug=slug)
        except Tutorial.DoesNotExist:
            return Response({"error": "Tutorial not found"}, status=404)

        section_order = int(request.data.get("section_order") or 0)
        quiz_passed = bool(request.data.get("quiz_passed"))
        mark_complete = bool(request.data.get("mark_complete"))
        completed_sections = request.data.get("completed_sections")

        prog, _ = TutorialProgress.objects.get_or_create(user=request.user, tutorial=tutorial)
        quiz_orders = _quiz_section_orders(tutorial)
        if isinstance(completed_sections, list):
            requested = {int(x) for x in completed_sections if str(x).isdigit()}
            already_passed_quizzes = set(prog.completed_sections or []) & quiz_orders
            newly_passed_quiz = {section_order} if quiz_passed and section_order in quiz_orders else set()
            allowed_quizzes = already_passed_quizzes | newly_passed_quiz
            prog.completed_sections = sorted(
                o for o in requested if o not in quiz_orders or o in allowed_quizzes
            )
        elif section_order and section_order not in prog.completed_sections:
            if section_order not in quiz_orders or quiz_passed:
                prog.completed_sections = sorted(set(prog.completed_sections or []) | {section_order})

        if section_order:
            prog.last_section_order = max(prog.last_section_order or 0, section_order)

        total = tutorial.sections.count()
        requirements = _completion_requirements(tutorial, request.user, prog.completed_sections)
        if mark_complete and not requirements["quiz_passed"]:
            # Do not let the legacy "Mark complete" button bypass the quiz.
            prog.completed_sections = sorted(set(prog.completed_sections or []) - quiz_orders)
            requirements = _completion_requirements(tutorial, request.user, prog.completed_sections)

        if total and _requirements_met(requirements):
            prog.completed = True
        else:
            prog.completed = False

        prog.save()
        return Response({
            "ok": True,
            "progress": TutorialProgressSerializer(prog).data,
            "completion_requirements": _completion_requirements(tutorial, request.user, prog.completed_sections),
        })
