from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import StrictAnonRateThrottle
from .service import (
    generate_support_reply,
    record_support_feedback,
    support_bot_config,
)


class SupportBotConfigView(APIView):
    """GET /api/support/config/ — public bot settings (if enabled)."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

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
    """POST /api/support/chat/ — message in, assistant reply out.

    Public (AllowAny) so the marketing-site widget works for guests, but
    strictly rate-limited. Config remains public so the widget can hide itself.
    """

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

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


class SupportBotFeedbackView(APIView):
    """POST /api/support/feedback/ — thumbs up/down on a bot reply."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def post(self, request):
        helpful = bool(request.data.get("helpful"))
        message = (request.data.get("message") or "")[:1000]
        reply = (request.data.get("reply") or "")[:2000]
        page_path = (request.data.get("page_path") or "")[:500]
        username = request.user.get_username() if request.user.is_authenticated else ""
        record_support_feedback(
            message=message,
            reply=reply,
            helpful=helpful,
            page_path=page_path,
            username=username,
        )
        return Response({"ok": True})
