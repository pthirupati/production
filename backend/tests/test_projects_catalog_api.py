"""§C3 — /api/projects/ catalog index + slug detail."""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.question_bank.models import Project, Technology


class ProjectsCatalogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tech = Technology.objects.create(
            name="Linux", slug="linux", is_active=True, order=1,
        )
        self.project = Project.objects.create(
            technology=self.tech,
            title="First Server",
            slug="linux-fundamentals-first-server",
            description="Build a hardened first server.",
            difficulty="beginner",
            estimated_hours=6,
            is_active=True,
            order=1,
        )

    def test_list_returns_active_projects(self):
        res = self.client.get("/api/projects/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["projects"][0]["slug"], "linux-fundamentals-first-server")
        self.assertEqual(body["projects"][0]["technology"]["slug"], "linux")

    def test_detail_by_slug(self):
        res = self.client.get("/api/projects/linux-fundamentals-first-server/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["slug"], "linux-fundamentals-first-server")
        self.assertEqual(body["title"], "First Server")
        self.assertEqual(body["technology"]["slug"], "linux")

    def test_inactive_project_is_hidden(self):
        self.project.is_active = False
        self.project.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/api/projects/").json()["count"], 0)
        self.assertEqual(
            self.client.get("/api/projects/linux-fundamentals-first-server/").status_code,
            404,
        )

    def test_filter_by_technology(self):
        other = Technology.objects.create(name="AWS", slug="aws", is_active=True, order=2)
        Project.objects.create(
            technology=other, title="VPC Lab", slug="aws-vpc-capstone",
            description="x", is_active=True,
        )
        res = self.client.get("/api/projects/", {"technology": "linux"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["projects"][0]["slug"], "linux-fundamentals-first-server")
