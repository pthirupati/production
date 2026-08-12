"""Optional interview voice stack — simulation-first (audit ENG_EPIC).

FixitLab default (like Jira / lab sims):
  * TTS  → browser SpeechSynthesis (simulates Piper / IndicF5)
  * STT  → browser SpeechRecognition (simulates faster-whisper / IndicWhisper)
  * LLM  → in-process phrasing normalizer (simulates llama.cpp / vLLM)

Real hosts activate only when the matching env points at a binary/URL.
No model weights are bundled in the repo.

Env (real overrides):
  FIXITLAB_PIPER_BIN / FIXITLAB_PIPER_VOICE
  FIXITLAB_INDICF5_URL / FIXITLAB_INDICF5_REF_B64
  FIXITLAB_FASTER_WHISPER_URL / FIXITLAB_FASTER_WHISPER_API
  FIXITLAB_INDIC_WHISPER_URL
  FIXITLAB_LLM_GENERATE_URL / FIXITLAB_LLM_API_KEY / FIXITLAB_LLM_MODEL

Simulation toggles (Django settings, default True):
  INTERVIEW_VOICE_SIMULATION_MODE
  INTERVIEW_LLM_SIMULATION_MODE
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _setting_bool(name: str, default: bool = True) -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, name, default))
    except Exception:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")


def voice_simulation_enabled() -> bool:
    return _setting_bool("INTERVIEW_VOICE_SIMULATION_MODE", True)


def llm_simulation_enabled() -> bool:
    return _setting_bool("INTERVIEW_LLM_SIMULATION_MODE", True)


def domain_vocab_prompt(*, extra: str = "") -> str:
    """Cheap ASR accuracy win: domain tokens already in the repo (audit Y1e)."""
    tokens: list[str] = []
    try:
        from .realism.callbacks import _TECH_HINTS

        tokens.extend(_TECH_HINTS)
    except Exception:
        pass
    try:
        from .question_generator import _TOOL_DRILLS

        tokens.extend(_TOOL_DRILLS.keys())
    except Exception:
        pass
    # Stable, capped — whisper initial_prompt budgets are small.
    uniq = sorted({t.lower().strip() for t in tokens if t and len(str(t)) >= 2})
    base = " ".join(uniq[:80])
    extra = (extra or "").strip()
    if extra:
        return f"{base} {extra}".strip()
    return base


def voice_stack_status() -> dict[str, Any]:
    """Report simulation vs real providers."""
    piper = os.environ.get("FIXITLAB_PIPER_BIN") or ""
    llm_url = (os.environ.get("FIXITLAB_LLM_GENERATE_URL") or "").strip()
    piper_real = bool(piper and Path(piper).exists()) or bool(
        shutil.which("piper") and os.environ.get("FIXITLAB_PIPER_VOICE")
    )
    return {
        "simulation": voice_simulation_enabled(),
        "llm_simulation": llm_simulation_enabled(),
        "piper": piper_real,
        "piper_sim": voice_simulation_enabled() and not piper_real,
        "indicf5": bool(os.environ.get("FIXITLAB_INDICF5_URL")),
        "indicf5_sim": voice_simulation_enabled() and not bool(os.environ.get("FIXITLAB_INDICF5_URL")),
        "faster_whisper": bool(os.environ.get("FIXITLAB_FASTER_WHISPER_URL")),
        "faster_whisper_sim": voice_simulation_enabled()
        and not bool(os.environ.get("FIXITLAB_FASTER_WHISPER_URL")),
        "indic_whisper": bool(os.environ.get("FIXITLAB_INDIC_WHISPER_URL")),
        "indic_whisper_sim": voice_simulation_enabled()
        and not bool(os.environ.get("FIXITLAB_INDIC_WHISPER_URL")),
        "llm_generate": bool(llm_url) or llm_simulation_enabled(),
        "llm_generate_sim": llm_simulation_enabled() and not bool(llm_url),
        "llm_url_normalized": _normalize_chat_url(llm_url) if llm_url else "",
        "default": "simulation" if voice_simulation_enabled() else "browser",
    }


def synthesize_piper(text: str, *, voice: str | None = None) -> bytes | None:
    """Run Piper CLI → WAV bytes. Returns None when not configured / failed."""
    binary = os.environ.get("FIXITLAB_PIPER_BIN") or which_piper() or ""
    model = voice or os.environ.get("FIXITLAB_PIPER_VOICE") or ""
    if not binary or not Path(binary).exists() or not text.strip():
        return None
    if not model:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            cmd = [binary, "--model", model, "--output_file", str(out)]
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0 or not out.exists():
                logger.info("piper failed rc=%s stderr=%s", proc.returncode, proc.stderr[:200])
                return None
            return out.read_bytes()
    except Exception:
        logger.debug("piper synthesize failed", exc_info=True)
        return None


def _post_json(url: str, payload: dict, timeout: float = 30.0, *, headers: dict | None = None) -> dict | None:
    if not url:
        return None
    try:
        import urllib.request
        import json

        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=hdrs,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.debug("voice stack POST %s failed", url, exc_info=True)
        return None


def _post_multipart_transcription(
    url: str,
    audio_wav: bytes,
    *,
    language: str,
    prompt: str,
    model: str,
    timeout: float = 60.0,
) -> dict | None:
    """OpenAI-compatible /v1/audio/transcriptions (faster-whisper-server, etc.)."""
    if not url or not audio_wav:
        return None
    try:
        import uuid
        import json
        import urllib.request

        boundary = f"----fixitlab{uuid.uuid4().hex}"
        parts: list[bytes] = []

        def field(name: str, value: str) -> None:
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        field("model", model)
        field("language", language)
        field("response_format", "verbose_json")
        if prompt:
            field("prompt", prompt)
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
                f"Content-Type: audio/wav\r\n\r\n"
            ).encode("utf-8")
        )
        parts.append(audio_wav)
        parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.debug("openai whisper POST %s failed", url, exc_info=True)
        return None


def synthesize_indicf5(text: str, *, lang: str = "hi", ref_audio_b64: str | None = None) -> bytes | None:
    """IndicF5 HTTP adapter (Hindi/Telugu). Needs consented reference clip in prod."""
    url = os.environ.get("FIXITLAB_INDICF5_URL") or ""
    ref = ref_audio_b64 or os.environ.get("FIXITLAB_INDICF5_REF_B64") or None
    data = _post_json(url, {"text": text, "lang": lang, "ref_audio_b64": ref})
    if not data:
        return None
    b64 = data.get("audio_b64")
    if not b64:
        return None
    import base64

    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _whisper_api_mode(url: str) -> str:
    explicit = (os.environ.get("FIXITLAB_FASTER_WHISPER_API") or "").strip().lower()
    if explicit in ("openai", "json"):
        return explicit
    low = (url or "").lower()
    if "transcriptions" in low or "/v1/audio" in low:
        return "openai"
    return "json"


def _normalize_whisper_openai_url(url: str) -> str:
    u = (url or "").rstrip("/")
    if not u:
        return ""
    if u.endswith("/transcriptions"):
        return u
    if u.endswith("/v1/audio"):
        return u + "/transcriptions"
    if u.endswith("/v1"):
        return u + "/audio/transcriptions"
    if "/v1/" not in u and not u.endswith("/audio/transcriptions"):
        return u + "/v1/audio/transcriptions"
    return u


def transcribe_faster_whisper(
    audio_wav: bytes,
    *,
    language: str = "en",
    prompt: str | None = None,
) -> dict | None:
    """faster-whisper HTTP adapter — JSON blob or OpenAI-compatible multipart."""
    url = os.environ.get("FIXITLAB_FASTER_WHISPER_URL") or ""
    if not url or not audio_wav:
        return None
    init_prompt = prompt if prompt is not None else domain_vocab_prompt()
    model = os.environ.get("FIXITLAB_FASTER_WHISPER_MODEL") or "small"
    mode = _whisper_api_mode(url)
    if mode == "openai":
        data = _post_multipart_transcription(
            _normalize_whisper_openai_url(url),
            audio_wav,
            language=language,
            prompt=init_prompt,
            model=model,
        )
    else:
        import base64

        data = _post_json(
            url,
            {
                "audio_b64": base64.b64encode(audio_wav).decode("ascii"),
                "language": language,
                "model": model,
                "initial_prompt": init_prompt,
            },
        )
    if not data:
        return None
    # Normalize OpenAI verbose_json → our fields.
    if "text" in data and "avg_logprob" not in data:
        segs = data.get("segments") or []
        if segs:
            probs = [float(s.get("avg_logprob") or 0.0) for s in segs if "avg_logprob" in s]
            if probs:
                data = {**data, "avg_logprob": sum(probs) / len(probs)}
            nsp = [float(s.get("no_speech_prob") or 0.0) for s in segs if "no_speech_prob" in s]
            if nsp:
                data = {**data, "no_speech_prob": sum(nsp) / len(nsp)}
    return data


def transcribe_indic_whisper(
    audio_wav: bytes,
    *,
    language: str = "hi",
    prompt: str | None = None,
) -> dict | None:
    url = os.environ.get("FIXITLAB_INDIC_WHISPER_URL") or ""
    if not url or not audio_wav:
        return None
    import base64

    init_prompt = prompt if prompt is not None else domain_vocab_prompt()
    return _post_json(
        url,
        {
            "audio_b64": base64.b64encode(audio_wav).decode("ascii"),
            "language": language,
            "initial_prompt": init_prompt,
        },
    )


def _normalize_chat_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    if u.endswith("/chat/completions"):
        return u
    if u.endswith("/v1"):
        return u + "/chat/completions"
    if "/v1/" not in u:
        return u + "/v1/chat/completions"
    return u


def _sim_llm_generate_reply(system: str, user: str, *, max_tokens: int = 180) -> str | None:
    """In-process LLM simulation — rules already chose *what*; normalize *how*.

    Keeps meaning stable (tests + scoring stay auditable) while exercising the
    same polish call sites as a real llama.cpp / vLLM host.
    """
    text = re.sub(r"\s+", " ", (user or "").strip())
    if not text:
        return None
    # Soft speechiness: drop markdown fences / bullets the rules sometimes emit.
    text = re.sub(r"^[`*#>\-\s]+", "", text)
    text = text.replace("**", "").replace("__", "")
    sys_l = (system or "").lower()
    wants_question = "question" in sys_l or "?" in text
    if wants_question and not text.endswith("?"):
        text = text.rstrip(".!") + "?"
    elif not text.endswith((".", "?", "!")):
        text = text + "."
    # Respect max_tokens ~approx chars (4 chars/token heuristic).
    cap = max(40, int(max_tokens) * 4)
    if len(text) > cap:
        text = text[: cap - 1].rsplit(" ", 1)[0] + ("?" if wants_question else ".")
    return text


def llm_generate_reply(system: str, user: str, *, max_tokens: int = 180) -> str | None:
    """Real OpenAI-compatible host when URL set; else in-process simulation."""
    raw = os.environ.get("FIXITLAB_LLM_GENERATE_URL") or ""
    url = _normalize_chat_url(raw)
    if url:
        payload = {
            "model": os.environ.get("FIXITLAB_LLM_MODEL") or "Qwen2.5-7B-Instruct",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }
        headers = {}
        key = (os.environ.get("FIXITLAB_LLM_API_KEY") or "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        data = _post_json(url, payload, timeout=60.0, headers=headers or None)
        if data:
            try:
                return data["choices"][0]["message"]["content"]
            except Exception:
                text = data.get("text") if isinstance(data, dict) else None
                if text:
                    return text
        # Fall through to simulation if the real host fails.
    if llm_simulation_enabled():
        return _sim_llm_generate_reply(system, user, max_tokens=max_tokens)
    return None


def llm_probe(*, timeout: float = 8.0) -> dict[str, Any]:
    """Ops health check — real host if URL set, else simulation pong."""
    raw = os.environ.get("FIXITLAB_LLM_GENERATE_URL") or ""
    url = _normalize_chat_url(raw)
    if not url:
        if llm_simulation_enabled():
            sample = _sim_llm_generate_reply(
                "reply with one word", "pong", max_tokens=8,
            )
            return {
                "ok": True,
                "configured": True,
                "simulation": True,
                "sample": (sample or "pong")[:80],
            }
        return {"ok": False, "configured": False, "error": "FIXITLAB_LLM_GENERATE_URL unset"}
    headers = {}
    key = (os.environ.get("FIXITLAB_LLM_API_KEY") or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = _post_json(
        url,
        {
            "model": os.environ.get("FIXITLAB_LLM_MODEL") or "Qwen2.5-7B-Instruct",
            "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
            "max_tokens": 8,
            "temperature": 0,
        },
        timeout=timeout,
        headers=headers or None,
    )
    if not data:
        return {"ok": False, "configured": True, "error": "no response"}
    text = ""
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = str(data.get("text") or "")
    return {"ok": True, "configured": True, "simulation": False, "sample": (text or "")[:80]}


def which_piper() -> str | None:
    configured = os.environ.get("FIXITLAB_PIPER_BIN")
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("piper")
    return found
