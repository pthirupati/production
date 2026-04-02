from .models import Hint

def get_next_hint(scenario, used_hint_orders=None):
    """
    Returns the next available hint for a scenario.
    """
    if used_hint_orders is None:
        used_hint_orders = []

    return Hint.objects.filter(
        scenario=scenario,
        is_active=True
    ).exclude(order__in=used_hint_orders).order_by("order").first()

