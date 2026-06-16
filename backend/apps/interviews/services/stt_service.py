"""
Speech-to-text service for FixitLab interviews.

Strategy:
  Server-side: OpenAI Whisper API (best accuracy, handles accents/noise)
  Fallback:    Browser SpeechRecognition (existing behavior)

The frontend sends audio blobs via POST and receives:
  { "transcript": "...", "is_final": true, "confidence": 0.95,
    "filtered_text": "...",   # filler words removed
    "word_timings": [...] }   # if available

Filler word filter removes: um, uh, like, you know, basically, literally,
so (sentence-initial), right (trailing), etc.
"""

from __future__ import annotations

import io
import logging
import os
import re
from functools import lru_cache

logger = logging.getLogger(__name__)

FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|er+|ah+|like(?=\s)|you know|basically|literally|"
    r"so\b(?=\s+\w)|right\b(?=\s*[,.])|kind of|sort of|i mean)\b",
    re.IGNORECASE,
)

DOUBLE_SPACE = re.compile(r" {2,}")


@lru_cache(maxsize=1)
def _whisper_available() -> bool:
    try:
        import openai  # noqa: PLC0415
        return bool(os.environ.get("OPENAI_API_KEY"))
    except ImportError:
        return False


def _get_openai_client():
    import openai  # noqa: PLC0415
    return openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def filter_fillers(text: str) -> str:
    """Remove common filler words and normalize whitespace."""
    cleaned = FILLER_PATTERN.sub("", text)
    cleaned = DOUBLE_SPACE.sub(" ", cleaned).strip()
    # Clean up leading punctuation artifacts
    cleaned = re.sub(r"^[,.\s]+", "", cleaned)
    return cleaned


def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/webm",
    language: str = "en",
    prompt: str = "",
) -> dict:
    """
    Transcribe audio using Whisper API.

    Args:
        audio_bytes: Raw audio data (webm, wav, mp4, ogg, m4a all supported)
        mime_type: Content-Type of the audio blob
        language: ISO 639-1 language code
        prompt: Optional context prompt to improve accuracy
                (e.g., "DevOps, Kubernetes, Prometheus, SRE" improves tech transcription)

    Returns:
        {
            "transcript": str,          # raw transcript
            "filtered_text": str,       # filler-word cleaned version
            "confidence": float,        # 0-1 (Whisper doesn't give per-token confidence;
                                        #  we estimate from no_speech_prob)
            "is_final": bool,           # always True for server-side
            "provider": str,            # "whisper" | "browser"
            "word_count": int,
            "duration_seconds": float | None,
        }
    """
    if not _whisper_available():
        return {
            "transcript": "",
            "filtered_text": "",
            "confidence": 0.0,
            "is_final": False,
            "provider": "browser",
            "word_count": 0,
            "duration_seconds": None,
        }

    # Map mime to file extension Whisper accepts
    ext_map = {
        "audio/webm": "webm",
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "audio/mp4": "mp4",
        "audio/m4a": "m4a",
        "audio/mpeg": "mp3",
    }
    ext = ext_map.get(mime_type, "webm")
    filename = f"interview_audio.{ext}"

    client = _get_openai_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    # Build context prompt for technical vocabulary
    tech_context = prompt or (
        "Interview about DevOps, SRE, Kubernetes, Docker, Prometheus, Grafana, "
        "CI/CD, Jenkins, Terraform, Ansible, Linux, Python, AWS, Azure, GCP."
    )

    try:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            prompt=tech_context,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )

        raw_text = response.text or ""
        no_speech_prob = getattr(response, "segments", [{}])[0].get("no_speech_prob", 0.0) if response.segments else 0.0
        confidence = max(0.0, 1.0 - no_speech_prob)

        word_timings = []
        if hasattr(response, "words") and response.words:
            word_timings = [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in response.words
            ]

        duration = None
        if hasattr(response, "duration"):
            duration = response.duration

        filtered = filter_fillers(raw_text)

        return {
            "transcript": raw_text,
            "filtered_text": filtered,
            "confidence": round(confidence, 3),
            "is_final": True,
            "provider": "whisper",
            "word_count": len(filtered.split()),
            "duration_seconds": duration,
            "word_timings": word_timings,
        }

    except Exception as exc:
        logger.error("Whisper transcription failed: %s", exc)
        return {
            "transcript": "",
            "filtered_text": "",
            "confidence": 0.0,
            "is_final": False,
            "provider": "browser",
            "word_count": 0,
            "duration_seconds": None,
            "error": str(exc),
        }


def stt_config_for_frontend() -> dict:
    """Tell frontend which STT strategy to use."""
    use_server = _whisper_available()
    return {
        "stt_provider": "whisper" if use_server else "browser",
        "uses_server_stt": use_server,
        "transcribe_endpoint": "/api/interviews/stt/transcribe/" if use_server else None,
        "max_blob_size_bytes": 5 * 1024 * 1024,  # 5 MB per chunk
        "chunk_interval_ms": 4000,                # send chunk every 4s
    }
