"""First-party activation funnel (audit Z6-6).

The audit's point stands — prioritisation was being done blind — but its remedy was
PostHog, and the owner has declined third-party analytics. That is not a dead end:
**seven of the nine funnel stages the audit asks for are already recorded**, because
this platform stores what users did rather than only what they clicked.

    signup_completed     User.date_joined
    lab_started          LabSession.started_at
    lab_first_command    first CommandHistory row for a session   <- activation
    lab_validated        LabSession.completion_finalized
    lab_provision_failed LabSession.status == "FAILED"
    checkout_started     PaymentTransaction created
    purchase_completed   PaymentTransaction.status == "success"

Deriving them from existing rows rather than emitting events is the better trade
here, and not only because it avoids a vendor:

* no third-party processor, so no DPDP consent basis and no cookie banner — the
  privacy policy published in Z4-8 promises we ask before setting any
  non-essential cookie, and this keeps that promise intact;
* the numbers are **retroactive**. Event-based analytics can only answer questions
  from the day it was installed; this answers them from the day the platform
  launched, which is what "we are prioritising blind" actually needs;
* it cannot drift from reality. An event fires because someone remembered to add
  it; a LabSession row exists because a lab started.

**`scenario_viewed` and `paywall_viewed` are NOT covered** and are stated as such
in the response rather than silently omitted. They are page views with no
server-side trace, so they need client instrumentation — which is exactly the part
that would need consent. A funnel that quietly skipped them would overstate its own
completeness.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Min, Q
from django.utils import timezone

User = get_user_model()


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def activation_funnel(days: int = 30) -> dict:
    """Stage counts and conversion for users who signed up in the window.

    Cohorted on signup, deliberately. Counting "labs started in the last 30 days"
    against "signups in the last 30 days" mixes populations and produces a
    conversion rate that can exceed 100% — the classic way a funnel dashboard ends
    up quietly meaningless.
    """
    from apps.billing.models import PaymentTransaction
    from apps.labs.models import CommandHistory, LabSession

    since = timezone.now() - timedelta(days=days)
    cohort = User.objects.filter(date_joined__gte=since, is_staff=False)
    cohort_ids = list(cohort.values_list("id", flat=True))
    signed_up = len(cohort_ids)

    if not signed_up:
        return {
            "days": days,
            "cohort": "users who signed up in this window",
            "signed_up": 0,
            "stages": [],
            "not_tracked": _NOT_TRACKED,
        }

    sessions = LabSession.objects.filter(user_id__in=cohort_ids)
    started_ids = set(sessions.values_list("user_id", flat=True))

    # Activation: typed at least one command. Starting a lab and never touching the
    # terminal is the single most useful drop-off on this platform, and it is
    # invisible to any funnel that stops at "lab_started".
    typed_ids = set(
        CommandHistory.objects.filter(session__user_id__in=cohort_ids)
        .values_list("session__user_id", flat=True)
    )

    validated_ids = set(
        sessions.filter(completion_finalized=True).values_list("user_id", flat=True)
    )
    failed_ids = set(
        sessions.filter(status="FAILED").values_list("user_id", flat=True)
    )

    txns = PaymentTransaction.objects.filter(user_id__in=cohort_ids)
    checkout_ids = set(txns.values_list("user_id", flat=True))
    paid_ids = set(txns.filter(status="success").values_list("user_id", flat=True))

    ordered = [
        ("signed_up", signed_up, "Created an account"),
        ("lab_started", len(started_ids), "Provisioned at least one lab"),
        ("lab_first_command", len(typed_ids), "Typed a command — the activation signal"),
        ("lab_validated", len(validated_ids), "Completed a lab with a passing grade"),
        ("checkout_started", len(checkout_ids), "Reached a payment attempt"),
        ("purchase_completed", len(paid_ids), "Paid successfully"),
    ]

    stages = []
    previous = signed_up
    for key, count, label in ordered:
        stages.append({
            "key": key,
            "label": label,
            "users": count,
            # Two rates, because they answer different questions: "of everyone who
            # signed up" for absolute health, "of the previous stage" for locating
            # the specific step that leaks.
            "pct_of_signups": _pct(count, signed_up),
            "pct_of_previous": _pct(count, previous) if key != "signed_up" else 100.0,
        })
        previous = count or previous

    return {
        "days": days,
        "cohort": "users who signed up in this window",
        "signed_up": signed_up,
        "stages": stages,
        "lab_provision_failed_users": len(failed_ids),
        "not_tracked": _NOT_TRACKED,
    }


_NOT_TRACKED = {
    "stages": ["scenario_viewed", "paywall_viewed"],
    "reason": (
        "Page views leave no server-side trace, so these need client-side "
        "instrumentation. Stated here rather than omitted so the funnel does not "
        "overstate its own completeness."
    ),
}


def technology_conversion(days: int = 90, limit: int = 15) -> list[dict]:
    """Which technologies convert a first lab into a purchase.

    Answers "which catalog areas are worth more content" from data that already
    exists, which is the question the audit says is being guessed at.
    """
    from apps.labs.models import LabSession

    since = timezone.now() - timedelta(days=days)
    rows = (
        LabSession.objects.filter(started_at__gte=since)
        .values("scenario__technology__slug", "scenario__technology__name")
        .annotate(
            sessions=Count("id"),
            learners=Count("user_id", distinct=True),
            completed=Count("id", filter=Q(completion_finalized=True)),
            failed=Count("id", filter=Q(status="FAILED")),
        )
        .order_by("-sessions")[:limit]
    )
    out = []
    for r in rows:
        sessions = r["sessions"] or 0
        out.append({
            "technology": r["scenario__technology__name"] or "unknown",
            "slug": r["scenario__technology__slug"] or "",
            "sessions": sessions,
            "learners": r["learners"] or 0,
            "completion_rate": _pct(r["completed"] or 0, sessions),
            # A high provision-failure rate is an infrastructure problem wearing a
            # content problem's clothes; separating them is the point.
            "provision_failure_rate": _pct(r["failed"] or 0, sessions),
        })
    return out


def time_to_activation(days: int = 30) -> dict:
    """How long from signup to first typed command.

    A median rather than a mean: a handful of users who return after three months
    would drag an average into uselessness.
    """
    from apps.labs.models import CommandHistory

    since = timezone.now() - timedelta(days=days)
    first_commands = (
        CommandHistory.objects.filter(session__user__date_joined__gte=since)
        .values("session__user_id", "session__user__date_joined")
        .annotate(first_at=Min("timestamp"))
    )
    deltas = sorted(
        (row["first_at"] - row["session__user__date_joined"]).total_seconds() / 60
        for row in first_commands
        if row["first_at"] and row["session__user__date_joined"]
    )
    if not deltas:
        return {"activated_users": 0, "median_minutes": None}
    mid = len(deltas) // 2
    median = deltas[mid] if len(deltas) % 2 else (deltas[mid - 1] + deltas[mid]) / 2
    return {
        "activated_users": len(deltas),
        "median_minutes": round(median, 1),
        "p90_minutes": round(deltas[int(len(deltas) * 0.9)], 1),
    }
