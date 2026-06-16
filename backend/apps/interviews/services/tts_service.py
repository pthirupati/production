"""
Text-to-speech service for FixitLab interviews.

Priority chain:
  1. ElevenLabs (highest quality, streaming)
  2. AWS Polly (good quality, low latency, no per-char cost cap issues)
  3. Browser SpeechSynthesis (original fallback — zero server cost)

Configure via environment variables:
  ELEVENLABS_API_KEY   — enables ElevenLabs
  AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_REGION — enables Polly
  (If neither is set, frontend falls back to browser TTS automatically.)

All server-side methods return base64-encoded audio or a signed URL
suitable for <audio> element autoplay.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

logger = logging.getLogger(__name__)

AudioFormat = Literal["mp3", "pcm", "ogg"]


# ---------------------------------------------------------------------------
# Voice mapping
# ---------------------------------------------------------------------------

# Maps our internal voice_code (used in InterviewVoiceOption) to provider IDs
ELEVENLABS_VOICE_MAP: dict[str, str] = {
    "IN_F_NEERJA":  "21m00Tcm4TlvDq8ikWAM",   # Rachel — warm female
    "IN_M_PRABHAT": "AZnzlk1XvdvUeBnXmlld",   # Domi — assertive male
    "UK_F_SONIA":   "EXAVITQu4vr4xnSDxMaL",   # Bella — British female
    "UK_M_GEORGE":  "VR6AewLTigWG4xSOukaG",   # Arnold — British male
    "US_F_ZIRA":    "pNInz6obpgDQGcFmaJgB",   # Adam (fem) — US neutral
    "US_M_DAVID":   "yoZ06aMxZJJ28mfd3POQ",   # Sam — US male
}

POLLY_VOICE_MAP: dict[str, str] = {
    "IN_F_NEERJA":  "Aditi",
    "IN_M_PRABHAT": "Kajal",
    "UK_F_SONIA":   "Amy",
    "UK_M_GEORGE":  "Brian",
    "US_F_ZIRA":    "Joanna",
    "US_M_DAVID":   "Matthew",
}


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _tts_provider() -> Literal["elevenlabs", "polly", "browser"]:
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        return "polly"
    return "browser"


# ---------------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------------

def _elevenlabs_synthesize(text: str, voice_code: str, streaming: bool = False) -> bytes | None:
    """
    Synthesize speech using ElevenLabs.
    Returns raw MP3 bytes or None on failure.
    """
    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        logger.warning("httpx not installed — cannot use ElevenLabs")
        return None

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = ELEVENLABS_VOICE_MAP.get(voice_code, list(ELEVENLABS_VOICE_MAP.values())[0])

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    if streaming:
        url += "/stream"

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",   # lowest latency model
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.content
    except Exception as exc:
        logger.error("ElevenLabs TTS failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# AWS Polly
# ---------------------------------------------------------------------------

def _polly_synthesize(text: str, voice_code: str) -> bytes | None:
    """Synthesize speech using AWS Polly. Returns MP3 bytes or None."""
    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        logger.warning("boto3 not installed — cannot use AWS Polly")
        return None

    voice_id = POLLY_VOICE_MAP.get(voice_code, "Joanna")
    region = os.environ.get("AWS_REGION", "us-east-1")

    try:
        polly = boto3.client("polly", region_name=region)
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine="neural",   # neural engine for natural sound
            SampleRate="24000",
        )
        audio_stream = response["AudioStream"]
        return audio_stream.read()
    except Exception as exc:
        logger.error("AWS Polly TTS failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class TTSResult:
    provider: str          # "elevenlabs" | "polly" | "browser"
    audio_b64: str | None  # base64-encoded MP3; None if browser TTS
    voice_code: str
    text_length: int


def synthesize(text: str, voice_code: str = "US_F_ZIRA") -> TTSResult:
    """
    Synthesize text to speech using the best available provider.
    Returns TTSResult with base64 audio or provider="browser" signal.

    Usage in view:
        result = synthesize(reply_text, round_obj.voice_code)
        if result.provider == "browser":
            # tell frontend to use SpeechSynthesis
            return JsonResponse({"tts_provider": "browser", "text": reply_text})
        else:
            return JsonResponse({"tts_provider": result.provider,
                                 "audio_b64": result.audio_b64,
                                 "mime": "audio/mpeg"})
    """
    provider = _tts_provider()
    audio_bytes: bytes | None = None

    if provider == "elevenlabs":
        audio_bytes = _elevenlabs_synthesize(text, voice_code)
        if audio_bytes is None:
            # Try Polly as secondary fallback
            audio_bytes = _polly_synthesize(text, voice_code)
            provider = "polly" if audio_bytes else "browser"
    elif provider == "polly":
        audio_bytes = _polly_synthesize(text, voice_code)
        if audio_bytes is None:
            provider = "browser"

    if audio_bytes:
        b64 = base64.b64encode(audio_bytes).decode("ascii")
    else:
        b64 = None
        provider = "browser"

    return TTSResult(
        provider=provider,
        audio_b64=b64,
        voice_code=voice_code,
        text_length=len(text),
    )


def tts_config_for_frontend() -> dict:
    """
    Return the TTS strategy the frontend should use.
    Called once on room load to configure the voice player.
    """
    provider = _tts_provider()
    return {
        "tts_provider": provider,
        "uses_server_tts": provider != "browser",
        "streaming_endpoint": "/api/interviews/tts/stream/" if provider != "browser" else None,
        "synthesis_endpoint": "/api/interviews/tts/synthesize/" if provider != "browser" else None,
    }
