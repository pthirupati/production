"""Cross-technology bridge: OpenStack Horizon ⇄ Linux lab terminal."""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"openstack_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_resize": None, "instance_power": None}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_resize", None)
    data.setdefault("instance_power", None)
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_instance_resize(session_id: str, size: dict, *, trace_id: str | None = None) -> None:
    data = _load(session_id)
    data["pending_resize"] = {
        "vcpus": int(size.get("vcpus", 2)),
        "ram_gb": int(size.get("ram_gb", 4)),
        "trace_id": trace_id,
    }
    _save(session_id, data)


def consume_pending_resize(session_id: str) -> dict | None:
    data = _load(session_id)
    resize = data.get("pending_resize")
    if not resize:
        return None
    data["pending_resize"] = None
    _save(session_id, data)
    return resize


def record_instance_power(session_id: str, action: str, *, trace_id: str | None = None) -> None:
    if action not in ("start", "stop", "restart"):
        return
    data = _load(session_id)
    data["instance_power"] = action
    _save(session_id, data)
    try:
        from .server_identity import get_primary, set_power
        primary = get_primary(session_id)
        if primary:
            power = "off" if action == "stop" else ("reboot_pending" if action == "restart" else "on")
            set_power(session_id, primary["id"], power, source="openstack", trace_id=trace_id)
    except Exception:
        pass


def consume_power(session_id: str) -> str | None:
    data = _load(session_id)
    action = data.get("instance_power")
    if not action:
        return None
    data.pop("instance_power", None)
    _save(session_id, data)
    return action


def record_disk_attach(
    session_id: str, disk_name: str, *, size_gb: int = 50, device: str = "/dev/vdb",
    trace_id: str | None = None,
) -> None:
    try:
        from .server_identity import attach_disk, get_primary
        primary = get_primary(session_id)
        if primary:
            letter = (device or "/dev/vdb").rstrip("0123456789").split("/")[-1]
            attach_disk(session_id, primary["id"], name=letter or "vdb", size_gb=int(size_gb), source="openstack", trace_id=trace_id)
    except Exception:
        pass
    try:
        from . import aws_bridge
        aws_bridge.record_volume_attach(
            session_id, disk_name, size_gb=size_gb, device=device, trace_id=trace_id,
        )
    except Exception:
        pass


def record_disk_detach(session_id: str, device: str, *, trace_id: str | None = None) -> None:
    try:
        from .server_identity import detach_disk, get_primary
        primary = get_primary(session_id)
        if primary:
            letter = (device or "").rstrip("0123456789").split("/")[-1]
            detach_disk(session_id, primary["id"], name=letter or "vdb", source="openstack", trace_id=trace_id)
    except Exception:
        pass
    try:
        from . import aws_bridge
        aws_bridge.record_volume_detach(session_id, device, trace_id=trace_id)
    except Exception:
        pass
