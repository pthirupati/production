"""
Speech-to-text helpers for FixitLab interviews.

Default: browser Web Speech API (frontend). Note Chrome Web Speech
streams audio to Google — free to us but NOT offline/privacy-local.

Optional self-hosted (audit Y1e):
  FIXITLAB_FASTER_WHISPER_URL — English (small/medium)
  FIXITLAB_INDIC_WHISPER_URL  — Hindi / Telugu
  INTERVIEW_STT_ENGINE=vosk   — legacy local hook (still NotImplemented until model path set)
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|er+|ah+|like(?=\s)|you know|basically|literally|"
    r"so\b(?=\s+\w)|right\b(?=\s*[,.])|kind of|sort of|i mean)\b",
    re.IGNORECASE,
)

DOUBLE_SPACE = re.compile(r" {2,}")


def _vosk_enabled() -> bool:
    return os.environ.get("INTERVIEW_STT_ENGINE", "").lower() == "vosk"


def _faster_whisper_ready() -> bool:
    return bool(os.environ.get("FIXITLAB_FASTER_WHISPER_URL"))


def _indic_whisper_ready() -> bool:
    return bool(os.environ.get("FIXITLAB_INDIC_WHISPER_URL"))


def filter_fillers(text: str) -> str:
    """Remove common filler words and normalize whitespace."""
    cleaned = FILLER_PATTERN.sub("", text or "")
    cleaned = DOUBLE_SPACE.sub(" ", cleaned).strip()
    cleaned = re.sub(r"^[,.\s]+", "", cleaned)
    return cleaned


def _pack_result(
    *,
    transcript: str,
    confidence: float,
    provider: str,
    avg_logprob: float | None = None,
    no_speech_prob: float | None = None,
) -> dict:
    filtered = filter_fillers(transcript)
    return {
        "transcript": transcript,
        "filtered_text": filtered,
        "confidence": confidence,
        "is_final": True,
        "provider": provider,
        "word_count": len(filtered.split()) if filtered else 0,
        "duration_seconds": None,
        "avg_logprob": avg_logprob,
        "no_speech_prob": no_speech_prob,
        "message": "",
    }


def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/webm",
    language: str = "en",
    prompt: str = "",
) -> dict:
    """Server STT — faster-whisper / IndicWhisper when URLs set, else browser."""
    lang = (language or "en").lower()

    try:
        from . import voice_stack as vs

        vocab = vs.domain_vocab_prompt(extra=prompt or "")

        if _indic_whisper_ready() and lang.startswith(("hi", "te")):
            data = vs.transcribe_indic_whisper(
                audio_bytes, language=lang[:2], prompt=vocab,
            )
            if data and (data.get("text") or data.get("transcript")):
                text = data.get("text") or data.get("transcript") or ""
                return _pack_result(
                    transcript=text,
                    confidence=float(data.get("confidence") or data.get("avg_logprob") or 0.7),
                    provider="indic_whisper",
                    avg_logprob=data.get("avg_logprob"),
                    no_speech_prob=data.get("no_speech_prob"),
                )

        if _faster_whisper_ready():
            data = vs.transcribe_faster_whisper(
                audio_bytes, language=lang[:2] or "en", prompt=vocab,
            )
            if data and (data.get("text") or data.get("transcript")):
                text = data.get("text") or data.get("transcript") or ""
                conf = data.get("confidence")
                if conf is None and data.get("avg_logprob") is not None:
                    # Map logprob (~-1..0) into a soft 0..1 for Y1b clarity paths.
                    conf = max(0.0, min(1.0, 1.0 + float(data["avg_logprob"])))
                return _pack_result(
                    transcript=text,
                    confidence=float(conf if conf is not None else 0.7),
                    provider="faster_whisper",
                    avg_logprob=data.get("avg_logprob"),
                    no_speech_prob=data.get("no_speech_prob"),
                )
    except Exception:
        logger.warning("self-hosted STT failed; falling through", exc_info=True)

    if _vosk_enabled():
        try:
            return _transcribe_vosk(audio_bytes, language=language)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vosk STT failed, falling back to browser: %s", exc)

    return {
        "transcript": "",
        "filtered_text": "",
        "confidence": 0.0,
        "is_final": False,
        "provider": "browser_sim",
        "word_count": 0,
        "duration_seconds": None,
        "message": (
            "Browser speech recognition simulates faster-whisper / IndicWhisper "
            "(FixitLab simulation-first). Chrome may send audio to Google — not offline. "
            "Set FIXITLAB_FASTER_WHISPER_URL for a real self-hosted model."
        ),
    }


def _transcribe_vosk(audio_bytes: bytes, *, language: str = "en") -> dict:
    """Optional local Vosk hook — not required for the free browser path."""
    raise NotImplementedError(
        "Vosk STT is not configured. Set INTERVIEW_STT_ENGINE=vosk and install vosk + model."
    )


def stt_config_for_frontend() -> dict:
    """Tell frontend which STT strategy to use."""
    use_fw = _faster_whisper_ready()
    use_indic = _indic_whisper_ready()
    use_vosk = _vosk_enabled()
    uses_server = use_fw or use_indic or use_vosk
    sim = True
    status = {}
    try:
        from . import voice_stack as vs

        sim = vs.voice_simulation_enabled()
        status = vs.voice_stack_status()
    except Exception:
        pass
    if use_fw:
        provider = "faster_whisper"
    elif use_indic:
        provider = "indic_whisper"
    elif use_vosk:
        provider = "vosk"
    elif sim:
        provider = "browser_sim"
    else:
        provider = "browser"
    return {
        "stt_provider": provider,
        "uses_server_stt": uses_server,
        "uses_paid_apis": False,
        "simulation": sim and not uses_server,
        "transcribe_endpoint": "/api/interviews/stt/transcribe/" if uses_server else None,
        "max_blob_size_bytes": 5 * 1024 * 1024,
        "chunk_interval_ms": 4000,
        "voice_stack": {
            "faster_whisper": use_fw,
            "indic_whisper": use_indic,
            "vosk": use_vosk,
            "faster_whisper_sim": bool(status.get("faster_whisper_sim")),
            "indic_whisper_sim": bool(status.get("indic_whisper_sim")),
            "status": status,
        },
        "initial_prompt_vocab": True,
    }
