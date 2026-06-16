"""
TTS API views — called by InterviewRoom.jsx for server-side voice synthesis.
Add these URLs to interviews/urls.py:
    path("tts/synthesize/", tts_views.TTSSynthesizeView.as_view(), name="tts-synthesize"),
    path("tts/config/", tts_views.TTSConfigView.as_view(), name="tts-config"),
"""

from __future__ import annotations

from django.http import JsonResponse
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.interviews.services.tts_service import synthesize, tts_config_for_frontend
from common.throttles import StrictAnonRateThrottle


class TTSConfigView(APIView):
    """GET /api/interviews/tts/config/ — returns provider capabilities."""
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        return JsonResponse(tts_config_for_frontend())


class TTSSynthesizeView(APIView):
    """
    POST /api/interviews/tts/synthesize/
    Body: { "text": "...", "voice_code": "US_F_ZIRA" }
    Response: { "provider": "elevenlabs"|"polly"|"browser",
                "audio_b64": "<base64 MP3>"|null,
                "mime": "audio/mpeg" }
    Frontend plays audio_b64 if present, else falls back to SpeechSynthesis.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        voice_code = request.data.get("voice_code") or "US_F_ZIRA"

        if not text:
            return JsonResponse({"error": "text required"}, status=400)
        if len(text) > 1000:
            text = text[:1000]

        result = synthesize(text, voice_code)
        return JsonResponse({
            "provider": result.provider,
            "audio_b64": result.audio_b64,
            "mime": "audio/mpeg",
        })
