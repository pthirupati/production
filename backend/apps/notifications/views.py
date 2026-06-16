from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status as http_status
from django.contrib.auth import get_user_model
from .models import Notification, NotificationPreference
from .unsubscribe import verify_marketing_unsubscribe_token

User = get_user_model()


class NotificationListView(APIView):
    """List user's notifications (most recent first)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)[:50]
        unread_count = Notification.objects.filter(user=request.user, read=False).count()
        data = {
            "unread_count": unread_count,
            "notifications": [
                {
                    "id": n.id,
                    "type": n.type,
                    "message": n.message,
                    "title": n.title,
                    "read": n.read,
                    "metadata": n.metadata,
                    "created_at": n.created_at.isoformat(),
                }
                for n in notifications
            ],
        }
        return Response(data)


class NotificationMarkReadView(APIView):
    """Mark one or all notifications as read."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if pk:
            Notification.objects.filter(user=request.user, id=pk).update(read=True)
        else:
            Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"message": "Marked as read"})


class NotificationDismissView(APIView):
    """Dismiss (delete) a single notification."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = Notification.objects.filter(user=request.user, id=pk).delete()
        if not deleted:
            return Response({"error": "Not found"}, status=404)
        return Response({"message": "Dismissed"})


class NotificationPreferenceView(APIView):
    """Get and update notification preferences."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prefs = NotificationPreference.get_for_user(request.user)
        return Response({
            "email_achievements": prefs.email_achievements,
            "email_lab_completed": prefs.email_lab_completed,
            "email_lab_expired": prefs.email_lab_expired,
            "email_subscription": prefs.email_subscription,
            "email_marketing": prefs.email_marketing,
            "inapp_achievements": prefs.inapp_achievements,
            "inapp_lab_events": prefs.inapp_lab_events,
            "inapp_system": prefs.inapp_system,
        })

    def patch(self, request):
        prefs = NotificationPreference.get_for_user(request.user)
        allowed_fields = [
            "email_achievements", "email_lab_completed", "email_lab_expired",
            "email_subscription", "email_marketing",
            "inapp_achievements", "inapp_lab_events", "inapp_system",
        ]
        for field in allowed_fields:
            if field in request.data:
                setattr(prefs, field, bool(request.data[field]))
        prefs.save()
        return Response({"message": "Preferences updated"})


class MarketingUnsubscribeView(APIView):
    """One-click unsubscribe from marketing emails via signed token (no login required)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        token = request.query_params.get("token", "")
        user_id = verify_marketing_unsubscribe_token(token)
        if not user_id:
            return Response(
                {"error": "Invalid or expired unsubscribe link."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "Account not found."},
                status=http_status.HTTP_404_NOT_FOUND,
            )
        prefs = NotificationPreference.get_for_user(user)
        prefs.email_marketing = False
        prefs.save(update_fields=["email_marketing", "updated_at"])
        return Response({
            "message": "You have been unsubscribed from marketing emails.",
            "email_marketing": False,
        })

    def post(self, request):
        """Same as GET — supports form POST from email clients."""
        return self.get(request)
