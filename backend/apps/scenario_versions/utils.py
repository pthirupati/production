from .models import ScenarioVersion


def get_active_version(scenario):
    """
    Returns the active version for a scenario, or None if it has no history.

    The writer (question_bank/apps.py) keeps exactly one is_active row per
    scenario. It did not always: every save used to insert another is_active
    row, so this .first() picked an arbitrary member of the whole history and
    only looked right because Meta.ordering is ["-version"]. The explicit
    order_by here does not depend on that invariant holding.
    """
    return (
        ScenarioVersion.objects.filter(scenario=scenario, is_active=True)
        .order_by("-version")
        .first()
    )


def get_version_history(scenario):
    """
    Returns every recorded version for a scenario, newest first.

    Used by the admin changelog view; kept here so callers do not have to
    reach past the app boundary into the model.
    """
    return ScenarioVersion.objects.filter(scenario=scenario).order_by("-version")
