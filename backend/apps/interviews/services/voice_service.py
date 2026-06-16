"""Free browser-based voice configuration — no paid TTS/STT APIs."""

from __future__ import annotations

from apps.interviews.models import InterviewVoiceOption
from apps.interviews.services.interview_settings import get_platform_settings


def voice_config_payload() -> dict:
    settings_row = get_platform_settings()
    voices = list(
        InterviewVoiceOption.objects.filter(is_active=True).values(
            "code", "label", "locale", "gender", "region",
            "browser_voice_hint", "pitch", "rate", "is_default",
        )
    )
    if not voices:
        voices = _default_voices()
    default = next((v for v in voices if v.get("is_default")), voices[0] if voices else None)
    return {
        "stt_provider": "browser",
        "tts_provider": "browser",
        "voice_engine": settings_row.voice_engine or "browser",
        "uses_paid_apis": False,
        "voices": voices,
        "default_voice_code": default["code"] if default else "indian-female",
        "hints": {
            "stt": "Uses browser SpeechRecognition (Chrome/Edge recommended)",
            "tts": "Uses browser SpeechSynthesis — admin picks accent in Admin → Interviews → Voices",
        },
    }


def _default_voices() -> list[dict]:
    return [
        {
            "code": "indian-female", "label": "Indian Female", "locale": "en-IN",
            "gender": "female", "region": "india", "browser_voice_hint": "Neerja",
            "pitch": 1.0, "rate": 0.95, "is_default": True,
        },
        {
            "code": "indian-male", "label": "Indian Male", "locale": "en-IN",
            "gender": "male", "region": "india", "browser_voice_hint": "Prabhat",
            "pitch": 0.95, "rate": 0.92, "is_default": False,
        },
        {
            "code": "uk-female", "label": "UK Female", "locale": "en-GB",
            "gender": "female", "region": "uk", "browser_voice_hint": "Sonia",
            "pitch": 1.0, "rate": 0.94, "is_default": False,
        },
        {
            "code": "uk-male", "label": "UK Male", "locale": "en-GB",
            "gender": "male", "region": "uk", "browser_voice_hint": "Ryan",
            "pitch": 0.9, "rate": 0.93, "is_default": False,
        },
        {
            "code": "us-female", "label": "US Female", "locale": "en-US",
            "gender": "female", "region": "us", "browser_voice_hint": "Samantha",
            "pitch": 1.0, "rate": 0.96, "is_default": False,
        },
        {
            "code": "us-male", "label": "US Male", "locale": "en-US",
            "gender": "male", "region": "us", "browser_voice_hint": "Daniel",
            "pitch": 0.92, "rate": 0.94, "is_default": False,
        },
    ]


def resolve_voice_for_code(code: str) -> dict | None:
    row = InterviewVoiceOption.objects.filter(code=code, is_active=True).first()
    if row:
        return {
            "code": row.code,
            "label": row.label,
            "locale": row.locale,
            "browser_voice_hint": row.browser_voice_hint,
            "pitch": row.pitch,
            "rate": row.rate,
        }
    for v in _default_voices():
        if v["code"] == code:
            return v
    return _default_voices()[0]
