from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .service import generate_support_reply, support_bot_config


class SupportBotConfigView(APIView):
    """GET /api/support/config/ — public bot settings (if enabled)."""

    permission_classes = [AllowAny]

    def get(self, request):
        config = support_bot_config()
        user_enabled = True
        if request.user.is_authenticated:
            from apps.accounts.models import Profile

            profile = Profile.objects.filter(user=request.user).first()
            if profile is not None:
                user_enabled = profile.support_bot_enabled
        if not config["enabled"] or not user_enabled:
            return Response({"enabled": False})
        return Response({**config, "enabled": True, "user_enabled": user_enabled})


class SupportBotChatView(APIView):
    """POST /api/support/chat/ — message in, assistant reply out."""

    permission_classes = [AllowAny]

    def post(self, request):
        config = support_bot_config()
        if not config["enabled"]:
            return Response({"error": "Support assistant is disabled"}, status=403)

        if request.user.is_authenticated:
            from apps.accounts.models import Profile

            profile = Profile.objects.filter(user=request.user).first()
            if profile and not profile.support_bot_enabled:
                return Response({"error": "You disabled the support assistant"}, status=403)

        text = (request.data.get("message") or request.data.get("text") or "").strip()
        if not text:
            return Response({"error": "message is required"}, status=400)

        page_path = (request.data.get("page_path") or "")[:500]
        result = generate_support_reply(
            text,
            is_authenticated=request.user.is_authenticated,
            page_path=page_path,
        )
        return Response(result)
