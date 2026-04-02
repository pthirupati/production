from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification, NotificationPreference


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
                    "title": n.title,
                    "message": n.message,
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
            # Mark all as read
            Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"message": "Marked as read"})


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
