"""
Multiplayer War-Room consumer (foundation).

Collaborative incident response layered on the existing Channels/WebSocket
infra. Multiple authenticated users join a room keyed by a WarRoomSession UUID
and share an event stream (presence, chat, status, command log) via a Channels
group. Auth + origin validation are reused verbatim from the terminal path:
this consumer is mounted behind the SAME AllowedHostsOriginValidator +
JWTAuthMiddleware in config/asgi.py (see routing.py), and it re-checks
`scope["user"].is_authenticated` on connect just like TerminalConsumer.

This is the FOUNDATION: a shared event stream + one "driver". It intentionally
does NOT multiplex N users into a single PTY (that's future work) — the terminal
remains strictly single-user. Nothing here alters TerminalConsumer.

Protocol (client -> server), JSON text frames:
  {"type": "claim_role", "role": "IC"|"OPS"|"COMMS"|"SCRIBE"}
  {"type": "status",     "status": "INVESTIGATING"|"MITIGATING"|"ACTIVE"}
  {"type": "chat",       "message": "..."}
  {"type": "command_log","command": "..."}     # shared timeline of driver actions
  {"type": "resolve"}                            # stamps resolved_at + scores

Server -> client broadcasts (to the whole group):
  {"type": "presence", "event": "join"|"leave"|"role", "user_id", "username",
   "role", "participants": [...]}
  {"type": "status",   "status", "user_id", "username"}
  {"type": "chat",     "message", "user_id", "username"}
  {"type": "command_log", "command", "user_id", "username"}
  {"type": "resolved", "mttr_seconds", "time_to_first_action_seconds",
   "team_score", "user_id", "username"}
"""
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

# Sane cap on concurrent participants per room (foundation safety limit).
MAX_PARTICIPANTS_PER_ROOM = 12

# Client message types that count as a "first action" for MTTR purposes.
_ACTION_TYPES = {"status", "command_log", "resolve", "claim_role"}


class WarRoomConsumer(AsyncWebsocketConsumer):
    """AsyncWebsocketConsumer for a shared incident war-room."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room = None
        self.room_key = None
        self.group_name = None
        self.role = None
        self._joined_group = False

    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        room_key = self.scope["url_route"]["kwargs"].get("room_key")

        # Auth is enforced identically to the terminal consumer. The middleware
        # (JWTAuthMiddleware) has already populated scope["user"]; anonymous is
        # rejected with the same close code the terminal uses.
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.room = await self._get_or_create_room(room_key)
        if not self.room:
            await self.close(code=4004)
            return

        self.room_key = str(self.room.room_key)
        self.group_name = self._group_name(self.room_key)

        # Enforce a sane participant cap. Rejoining users (already a participant)
        # don't count against a full room.
        already_member = await self._is_member(self.room, user)
        if not already_member:
            count = await self._participant_count(self.room)
            if count >= MAX_PARTICIPANTS_PER_ROOM:
                logger.warning("WarRoom %s full (%s)", self.room_key, count)
                await self.close(code=4008)
                return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        self._joined_group = True

        await self.accept()

        # Default role on join is OPS; may be re-claimed. Persist membership.
        self.role = await self._ensure_participant(self.room, user)

        participants = await self._participant_list(self.room)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "wr.presence",
                "event": "join",
                "user_id": user.id,
                "username": self._username(user),
                "role": self.role,
                "participants": participants,
            },
        )

    async def disconnect(self, close_code):
        if not self._joined_group or not self.group_name:
            return
        user = self.scope.get("user", AnonymousUser())
        participants = await self._participant_list(self.room) if self.room else []
        try:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "wr.presence",
                    "event": "leave",
                    "user_id": getattr(user, "id", None),
                    "username": self._username(user),
                    "role": self.role,
                    "participants": participants,
                },
            )
        finally:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            self._joined_group = False

    async def receive(self, text_data=None, bytes_data=None):
        user = self.scope.get("user", AnonymousUser())
        if not user.is_authenticated or not self.room:
            return
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return

        msg_type = data.get("type")

        # The first meaningful action stamps the MTTR first-action clock.
        if msg_type in _ACTION_TYPES:
            await self._maybe_stamp_first_action(self.room)

        if msg_type == "claim_role":
            await self._handle_claim_role(user, data)
        elif msg_type == "status":
            await self._handle_status(user, data)
        elif msg_type == "chat":
            await self._handle_chat(user, data)
        elif msg_type == "command_log":
            await self._handle_command_log(user, data)
        elif msg_type == "resolve":
            await self._handle_resolve(user)
        # Unknown types are ignored (forward-compatible).

    # ── Message handlers ────────────────────────────────────────────────

    async def _handle_claim_role(self, user, data):
        from apps.terminal.models import WarRoomParticipant

        role = (data.get("role") or "").upper()
        if role not in WarRoomParticipant.VALID_ROLES:
            return
        self.role = await self._set_role(self.room, user, role)
        participants = await self._participant_list(self.room)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "wr.presence",
                "event": "role",
                "user_id": user.id,
                "username": self._username(user),
                "role": self.role,
                "participants": participants,
            },
        )

    async def _handle_status(self, user, data):
        from apps.terminal.models import WarRoomSession

        status = (data.get("status") or "").upper()
        if status not in WarRoomSession.OPEN_STATUSES:
            return
        await self._set_status(self.room, status)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "wr.status",
                "status": status,
                "user_id": user.id,
                "username": self._username(user),
            },
        )

    async def _handle_chat(self, user, data):
        message = (data.get("message") or "").strip()
        if not message:
            return
        # Cap message size to keep the shared stream sane.
        message = message[:2000]
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "wr.chat",
                "message": message,
                "user_id": user.id,
                "username": self._username(user),
            },
        )

    async def _handle_command_log(self, user, data):
        command = (data.get("command") or "").strip()
        if not command:
            return
        command = command[:2000]
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "wr.command_log",
                "command": command,
                "user_id": user.id,
                "username": self._username(user),
            },
        )

    async def _handle_resolve(self, user):
        scores = await self._resolve_room(self.room)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "wr.resolved",
                "user_id": user.id,
                "username": self._username(user),
                **scores,
            },
        )

    # ── Group event fan-out (channel-layer -> client) ───────────────────

    async def wr_presence(self, event):
        await self._emit(event)

    async def wr_status(self, event):
        await self._emit(event)

    async def wr_chat(self, event):
        await self._emit(event)

    async def wr_command_log(self, event):
        await self._emit(event)

    async def wr_resolved(self, event):
        await self._emit(event)

    async def _emit(self, event):
        payload = {k: v for k, v in event.items() if k != "type"}
        # Re-add a client-facing type derived from the channel-layer handler.
        payload["type"] = event["type"].split(".", 1)[-1]
        await self.send(text_data=json.dumps(payload))

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _group_name(room_key):
        # Channels group names must be <100 chars and use a limited charset.
        return f"warroom_{str(room_key).replace('-', '')}"

    @staticmethod
    def _username(user):
        return getattr(user, "username", None) or getattr(user, "email", "") or str(
            getattr(user, "id", "")
        )

    # ── DB access (sync -> async) ───────────────────────────────────────

    @database_sync_to_async
    def _get_or_create_room(self, room_key):
        from django.core.exceptions import ValidationError

        from apps.terminal.models import WarRoomSession

        if not room_key:
            return None
        try:
            return WarRoomSession.objects.get(room_key=room_key)
        except WarRoomSession.DoesNotExist:
            # Foundation: auto-create the room on first join so a team can
            # rally around any incident id without a separate provisioning step.
            try:
                return WarRoomSession.objects.create(room_key=room_key)
            except Exception:
                return None
        except (ValueError, ValidationError):
            # Malformed room key (not a valid UUID) — reject the connection.
            return None

    @database_sync_to_async
    def _is_member(self, room, user):
        from apps.terminal.models import WarRoomParticipant

        return WarRoomParticipant.objects.filter(room=room, user=user).exists()

    @database_sync_to_async
    def _participant_count(self, room):
        return room.participants.count()

    @database_sync_to_async
    def _ensure_participant(self, room, user):
        from apps.terminal.models import WarRoomParticipant

        obj, _ = WarRoomParticipant.objects.get_or_create(
            room=room,
            user=user,
            defaults={"role": WarRoomParticipant.ROLE_OPS},
        )
        return obj.role

    @database_sync_to_async
    def _set_role(self, room, user, role):
        from apps.terminal.models import WarRoomParticipant

        obj, _ = WarRoomParticipant.objects.get_or_create(
            room=room, user=user, defaults={"role": role}
        )
        if obj.role != role:
            obj.role = role
            obj.save(update_fields=["role"])
        return obj.role

    @database_sync_to_async
    def _set_status(self, room, status):
        from apps.terminal.models import WarRoomSession

        room.refresh_from_db(fields=["status", "resolved_at"])
        # Never override a resolved room with an open status.
        if room.status == WarRoomSession.STATUS_RESOLVED:
            return room.status
        room.status = status
        room.save(update_fields=["status"])
        return status

    @database_sync_to_async
    def _participant_list(self, room):
        from apps.terminal.models import WarRoomParticipant

        rows = (
            WarRoomParticipant.objects.filter(room=room)
            .select_related("user")
            .order_by("joined_at")
        )
        return [
            {
                "user_id": p.user_id,
                "username": self._username(p.user),
                "role": p.role,
            }
            for p in rows
        ]

    @database_sync_to_async
    def _maybe_stamp_first_action(self, room):
        room.refresh_from_db(fields=["first_action_at", "started_at"])
        if room.mark_first_action():
            room.save(update_fields=["first_action_at"])

    @database_sync_to_async
    def _resolve_room(self, room):
        from apps.terminal.models import WarRoomSession

        room.refresh_from_db()
        if room.status == WarRoomSession.STATUS_RESOLVED and room.resolved_at:
            # Idempotent: return the already-computed scores.
            return {
                "mttr_seconds": room.mttr_seconds,
                "time_to_first_action_seconds": room.time_to_first_action_seconds,
                "team_score": room.team_score,
            }
        room.resolve()
        room.save(
            update_fields=[
                "status",
                "resolved_at",
                "mttr_seconds",
                "time_to_first_action_seconds",
                "team_score",
            ]
        )
        return {
            "mttr_seconds": room.mttr_seconds,
            "time_to_first_action_seconds": room.time_to_first_action_seconds,
            "team_score": room.team_score,
        }
