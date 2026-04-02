from .models import ScenarioVersion

def get_active_version(scenario):
    """
    Returns the active version for a scenario.
    """
    return ScenarioVersion.objects.filter(
        scenario=scenario,
        is_active=True
    ).first()

