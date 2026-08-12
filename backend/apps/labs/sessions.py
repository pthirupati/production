"""Programmatic lab-session start (capacity-gated).

Audit L1506/L1511. ``start_lab_session`` used to be a plain
"INSERT then provision" helper that never consulted
``apps.labs.capacity.at_global_capacity``, so *any* caller of it silently
bypassed the platform-wide ``MAX_CONCURRENT_LABS`` ceiling. Both known call
paths (``public_api.views.StartLabView`` and
``interviews.services.practical_lab.start_practical_lab``) were rewritten to
create the row themselves under the capacity lock, which left this function with
no callers at all — but an ungated session factory sitting in a shared module is
a bypass waiting to be re-imported by the next caller who wants "just start a
lab". So it gates rather than being deleted: reintroducing it cannot reintroduce
the hole.
"""
import logging

from django.db import transaction

from .capacity import at_global_capacity, get_max_concurrent_labs
from .infra import lab_infra_type
from .models import LabSession
from .provisioner import get_provisioner

logger = logging.getLogger(__name__)


class LabCapacityError(RuntimeError):
    """Raised when a start is shed because the platform is at its lab ceiling.

    A distinct type (rather than a generic exception) so callers can map it to a
    503/"try again shortly" instead of the 500 an unclassified provisioning
    failure would produce.
    """


def reserve_lab_session(user, scenario) -> LabSession:
    """Claim a capacity slot and INSERT the ``LabSession`` row, atomically.

    The capacity check and the INSERT are in ONE ``transaction.atomic()`` block
    on purpose: ``at_global_capacity`` takes a transaction-scoped advisory lock
    and re-counts live sessions under it, and holding that lock through the
    INSERT is what makes "count < cap ⇒ create" atomic. Split them and two
    concurrent starts at ``cap - 1`` both read "under cap" and both insert.

    Deliberately does NO network I/O — see ``provision_reserved_session``.

    Raises ``LabCapacityError`` if the platform is at the ceiling; no row is
    created in that case.
    """
    infra_type = lab_infra_type(scenario)

    with transaction.atomic():
        if at_global_capacity(infra_type):
            raise LabCapacityError(
                f"Global lab capacity reached ({get_max_concurrent_labs()} concurrent "
                f"labs); refusing to start a new {infra_type} lab."
            )

        return LabSession.objects.create(
            user=user,
            scenario=scenario,
            status="PROVISIONING",
            provider=infra_type,
        )


def provision_reserved_session(session: LabSession) -> LabSession:
    """Provision a ``LabSession`` row that already holds a capacity slot.

    The provisioning half of ``start_lab_session``, split out so it runs
    strictly OUTSIDE the atomic block that holds the capacity advisory lock:
    ``provisioner.provision()`` does SSH/API round trips, and holding a
    platform-wide lock across that would serialise every lab start on the
    platform behind the slowest provision (see the same rationale at
    ``public_api/views.py``).

    On failure the session is marked FAILED (a terminal status), which releases
    its capacity slot — ``count_active_engine_labs`` only counts
    RUNNING/PROVISIONING — before the exception propagates to the caller.
    """
    infra_type = session.provider

    try:
        provisioner = get_provisioner(infra_type)
        resource_id, resource_name = provisioner.provision(session)

        if infra_type == "docker":
            session.container_id = resource_id
            session.container_name = resource_name
        else:
            session.instance_id = resource_id

        session.status = "RUNNING"
        session.save()
        logger.info("Lab session %s provisioned: %s (%s)", session.id, resource_name, infra_type)
    except Exception as exc:
        session.status = "FAILED"
        session.save()
        logger.error("Failed to provision lab session %s: %s", session.id, exc)
        raise

    return session


def start_lab_session(user, scenario):
    """
    Create a lab session and provision infrastructure.
    Handles Docker, AWS EC2, DigitalOcean, and simulation labs.

    Utility entry point for programmatic use (shell, management commands). The
    request paths do NOT go through here — ``StartLabView`` and the interview
    practical-lab bridge inline the same two phases because they interleave
    their own checks and responses between them.

    Subject to the platform-wide ``MAX_CONCURRENT_LABS`` ceiling: raises
    ``LabCapacityError`` (before creating any row) when the platform is full.
    Note this is the *global* ceiling only — it does not apply the per-user /
    entitlement gates in ``apps.labs.start_gates.lab_start_block_reason``, which
    a request path must still call for itself.
    """
    session = reserve_lab_session(user, scenario)
    return provision_reserved_session(session)
