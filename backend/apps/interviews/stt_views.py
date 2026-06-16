"""
STT API views.
Add to interviews/urls.py:
    path("stt/transcribe/", stt_views.STTTranscribeView.as_view(), name="stt-transcribe"),
    path("stt/config/", stt_views.STTConfigView.as_view(), name="stt-config"),
"""

from __future__ import annotations

from django.http import JsonResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.interviews.services.stt_service import transcribe_audio, stt_config_for_frontend


class STTConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return JsonResponse(stt_config_for_frontend())


class STTTranscribeView(APIView):
    """
    POST /api/interviews/stt/transcribe/
    Multipart: audio_blob (file), mime_type (str), prompt (str, optional)
    Returns Whisper transcript with filler filtering.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        audio_file = request.FILES.get("audio_blob")
        if not audio_file:
            return JsonResponse({"error": "audio_blob required"}, status=400)

        if audio_file.size > 10 * 1024 * 1024:
            return JsonResponse({"error": "Audio blob too large (max 10 MB)"}, status=400)

        mime_type = request.data.get("mime_type", "audio/webm")
        prompt = request.data.get("prompt", "")

        audio_bytes = audio_file.read()
        result = transcribe_audio(audio_bytes, mime_type=mime_type, prompt=prompt)
        return JsonResponse(result)
