"""
Regression tests for JWT session-enforcement robustness.

These guard the production outage where, at the end of every deploy, flipping
JWT_SESSION_ENFORCEMENT back on logged every real user out:

  * a refreshed/rotated access token carries a brand-new jti that was never
    recorded in SessionTracker → 401 "session invalidated" → forced logout;
  * a backend restart / cache flush left the tracker empty → every live token
    was rejected.

They also cover the runtime enforcement toggle (so CI/E2E never has to restart
the live backend or rewrite .env) and the multi-session model.

Run in the standard suite (no RUN_EXTENDED_TESTS gate) so they protect the green
pipeline.
"""
import jwt
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status

from common.security import (
    SessionTracker,
    TokenHelper,
    session_enforcement_enabled,
    set_session_enforcement_override,
)

User = get_user_model()


def _jti(token):
    return jwt.decode(token, options={"verify_signature": False}).get("jti")


@override_settings(JWT_SESSION_ENFORCEMENT=True)
class RefreshReRegistersSessionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="enf", email="enf@example.com", password="SecurePass123!"
        )

    def test_refresh_rotated_jti_is_recorded(self):
        login = self.client.post(
            "/api/auth/login/",
            {"email": "enf@example.com", "password": "SecurePass123!"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        login_jti = _jti(login.data["access"])
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, login_jti))

        refreshed = self.client.post(
            "/api/auth/refresh/", {"refresh": login.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        new_jti = _jti(refreshed.data["access"])

        # The rotated jti is different AND now tracked.
        self.assertNotEqual(new_jti, login_jti)
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, new_jti))

    def test_request_with_refreshed_token_succeeds(self):
        login = self.client.post(
            "/api/auth/login/",
            {"email": "enf@example.com", "password": "SecurePass123!"},
            format="json",
        )
        refreshed = self.client.post(
            "/api/auth/refresh/", {"refresh": login.data["refresh"]}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        # Must NOT be 401 session_invalidated.
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, status.HTTP_200_OK)


@override_settings(JWT_SESSION_ENFORCEMENT=True)
class TrackerFailOpenTests(TestCase):
    """A cold/empty tracker must NOT mass-reject otherwise-valid tokens."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="fo", email="fo@example.com", password="SecurePass123!"
        )

    def test_empty_tracker_fails_open(self):
        # Simulate a token that exists but for which we have no tracking entry
        # (cache flushed / backend restarted / Redis cleared).
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, "some-jti"))

    def test_nonempty_tracker_rejects_unknown_jti(self):
        TokenHelper.create_tokens_with_session(self.user, "", "")
        # With a populated set, an unknown jti is correctly rejected.
        self.assertFalse(SessionTracker.is_session_valid(self.user.id, "not-a-real-jti"))

    def test_missing_jti_is_not_hard_failed(self):
        # A token with no jti can't be tracked; don't reject it here.
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, None))


class MultiSessionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="ms", email="ms@example.com", password="SecurePass123!"
        )

    def test_record_session_is_additive(self):
        t1 = TokenHelper.create_tokens_with_session(self.user, "", "")
        t2 = TokenHelper.create_tokens_with_session(self.user, "", "")
        # Both sessions remain valid (no auto-eviction of the first).
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, t1["jti"]))
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, t2["jti"]))

    def test_replace_drops_previous(self):
        SessionTracker.record_session(self.user.id, "old-jti")
        SessionTracker.record_session(self.user.id, "new-jti", replace=True)
        self.assertFalse(SessionTracker.is_session_valid(self.user.id, "old-jti"))
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, "new-jti"))

    def test_session_cap_is_bounded(self):
        for i in range(SessionTracker.MAX_SESSIONS + 5):
            SessionTracker.record_session(self.user.id, f"jti-{i}")
        key = SessionTracker._get_cache_key(self.user.id)
        self.assertLessEqual(len(cache.get(key, {})), SessionTracker.MAX_SESSIONS)
        # Oldest evicted, newest kept.
        self.assertFalse(SessionTracker.is_session_valid(self.user.id, "jti-0"))
        self.assertTrue(
            SessionTracker.is_session_valid(self.user.id, f"jti-{SessionTracker.MAX_SESSIONS + 4}")
        )


class RuntimeEnforcementToggleTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(JWT_SESSION_ENFORCEMENT=True)
    def test_override_off_beats_setting_on(self):
        self.assertTrue(session_enforcement_enabled())
        set_session_enforcement_override(False)
        self.assertFalse(session_enforcement_enabled())
        set_session_enforcement_override(None)
        self.assertTrue(session_enforcement_enabled())  # back to static setting

    @override_settings(JWT_SESSION_ENFORCEMENT=False)
    def test_override_on_beats_setting_off(self):
        self.assertFalse(session_enforcement_enabled())
        set_session_enforcement_override(True)
        self.assertTrue(session_enforcement_enabled())


@override_settings(JWT_SESSION_ENFORCEMENT=True)
class LogoutIdempotencyTests(TestCase):
    """Logout must succeed even when the caller's session was just invalidated.

    Regression for the E2E "Auth logout" 401: a password change tombstones all
    sessions (SessionTracker.invalidate_all_sessions), and the very next call —
    logout, reusing the same access token — was rejected 401 "session has been
    invalidated" before LogoutView could run. Logout is now authenticated with
    LogoutJWTAuthentication, which skips ONLY the session-validity check. This
    test also pins the invariant that enforcement stays ON for other endpoints.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="lo", email="lo@example.com", password="SecurePass123!"
        )

    def _login(self):
        r = self.client.post(
            "/api/auth/login/",
            {"email": "lo@example.com", "password": "SecurePass123!"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return r.data["access"], r.data["refresh"]

    def test_logout_succeeds_after_session_invalidated(self):
        access, refresh = self._login()
        # Simulate the password-change tombstone that precedes logout in the E2E.
        SessionTracker.invalidate_all_sessions(self.user.id)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        # Invariant: a normal protected endpoint STILL hard-rejects the tombstoned
        # session (the security hardening is intact everywhere except logout).
        self.assertEqual(
            self.client.get("/api/auth/profile/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        # The fix: logout is idempotent and still tears the session down (200).
        logout = self.client.post("/api/auth/logout/", {"refresh": refresh}, format="json")
        self.assertEqual(logout.status_code, status.HTTP_200_OK)

    def test_logout_still_rejects_garbage_token(self):
        # Idempotency must NOT mean "no auth": an absent/garbage token is still 401.
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-jwt")
        self.assertEqual(
            self.client.post("/api/auth/logout/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
