from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TechnologyViewSet, ScenarioViewSet

router = DefaultRouter()
router.register(r'technologies', TechnologyViewSet)
router.register(r'scenarios', ScenarioViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
