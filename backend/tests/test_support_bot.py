"""Tests for FixitLab support assistant."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.support.service import generate_support_reply, support_bot_config


@pytest.mark.django_db
def test_support_bot_config_defaults():
    cfg = support_bot_config()
    assert cfg["enabled"] is True
    assert cfg["name"]
    assert len(cfg["quick_topics"]) >= 3


@pytest.mark.django_db
def test_generate_launch_lab_reply():
    result = generate_support_reply("How do I launch a lab?", is_authenticated=True)
    assert "Technologies" in result["reply"] or "lab" in result["reply"].lower()
    assert result["typing_delay_ms"] >= 300


@pytest.mark.django_db
def test_generate_jira_reply():
    result = generate_support_reply("How does Jira work during labs?")
    assert "jira" in result["reply"].lower() or "team" in result["reply"].lower()


@pytest.mark.django_db
def test_custom_faq_from_admin():
    from apps.adminpanel.platform_config import get_settings_row

    row = get_settings_row()
    row.support_bot_custom_faq = [
        {"keywords": ["customtoken"], "answer": "Custom admin answer here."},
    ]
    row.save()
    result = generate_support_reply("I have a customtoken question")
    assert "Custom admin answer" in result["reply"]


@pytest.mark.django_db
def test_support_chat_api():
    User = get_user_model()
    user = User.objects.create_user(username="helpuser", email="h@example.com", password="pass12345")
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.post("/api/support/chat/", {"message": "Who do I contact?"}, format="json")
    assert res.status_code == 200
    assert "reply" in res.json()


@pytest.mark.django_db
def test_user_can_disable_bot():
    from apps.accounts.models import Profile

    User = get_user_model()
    user = User.objects.create_user(username="nobot", email="n@example.com", password="pass12345")
    Profile.objects.filter(user=user).update(support_bot_enabled=False)
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.post("/api/support/chat/", {"message": "hi"}, format="json")
    assert res.status_code == 403
