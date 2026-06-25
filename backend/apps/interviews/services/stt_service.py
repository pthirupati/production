"""
Speech-to-text helpers for FixitLab interviews.

100% FREE path: browser Web Speech API is the default (frontend).
Server-side paid APIs (OpenAI Whisper, etc.) are intentionally disabled.

Optional future hook: local Vosk when INTERVIEW_STT_ENGINE=vosk (still free/offline).
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


def filter_fillers(text: str) -> str:
    """Remove common filler words and normalize whitespace."""
    cleaned = FILLER_PATTERN.sub("", text or "")
    cleaned = DOUBLE_SPACE.sub(" ", cleaned).strip()
    cleaned = re.sub(r"^[,.\s]+", "", cleaned)
    return cleaned


def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/webm",
    language: str = "en",
    prompt: str = "",
) -> dict:
    """Server STT endpoint — returns browser fallback unless Vosk is enabled."""
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
        "provider": "browser",
        "word_count": 0,
        "duration_seconds": None,
        "message": "Use browser speech recognition (free, offline-capable in supported browsers).",
    }


def _transcribe_vosk(audio_bytes: bytes, *, language: str = "en") -> dict:
    """Optional local Vosk hook — not required for the free browser path."""
    raise NotImplementedError(
        "Vosk STT is not configured. Set INTERVIEW_STT_ENGINE=vosk and install vosk + model."
    )


def stt_config_for_frontend() -> dict:
    """Tell frontend which STT strategy to use — always browser by default."""
    use_vosk = _vosk_enabled()
    return {
        "stt_provider": "vosk" if use_vosk else "browser",
        "uses_server_stt": use_vosk,
        "uses_paid_apis": False,
        "transcribe_endpoint": "/api/interviews/stt/transcribe/" if use_vosk else None,
        "max_blob_size_bytes": 5 * 1024 * 1024,
        "chunk_interval_ms": 4000,
    }
