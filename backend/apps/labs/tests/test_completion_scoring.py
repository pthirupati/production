"""Tests for lab completion scoring."""
from types import SimpleNamespace

from apps.labs.completion import compute_score


def _session(hints_used):
    return SimpleNamespace(duration_limit=100, time_remaining=0, hints_used=hints_used)


def test_compute_score_uses_progressive_hint_penalties():
    assert compute_score(_session(0)) == 100
    assert compute_score(_session(1)) == 100
    assert compute_score(_session(2)) == 75
    assert compute_score(_session(3)) == 25
    assert compute_score(_session(4)) == 15
    assert compute_score(_session(5)) == 10
