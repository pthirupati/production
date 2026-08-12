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
from channels.exceptions import StopConsumer
from channels.utils import await_many_dispatch
from django.contrib.auth.models import AnonymousUser

from common.ws_slots import acquire_ws_slot, release_ws_slot

logger = logging.getLogger(__name__)

PUSH_INTERVAL_SECONDS = 1.5

# Audit Z5-6. The tick loop exists for one reason: to animate wall-clock progress
# while a machine is Commissioning/Deploying/etc. Every other state change already
# arrives instantly over the channel layer (`baremetal_engine._notify_session` →
# `baremetal_push`), so polling an idle session buys nothing.
#
# It cost plenty, though: `_get_state()` is a select_related query plus a Redis get
# on every tick, and the snapshot comparison suppressed the *send*, not the *work*.
# 100 idle sockets meant 4,000 DB queries a minute on a 2-vCPU box, sending nothing.
#
# So an idle socket backs off geometrically to IDLE_MAX_INTERVAL_SECONDS and snaps
# straight back to PUSH_INTERVAL_SECONDS the moment anything is transient. Nothing
# is lost by backing off: the push path is authoritative and immediate.
IDLE_MAX_INTERVAL_SECONDS = 30.0
IDLE_BACKOFF_FACTOR = 2.0

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

    async def __call__(self, scope, receive, send):
        """Always release the per-user WS slot, even if `disconnect()` never runs.

        Modelled on `TerminalConsumer.__call__` (audit Z5-6): an abrupt drop skips
        `disconnect`, and without this the slot leaks until its cache TTL expires —
        so a user who reconnects through a flaky network locks themselves out.
        """
        self.scope = scope
        self.base_send = send
        try:
            await await_many_dispatch([receive], self.dispatch)
        except StopConsumer:
            pass
        finally:
            self._release_connection_slot()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.group_name = None
        self._tick_task = None
        self._last_snapshot = None
        self._joined_group = False
        self._tracked_user_id = None
        self._tick_interval = PUSH_INTERVAL_SECONDS

    def _release_connection_slot(self) -> None:
        user_id = self._tracked_user_id
        if user_id is None:
            return
        self._tracked_user_id = None   # cleared first, so a repeat call is a no-op
        release_ws_slot(user_id)

    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Same per-user cap as the terminal. Without it one account could open
        # unlimited sockets, each with its own polling loop.
        if not acquire_ws_slot(user.id):
            await self.close(code=4008)
            return
        self._tracked_user_id = user.id

        session_id = self.scope["url_route"]["kwargs"].get("session_id")
        if not session_id:
            self._release_connection_slot()
            await self.close(code=4004)
            return

        exists = await self._session_exists(session_id)
        if not exists:
            await self.accept()
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Bare metal session not found",
            }))
            self._release_connection_slot()
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
        self._release_connection_slot()
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
                await asyncio.sleep(self._tick_interval)
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

        # Pace the *work*, not just the send. A machine mid-transition needs the
        # fast tick for its progress bar; an unchanged idle session does not, and
        # any real mutation reaches us over the channel layer regardless.
        if transient:
            self._tick_interval = PUSH_INTERVAL_SECONDS
        elif snapshot == self._last_snapshot:
            self._tick_interval = min(
                self._tick_interval * IDLE_BACKOFF_FACTOR, IDLE_MAX_INTERVAL_SECONDS
            )
        else:
            self._tick_interval = PUSH_INTERVAL_SECONDS

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
