"""
Text-to-speech helpers for FixitLab interviews.

100% FREE path: browser SpeechSynthesis (frontend default).
Paid cloud TTS (ElevenLabs, Polly) is intentionally disabled in the interview path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

AudioFormat = Literal["mp3", "pcm", "ogg"]


@dataclass
class TTSResult:
    provider: str
    audio_b64: str | None = None
    mime_type: str = "audio/mpeg"
    use_browser: bool = True
    voice_hint: str = ""


def _tts_provider() -> Literal["browser"]:
    return "browser"


def synthesize(text: str, voice_code: str = "default", streaming: bool = False) -> TTSResult:
    """Server TTS — always defers to browser synthesis on the client."""
    return TTSResult(
        provider="browser",
        audio_b64=None,
        use_browser=True,
        voice_hint=voice_code or "default",
    )


def tts_config_for_frontend() -> dict:
    return {
        "tts_provider": "browser",
        "uses_paid_apis": False,
        "synthesize_endpoint": None,
        "streaming_supported": False,
    }
