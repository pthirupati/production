"""Decide the interviewer's next conversational move."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from apps.interviews.services.conversation.analysis import AnswerAnalysis
from apps.interviews.services.conversation.memory import CampaignMemory
from apps.interviews.services.conversation_intelligence import detect_contradiction


class NextMove(str, Enum):
    DRILL_DOWN = "drill_down"
    CLARIFY = "clarify"
    CHALLENGE = "challenge"
    SCENARIO_ESCALATE = "scenario_escalate"
    EASE_REDIRECT = "ease_redirect"
    HINT_THEN_MOVE = "hint_then_move"
    ANSWER_CANDIDATE = "answer_candidate"
    THREAD_BACK = "thread_back"
    NEW_TOPIC = "new_topic"


MAX_THREAD_DEPTH = 3


@dataclass
class PolicyDecision:
    move: NextMove
    thread_key: str = ""
    prior_claim: str = ""
    reason: str = ""


def decide_next_move(
    *,
    analysis: AnswerAnalysis,
    memory: CampaignMemory,
    strong_streak: int = 0,
    brief_streak: int = 0,
) -> PolicyDecision:
    thread_key = (
        analysis.entities[0] if analysis.entities
        else (analysis.noun_phrases[0] if analysis.noun_phrases else "general")
    )
    depth = int(memory.thread_depth.get(thread_key, 0))

    if analysis.is_candidate_question:
        return PolicyDecision(NextMove.ANSWER_CANDIDATE, thread_key=thread_key)

    if analysis.is_idk:
        return PolicyDecision(NextMove.HINT_THEN_MOVE, thread_key=thread_key)

    prior = detect_contradiction({"claims": memory.claims}, analysis.normalized_text)
    if prior:
        return PolicyDecision(NextMove.CHALLENGE, thread_key=thread_key, prior_claim=prior)

    if brief_streak >= 2 or analysis.sentiment_stress > 0.55:
        return PolicyDecision(NextMove.EASE_REDIRECT, thread_key=thread_key)

    if analysis.vagueness > 0.45 or not analysis.answered_question:
        return PolicyDecision(NextMove.CLARIFY, thread_key=thread_key)

    if strong_streak >= 2 and memory.competence_estimate >= 0.65:
        return PolicyDecision(NextMove.SCENARIO_ESCALATE, thread_key=thread_key)

    if depth >= MAX_THREAD_DEPTH:
        if memory.open_threads:
            return PolicyDecision(NextMove.THREAD_BACK, thread_key=memory.open_threads[0].get("key", ""))
        return PolicyDecision(NextMove.NEW_TOPIC, thread_key=thread_key)

    if analysis.depth >= 0.35 and (analysis.evidence or analysis.numbers):
        return PolicyDecision(NextMove.DRILL_DOWN, thread_key=thread_key)

    if memory.claims and depth == 0:
        return PolicyDecision(NextMove.THREAD_BACK, thread_key=thread_key)

    return PolicyDecision(NextMove.NEW_TOPIC, thread_key=thread_key)
