"""Community thread report API tests."""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.community.models import Thread, ThreadReport
from apps.question_bank.models import Technology

User = get_user_model()


class ThreadReportAPITest(APITestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(
            username="reporter", email="reporter@test.com", password="Test123!@",
        )
        self.author = User.objects.create_user(
            username="author", email="author@test.com", password="Test123!@",
        )
        tech = Technology.objects.create(name="Linux", slug="linux")
        self.thread = Thread.objects.create(
            author=self.author,
            title="Broken nginx thread",
            body="Need help fixing nginx",
            technology=tech,
        )

    def test_report_requires_auth(self):
        url = f"/api/community/threads/{self.thread.id}/report/"
        resp = self.client.post(url, {"reason": "spam"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_report_thread_success(self):
        self.client.force_authenticate(user=self.reporter)
        url = f"/api/community/threads/{self.thread.id}/report/"
        resp = self.client.post(url, {"reason": "spam", "details": "Promotional link"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data.get("reported"))
        self.assertTrue(
            ThreadReport.objects.filter(thread=self.thread, reporter=self.reporter).exists()
        )

    def test_report_duplicate_rejected(self):
        self.client.force_authenticate(user=self.reporter)
        url = f"/api/community/threads/{self.thread.id}/report/"
        self.client.post(url, {"reason": "spam"})
        resp = self.client.post(url, {"reason": "abuse"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_report_invalid_reason(self):
        self.client.force_authenticate(user=self.reporter)
        url = f"/api/community/threads/{self.thread.id}/report/"
        resp = self.client.post(url, {"reason": "not-a-valid-reason"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
