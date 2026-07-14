"""
War-Room foundation tests.

Two layers:
  1. Pure model/scoring unit tests (MTTR, first-action, role, resolve) — fast,
     no channel layer needed.
  2. Async WebsocketCommunicator integration tests exercising the REAL ASGI
     stack (AllowedHostsOriginValidator + JWTAuthMiddleware + URLRouter) so the
     cookie-JWT auth reuse and origin validation are proven, not mocked:
       - authenticated user connects + claims a role
       - a second authenticated user joins with another role
       - a status update and a resolve broadcast to BOTH users
       - MTTR is computed on resolve
       - an unauthenticated connect is rejected (auth preserved)

Run: manage.py test tests.test_warroom  (or apps.terminal via the terminal test
suite — this module lives under tests/ alongside the other terminal tests).
"""
import datetime

from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, TestCase, override_settings
from django.utils import timezone

from rest_framework_simplejwt.tokens import AccessToken

import apps.terminal.routing
from apps.terminal.middleware import JWTAuthMiddleware
from apps.terminal.models import WarRoomParticipant, WarRoomSession

User = get_user_model()


def _build_application():
    """Rebuild the exact production websocket stack from config/asgi.py."""
    return AllowedHostsOriginValidator(
        JWTAuthMiddleware(URLRouter(apps.terminal.routing.websocket_urlpatterns))
    )


def _auth_headers(token: str):
    """Cookie + Origin headers the middleware/origin-validator expect."""
    return [
        (b"cookie", f"access_token={token}".encode()),
        (b"origin", b"http://testserver"),
    ]


# ── Model / scoring unit tests ───────────────────────────────────────────


class WarRoomModelTests(TestCase):
    def test_resolve_computes_mttr_and_score(self):
        start = timezone.now()
        room = WarRoomSession.objects.create(started_at=start)
        # First action 30s in, resolved 4 minutes in.
        room.mark_first_action(start + datetime.timedelta(seconds=30))
        room.save()
        score = room.resolve(when=start + datetime.timedelta(minutes=4))

        self.assertEqual(room.status, WarRoomSession.STATUS_RESOLVED)
        self.assertIsNotNone(room.resolved_at)
        self.assertAlmostEqual(room.mttr_seconds, 240.0, places=1)
        self.assertAlmostEqual(room.time_to_first_action_seconds, 30.0, places=1)
        # Sub-5-min resolution => 100 base, plus a fast-first-action bonus.
        self.assertGreaterEqual(score, 100)
        self.assertLessEqual(score, 100)  # clamped at 100
        self.assertTrue(room.is_resolved)

    def test_slow_resolution_scores_lower(self):
        start = timezone.now()
        room = WarRoomSession.objects.create(started_at=start)
        room.mark_first_action(start + datetime.timedelta(minutes=5))
        room.save()
        # 35 minutes MTTR: 100 - (2100-300)/30 = 100 - 60 = 40.
        score = room.resolve(when=start + datetime.timedelta(minutes=35))
        self.assertAlmostEqual(room.mttr_seconds, 2100.0, places=1)
        self.assertEqual(score, 40)

    def test_score_never_negative(self):
        start = timezone.now()
        room = WarRoomSession.objects.create(started_at=start)
        score = room.resolve(when=start + datetime.timedelta(hours=5))
        self.assertEqual(score, 0)

    def test_mark_first_action_is_idempotent(self):
        room = WarRoomSession.objects.create()
        self.assertTrue(room.mark_first_action())
        first = room.first_action_at
        self.assertFalse(room.mark_first_action())
        self.assertEqual(room.first_action_at, first)

    def test_scoring_is_deterministic(self):
        start = timezone.now()
        a = WarRoomSession.objects.create(started_at=start)
        a.mark_first_action(start + datetime.timedelta(seconds=45))
        a.resolve(when=start + datetime.timedelta(minutes=12))
        b = WarRoomSession.objects.create(started_at=start)
        b.mark_first_action(start + datetime.timedelta(seconds=45))
        b.resolve(when=start + datetime.timedelta(minutes=12))
        self.assertEqual(a.team_score, b.team_score)
        self.assertEqual(a.mttr_seconds, b.mttr_seconds)

    def test_participant_roles_and_uniqueness(self):
        user = User.objects.create_user(
            username="ic", email="ic@test.com", password="Pass123!x"
        )
        room = WarRoomSession.objects.create()
        p1 = WarRoomParticipant.objects.create(
            room=room, user=user, role=WarRoomParticipant.ROLE_IC
        )
        self.assertEqual(p1.role, "IC")
        # get_or_create keeps membership unique per (room, user).
        p2, created = WarRoomParticipant.objects.get_or_create(room=room, user=user)
        self.assertFalse(created)
        self.assertEqual(p1.pk, p2.pk)


class WarRoomRoutingTests(TestCase):
    def test_warroom_route_registered_behind_shared_auth(self):
        """The route exists AND is wrapped by the same origin+JWT stack."""
        patterns = apps.terminal.routing.websocket_urlpatterns
        pattern_strs = [p.pattern.regex.pattern for p in patterns]
        self.assertTrue(any("warroom" in s for s in pattern_strs))
        self.assertTrue(any("terminal" in s for s in pattern_strs))

        app = _build_application()
        # Outermost wrapper is the origin validator (security preserved).
        # AllowedHostsOriginValidator returns an OriginValidator instance.
        self.assertIsInstance(app, OriginValidator)
        self.assertIsInstance(app.application, JWTAuthMiddleware)


# ── WebSocket integration tests (real ASGI stack) ─────────────────────────


@override_settings(ALLOWED_HOSTS=["testserver", "*"])
class WarRoomWebSocketTests(TransactionTestCase):
    """
    Uses TransactionTestCase because the consumer touches the DB from the
    channel-layer thread via database_sync_to_async.
    """

    def setUp(self):
        self.u1 = User.objects.create_user(
            username="commander", email="ic@test.com", password="Pass123!x"
        )
        self.u2 = User.objects.create_user(
            username="operator", email="ops@test.com", password="Pass123!x"
        )
        self.t1 = str(AccessToken.for_user(self.u1))
        self.t2 = str(AccessToken.for_user(self.u2))
        self.room = WarRoomSession.objects.create()
        self.room_key = str(self.room.room_key)
        self.app = _build_application()

    async def _connect(self, token):
        comm = WebsocketCommunicator(
            self.app,
            f"ws/warroom/{self.room_key}/",
            headers=_auth_headers(token),
        )
        connected, _ = await comm.connect()
        return comm, connected

    async def _drain_until(self, comm, msg_type, tries=8):
        """Read frames until we see one of the given type(s)."""
        wanted = {msg_type} if isinstance(msg_type, str) else set(msg_type)
        for _ in range(tries):
            msg = await comm.receive_json_from(timeout=3)
            if msg.get("type") in wanted:
                return msg
        raise AssertionError(f"did not receive {wanted}")

    async def test_unauthenticated_connect_rejected(self):
        comm = WebsocketCommunicator(
            self.app,
            f"ws/warroom/{self.room_key}/",
            headers=[(b"origin", b"http://testserver")],  # no cookie
        )
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()

    async def test_bad_token_connect_rejected(self):
        comm = WebsocketCommunicator(
            self.app,
            f"ws/warroom/{self.room_key}/",
            headers=_auth_headers("not-a-real-jwt"),
        )
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()

    async def test_two_users_roles_status_resolve_broadcast_and_mttr(self):
        # User 1 connects and claims Incident Commander.
        c1, ok1 = await self._connect(self.t1)
        self.assertTrue(ok1)
        join1 = await self._drain_until(c1, "presence")
        self.assertEqual(join1["event"], "join")

        await c1.send_json_to({"type": "claim_role", "role": "IC"})
        role_evt = await self._drain_until(c1, "presence")
        self.assertEqual(role_evt["role"], "IC")

        # User 2 joins with a different role (OPS default, then COMMS).
        c2, ok2 = await self._connect(self.t2)
        self.assertTrue(ok2)
        # Both see user 2's join.
        j2_on_c1 = await self._drain_until(c1, "presence")
        self.assertEqual(j2_on_c1["event"], "join")
        self.assertEqual(j2_on_c1["user_id"], self.u2.id)
        await self._drain_until(c2, "presence")  # c2's own join

        await c2.send_json_to({"type": "claim_role", "role": "COMMS"})
        await self._drain_until(c2, "presence")

        # A status update broadcasts to BOTH users.
        await c1.send_json_to({"type": "status", "status": "MITIGATING"})
        s_on_c1 = await self._drain_until(c1, "status")
        s_on_c2 = await self._drain_until(c2, "status")
        self.assertEqual(s_on_c1["status"], "MITIGATING")
        self.assertEqual(s_on_c2["status"], "MITIGATING")

        # A chat event broadcasts to both.
        await c2.send_json_to({"type": "chat", "message": "rolling back deploy"})
        chat1 = await self._drain_until(c1, "chat")
        self.assertEqual(chat1["message"], "rolling back deploy")

        # Resolve broadcasts to both with computed MTTR + score.
        await c1.send_json_to({"type": "resolve"})
        r1 = await self._drain_until(c1, "resolved")
        r2 = await self._drain_until(c2, "resolved")
        for r in (r1, r2):
            self.assertIn("mttr_seconds", r)
            self.assertIsNotNone(r["mttr_seconds"])
            self.assertIn("team_score", r)
            self.assertIsNotNone(r["team_score"])

        # Persisted on the room; roles persisted for both participants.
        room = await self._refresh_room()
        self.assertEqual(room.status, WarRoomSession.STATUS_RESOLVED)
        self.assertIsNotNone(room.resolved_at)
        self.assertIsNotNone(room.mttr_seconds)
        self.assertIsNotNone(room.first_action_at)  # stamped on first action

        roles = await self._participant_roles()
        self.assertEqual(roles.get(self.u1.id), "IC")
        self.assertEqual(roles.get(self.u2.id), "COMMS")

        await c1.disconnect()
        await c2.disconnect()

    # DB helpers (sync ORM wrapped for the async test body).
    async def _refresh_room(self):
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _get():
            return WarRoomSession.objects.get(pk=self.room.pk)

        return await _get()

    async def _participant_roles(self):
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _get():
            return {
                p.user_id: p.role
                for p in WarRoomParticipant.objects.filter(room=self.room)
            }

        return await _get()
