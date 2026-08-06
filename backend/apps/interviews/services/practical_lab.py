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
keyed by question id (banked) or message id (generated), so the next ``/message/``
answer for that question is scored with ``command_validated=True`` (the +15 bonus
in scoring.py) automatically.
"""

from __future__ import annotations

import logging
import re

from django.db import transaction

from apps.interviews.models import InterviewMessage, InterviewRound
from apps.labs.capacity import at_global_capacity
from apps.labs.infra import lab_infra_type
from apps.labs.models import LabSession
# Re-exported into this module's namespace on purpose: the provisioning half is
# shared with apps.labs.sessions.start_lab_session (one implementation, not two
# that can drift), and tests patch it at `practical_lab.provision_reserved_session`.
from apps.labs.sessions import provision_reserved_session
from apps.question_bank.models import Scenario

logger = logging.getLogger(__name__)

# Mirrors public_api.views.LAB_CAPACITY_FULL_RESPONSE so the interview UI can
# show the same "retry soon" message instead of a generic provisioning error.
LAB_CAPACITY_FULL = {
    "error": "All lab capacity is in use right now — please try again in a few minutes.",
    "code": "CAPACITY_FULL",
}


def _practical_config_from_message(msg: InterviewMessage | None) -> dict:
    """Resolve practical_config from message metadata and/or banked question."""
    if not msg:
        return {}
    meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    config = dict(meta.get("practical_config") or {})
    if msg.question_id and msg.question:
        banked = msg.question.practical_config or {}
        if isinstance(banked, dict):
            merged = dict(banked)
            merged.update(config)
            config = merged
    return config


def _validation_key(msg: InterviewMessage) -> str:
    if msg.question_id:
        return str(msg.question_id)
    return f"msg:{msg.id}"


def _current_practical_message(round_obj: InterviewRound) -> InterviewMessage | None:
    """The most recent practical / live-coding question asked this round."""
    for msg in (
        round_obj.messages.filter(role="interviewer")
        .select_related("question")
        .order_by("-created_at")[:12]
    ):
        meta = msg.metadata if isinstance(msg.metadata, dict) else {}
        pc = meta.get("practical_config") if isinstance(meta.get("practical_config"), dict) else {}
        if msg.message_type == "practical":
            return msg
        if meta.get("kind") in ("live_coding", "live_coding_followup"):
            return msg
        if pc.get("kind") in ("code", "command"):
            return msg
    return (
        round_obj.messages.filter(question__category="practical", question__isnull=False)
        .select_related("question")
        .order_by("-created_at")
        .first()
    )


def _fallback_scenario_slug(round_obj: InterviewRound) -> str | None:
    """Best-effort default lab when a generated practical omits scenario_slug."""
    snap = round_obj.campaign.profile_snapshot if round_obj.campaign else {}
    if not isinstance(snap, dict):
        snap = {}
    tech = str(snap.get("primary_technology_slug") or snap.get("primary_technology_name") or "").lower()
    if any(k in tech for k in ("k8s", "kube", "kubernetes")):
        return "sim-k8s-crashloop"
    if any(k in tech for k in ("docker", "container")):
        return "sim-rhel-nginx-down"
    return "sim-rhel-ssh-stop"


def _practical_scenario_slug(round_obj: InterviewRound) -> str | None:
    msg = _current_practical_message(round_obj)
    if not msg:
        return _fallback_scenario_slug(round_obj)
    config = _practical_config_from_message(msg)
    slug = config.get("scenario_slug")
    if slug:
        return slug
    # Code-only live coding does not require a lab session.
    if config.get("kind") == "code" and not config.get("scenario_slug"):
        return None
    return _fallback_scenario_slug(round_obj)


def start_practical_lab(user, round_obj: InterviewRound) -> dict:
    """Provision lab for current practical question; idempotent per round."""
    if round_obj.practical_lab_session_id:
        session = LabSession.objects.filter(id=round_obj.practical_lab_session_id).first()
        if session:
            return _session_payload(session)

    slug = _practical_scenario_slug(round_obj)
    if not slug:
        return {
            "error": "Inline code grading is available — no terminal lab needed for this task.",
            "code": "NO_PRACTICAL",
            "inline_only": True,
        }

    scenario = Scenario.objects.filter(slug=slug, is_active=True).first()
    if not scenario:
        return {"error": f"Scenario '{slug}' not found on this server", "code": "SCENARIO_MISSING"}

    from apps.labs.start_gates import lab_start_block_reason

    block = lab_start_block_reason(user, scenario)
    if block:
        return block

    # ── Global capacity gate + row INSERT in ONE atomic block (audit L1506/L1511) ──
    # This path previously called start_lab_session(), which back then created the
    # LabSession without ever consulting at_global_capacity() — so interview
    # practical labs bypassed the MAX_CONCURRENT_LABS ceiling entirely and could
    # drive the engine past exhaustion no matter how many labs were already live.
    # (start_lab_session now gates too, but this path stays inlined: it needs to
    # return LAB_CAPACITY_FULL as a payload rather than raise, and it records the
    # session on the round between the reserve and provision phases.)
    #
    # We follow the reference pattern in public_api/views.py (the StartLabView
    # path): at_global_capacity() takes a transaction-scoped advisory lock and
    # re-counts live sessions under it, and because we hold that lock through the
    # INSERT below, "count < cap ⇒ create" is atomic and cannot overshoot.
    #
    # Provisioning is deliberately kept OUTSIDE the atomic block (see the comment
    # at public_api/views.py:119): provisioner.provision() does network I/O
    # (SSH/API round trips), and holding the platform-wide advisory lock across it
    # would serialise every lab start on the platform behind the slowest provision.
    infra_type = lab_infra_type(scenario)
    try:
        with transaction.atomic():
            if at_global_capacity(infra_type):
                return dict(LAB_CAPACITY_FULL)

            session = LabSession.objects.create(
                user=user,
                scenario=scenario,
                status="PROVISIONING",
                provider=infra_type,
            )
    except Exception:
        logger.exception("Interview practical lab reserve failed round=%s", round_obj.id)
        return {"error": "Could not start the practical lab environment.", "code": "PROVISION_FAILED"}

    # The row now holds a capacity slot; provision it (or release the slot on
    # failure so a dead PROVISIONING row doesn't permanently consume the cap).
    try:
        session = provision_reserved_session(session)
        round_obj.practical_lab_session_id = session.id
        round_obj.save(update_fields=["practical_lab_session_id"])
        return _session_payload(session)
    except Exception:
        logger.exception("Interview practical lab failed round=%s", round_obj.id)
        return {"error": "Could not start the practical lab environment.", "code": "PROVISION_FAILED"}


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

_MAX_ANSWER_CHARS = 8000


def _normalize_cmd(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _matches_patterns(answer: str, patterns: list) -> bool:
    """True if the answer matches ANY configured pattern."""
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


def _record_validation(round_obj: InterviewRound, validation_key, *, validated: bool, detail: dict) -> None:
    meta = round_obj.metadata or {}
    bucket = meta.setdefault("practical_validations", {})
    bucket[str(validation_key)] = {"validated": bool(validated), **detail}
    round_obj.metadata = meta
    try:
        round_obj.save(update_fields=["metadata"])
    except Exception:  # noqa: BLE001
        logger.exception("could not persist practical validation round=%s", round_obj.id)


def practical_validation_passed(round_obj: InterviewRound, validation_key) -> bool:
    """Was the practical answer for this question/message already validated?"""
    bucket = (round_obj.metadata or {}).get("practical_validations", {})
    return bool(bucket.get(str(validation_key), {}).get("validated"))


def _grade_command_answer(round_obj: InterviewRound, question, answer: str, config: dict) -> dict:
    patterns = config.get("expected_commands") or config.get("validate_commands") or []
    if patterns and _matches_patterns(answer, patterns):
        return {
            "validated": True,
            "method": "command_pattern",
            "feedback": "Correct — that's exactly the command I'd expect here. Nicely done.",
        }

    slug = config.get("scenario_slug")
    session_id = round_obj.practical_lab_session_id
    if slug and session_id:
        graded = _grade_via_simulation(session_id, slug, answer)
        if graded is not None:
            return graded

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
    try:
        session = LabSession.objects.select_related("scenario").filter(id=session_id).first()
        if not session or (session.provider or "") != "simulation":
            return None

        from apps.labs.provisioner import get_provisioner

        provisioner = get_provisioner(session.provider or "simulation")
        resource_id = session.container_id or session.instance_id
        if not resource_id:
            return None

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
                        except Exception:  # noqa: BLE001
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


_SUBMISSION_FILENAME = "_submission.py"


def _needs_submission_file(tests: list[dict]) -> bool:
    """True if any test snippet reads the candidate's source off disk.

    The live_coding.py problem bank grades by grepping ``_submission.py``, but
    code_exec's python harness only ever writes ``_runner.py`` and exec()s the
    submission from an in-memory string — the file never exists. Every one of
    those tests therefore died with FileNotFoundError, so a perfect answer
    always scored 0/N. Detected here rather than assumed for every submission:
    materialising the file is only correct for tests that ask for it.
    """
    return any(_SUBMISSION_FILENAME in (t.get("code") or "") for t in tests)


def _with_submission_file(answer: str) -> str:
    """Append a shim that writes the candidate's source to ``_submission.py``.

    Appended (not prepended) so a traceback from the candidate's own code still
    reports the line numbers they wrote. The sandbox cwd is a per-submission
    temp dir (in-process) or the writable ``/work`` tmpfs (container), so this
    write is isolated and disposable in both backends. Failures are swallowed:
    an unwritable cwd should leave the source-grep tests failing exactly as
    before, never break an otherwise-runnable submission.
    """
    shim = (
        "\ntry:\n"
        "    with open(" + repr(_SUBMISSION_FILENAME) + ", 'w', encoding='utf-8') as _fh:\n"
        "        _fh.write(" + repr(answer) + ")\n"
        "except Exception:\n"
        "    pass\n"
    )
    return answer + shim


def _grade_code_answer(round_obj: InterviewRound, question, answer: str, code_spec: dict) -> dict:
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
        source = answer
        if language == "python" and _needs_submission_file(tests):
            source = _with_submission_file(answer)
        result = grade_submission(language, source, tests, timeout=int(code_spec.get("timeout", 8)))
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
    """Validate a candidate's inline practical command/code answer."""
    answer = (answer or "")[:_MAX_ANSWER_CHARS]
    msg = _current_practical_message(round_obj)
    if not msg:
        return {
            "validated": False,
            "method": "unverified",
            "feedback": "There's no active practical task to check right now.",
            "question_id": None,
            "code": "NO_PRACTICAL",
        }

    config = _practical_config_from_message(msg)
    if not config:
        return {
            "validated": False,
            "method": "unverified",
            "feedback": "This practical task has no validation config yet.",
            "question_id": msg.question_id,
            "code": "NO_CONFIG",
        }

    if not answer.strip():
        return {
            "validated": False,
            "method": "unverified",
            "feedback": "Type the command or code you'd run, then I'll check it.",
            "question_id": msg.question_id,
        }

    code_spec = config.get("code")
    if code_spec and (code_spec.get("tests")):
        result = _grade_code_answer(round_obj, msg.question, answer, code_spec)
        if not result.get("validated"):
            signals = config.get("expected_signals") or []
            if signals:
                from apps.interviews.services.live_coding import grade_by_signals

                sig = grade_by_signals(answer, signals)
                if sig.get("partial_signals"):
                    result = {**result, **sig, "validated": False}
    elif config.get("expected_signals") and config.get("kind") == "code":
        from apps.interviews.services.live_coding import grade_by_signals

        result = grade_by_signals(answer, config.get("expected_signals") or [])
    else:
        result = _grade_command_answer(round_obj, msg.question, answer, config)

    vkey = _validation_key(msg)
    result["question_id"] = msg.question_id
    result["validation_key"] = vkey
    _record_validation(
        round_obj,
        vkey,
        validated=result["validated"],
        detail={"method": result.get("method"), "answer": answer[:500]},
    )
    return result
