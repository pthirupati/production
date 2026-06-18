from rest_framework.permissions import BasePermission

class IsPlatformAdmin(BasePermission):
    """
    Allow only staff or superusers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsSuperAdmin(BasePermission):
    """Only superusers can perform destructive/privilege operations."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )

