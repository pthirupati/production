"""IsPlatformAdmin gate on sensitive adminpanel routes (audit B7).

adminpanel has ~89 routes and historically one co-located test file
(test_monitoring.py). These assertions pin the permission class on a few
high-value GETs so a future regression that drops IsPlatformAdmin cannot
ship unnoticed.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()

# Representative surface: overview, user directory, orgs list.
SENSITIVE_GETS = (
    "/api/admin/overview/",
    "/api/admin/users/",
    "/api/admin/organizations/",
)


class AdminPanelAuthzTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="member@example.com",
            email="member@example.com",
            password="x",
        )
        self.staff = User.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="x",
            is_staff=True,
        )

    def test_anonymous_is_rejected(self):
        for url in SENSITIVE_GETS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertIn(
                    resp.status_code,
                    (401, 403),
                    f"{url} must not be public (got {resp.status_code})",
                )

    def test_authenticated_non_staff_is_forbidden(self):
        self.client.force_authenticate(self.user)
        for url in SENSITIVE_GETS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(
                    resp.status_code,
                    403,
                    f"{url} must require platform admin (got {resp.status_code})",
                )

    def test_staff_can_reach_overview(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get("/api/admin/overview/")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp.content))
