#!/usr/bin/env python3
"""Standalone E2E smoke for datacenter twin (no Django settings required).

Usage:
  python3 scripts/smoke_datacenter_e2e.py
"""

from __future__ import annotations

import json
import sys
import types
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

_store: dict[str, str] = {}


class _Cache:
    def get(self, key):
        return _store.get(key)

    def set(self, key, value, timeout=None):
        _store[key] = value

    def delete(self, key):
        _store.pop(key, None)

    def clear(self):
        _store.clear()


django = types.ModuleType("django")
django_core = types.ModuleType("django.core")
django_cache_mod = types.ModuleType("django.core.cache")
django_cache_mod.cache = _Cache()
sys.modules["django"] = django
sys.modules["django.core"] = django_core
sys.modules["django.core.cache"] = django_cache_mod


def _ok(dc, sid, action, payload=None):
    res = dc.apply_action(sid, action, payload or {})
    if not res.get("ok"):
        raise SystemExit(f"FAIL {action}: {res}")
    extra = f" · {payload.get('op')}" if payload and payload.get("op") else ""
    print(f"  ok  {action}{extra}")
    return res


def main() -> int:
    from apps.vmware_sim import datacenter_engine as dc

    _store.clear()
    sid = str(uuid.uuid4())
    print(f"Datacenter E2E smoke · session {sid[:8]}…")

    state = dc.get_state(sid)["state"]
    assert state.get("rooms"), "rooms missing"
    assert state.get("change_calendar"), "change_calendar missing"
    assert state.get("burnin"), "burnin missing"
    assert state.get("exporters"), "exporters missing"
    print("  ok  get_state bootstrap")

    _ok(dc, sid, "login", {"user": "tech"})
    _ok(dc, sid, "enter_room", {"room_id": "data-hall-a"})
    asset = (state.get("broken") or {}).get("server") or "srv-r01-u14"
    _ok(dc, sid, "select_asset", {"asset_id": asset})
    _ok(dc, sid, "open_bmc", {"asset_id": asset})
    _ok(dc, sid, "bmc_power", {"asset_id": asset, "mode": "cycle"})

    _ok(dc, sid, "enter_room", {"room_id": "noc"})
    _ok(dc, sid, "refresh_monitoring")
    tick = _ok(dc, sid, "live_tick")
    assert (tick.get("environmental") or {}).get("tick", 0) >= 1

    _ok(dc, sid, "change_ops", {"op": "enable_freeze", "reason": "E2E freeze"})
    blocked = dc.apply_action(sid, "power_cycle", {"asset_id": asset})
    assert not blocked.get("ok"), "freeze should block power_cycle"
    print("  ok  freeze blocks power_cycle")
    _ok(dc, sid, "change_ops", {"op": "disable_freeze"})

    _ok(dc, sid, "dr_ops", {"op": "utility_fail"})
    _ok(dc, sid, "dr_ops", {"op": "start_generator"})
    _ok(dc, sid, "access_ops", {"op": "badge_in", "badge_id": "BADGE-1001"})
    _ok(dc, sid, "automation_ops", {"op": "run", "runbook_id": "rb-dr-tabletop"})
    _ok(dc, sid, "generate_ops_report")

    state = dc.get_state(sid)["state"]
    mid = ((state.get("burnin") or {}).get("machines") or [{}])[0].get("id")
    assert mid, "no burn-in machine"
    _ok(dc, sid, "burnin_ops", {"op": "attach_load_bank", "machine_id": mid})
    _ok(dc, sid, "burnin_ops", {"op": "soak", "machine_id": mid})

    _ok(dc, sid, "exporter_ops", {"op": "snmp_walk"})
    _ok(dc, sid, "generate_evidence")
    _ok(dc, sid, "environmental_ops", {"op": "normalize"})
    _ok(dc, sid, "containment_ops", {"op": "toggle_door", "aisle_id": "CA-A"})
    _ok(dc, sid, "cable_plant_ops", {"op": "add_fill", "tray_id": "TRAY-EW-1", "delta": 5})
    _ok(dc, sid, "motherboard_ops", {"asset_id": asset, "op": "pulse_buses"})

    replay = _ok(dc, sid, "replay_twin_journal")
    assert (replay.get("replayed") or 0) >= 1, f"replay expected: {replay}"

    final = dc.get_state(sid)["state"]
    assert final.get("sustainability"), "sustainability missing"
    assert final.get("evidence_pack") or final.get("doc_library"), "evidence missing"
    print(json.dumps({
        "replayed": replay.get("replayed"),
        "skipped": replay.get("skipped"),
        "pue": (final.get("sustainability") or {}).get("pue"),
        "wue": (final.get("sustainability") or {}).get("wue"),
        "evidence": (final.get("evidence_pack") or {}).get("id"),
        "live_ticks": (final.get("environmental") or {}).get("tick"),
    }, indent=2))
    print("PASS datacenter E2E lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
