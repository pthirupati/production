from rest_framework import viewsets, permissions
from .models import Technology, Scenario
from .serializers import TechnologySerializer, ScenarioListSerializer, ScenarioAdminSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read for anyone, write only for admin/staff users."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class TechnologyViewSet(viewsets.ModelViewSet):
    queryset = Technology.objects.all()
    serializer_class = TechnologySerializer
    permission_classes = [IsAdminOrReadOnly]


class ScenarioViewSet(viewsets.ModelViewSet):
    queryset = Scenario.objects.select_related('technology').prefetch_related('tags').all()
    permission_classes = [IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ScenarioAdminSerializer
        return ScenarioListSerializer
