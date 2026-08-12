"""Audit Z6-12 — refresh-token rotation was security-critical and untested.

`auth_app` had zero tests, and the audit singles out `ROTATE_REFRESH_TOKENS` +
`BLACKLIST_AFTER_ROTATION` as "subtle, security-critical, and untested". Both are
`True`, and each protects a different thing:

* **rotation** limits the value of a stolen refresh token — it is good for one use;
* **blacklist-after-rotation** is what makes that true. Without it the old token
  keeps working and rotation is cosmetic.

There is a third, quieter requirement that has nothing to do with security and
everything to do with not logging the whole site out. simplejwt mints a **brand-new
jti** for the rotated access token, and `SessionTracker` validates requests against
registered jtis. If the rotated jti is not re-registered, the freshly-refreshed
token fails on the very next request — which, per the comment in
`CookieTokenRefreshView`, is exactly what happened sitewide when JWT session
enforcement was turned back on at the end of a deploy.

So the three tests that matter are: the old token dies, the new token works, and
the new token is actually *new*. Existing coverage tested blacklisting on **logout**
and on **password reset** — neither exercises the rotation path.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rot", email="rot@example.com", password=PASSWORD
        )
        self.client = APIClient()
        self.url = "/api/auth/refresh/"

    def _login(self):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": PASSWORD}, format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        return resp.data["access"], resp.data["refresh"]

    def _refresh(self, token, client=None):
        return (client or APIClient()).post(
            self.url, {"refresh": token}, format="json"
        )


class TheRouteExistsTests(_Base):
    def test_the_url_is_routed(self):
        from django.urls import resolve

        self.assertEqual(
            resolve(self.url).func.view_class.__name__, "CookieTokenRefreshView"
        )

    def test_rotation_and_blacklisting_are_both_enabled(self):
        """Either one alone is insufficient: rotation without blacklisting leaves
        the old token valid, and blacklisting without rotation has nothing to
        blacklist."""
        from django.conf import settings

        self.assertTrue(settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"])


class RotationIssuesANewTokenTests(_Base):
    def test_refreshing_returns_a_new_access_token(self):
        _, refresh = self._login()
        resp = self._refresh(refresh)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertIn("access", resp.data)

    def test_refreshing_returns_a_rotated_refresh_token(self):
        """`ROTATE_REFRESH_TOKENS=True` means the response carries a *different*
        refresh token. Returning the same one back would silently disable rotation
        while every other assertion here still passed."""
        _, refresh = self._login()
        resp = self._refresh(refresh)
        self.assertIn("refresh", resp.data)
        self.assertNotEqual(
            resp.data["refresh"], refresh,
            "the same refresh token was returned — rotation is not happening",
        )

    def test_the_rotated_tokens_are_set_as_cookies(self):
        """This app authenticates by cookie; returning tokens only in the body
        would leave the browser on the old, now-blacklisted pair."""
        _, refresh = self._login()
        resp = self._refresh(refresh)
        self.assertIn("access_token", resp.cookies)
        self.assertIn("refresh_token", resp.cookies)

    def test_the_access_cookie_is_httponly(self):
        _, refresh = self._login()
        resp = self._refresh(refresh)
        self.assertTrue(resp.cookies["access_token"]["httponly"])


class TheOldTokenDiesTests(_Base):
    """`BLACKLIST_AFTER_ROTATION` — without this, rotation is cosmetic."""

    def test_the_old_refresh_token_is_rejected_after_use(self):
        _, refresh = self._login()
        first = self._refresh(refresh)
        self.assertEqual(first.status_code, 200)

        replay = self._refresh(refresh)
        self.assertEqual(
            replay.status_code, 401,
            "a used refresh token still works — a stolen token is good forever, "
            "not for one use",
        )

    def test_the_new_refresh_token_works_once(self):
        """Guard the guard: if every refresh token were rejected the test above
        would pass while refresh was entirely broken."""
        _, refresh = self._login()
        rotated = self._refresh(refresh).data["refresh"]
        self.assertEqual(self._refresh(rotated).status_code, 200)

    def test_a_chain_of_refreshes_invalidates_each_previous_token(self):
        _, refresh = self._login()
        first = self._refresh(refresh).data["refresh"]
        second = self._refresh(first).data["refresh"]

        self.assertEqual(self._refresh(refresh).status_code, 401)
        self.assertEqual(self._refresh(first).status_code, 401)
        self.assertEqual(self._refresh(second).status_code, 200)

    def test_a_garbage_token_is_rejected(self):
        self.assertEqual(self._refresh("not-a-token").status_code, 401)

    def test_a_token_for_a_deleted_user_is_rejected(self):
        _, refresh = self._login()
        self.user.delete()
        self.assertIn(self._refresh(refresh).status_code, (401, 404))


class TheRotatedTokenActuallyWorksTests(_Base):
    """The quiet half. simplejwt mints a new jti on rotation, and SessionTracker
    validates against registered jtis — so a rotated token that is not re-registered
    401s on the very next request. Per the view's own comment, that is what logged
    the site out when session enforcement was re-enabled at the end of a deploy."""

    def test_the_refreshed_access_token_authenticates_a_request(self):
        _, refresh = self._login()
        resp = self._refresh(refresh)
        new_access = resp.data["access"]

        probe = APIClient()
        probe.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        profile = probe.get("/api/auth/profile/")
        self.assertEqual(
            profile.status_code, 200,
            "the freshly-rotated access token was rejected — the new jti was not "
            "registered, which logs every active user out on their next request",
        )

    def test_it_still_works_after_two_rotations(self):
        """Once could pass by accident if the original jti happened to remain
        registered; twice cannot."""
        _, refresh = self._login()
        rotated = self._refresh(refresh).data["refresh"]
        second = self._refresh(rotated)

        probe = APIClient()
        probe.credentials(HTTP_AUTHORIZATION=f"Bearer {second.data['access']}")
        self.assertEqual(probe.get("/api/auth/profile/").status_code, 200)


class TheCookieFallbackTests(_Base):
    """The browser never sends the refresh token in the body — it is httpOnly, so
    JavaScript cannot read it. If the cookie fallback breaks, every browser session
    silently stops refreshing and users are logged out after 15 minutes."""

    def test_refresh_works_with_no_body_using_the_cookie(self):
        client = APIClient()
        login = client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": PASSWORD}, format="json",
        )
        self.assertIn("refresh_token", login.cookies)

        resp = client.post(self.url, {}, format="json")
        self.assertEqual(
            resp.status_code, 200, getattr(resp, "data", resp),
        )
        self.assertIn("access", resp.data)

    def test_a_body_token_still_takes_precedence(self):
        """Non-browser clients pass it explicitly; the fallback must not override
        an explicitly supplied token."""
        _, refresh = self._login()
        client = APIClient()
        client.cookies["refresh_token"] = "garbage-cookie-value"
        self.assertEqual(self._refresh(refresh, client=client).status_code, 200)

    def test_no_token_anywhere_is_a_400_or_401(self):
        resp = APIClient().post(self.url, {}, format="json")
        self.assertIn(resp.status_code, (400, 401))


class BlacklistIsDurableTests(_Base):
    def test_the_rotated_token_is_recorded_in_the_blacklist_table(self):
        """Blacklisting is DB-backed rather than cache-backed on purpose: a Redis
        flush must not resurrect every previously-rotated refresh token."""
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

        _, refresh = self._login()
        before = BlacklistedToken.objects.count()
        self._refresh(refresh)
        self.assertGreater(
            BlacklistedToken.objects.count(), before,
            "rotation did not write a blacklist row — the old token survives a "
            "process restart",
        )

    def test_a_manually_blacklisted_token_is_refused(self):
        _, refresh = self._login()
        RefreshToken(refresh).blacklist()
        self.assertEqual(self._refresh(refresh).status_code, 401)
