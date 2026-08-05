"""Live WebSocket push for the MAAS / LXD / KVM bare-metal Lab Environment.

Purely additive: the REST ``GET .../baremetal/state`` polling endpoint keeps
working exactly as before. This consumer lets the frontend drop polling in
favor of a live socket that streams the same state shape.

Protocol (server -> client), JSON text frames:
  {"type": "state", "session_id", "scenario_slug", "state": {...}}
  {"type": "error", "message": "..."}

The socket is read-only from the client's perspective today — any inbound
frames are ignored. State is pushed:
  - immediately on connect,
  - on a ~1.5s tick while any machine is mid wall-clock transition (so
    Commissioning/Deploying/.../rescue progress bars animate live), and
  - whenever another request mutates this session's state (via
    ``baremetal_engine._notify_session`` group-sending ``baremetal.push``).
"""

from __future__ import annotations

import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

PUSH_INTERVAL_SECONDS = 1.5

# Machine statuses that are still advancing on wall-clock — while any machine
# is in one of these, keep pushing every tick so progress bars stay live.
_TRANSIENT_STATUSES = (
    "Commissioning",
    "Deploying",
    "Testing",
    "Releasing",
    "Entering rescue mode",
    "Exiting rescue mode",
)


class BaremetalConsumer(AsyncWebsocketConsumer):
    """AsyncWebsocketConsumer streaming bare-metal Lab Environment state."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.group_name = None
        self._tick_task = None
        self._last_snapshot = None
        self._joined_group = False

    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        session_id = self.scope["url_route"]["kwargs"].get("session_id")
        if not session_id:
            await self.close(code=4004)
            return

        exists = await self._session_exists(session_id)
        if not exists:
            await self.accept()
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Bare metal session not found",
            }))
            await self.close(code=4004)
            return

        self.session_id = str(session_id)
        self.group_name = f"baremetal_{self.session_id}"

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            self._joined_group = True
        except Exception:
            logger.exception("baremetal group_add failed for session %s", self.session_id)

        await self.accept()

        # Push the current snapshot immediately, then start the live tick loop.
        await self._send_state(force=True)
        self._tick_task = asyncio.ensure_future(self._tick_loop())

    async def disconnect(self, close_code):
        if self._tick_task is not None:
            self._tick_task.cancel()
            self._tick_task = None
        if self._joined_group and self.group_name:
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception:
                pass
            self._joined_group = False

    async def receive(self, text_data=None, bytes_data=None):
        # Read-only stream for now; inbound frames are ignored (forward-compatible).
        return

    # ── Group event fan-out (channel-layer -> client) ───────────────────
    async def baremetal_push(self, event):
        await self._send_state(force=True)

    # ── Internal ─────────────────────────────────────────────────────────
    async def _tick_loop(self):
        try:
            while True:
                await asyncio.sleep(PUSH_INTERVAL_SECONDS)
                await self._send_state(force=False)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("baremetal tick loop failed for session %s", self.session_id)

    async def _send_state(self, *, force: bool) -> None:
        try:
            payload = await self._get_state()
        except Exception:
            logger.exception("baremetal get_state failed for session %s", self.session_id)
            return
        if not payload:
            return
        state = payload.get("state") or {}
        transient = self._has_transient_machine(state)
        snapshot = json.dumps(state, default=str, sort_keys=True)
        if not force and not transient and snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot
        try:
            await self.send(text_data=json.dumps({
                "type": "state",
                "session_id": self.session_id,
                "scenario_slug": payload.get("scenario_slug"),
                "state": state,
            }, default=str))
        except Exception:
            logger.exception("baremetal send failed for session %s", self.session_id)

    @staticmethod
    def _has_transient_machine(state: dict) -> bool:
        machines = ((state or {}).get("maas") or {}).get("machines") or []
        return any((m.get("status") in _TRANSIENT_STATUSES) for m in machines)

    @database_sync_to_async
    def _session_exists(self, session_id):
        """Accept when the lab session belongs to this user (cache may not exist yet)."""
        from apps.labs.models import LabSession

        try:
            user = self.scope.get("user")
            if not user or not getattr(user, "is_authenticated", False):
                return False
            return LabSession.objects.filter(pk=session_id, user=user).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _get_state(self):
        from apps.labs.models import LabSession
        from apps.vmware_sim.baremetal_engine import get_state

        slug = ""
        try:
            row = LabSession.objects.select_related("scenario").filter(pk=self.session_id).first()
            if row and row.scenario_id:
                slug = row.scenario.slug or ""
        except Exception:
            pass
        return get_state(self.session_id, slug)
