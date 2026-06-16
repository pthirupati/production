"""Voice API — free browser Speech API config only."""

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.services.voice_service import resolve_voice_for_code, voice_config_payload


class InterviewVoiceConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(voice_config_payload())


class InterviewVoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, code):
        voice = resolve_voice_for_code(code)
        if not voice:
            return Response({"error": "Voice not found"}, status=404)
        return Response(voice)
