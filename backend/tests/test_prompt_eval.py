"""Tests for rule-based prompt engineering grader."""

from apps.labs.prompt_eval import evaluate_course, evaluate_prompt


def test_role_and_limit_pass():
    prompt = "You are a senior SRE. In 3 bullet points, list steps to restart nginx safely."
    chk = evaluate_prompt(prompt, {"require_any_role": True, "mentions_limit": True, "min_words": 8})
    assert chk.passed
    assert chk.score >= 80


def test_vague_prompt_fails():
    chk = evaluate_prompt("explain things", {"require_any_role": True, "min_words": 15})
    assert not chk.passed


def test_course_all_exercises():
    config = {
        "exercises": [
            {"id": "a", "success": {"require_any_role": True, "min_words": 5}},
            {"id": "b", "success": {"mentions_limit": True, "min_words": 8}},
        ]
    }
    subs = {
        "a": "You are a tutor. Explain VPC peering.",
        "b": "Summarize in under 100 words with bullet points.",
    }
    verdict = evaluate_course(config, subs)
    assert verdict["all_passed"]
    assert verdict["passed_count"] == 2
