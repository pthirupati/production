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

    def test_technical_queries_get_specific_answers(self):
        """Distinct technical questions must return targeted, non-fallback answers."""
        cases = {
            "vm won't power on": ["vim-cmd", "power"],
            "how do I add a datastore": ["esxcli", "vmfs"],
            "ssh connection refused": ["sshd", "ss -ltnp"],
            "my service won't start": ["systemctl", "journalctl"],
            "pod stuck in pending": ["kubectl describe", "pending"],
            "container keeps restarting": ["docker logs", "exit"],
            "disk is full no space left": ["df -h", "du"],
            "dns not resolving": ["resolv.conf", "dig"],
        }
        for query, needles in cases.items():
            result = generate_support_reply(query)
            reply = result["reply"].lower()
            self.assertNotEqual(
                result.get("intent"), "fallback", f"{query!r} fell through to fallback"
            )
            for needle in needles:
                self.assertIn(
                    needle.lower(), reply, f"{query!r} reply missing {needle!r}"
                )

    def test_fallback_is_clarifying_not_dismissive(self):
        result = generate_support_reply("asdkfj qwerty zzz")
        self.assertEqual(result.get("intent"), "fallback")
        reply = result["reply"].lower()
        self.assertIn("?", result["reply"])  # asks a clarifying question
        self.assertNotIn("i can't help", reply)
        self.assertNotIn("i cannot help", reply)
        self.assertTrue(len(result["suggestions"]) >= 3)

    def test_context_aware_reply_uses_active_scenario(self):
        """A vague query inside a VMware lab should surface VMware topics."""
        from apps.question_bank.models import Technology, Scenario
        from apps.labs.models import LabSession

        User = get_user_model()
        user = User.objects.create_user(
            username="ctxuser", email="c@example.com", password="pass12345"
        )
        tech = Technology.objects.create(name="VMware vSphere", slug="vmware")
        scenario = Scenario.objects.create(
            technology=tech, slug="vmware-host-down", title="ESXi Host Down"
        )
        session = LabSession.objects.create(user=user, scenario=scenario, status="RUNNING")
        result = generate_support_reply(
            "something is broken, not sure what",
            is_authenticated=True,
            page_path=f"/lab/{session.id}",
            # Lab context is now resolved against THIS user's sessions (audit Z3-9).
            # Previously `is_authenticated=True` was an unbacked claim — the caller
            # asserted authentication without saying who, so any session id resolved
            # for anyone. That gap is precisely what the flag's shape allowed.
            user=user,
        )
        joined = " ".join(result["suggestions"]).lower()
        self.assertTrue(
            "datastore" in joined or "host" in joined or "power on" in joined,
            f"expected VMware topics, got {result['suggestions']}",
        )

    def test_jira_actions_still_redirect(self):
        result = generate_support_reply("@storage team please add a 50G disk")
        self.assertIn("Jira panel", result["reply"])

    def test_feedback_endpoint(self):
        client = APIClient()
        res = client.post(
            "/api/support/feedback/",
            {"message": "vm won't power on", "reply": "steps...", "helpful": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("ok"))

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
