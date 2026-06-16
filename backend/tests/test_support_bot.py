"""Tests for FixitLab support assistant."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.support.service import generate_support_reply, support_bot_config


class SupportBotTests(TestCase):
    def test_support_bot_config_defaults(self):
        cfg = support_bot_config()
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["name"])
        self.assertGreaterEqual(len(cfg["quick_topics"]), 3)

    def test_generate_launch_lab_reply(self):
        result = generate_support_reply("How do I launch a lab?", is_authenticated=True)
        self.assertTrue(
            "Technologies" in result["reply"] or "lab" in result["reply"].lower()
        )
        self.assertGreaterEqual(result["typing_delay_ms"], 300)

    def test_jira_questions_redirect_to_lab_panel(self):
        result = generate_support_reply("@backup team please stop database for patching")
        self.assertTrue(
            "Jira panel" in result["reply"] or "Jira ticket" in result["reply"]
        )

    def test_generate_jira_reply_redirects_not_explains(self):
        result = generate_support_reply("How does Jira work during labs?")
        self.assertTrue(
            "Jira panel" in result["reply"] or "Jira ticket" in result["reply"]
        )

    def test_custom_faq_from_admin(self):
        from apps.adminpanel.platform_config import get_settings_row

        row = get_settings_row()
        row.support_bot_custom_faq = [
            {"keywords": ["customtoken"], "answer": "Custom admin answer here."},
        ]
        row.save()
        result = generate_support_reply("I have a customtoken question")
        self.assertIn("Custom admin answer", result["reply"])

    def test_support_chat_api(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="helpuser", email="h@example.com", password="pass12345"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.post(
            "/api/support/chat/", {"message": "Who do I contact?"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("reply", res.json())

    def test_user_can_disable_bot(self):
        from apps.accounts.models import Profile

        User = get_user_model()
        user = User.objects.create_user(
            username="nobot", email="n@example.com", password="pass12345"
        )
        Profile.objects.filter(user=user).update(support_bot_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.post("/api/support/chat/", {"message": "hi"}, format="json")
        self.assertEqual(res.status_code, 403)
