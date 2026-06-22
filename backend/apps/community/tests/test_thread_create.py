"""Regression tests for community thread creation (and reply/vote)."""
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.community.models import Thread
from apps.question_bank.models import Technology

User = get_user_model()


@override_settings(JWT_SESSION_ENFORCEMENT=False)
class ThreadCreateTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="poster", email="poster@example.com", password="pw-Str0ng!23"
        )
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_thread_general_no_technology(self):
        """Frontend 'General' option sends technology: null."""
        resp = self.client.post(
            "/api/community/threads/",
            {"title": "Help with grub", "body": "It won't boot", "technology": None},
            format="json",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))
        assert Thread.objects.filter(title="Help with grub").exists()

    def test_create_thread_with_technology_id(self):
        resp = self.client.post(
            "/api/community/threads/",
            {"title": "systemd q", "body": "unit files?", "technology": self.tech.id},
            format="json",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))
        thread = Thread.objects.get(title="systemd q")
        assert thread.technology_id == self.tech.id

    def test_create_thread_with_technology_string_id(self):
        """The DOM <select> sends the id as a STRING — DRF must coerce it."""
        resp = self.client.post(
            "/api/community/threads/",
            {"title": "str id", "body": "b", "technology": str(self.tech.id)},
            format="json",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))

    def test_create_thread_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.post(
            "/api/community/threads/",
            {"title": "x", "body": "y"},
            format="json",
        )
        assert resp.status_code in (401, 403), resp.status_code

    def test_reply_and_vote_still_work(self):
        thread = Thread.objects.create(
            author=self.user, title="t", body="b",
        )
        reply = self.client.post(
            f"/api/community/threads/{thread.id}/replies/",
            {"body": "first reply"},
            format="json",
        )
        assert reply.status_code == 201, (reply.status_code, dict(reply.data))

        vote = self.client.post(
            f"/api/community/threads/{thread.id}/vote/",
            {"vote_type": "up"},
            format="json",
        )
        assert vote.status_code in (200, 201), (vote.status_code, dict(vote.data))
