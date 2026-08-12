"""
Text-to-speech helpers for FixitLab interviews.

Default: browser SpeechSynthesis (frontend).
Optional self-hosted: Piper (en) / IndicF5 (hi/te) via ``voice_stack`` when env is set.
Paid cloud TTS (ElevenLabs, Polly) stays disabled.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

AudioFormat = Literal["mp3", "pcm", "ogg", "wav"]


@dataclass
class TTSResult:
    provider: str
    audio_b64: str | None = None
    mime_type: str = "audio/mpeg"
    use_browser: bool = True
    voice_hint: str = ""


def _piper_ready() -> bool:
    from . import voice_stack as vs
    return bool(vs.which_piper() and os.environ.get("FIXITLAB_PIPER_VOICE"))


def _indicf5_ready() -> bool:
    return bool(os.environ.get("FIXITLAB_INDICF5_URL"))


def synthesize(text: str, voice_code: str = "default", streaming: bool = False) -> TTSResult:
    """Prefer self-hosted Piper/IndicF5 when configured; else browser."""
    code = (voice_code or "default").lower()
    try:
        from . import voice_stack as vs

        # Indic personas → IndicF5 when URL is set.
        if _indicf5_ready() and any(tag in code for tag in ("hi_", "te_", "hindi", "telugu", "indic")):
            lang = "te" if "te" in code or "telugu" in code else "hi"
            audio = vs.synthesize_indicf5(text, lang=lang)
            if audio:
                return TTSResult(
                    provider="indicf5",
                    audio_b64=base64.b64encode(audio).decode("ascii"),
                    mime_type="audio/wav",
                    use_browser=False,
                    voice_hint=voice_code or "indic",
                )

        if _piper_ready():
            # Allow which_piper() to fill FIXITLAB_PIPER_BIN when only VOICE is set.
            if not os.environ.get("FIXITLAB_PIPER_BIN"):
                found = vs.which_piper()
                if found:
                    os.environ["FIXITLAB_PIPER_BIN"] = found
            audio = vs.synthesize_piper(text)
            if audio:
                return TTSResult(
                    provider="piper",
                    audio_b64=base64.b64encode(audio).decode("ascii"),
                    mime_type="audio/wav",
                    use_browser=False,
                    voice_hint=voice_code or "piper",
                )
    except Exception:
        logger.debug("self-hosted TTS failed; browser fallback", exc_info=True)

    sim = False
    try:
        from . import voice_stack as vs

        sim = vs.voice_simulation_enabled()
    except Exception:
        sim = True
    return TTSResult(
        provider="browser_sim" if sim else "browser",
        audio_b64=None,
        use_browser=True,
        voice_hint=voice_code or "default",
    )


def tts_config_for_frontend() -> dict:
    piper = _piper_ready()
    indic = _indicf5_ready()
    uses_server = piper or indic
    status = {}
    sim = True
    try:
        from . import voice_stack as vs

        status = vs.voice_stack_status()
        sim = vs.voice_simulation_enabled()
    except Exception:
        status = {}
    if uses_server:
        provider = "piper" if piper else "indicf5"
    elif sim:
        provider = "browser_sim"
    else:
        provider = "browser"
    return {
        "tts_provider": provider,
        "uses_paid_apis": False,
        "uses_server_tts": uses_server,
        "simulation": sim and not uses_server,
        "synthesize_endpoint": "/api/interviews/tts/synthesize/" if uses_server else None,
        "streaming_supported": False,
        "voice_stack": {
            "piper": piper,
            "indicf5": indic,
            "piper_sim": bool(status.get("piper_sim")),
            "indicf5_sim": bool(status.get("indicf5_sim")),
            "status": status,
        },
    }
