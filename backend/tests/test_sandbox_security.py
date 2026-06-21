"""Security-hardening tests for SECURITY_AUDIT items implemented in P9.

Covers:
  * A-01 — CookieJWTAuthentication requires a custom JS header on the
    cookie-authenticated path for state-changing methods (CSRF defense), while
    leaving the Authorization: Bearer path and safe methods untouched.
  * I-01 — AdminIPRestrictionMiddleware fails CLOSED in production when the
    allowlist is empty AND the opt-in flag is set, and stays fail-open (legacy)
    otherwise so the existing deploy/E2E is unaffected.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken

from apps.auth_app.cookie_auth import CookieJWTAuthentication
from common.middleware_security import AdminIPRestrictionMiddleware

User = get_user_model()


def _noop_get_response(request):  # for instantiating middleware
    from django.http import HttpResponse
    return HttpResponse("ok")


@override_settings(JWT_SESSION_ENFORCEMENT=False)
class CookieAuthCsrfTests(TestCase):
    """A-01: cookie-auth state changes need the X-Requested-With header."""

    def setUp(self):
        self.factory = RequestFactory()
        self.auth = CookieJWTAuthentication()
        self.user = User.objects.create_user(
            username="cookieuser", email="cookie@test.com", password="Pass123!x"
        )
        self.token = str(AccessToken.for_user(self.user))

    def _req(self, method, *, cookie=True, header=True, bearer=False):
        fn = getattr(self.factory, method.lower())
        kwargs = {}
        if header:
            kwargs["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        if bearer:
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"
        request = fn("/api/whatever/", **kwargs)
        if cookie:
            request.COOKIES["access_token"] = self.token
        return request

    @override_settings(COOKIE_AUTH_REQUIRE_CSRF_HEADER=True)
    def test_cookie_post_without_header_is_rejected(self):
        request = self._req("post", cookie=True, header=False)
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(ctx.exception.detail.code, "csrf_header_required")

    @override_settings(COOKIE_AUTH_REQUIRE_CSRF_HEADER=True)
    def test_cookie_post_with_header_is_accepted(self):
        request = self._req("post", cookie=True, header=True)
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].id, self.user.id)

    @override_settings(COOKIE_AUTH_REQUIRE_CSRF_HEADER=True)
    def test_cookie_get_without_header_is_allowed(self):
        # Safe methods never need the header (reads can't be CSRF'd into a change).
        request = self._req("get", cookie=True, header=False)
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].id, self.user.id)

    @override_settings(COOKIE_AUTH_REQUIRE_CSRF_HEADER=True)
    def test_bearer_post_without_header_is_allowed(self):
        # The Authorization header path is immune to CSRF (a cross-site form
        # cannot set it), so it is NOT subject to the X-Requested-With check.
        request = self._req("post", cookie=False, header=False, bearer=True)
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].id, self.user.id)

    @override_settings(COOKIE_AUTH_REQUIRE_CSRF_HEADER=False)
    def test_control_can_be_disabled(self):
        # When the control is off, cookie POST without the header is honoured
        # (legacy behaviour) — proves the gate is wired to the setting.
        request = self._req("post", cookie=True, header=False)
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)

    @override_settings(COOKIE_AUTH_REQUIRE_CSRF_HEADER=True)
    def test_no_credentials_returns_none(self):
        request = self.factory.post("/api/whatever/")
        self.assertIsNone(self.auth.authenticate(request))


class AdminIpFailClosedTests(TestCase):
    """I-01: admin IP allowlist fail-closed behaviour (opt-in)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = AdminIPRestrictionMiddleware(_noop_get_response)

    def _admin_request(self, ip="203.0.113.9"):
        request = self.factory.get("/api/admin/overview/")
        request.client_ip = ip
        request.META["REMOTE_ADDR"] = ip
        return request

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=[],
                       ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=True)
    def test_prod_empty_allowlist_fails_closed_when_opted_in(self):
        resp = self.mw.process_request(self._admin_request())
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=[],
                       ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=True)
    def test_fail_closed_does_not_block_non_admin_paths(self):
        request = self.factory.get("/api/scenarios/")
        request.client_ip = "203.0.113.9"
        self.assertIsNone(self.mw.process_request(request))

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=[],
                       ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=False)
    def test_prod_empty_allowlist_legacy_fail_open_by_default(self):
        # Default (flag off) preserves current deploy/E2E behaviour: allowed.
        self.assertIsNone(self.mw.process_request(self._admin_request()))

    @override_settings(DEBUG=True, ADMIN_ALLOWED_IPS=[],
                       ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=True)
    def test_debug_never_fails_closed(self):
        # Dev must stay open even with the flag on.
        self.assertIsNone(self.mw.process_request(self._admin_request()))

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=["203.0.113.9"])
    def test_allowlisted_ip_passes(self):
        self.assertIsNone(self.mw.process_request(self._admin_request("203.0.113.9")))

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=["203.0.113.9"])
    def test_non_allowlisted_ip_blocked(self):
        resp = self.mw.process_request(self._admin_request("198.51.100.7"))
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)
