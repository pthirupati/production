"""Conversation + campaign memory persisted in round metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.interviews.services.conversation.analysis import AnswerAnalysis


@dataclass
class CampaignMemory:
  topics_depth: dict[str, int] = field(default_factory=dict)
  claims: list[str] = field(default_factory=list)
  tools_mentioned: list[str] = field(default_factory=list)
  numbers_stated: list[str] = field(default_factory=list)
  questions_asked: list[str] = field(default_factory=list)
  open_threads: list[dict] = field(default_factory=list)
  contradictions: list[dict] = field(default_factory=list)
  thread_depth: dict[str, int] = field(default_factory=dict)
  competence_estimate: float = 0.5
  phrases: list[str] = field(default_factory=list)

  @classmethod
  def from_dict(cls, data: dict | None) -> "CampaignMemory":
    data = data or {}
    return cls(
      topics_depth=dict(data.get("topics_depth") or data.get("topics_hit") or {}),
      claims=list(data.get("claims") or [])[:20],
      tools_mentioned=list(data.get("tools_mentioned") or [])[:30],
      numbers_stated=list(data.get("numbers_stated") or [])[:20],
      questions_asked=list(data.get("questions_asked") or [])[:50],
      open_threads=list(data.get("open_threads") or [])[:12],
      contradictions=list(data.get("contradictions") or [])[:8],
      thread_depth=dict(data.get("thread_depth") or {}),
      competence_estimate=float(data.get("competence_estimate") or 0.5),
      phrases=list(data.get("phrases") or [])[:15],
    )

  def to_dict(self) -> dict[str, Any]:
    return {
      "topics_depth": self.topics_depth,
      "claims": self.claims,
      "tools_mentioned": self.tools_mentioned,
      "numbers_stated": self.numbers_stated,
      "questions_asked": self.questions_asked,
      "open_threads": self.open_threads,
      "contradictions": self.contradictions,
      "thread_depth": self.thread_depth,
      "competence_estimate": self.competence_estimate,
      "phrases": self.phrases,
    }


def update_campaign_memory(
    memory: CampaignMemory | dict,
    *,
    analysis: AnswerAnalysis,
    question_text: str = "",
    topic: str | None = None,
    score: float = 0.0,
) -> CampaignMemory:
    mem = memory if isinstance(memory, CampaignMemory) else CampaignMemory.from_dict(memory)

    if topic:
        mem.topics_depth[topic] = int(mem.topics_depth.get(topic, 0)) + 1

    for tool in analysis.entities + analysis.evidence:
        token = tool.split()[0] if tool else ""
        if token and token.lower() not in {t.lower() for t in mem.tools_mentioned}:
            mem.tools_mentioned.append(token[:40])

    for num in analysis.numbers:
        if num not in mem.numbers_stated:
            mem.numbers_stated.append(num)

    if analysis.normalized_text and len(analysis.normalized_text) > 20:
        snippet = analysis.normalized_text[:90]
        if snippet not in mem.claims:
            mem.claims.append(snippet)

    if question_text:
        qnorm = question_text.strip().lower()[:200]
        if qnorm and qnorm not in {q.lower() for q in mem.questions_asked}:
            mem.questions_asked.append(question_text.strip()[:200])

    thread_key = topic or (analysis.entities[0] if analysis.entities else "general")
    mem.thread_depth[thread_key] = int(mem.thread_depth.get(thread_key, 0)) + 1

    if score >= 75:
        mem.competence_estimate = min(1.0, mem.competence_estimate + 0.08)
    elif score < 45:
        mem.competence_estimate = max(0.0, mem.competence_estimate - 0.06)

    return mem
