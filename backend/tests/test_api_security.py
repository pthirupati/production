"""API security middleware tests (admin IP allowlist, security headers)."""

from django.test import RequestFactory, TestCase, override_settings

from common.middleware_security import AdminIPRestrictionMiddleware, SecurityHeadersMiddleware


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
