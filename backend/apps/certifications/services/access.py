"""Certification-track access helpers.

Cert scenarios live in ``question_bank`` like any other lab. A learner may
reach them via the certification track *or* the base technology. Access is
granted when any linked track is free, the user holds an active cert-track
subscription, or they already have the base technology subscription.
"""

from django.utils import timezone

from apps.billing.subscription_utils import get_subscribed_technology_ids
from apps.certifications.models import CertificationTrack, CertificationTrackSubscription, TrackScenario


def _user_has_technology_sub(user, technology_id) -> bool:
    if not user or not user.is_authenticated or not technology_id:
        return False
    if getattr(user, "is_staff", False):
        return True
    return int(technology_id) in get_subscribed_technology_ids(user)


def tracks_for_scenario(scenario_id):
    """Active certification tracks that include this scenario."""
    return CertificationTrack.objects.filter(
        is_active=True,
        objectives__track_scenarios__scenario_id=scenario_id,
    ).distinct()


def user_has_cert_scenario_access(user, scenario) -> bool:
    """True when the scenario is cert-mapped and the user may run it via a track."""
    track_ids = list(
        TrackScenario.objects.filter(scenario_id=scenario.id)
        .values_list("objective__track_id", flat=True)
        .distinct()
    )
    if not track_ids:
        return False

    tracks = CertificationTrack.objects.filter(id__in=track_ids, is_active=True)
    if tracks.filter(is_free=True).exists():
        return True

    if not user or not user.is_authenticated:
        return False

    now = timezone.now()
    if CertificationTrackSubscription.objects.filter(
        user=user,
        track_id__in=track_ids,
        is_active=True,
        expires_at__gt=now,
    ).exists():
        return True

    # Base technology subscription unlocks cert-mapped labs for linked tracks.
    for track in tracks:
        if track.technology_id and _user_has_technology_sub(user, track.technology_id):
            return True
    return False


def user_has_cert_track_access(user, track) -> bool:
    """True when the user may start the timed mock exam for this track."""
    if not track or not track.is_active:
        return False
    if track.is_free:
        return True
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    now = timezone.now()
    if CertificationTrackSubscription.objects.filter(
        user=user,
        track=track,
        is_active=True,
        expires_at__gt=now,
    ).exists():
        return True

    # Linked technology subscription includes cert labs + mock exam (addon bundled at subscribe).
    if track.technology_id and _user_has_technology_sub(user, track.technology_id):
        return True
    return False


def effective_cert_prices(track):
    """Return standalone, addon, and bundled INR prices for admin/UI display."""
    tech = track.technology
    tech_price = int(getattr(tech, "price", 0) or 0) if tech else 0
    standalone = 0 if track.is_free else int(track.price or 0)
    addon = 0 if track.is_free else int(getattr(track, "addon_price", 0) or 0)
    bundled = addon if addon > 0 else standalone
    if tech_price and bundled:
        bundled = tech_price + addon if addon > 0 else max(standalone, tech_price)
    return {
        "technology_price": tech_price,
        "standalone_price": standalone,
        "addon_price": addon,
        "bundled_price": bundled,
    }
