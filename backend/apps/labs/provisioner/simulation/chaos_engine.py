"""Small shared fault-injection helper for lab consoles.

Several consoles (physical datacenter, lab terminal, network labs) want a
quick, uniform way to inject and track "chaos" style faults — trip a PDU
breaker, drop a NIC, fill a disk, kill a service, spike a temperature sensor —
without each engine hand-rolling its own cache bookkeeping. This module is the
single place those faults live for a session, so any console can list or
clear what is currently broken.

Everything is in-memory (Django cache / Redis backed); nothing here touches
real hardware or processes.
"""

from __future__ import annotations

import time
import uuid

from django.core.cache import cache

FAULT_TTL = 7200

VALID_FAULT_TYPES = frozenset({
    "drop_nic",
    "fill_disk",
    "stop_service",
    "trip_pdu",
    "raise_temp",
})


def _key(session_id: str) -> str:
    return f"chaos:{session_id}"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load(session_id: str) -> list[dict]:
    return list(cache.get(_key(str(session_id))) or [])


def _save(session_id: str, faults: list[dict]) -> None:
    cache.set(_key(str(session_id)), faults, FAULT_TTL)


def inject(session_id: str, fault_type: str, target: str, *, detail: dict | None = None) -> dict:
    """Record a fault injection and return the stored fault record.

    ``fault_type`` must be one of ``drop_nic``, ``fill_disk``, ``stop_service``,
    ``trip_pdu``, ``raise_temp``. ``target`` identifies the affected asset
    (server id, NIC name, PDU id, etc).
    """
    if fault_type not in VALID_FAULT_TYPES:
        raise ValueError(
            f"Unknown fault_type {fault_type!r}; expected one of {sorted(VALID_FAULT_TYPES)}"
        )
    faults = _load(session_id)
    fault = {
        "id": uuid.uuid4().hex[:10],
        "fault_type": fault_type,
        "target": target,
        "detail": detail or {},
        "time": _now_iso(),
        "active": True,
    }
    faults.insert(0, fault)
    _save(session_id, faults)
    return fault


def list_faults(session_id: str, *, active_only: bool = False) -> list[dict]:
    faults = _load(session_id)
    if active_only:
        return [f for f in faults if f.get("active")]
    return faults


def clear_faults(session_id: str, *, fault_type: str | None = None, target: str | None = None) -> int:
    """Deactivate faults matching the given filters (or all active faults when
    no filter is given). Returns the number of faults cleared."""
    faults = _load(session_id)
    cleared = 0
    for fault in faults:
        if not fault.get("active"):
            continue
        if fault_type and fault.get("fault_type") != fault_type:
            continue
        if target and fault.get("target") != target:
            continue
        fault["active"] = False
        cleared += 1
    _save(session_id, faults)
    return cleared


def drop_session(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
