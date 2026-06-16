"""
LLM-powered interview engine using Claude API.

Drop-in upgrade for interview_ai.py + scoring.py.
Zero breaking changes to engine.py call sites — all public functions
have identical signatures to the originals.

Set ANTHROPIC_API_KEY in environment to enable; falls back to rule-based
system automatically if key is absent or the call fails.
"""

from __future__ import annotations

import json
import logging
import os
import re
import textwrap
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client bootstrap (lazy, singleton)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_client():
    """Return Anthropic client or None if SDK / key not available."""
    try:
        import anthropic  # noqa: PLC0415
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic SDK not installed — falling back to rule-based AI")
        return None


def _llm_available() -> bool:
    return _get_client() is not None


# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

PERSONAS: dict[str, dict] = {
    "technical": {
        "name_default": "Alex",
        "style": "precise and probing",
        "tone": "professional but approachable",
        "focus": "technical depth, system design, troubleshooting methodology, and production readiness",
        "quirks": (
            "You occasionally say 'walk me through that' or 'let's get concrete' when answers are vague. "
            "You push on failure modes and edge cases. You're impressed by candidates who think about "
            "observability and rollback before writing code."
        ),
    },
    "hr": {
        "name_default": "Priya",
        "style": "warm and conversational",
        "tone": "friendly, encouraging, genuinely curious",
        "focus": "cultural fit, motivation, career narrative, logistics, and team collaboration",
        "quirks": (
            "You use phrases like 'that's interesting' and 'tell me more about that'. "
            "You listen for self-awareness, growth mindset, and clear communication of values."
        ),
    },
    "manager": {
        "name_default": "Jordan",
        "style": "direct and results-oriented",
        "tone": "businesslike, fair, occasionally challenging",
        "focus": "incident management, SLA ownership, ITIL process, stakeholder communication, and team leadership",
        "quirks": (
            "You reference real operational scenarios. You care about MTTR, on-call discipline, "
            "and how engineers escalate. You notice when candidates dodge ownership."
        ),
    },
    "deep_dive": {
        "name_default": "Morgan",
        "style": "intellectually rigorous",
        "tone": "focused, respectful of expertise, slightly Socratic",
        "focus": "architecture trade-offs, scalability, security posture, and engineering war stories",
        "quirks": (
            "You follow up on any claim with 'and how did you measure that?' or 'what would you do differently now?'. "
            "You're looking for engineers who've actually operated systems at scale."
        ),
    },
    "leadership": {
        "name_default": "Sam",
        "style": "strategic and empathetic",
        "tone": "senior peer — collegial, confident",
        "focus": "influence without authority, mentoring, delivery under pressure, cross-team alignment",
        "quirks": (
            "You listen for examples where the candidate changed minds, unblocked others, or took ownership "
            "beyond their job description. You notice absence of 'we' versus 'I'."
        ),
    },
}


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(
    *,
    persona_name: str,
    round_type: str,
    profile_snapshot: dict,
    round_number: int,
    total_rounds: int,
    prior_round_summaries: list[dict] | None = None,
) -> str:
    persona = PERSONAS.get(round_type, PERSONAS["technical"])
    name = persona_name or persona["name_default"]
    candidate_name = profile_snapshot.get("name") or "the candidate"
    tech = profile_snapshot.get("primary_technology") or "general DevOps/SRE"
    level = profile_snapshot.get("experience_level") or "mid"
    company = profile_snapshot.get("current_company") or "their current employer"
    role = profile_snapshot.get("target_role") or f"{level}-level engineer"
    skills = profile_snapshot.get("skills") or []
    skills_str = ", ".join(skills[:8]) if skills else "not specified"

    prior_context = ""
    if prior_round_summaries:
        lines = []
        for rs in prior_round_summaries:
            lines.append(
                f"  - Round {rs['round_number']} ({rs['round_type']}): "
                f"score {rs['overall_score']:.0f}/100 — {rs['summary']}"
            )
        prior_context = (
            "\n\n## Prior round context (use this to personalize follow-ups)\n"
            + "\n".join(lines)
        )

    # Pull in interview-type-specific persona addendum
    try:
        from apps.interviews.services.interview_types import get_persona_addendum
        type_addendum = get_persona_addendum(round_type)
    except Exception:
        type_addendum = ""

    type_section = f"\n\n## Interview type specifics\n{type_addendum}" if type_addendum else ""

    return textwrap.dedent(f"""
        You are {name}, an expert technical interviewer at FixitLab.

        ## Your persona
        - Style: {persona['style']}
        - Tone: {persona['tone']}
        - Focus areas: {persona['focus']}
        - Behavioral quirks: {persona['quirks']}

        ## Candidate context
        - Name: {candidate_name}
        - Target role: {role}
        - Experience level: {level}
        - Primary technology: {tech}
        - Known skills: {skills_str}
        - Current employer: {company}
        {prior_context}{type_section}

        ## Interview structure
        This is round {round_number} of {total_rounds} total rounds.
        Round type: {round_type}.

        ## Rules you MUST follow
        1. NEVER break character or mention you are an AI.
        2. Keep each response under 60 words — you are speaking aloud.
        3. After acknowledging the candidate's answer, either:
           a. Ask a targeted follow-up that probes a specific claim they made, OR
           b. Transition naturally to the next question (only if the topic is exhausted).
        4. Reference specific things the candidate said — do not give generic feedback.
        5. If the answer was vague or short, gently press for a real example or specific tooling.
        6. If the answer was strong, escalate: probe an edge case, failure mode, or scale dimension.
        7. For HR rounds: be warm, but still guide toward concrete behavioral examples (STAR).
        8. Never reveal scores or tell the candidate how they are doing overall.
        9. Occasional filler phrases are encouraged: 'Right...', 'Hmm, interesting.', 'Got it.'
        10. Do NOT output JSON, bullet points, or markdown. Plain conversational text only.
    """).strip()


# ---------------------------------------------------------------------------
# Conversation reply (replaces generate_interviewer_reply)
# ---------------------------------------------------------------------------

def generate_interviewer_reply(
    *,
    persona_name: str,
    round_type: str,
    question_text: str,
    candidate_answer: str,
    score_hint: dict,
    profile_snapshot: dict,
    conversation_tail: list[dict],
    strong_streak: int = 0,
    round_number: int = 1,
    total_rounds: int = 3,
    prior_round_summaries: list[dict] | None = None,
) -> str:
    """
    Generate a contextual interviewer reply.
    Falls back to rule-based reply if LLM unavailable.
    """
    client = _get_client()
    if client is None:
        from apps.interviews.services.interview_ai import generate_interviewer_reply as _free_reply
        return _free_reply(
            persona_name=persona_name,
            round_type=round_type,
            question_text=question_text,
            candidate_answer=candidate_answer,
            score_hint=score_hint,
            profile_snapshot=profile_snapshot,
            conversation_tail=conversation_tail,
            strong_streak=strong_streak,
        )

    system = _build_system_prompt(
        persona_name=persona_name,
        round_type=round_type,
        profile_snapshot=profile_snapshot,
        round_number=round_number,
        total_rounds=total_rounds,
        prior_round_summaries=prior_round_summaries,
    )

    # Build message history
    messages: list[dict] = []
    for m in conversation_tail:
        role = "assistant" if m["role"] == "interviewer" else "user"
        messages.append({"role": role, "content": m["content"]})

    # Inject score hint as a hidden context note in the system turn
    quality = score_hint.get("quality", "adequate")
    score = score_hint.get("score", 50)
    hint_note = (
        f"\n\n[INTERNAL SCORING NOTE — do not mention to candidate: "
        f"quality={quality}, score={score:.0f}/100, "
        f"strong_streak={strong_streak}. "
        f"Adjust follow-up depth accordingly.]"
    )

    try:
        import anthropic  # noqa: PLC0415
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=150,
            system=system + hint_note,
            messages=messages,
        )
        reply = response.content[0].text.strip()
        # Safety: truncate if model ignores length instructions
        if len(reply) > 400:
            reply = reply[:400].rsplit(".", 1)[0] + "."
        return reply
    except Exception as exc:
        logger.warning("LLM reply failed (%s) — using rule-based fallback", exc)
        from apps.interviews.services.interview_ai import generate_interviewer_reply as _free_reply
        return _free_reply(
            persona_name=persona_name,
            round_type=round_type,
            question_text=question_text,
            candidate_answer=candidate_answer,
            score_hint=score_hint,
            profile_snapshot=profile_snapshot,
            conversation_tail=conversation_tail,
            strong_streak=strong_streak,
        )


# ---------------------------------------------------------------------------
# Dynamic follow-up question generation
# ---------------------------------------------------------------------------

def generate_follow_up_question(
    *,
    persona_name: str,
    round_type: str,
    question_text: str,
    candidate_answer: str,
    profile_snapshot: dict,
    conversation_tail: list[dict],
) -> str | None:
    """
    Generate a targeted follow-up question based on what the candidate said.
    Returns None if LLM unavailable or generation fails.
    """
    client = _get_client()
    if client is None:
        return None

    tech = profile_snapshot.get("primary_technology") or "their stack"
    level = profile_snapshot.get("experience_level") or "mid"

    system = textwrap.dedent(f"""
        You are {persona_name}, a technical interviewer.
        The candidate is a {level}-level engineer working with {tech}.

        Your task: given the original question and the candidate's answer,
        generate ONE sharp follow-up question that:
        - References something specific the candidate mentioned
        - Probes a gap, assumption, or claim they made
        - Is appropriate for {round_type} round
        - Is under 25 words
        - Is a question only — no preamble, no acknowledgment

        Output only the question text. No quotes. No numbering.
    """).strip()

    messages = [
        {
            "role": "user",
            "content": (
                f"Original question: {question_text}\n\n"
                f"Candidate answer: {candidate_answer}"
            ),
        }
    ]

    try:
        import anthropic  # noqa: PLC0415
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=60,
            system=system,
            messages=messages,
        )
        q = response.content[0].text.strip().strip('"').strip("'")
        return q if q.endswith("?") or len(q) > 10 else None
    except Exception as exc:
        logger.warning("Follow-up generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# AI Scorecard (replaces aggregate_round_scores + build_strengths_and_improvements)
# ---------------------------------------------------------------------------

def generate_ai_scorecard(
    *,
    round_type: str,
    round_number: int,
    total_rounds: int,
    profile_snapshot: dict,
    messages: list[dict],
    prior_round_summaries: list[dict] | None = None,
) -> dict:
    """
    Generate a rich AI scorecard using Claude.
    Returns dict compatible with InterviewReport fields.
    Falls back to heuristic scoring if LLM unavailable.
    """
    client = _get_client()
    if client is None:
        return _heuristic_scorecard(messages, round_type)

    tech = profile_snapshot.get("primary_technology") or "general DevOps"
    level = profile_snapshot.get("experience_level") or "mid"
    role = profile_snapshot.get("target_role") or "engineer"

    # Build transcript summary for scoring
    qa_pairs = []
    interviewer_q = None
    for m in messages:
        if m["role"] == "interviewer" and m.get("message_type") in ("question", "practical"):
            interviewer_q = m["content"]
        elif m["role"] == "candidate" and interviewer_q:
            score = m.get("score", 0) or 0
            qa_pairs.append({
                "question": interviewer_q[:200],
                "answer": m["content"][:300],
                "heuristic_score": score,
            })
            interviewer_q = None

    if not qa_pairs:
        return _heuristic_scorecard(messages, round_type)

    transcript_block = json.dumps(qa_pairs[:12], indent=2)

    prior_context = ""
    if prior_round_summaries:
        prior_context = "Prior rounds: " + "; ".join(
            f"Round {r['round_number']} score {r['overall_score']:.0f}" for r in prior_round_summaries
        )

    system = textwrap.dedent(f"""
        You are a senior engineering hiring manager evaluating a {level}-level {role}
        candidate for a {tech} role (round {round_number}/{total_rounds}, type: {round_type}).
        {prior_context}

        Analyze the Q&A transcript and return ONLY a valid JSON object with these exact keys:
        {{
          "technical_score": <0-100 float>,
          "communication_score": <0-100 float>,
          "problem_solving_score": <0-100 float>,
          "practical_score": <0-100 float>,
          "presence_score": <0-100 float>,
          "resume_alignment_score": <0-100 float>,
          "overall_score": <0-100 float>,
          "passed": <true|false>,
          "summary": "<2-3 sentence hiring recommendation>",
          "strengths": ["<specific strength 1>", "<specific strength 2>", "<specific strength 3>"],
          "improvements": ["<specific improvement 1>", "<specific improvement 2>", "<specific improvement 3>"],
          "study_plan_topics": ["<topic 1>", "<topic 2>", "<topic 3>"],
          "confidence_signals": "<1 sentence about candidate confidence and communication style>",
          "time_management_note": "<1 sentence about pacing>",
          "benchmark_comparison": "<1 sentence comparing to typical {level} candidates for {tech}>"
        }}

        Scoring rubric:
        - technical_score: correctness, depth, production awareness
        - communication_score: clarity, structure, conciseness
        - problem_solving_score: methodology, edge cases, trade-offs
        - practical_score: tool knowledge, commands, real examples cited
        - presence_score: confidence inferred from answer length/depth variance
        - resume_alignment_score: how well answers match claimed experience level
        - overall_score: weighted average (technical 35%, communication 20%, problem_solving 25%, practical 20%)
        - passed: overall_score >= 65

        Base strengths and improvements on SPECIFIC content from the transcript.
        No generic phrases like "good communication" without evidence.
    """).strip()

    try:
        import anthropic  # noqa: PLC0415
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=700,
            system=system,
            messages=[{"role": "user", "content": f"Transcript:\n{transcript_block}"}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON from response
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in LLM response")
        data = json.loads(json_match.group())
        # Ensure all required fields present
        data.setdefault("strengths", [])
        data.setdefault("improvements", [])
        data.setdefault("study_plan_topics", [])
        data.setdefault("summary", "Score generated by AI evaluation.")
        return data
    except Exception as exc:
        logger.warning("AI scorecard failed (%s) — using heuristic fallback", exc)
        return _heuristic_scorecard(messages, round_type)


# ---------------------------------------------------------------------------
# STAR method evaluator (behavioral rounds)
# ---------------------------------------------------------------------------

def evaluate_star_response(answer_text: str) -> dict:
    """
    Evaluate whether a candidate's behavioral answer follows STAR structure.
    Returns presence flags and a coaching note.
    """
    client = _get_client()
    if client is None:
        from apps.interviews.services.interview_ai import _score_star_coverage
        coverage = _score_star_coverage(answer_text)
        score = sum(coverage.values())
        missing = [k.capitalize() for k, v in coverage.items() if not v]
        return {
            "situation_present": coverage["situation"],
            "task_present": coverage["task"],
            "action_present": coverage["action"],
            "result_present": coverage["result"],
            "star_score": score,
            "missing_components": missing,
            "coaching_note": f"Add {', '.join(missing)} to complete your STAR response." if missing else "",
            "star_detected": score >= 3,
        }

    system = textwrap.dedent("""
        You analyze interview answers for STAR method structure.
        STAR = Situation, Task, Action, Result.

        Given an answer, return ONLY valid JSON:
        {
          "situation_present": <true|false>,
          "task_present": <true|false>,
          "action_present": <true|false>,
          "result_present": <true|false>,
          "star_score": <0-4 integer, count of STAR components present>,
          "missing_components": ["<component>", ...],
          "coaching_note": "<one sentence coaching tip if incomplete, empty string if full STAR>"
        }
    """).strip()

    try:
        import anthropic  # noqa: PLC0415
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=120,
            system=system,
            messages=[{"role": "user", "content": answer_text[:600]}],
        )
        raw = response.content[0].text.strip()
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group())
        data["star_detected"] = data.get("star_score", 0) >= 3
        return data
    except Exception:
        return {"star_detected": False, "coaching_note": ""}


# ---------------------------------------------------------------------------
# Heuristic fallbacks (identical to original scoring.py logic)
# ---------------------------------------------------------------------------

def _heuristic_scorecard(messages: list[dict], round_type: str) -> dict:
    """Reproduce original scoring.py output as fallback."""
    scores = [
        m.get("score", 0) or 0
        for m in messages
        if m.get("role") == "candidate" and m.get("score") is not None
    ]
    if not scores:
        avg = 0.0
    else:
        avg = sum(scores) / len(scores)

    strong = [s for s in scores if s >= 75]
    weak = [s for s in scores if s < 55]

    strengths = []
    improvements = []
    if strong:
        strengths.append(f"Strong answers on {len(strong)} question(s) — clear reasoning under pressure.")
    if round_type == "technical":
        strengths.append("Engaged with troubleshooting and technical follow-ups.")
    if weak:
        improvements.append(f"Deepen answers where score was below 55 — {len(weak)} area(s) flagged.")
    improvements.append("Add quantified outcomes (MTTR, uptime, cost) when describing past work.")

    passed = avg >= 65
    return {
        "technical_score": round(min(100, avg * 1.05), 1),
        "communication_score": round(min(100, avg * 0.95 + 5), 1),
        "problem_solving_score": round(min(100, avg), 1),
        "practical_score": round(min(100, avg * 1.1), 1),
        "presence_score": 72.0,
        "resume_alignment_score": 68.0,
        "overall_score": round(avg, 1),
        "passed": passed,
        "summary": (
            "Solid performance." if passed else
            "Below passing threshold — focus on depth and real examples."
        ),
        "strengths": strengths[:5],
        "improvements": improvements[:5],
        "study_plan_topics": [],
        "confidence_signals": "",
        "time_management_note": "",
        "benchmark_comparison": "",
    }


def _rule_based_reply(
    *,
    persona_name: str,
    round_type: str,
    candidate_answer: str,
    score_hint: dict,
    profile_snapshot: dict,
    strong_streak: int,
) -> str:
    """Original rule-based reply from interview_ai.py — kept as LLM fallback."""
    import random  # noqa: PLC0415

    _REACTIONS_STRONG = [
        "Right — and in production, how would you prove that quickly?",
        "Okay, I hear you. What would break first if we scaled that 10x?",
        "That's a solid line of thinking. What metric would you watch after the change?",
    ]
    _REACTIONS_WEAK = [
        "I'd want a bit more depth there — walk me through your mental checklist.",
        "Help me understand the sequence — what do you check first, second?",
        "Let's slow down — what's the failure mode you're most worried about?",
    ]
    _REACTIONS_BRIEF = [
        "Short answer — can you expand with a real incident or example?",
        "I didn't catch the full picture — what tools or commands would you use?",
    ]
    _REACTIONS_SKIPPED = [
        "No worries, let's keep moving —",
        "We'll come back to that theme later — for now,",
    ]
    _CASUAL_HR = [
        "By the way, how's the team culture where you are now?",
        "What would make you say yes to an offer in the next month?",
    ]
    _ITIL_NUDGES = [
        "Where does that sit with change management — normal, standard, or emergency?",
        "Who owns the SLA clock when vendors are in the blast radius?",
    ]

    quality = score_hint.get("quality", "adequate")
    company = profile_snapshot.get("current_company") or "your current org"
    role = profile_snapshot.get("target_role") or "engineer"

    if quality == "skipped":
        base = random.choice(_REACTIONS_SKIPPED)
    elif quality == "strong":
        base = random.choice(_REACTIONS_STRONG)
        if strong_streak >= 5:
            base = f"Let me push harder — what's the nastiest edge case you've seen with this at {company}?"
    elif quality == "weak":
        base = random.choice(_REACTIONS_WEAK)
    elif quality == "brief":
        base = random.choice(_REACTIONS_BRIEF)
    else:
        base = score_hint.get("feedback", "Tell me more about how you'd validate that.")

    if round_type == "hr" and random.random() < 0.35:
        return f"{base} {random.choice(_CASUAL_HR)}"
    if round_type == "manager" and random.random() < 0.4:
        return f"{base} {random.choice(_ITIL_NUDGES)}"
    if "resume" in (candidate_answer or "").lower():
        return f"{base} Your resume mentions {role} work — how does that tie to what you just described?"

    follow_templates = [
        f"{base} If this happened on a Friday evening at {company}, what's step one?",
        f"{base} What would you log so the next engineer isn't guessing?",
    ]
    return random.choice(follow_templates)
