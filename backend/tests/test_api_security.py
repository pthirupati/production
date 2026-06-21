"""API security middleware tests (admin IP allowlist, security headers)."""

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.request import Request
from rest_framework.parsers import JSONParser
from rest_framework.test import APIRequestFactory

from common.middleware_security import AdminIPRestrictionMiddleware, SecurityHeadersMiddleware
from common.throttles import LoginRateThrottle


class LoginThrottleTests(TestCase):
    """The login throttle counts only FAILED attempts, keyed on (IP + email)."""

    LIMIT = 3

    def setUp(self):
        self.factory = APIRequestFactory()
        cache.clear()

    def _throttle(self):
        # test_settings forces every scope to 10000/min and the api_settings
        # cache ignores override_settings(REST_FRAMEWORK=...), so pin the parsed
        # rate directly on the instance to exercise the failure-counting logic.
        t = LoginRateThrottle()
        t.num_requests = self.LIMIT
        t.duration = 60
        return t

    def _request(self, email, ip="203.0.113.9"):
        raw = self.factory.post("/api/auth/login/", {"email": email, "password": "x"}, format="json")
        raw.META["REMOTE_ADDR"] = ip
        return Request(raw, parsers=[JSONParser()])

    def test_successful_logins_never_throttled(self):
        # allow_request alone (no record_failure) must never block, even when
        # called far more than the limit — successes don't consume quota.
        for _ in range(self.LIMIT * 5):
            self.assertTrue(self._throttle().allow_request(self._request("admin@x.com"), None))

    def test_failures_block_after_limit(self):
        # LIMIT failures allowed, the next one blocked.
        for i in range(self.LIMIT):
            t = self._throttle()
            self.assertTrue(t.allow_request(self._request("admin@x.com"), None), f"attempt {i}")
            t.record_failure(self._request("admin@x.com"), None)
        self.assertFalse(self._throttle().allow_request(self._request("admin@x.com"), None))

    def test_failures_are_per_account(self):
        # Exhausting one account's bucket must not lock out a different account
        # from the same IP (shared-NAT / shared-egress safety).
        for _ in range(self.LIMIT + 2):
            t = self._throttle()
            t.allow_request(self._request("victim@x.com"), None)
            t.record_failure(self._request("victim@x.com"), None)
        self.assertTrue(self._throttle().allow_request(self._request("other@x.com"), None))


class AdminIPRestrictionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AdminIPRestrictionMiddleware(lambda r: None)

    @override_settings(ADMIN_ALLOWED_IPS=[])
    def test_allows_all_when_allowlist_empty(self):
        request = self.factory.get("/django-admin/")
        request.META["REMOTE_ADDR"] = "203.0.113.50"
        self.assertIsNone(self.middleware.process_request(request))

    @override_settings(ADMIN_ALLOWED_IPS=["203.0.113.50"])
    def test_allows_listed_ip_for_admin(self):
        request = self.factory.get("/django-admin/")
        request.META["REMOTE_ADDR"] = "203.0.113.50"
        self.assertIsNone(self.middleware.process_request(request))

    @override_settings(ADMIN_ALLOWED_IPS=["203.0.113.50"])
    def test_blocks_unlisted_ip_for_admin(self):
        request = self.factory.get("/api/admin/users/")
        request.META["REMOTE_ADDR"] = "198.51.100.1"
        response = self.middleware.process_request(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(ADMIN_ALLOWED_IPS=["203.0.113.50"])
    def test_does_not_block_public_api(self):
        request = self.factory.get("/api/scenarios/")
        request.META["REMOTE_ADDR"] = "198.51.100.1"
        self.assertIsNone(self.middleware.process_request(request))


class SecurityHeadersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(lambda r: None)

    @override_settings(DEBUG=False)
    def test_adds_security_headers(self):
        from django.http import HttpResponse
        request = self.factory.get("/api/health/")
        response = HttpResponse("ok")
        response = self.middleware.process_response(request, response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", response)
