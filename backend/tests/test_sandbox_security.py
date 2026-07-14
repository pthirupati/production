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


class AdminIpFailClosedDefaultTests(TestCase):
    """SECURITY_AUDIT I-04: default posture. Admin IP fail-closed is OPT-IN
    (ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST). With the flag UNSET (the default, and
    what prod uses) an empty allowlist ALLOWS through the IP middleware — admin
    stays gated by superuser auth — so the owner can never be locked out and the
    green pipeline is unaffected. Loopback / in-container callers are always
    allowed regardless of the flag."""

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = AdminIPRestrictionMiddleware(_noop_get_response)

    def _admin_request(self, *, remote_addr, xff=None):
        extra = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        request = self.factory.get("/api/admin/overview/", **extra)
        # Mimic RequestMetadataMiddleware having populated client_ip.
        from common.middleware_security import client_ip_from_request
        request.client_ip = client_ip_from_request(request)
        return request

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=[],
                       ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=False)
    def test_remote_ip_allowed_by_default_in_prod(self):
        # DEFAULT posture (flag unset): an external client (through gateway,
        # XFF right-most is the real peer) is ALLOWED through the IP middleware
        # — admin remains gated by superuser auth elsewhere. This is what prod
        # runs, so it stays unlocked (no owner lockout).
        resp = self.mw.process_request(
            self._admin_request(remote_addr="172.18.0.5", xff="203.0.113.9")
        )
        self.assertIsNone(resp)

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=[],
                       ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=True)
    def test_loopback_allowed_when_fail_closed(self):
        # In-container E2E / health check: no XFF, REMOTE_ADDR is loopback.
        self.assertIsNone(
            self.mw.process_request(self._admin_request(remote_addr="127.0.0.1"))
        )

    @override_settings(DEBUG=False, ADMIN_ALLOWED_IPS=["203.0.113.9"])
    def test_loopback_allowed_even_with_allowlist(self):
        self.assertIsNone(
            self.mw.process_request(self._admin_request(remote_addr="127.0.0.1"))
        )


class XffClientIpTests(TestCase):
    """SECURITY_AUDIT A-01: client IP comes from the right-most trusted-proxy
    hop, not the spoofable left-most X-Forwarded-For entry."""

    def setUp(self):
        self.factory = RequestFactory()

    def _ip(self, *, remote_addr="172.18.0.5", xff=None, hops=1):
        from common.middleware_security import client_ip_from_request
        extra = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        request = self.factory.get("/api/whatever/", **extra)
        with override_settings(GATEWAY_PROXY_HOPS=hops):
            return client_ip_from_request(request)

    def test_spoofed_left_xff_is_ignored(self):
        # Attacker sends "1.2.3.4"; nginx appends the real peer "203.0.113.9".
        # We must return the REAL peer (right-most), not the spoof.
        ip = self._ip(xff="1.2.3.4, 203.0.113.9")
        self.assertEqual(ip, "203.0.113.9")
        self.assertNotEqual(ip, "1.2.3.4")

    def test_single_hop_takes_only_xff_value(self):
        ip = self._ip(xff="203.0.113.9")
        self.assertEqual(ip, "203.0.113.9")

    def test_no_xff_falls_back_to_remote_addr(self):
        ip = self._ip(remote_addr="127.0.0.1", xff=None)
        self.assertEqual(ip, "127.0.0.1")

    def test_multiple_trusted_hops(self):
        # Two trusted proxies: real client is 2 from the right.
        ip = self._ip(xff="9.9.9.9, 203.0.113.9, 172.18.0.2", hops=2)
        self.assertEqual(ip, "203.0.113.9")

    def test_request_metadata_middleware_sets_unspoofable_ip(self):
        from common.middleware_security import RequestMetadataMiddleware
        mw = RequestMetadataMiddleware(_noop_get_response)
        request = self.factory.get(
            "/api/x/", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.9",
            REMOTE_ADDR="172.18.0.5",
        )
        with override_settings(GATEWAY_PROXY_HOPS=1):
            mw.process_request(request)
        self.assertEqual(request.client_ip, "203.0.113.9")


class CodeExecFailClosedTests(TestCase):
    """SECURITY_AUDIT S-01: the grader never runs untrusted user code in-process
    on the host in production — it fails closed to needs_review when the
    container sandbox is unavailable."""

    def _python_tests(self):
        return [{"name": "t", "code": "assert add(2, 3) == 5", "hidden": False}]

    @override_settings(SANDBOX_DOCKER=False)
    def test_inprocess_allowed_when_sandbox_disabled(self):
        # Dev/CI (sandbox off): in-process grading works (no Docker engine needed).
        from apps.labs import code_exec
        result = code_exec.grade_submission(
            "python", "def add(a, b):\n    return a + b\n", self._python_tests(),
        )
        self.assertTrue(result.ran)
        self.assertTrue(result.all_passed)

    @override_settings(DEBUG=False, SANDBOX_DOCKER=True)
    def test_prod_without_container_fails_closed_to_review(self):
        # Production with no reachable container engine: must NOT execute on the
        # host. grade_submission returns needs_review, never a pass.
        from apps.labs import code_exec, sandbox_runner
        orig = sandbox_runner.docker_runtime_available
        sandbox_runner.docker_runtime_available = lambda *a, **k: False
        try:
            result = code_exec.grade_submission(
                "python", "def add(a, b):\n    return a + b\n", self._python_tests(),
            )
        finally:
            sandbox_runner.docker_runtime_available = orig
        self.assertFalse(result.all_passed)
        self.assertTrue(result.needs_review)
        self.assertFalse(result.ran)

    @override_settings(DEBUG=False, SANDBOX_DOCKER=True)
    def test_execute_raises_forbidden_in_prod_without_container(self):
        from apps.labs import code_exec, sandbox_runner
        orig = sandbox_runner.docker_runtime_available
        sandbox_runner.docker_runtime_available = lambda *a, **k: False
        try:
            with self.assertRaises(code_exec.InProcessExecutionForbidden):
                code_exec._execute(
                    "python", "print('x')", "_runner.py",
                    ["python3", "-c", "pass"], "/tmp", 5, limit_address_space=True,
                )
        finally:
            sandbox_runner.docker_runtime_available = orig
