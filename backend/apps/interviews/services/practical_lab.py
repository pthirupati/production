"""Start FixitLab lab sessions for interview practical segments + validate
inline command/code answers (P2.4).

Two ways a candidate proves a practical answer, both 100% free and deterministic
(no paid API, no LLM):

1. **Command answer** — they type the command(s) they'd run. We grade those
   against the practical question's configured expectation:
     a. ``practical_config.expected_commands`` / ``validate_commands`` — a list of
        accepted command patterns (substring or regex). Pure-Python, no lab needed.
     b. ``practical_config.scenario_slug`` — we reuse the labs SIMULATION validator
        (``apps.labs.provisioner.simulation`` via the provisioner ``run_validation``)
        on the live lab session the bridge provisioned, so the candidate's typed
        command is checked against the *same* ``check.sh`` rules the labs use.

2. **Code answer** — for coding-style practical questions
   (``practical_config.code`` carries tests), we reuse the labs sandbox grader
   ``apps.labs.code_exec.grade_submission`` (the exact engine the coding IDE uses).

A successful validation is stamped onto ``round.metadata['practical_validations']``
keyed by question id, so the next ``/message/`` answer for that question is scored
with ``command_validated=True`` (the +15 bonus in scoring.py) automatically.
"""

from __future__ import annotations

import logging
import re

from apps.interviews.models import InterviewMessage, InterviewRound
from apps.labs.models import LabSession
from apps.labs.sessions import start_lab_session
from apps.question_bank.models import Scenario

logger = logging.getLogger(__name__)


def _current_practical_message(round_obj: InterviewRound) -> InterviewMessage | None:
    """The most recent practical question asked this round (with its config)."""
    msg = (
        round_obj.messages.filter(message_type="practical", question__isnull=False)
        .select_related("question")
        .order_by("-created_at")
        .first()
    )
    if not msg:
        msg = (
            round_obj.messages.filter(question__category="practical", question__isnull=False)
            .select_related("question")
            .order_by("-created_at")
            .first()
        )
    return msg


def _practical_scenario_slug(round_obj: InterviewRound) -> str | None:
    msg = _current_practical_message(round_obj)
    if not msg or not msg.question:
        return None
    return (msg.question.practical_config or {}).get("scenario_slug")


def start_practical_lab(user, round_obj: InterviewRound) -> dict:
    """Provision lab for current practical question; idempotent per round."""
    if round_obj.practical_lab_session_id:
        session = LabSession.objects.filter(id=round_obj.practical_lab_session_id).first()
        if session:
            return _session_payload(session)

    slug = _practical_scenario_slug(round_obj)
    if not slug:
        return {"error": "No practical scenario configured for this round", "code": "NO_PRACTICAL"}

    scenario = Scenario.objects.filter(slug=slug, is_active=True).first()
    if not scenario:
        return {"error": f"Scenario '{slug}' not found on this server", "code": "SCENARIO_MISSING"}

    try:
        session = start_lab_session(user, scenario)
        round_obj.practical_lab_session_id = session.id
        round_obj.save(update_fields=["practical_lab_session_id"])
        return _session_payload(session)
    except Exception as exc:
        logger.exception("Interview practical lab failed round=%s", round_obj.id)
        return {"error": str(exc)[:200], "code": "PROVISION_FAILED"}


def _session_payload(session: LabSession) -> dict:
    return {
        "session_id": str(session.id),
        "status": session.status,
        "scenario_slug": session.scenario.slug if session.scenario_id else "",
        "scenario_title": session.scenario.title if session.scenario_id else "",
        "lab_url": f"/lab/{session.id}",
    }


# ---------------------------------------------------------------------------
# Inline practical answer validation (P2.4)
# ---------------------------------------------------------------------------

# Cap accepted inputs so a pathological answer can't blow up grading.
_MAX_ANSWER_CHARS = 8000


def _normalize_cmd(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _matches_patterns(answer: str, patterns: list) -> bool:
    """True if the answer matches ANY configured pattern.

    A pattern is matched if it appears as a normalized substring of the answer,
    OR (when it looks like a regex / the substring test fails) it matches as a
    regular expression. Deterministic, free, no shell execution.
    """
    low = _normalize_cmd(answer)
    if not low:
        return False
    for raw in patterns or []:
        pat = _normalize_cmd(str(raw))
        if not pat:
            continue
        if pat in low:
            return True
        try:
            if re.search(pat, low):
                return True
        except re.error:
            continue
    return False


def _record_validation(round_obj: InterviewRound, question_id, *, validated: bool, detail: dict) -> None:
    """Persist the latest validation for this question on round.metadata so the
    follow-up /message/ answer is scored with command_validated when it passed.

    Uses the existing ``metadata`` JSONField — no migration required.
    """
    meta = round_obj.metadata or {}
    bucket = meta.setdefault("practical_validations", {})
    bucket[str(question_id)] = {"validated": bool(validated), **detail}
    round_obj.metadata = meta
    try:
        round_obj.save(update_fields=["metadata"])
    except Exception:  # noqa: BLE001 - persistence is best-effort, never 500 a live round
        logger.exception("could not persist practical validation round=%s", round_obj.id)


def practical_validation_passed(round_obj: InterviewRound, question_id) -> bool:
    """Was the practical answer for this question already validated as correct?"""
    bucket = (round_obj.metadata or {}).get("practical_validations", {})
    return bool(bucket.get(str(question_id), {}).get("validated"))


def _grade_command_answer(round_obj: InterviewRound, question, answer: str, config: dict) -> dict:
    """Validate a typed command answer.

    Order:
      1. Configured accepted command patterns (no lab needed) — fast, deterministic.
      2. If a scenario_slug + a live lab session exist, run the SAME simulation
         validator the labs use against the candidate's command(s).
    """
    patterns = config.get("expected_commands") or config.get("validate_commands") or []
    if patterns and _matches_patterns(answer, patterns):
        return {
            "validated": True,
            "method": "command_pattern",
            "feedback": "Correct — that's exactly the command I'd expect here. Nicely done.",
        }

    # Try the real labs simulation validator against the provisioned session.
    slug = config.get("scenario_slug")
    session_id = round_obj.practical_lab_session_id
    if slug and session_id:
        graded = _grade_via_simulation(session_id, slug, answer)
        if graded is not None:
            return graded

    # Couldn't prove it. Give actionable, specific feedback (never auto-pass).
    if patterns:
        hint = patterns[0]
        return {
            "validated": False,
            "method": "command_pattern",
            "feedback": f"Not quite — I'm looking for something closer to `{hint}`. "
            "Check the exact subcommand and target, then try again.",
        }
    return {
        "validated": False,
        "method": "unverified",
        "feedback": "Walk me through the precise command and what its output would tell you — "
        "I want to see the exact tool and flags you'd run.",
    }


def _grade_via_simulation(session_id, slug: str, answer: str) -> dict | None:
    """Run the candidate's typed command(s) through the labs SIMULATION validator.

    We feed each non-empty line the candidate typed into the lab session's
    simulation engine (the same engine the terminal labs drive), then run the
    scenario's validation script against the resulting state — reusing
    ``run_validation`` so the verdict matches the labs' own ``check.sh`` logic.

    Returns a result dict, or None if this path isn't applicable (so the caller
    can fall back). Never raises — a grader failure degrades to "unverified".
    """
    try:
        session = LabSession.objects.select_related("scenario").filter(id=session_id).first()
        if not session or (session.provider or "") != "simulation":
            return None

        from apps.labs.provisioner import get_provisioner

        provisioner = get_provisioner(session.provider or "simulation")
        resource_id = session.container_id or session.instance_id
        if not resource_id:
            return None

        # Replay the candidate's commands into the sim so state reflects their fix.
        entry = None
        try:
            from apps.labs.provisioner.simulation_provisioner import (
                ensure_sim_session,
                get_sim_session_by_resource,
            )

            entry = get_sim_session_by_resource(resource_id) or ensure_sim_session(session)
        except Exception:  # noqa: BLE001
            entry = None
        engine = (entry or {}).get("state", {}).get("engine") if entry else None
        if engine is not None:
            # Drive each typed line through the SAME line executor the terminal
            # uses (_handle_shell → RHELShell.run), which mutates engine.state.
            # run_validation then reads that state, so the verdict matches the
            # labs' own check.sh logic. Fall back to shell.run if needed.
            runner = None
            if hasattr(engine, "_handle_shell"):
                runner = engine._handle_shell
            elif getattr(engine, "shell", None) is not None and hasattr(engine.shell, "run"):
                runner = engine.shell.run
            if runner is not None:
                for line in (answer or "").splitlines():
                    cmd = line.strip()
                    if cmd:
                        try:
                            runner(cmd)
                        except Exception:  # noqa: BLE001 - a bad command shouldn't crash grading
                            continue

        db_script = (session.scenario.validation_script or "").strip()
        passed, output = provisioner.run_validation(
            resource_id, db_script, scenario_slug=session.scenario.slug or slug,
        )
        if passed:
            return {
                "validated": True,
                "method": "simulation",
                "feedback": "Verified against the live environment — the scenario checks pass. Solid work.",
            }
        return {
            "validated": False,
            "method": "simulation",
            "feedback": _clean_validator_output(output)
            or "The environment checks didn't pass yet — keep going on the fix.",
        }
    except Exception:  # noqa: BLE001
        logger.exception("interview practical simulation grade failed session=%s", session_id)
        return None


def _clean_validator_output(output: str) -> str:
    out = (output or "").strip()
    if not out or out in ("NO_VALIDATION_SCRIPT",):
        return ""
    return out[:300]


def _grade_code_answer(round_obj: InterviewRound, question, answer: str, code_spec: dict) -> dict:
    """Grade a coding-style practical answer with the labs sandbox grader.

    ``code_spec`` mirrors the labs coding_spec shape:
        {"language": "python", "tests": [{"name", "code", "hidden"}], "timeout": 8}
    Reuses ``apps.labs.code_exec.grade_submission`` (the IDE's grader) verbatim —
    fail-closed: no tests / unsupported language => not validated.
    """
    try:
        from apps.labs.code_exec import grade_submission

        language = (code_spec.get("language") or "python").lower()
        tests = [
            {
                "name": t.get("name", f"t{i}"),
                "code": t.get("code", ""),
                "hidden": bool(t.get("hidden")),
            }
            for i, t in enumerate(code_spec.get("tests") or [])
        ]
        result = grade_submission(language, answer, tests, timeout=int(code_spec.get("timeout", 8)))
        if result.all_passed:
            return {
                "validated": True,
                "method": "code",
                "feedback": "All tests pass — your implementation is correct. Let's build on that.",
            }
        if result.needs_review:
            return {
                "validated": False,
                "method": "code",
                "feedback": (result.error or "I can't auto-grade this one — talk me through your approach instead."),
            }
        passed = result.public_dict().get("passed_count", 0)
        total = result.public_dict().get("total_count", 0)
        detail = (result.error or "").strip()
        msg = f"{passed}/{total} tests pass."
        if detail:
            msg += f" {detail[:200]}"
        msg += " Review the failing case and resubmit."
        return {"validated": False, "method": "code", "feedback": msg}
    except Exception:  # noqa: BLE001
        logger.exception("interview practical code grade failed round=%s", round_obj.id)
        return {
            "validated": False,
            "method": "code",
            "feedback": "Couldn't run that just now — describe your approach and I'll follow along.",
        }


def validate_practical_answer(round_obj: InterviewRound, answer: str) -> dict:
    """Validate a candidate's inline practical command/code answer.

    Returns:
        {
          "validated": bool,
          "method": "command_pattern" | "simulation" | "code" | "unverified",
          "feedback": str,
          "question_id": int | None,
        }

    Deterministic + free. On success, stamps round.metadata so the candidate's
    next /message/ answer is scored with the practical (+15) bonus.
    """
    answer = (answer or "")[:_MAX_ANSWER_CHARS]
    msg = _current_practical_message(round_obj)
    question = msg.question if msg else None
    if not question:
        return {
            "validated": False,
            "method": "unverified",
            "feedback": "There's no active practical task to check right now.",
            "question_id": None,
            "code": "NO_PRACTICAL",
        }

    if not answer.strip():
        return {
            "validated": False,
            "method": "unverified",
            "feedback": "Type the command or code you'd run, then I'll check it.",
            "question_id": question.id,
        }

    config = question.practical_config or {}
    code_spec = config.get("code")
    if code_spec and (code_spec.get("tests")):
        result = _grade_code_answer(round_obj, question, answer, code_spec)
    else:
        result = _grade_command_answer(round_obj, question, answer, config)

    result["question_id"] = question.id
    _record_validation(
        round_obj,
        question.id,
        validated=result["validated"],
        detail={"method": result.get("method"), "answer": answer[:500]},
    )
    return result
