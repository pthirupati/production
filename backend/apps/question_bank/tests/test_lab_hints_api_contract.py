"""Contract tests for the lab hint API payload shape."""
import os
from types import SimpleNamespace

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.public_api.views import LabHintsView


class HintList(list):
    def count(self):
        return len(self)


def test_standard_hint_response_includes_tier_metadata():
    session = SimpleNamespace(hints_used=1)
    hints = HintList([
        SimpleNamespace(order=1, content="Where to look: inspect the failed unit.", penalty=0),
        SimpleNamespace(order=2, content="Diagnostic steps:\n1. Run systemctl status.", penalty=25),
        SimpleNamespace(order=3, content="Exact fix:\n1. Start the service.", penalty=50),
    ])

    payload = LabHintsView._standard_response(session, hints)

    assert payload["hints_used"] == 1
    assert payload["next_available"] is True
    assert [tier["label"] for tier in payload["tiers"]] == [
        "Hint 1: Where to look",
        "Hint 2: Step-by-step guide",
        "Hint 3: Full solution",
    ]
    assert payload["tiers"][0]["revealed"] is True
    assert payload["tiers"][0]["content"].startswith("Where to look")
    assert payload["tiers"][1]["unlocked"] is True
    assert payload["tiers"][1]["content"] == ""
    assert payload["tiers"][2]["locked"] is True
    assert payload["revealed"] == [payload["tiers"][0]]


def test_interview_mode_keeps_standard_hints_disabled():
    session = SimpleNamespace(hints_used=0)
    hints = HintList([SimpleNamespace(order=1, content="hidden", penalty=0)])

    payload = LabHintsView._standard_response(session, hints, interview_mode=True)

    assert payload["interview_mode"] is True
    assert payload["tiers"] == []
    assert payload["next_available"] is False
    assert payload["ai_hints_available"] is True
