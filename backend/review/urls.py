# pyrefly: ignore [missing-import]
from django.urls import path, include
# pyrefly: ignore [missing-import]
from rest_framework.routers import DefaultRouter
from .views import NormalizedActivityViewSet, dashboard_stats

router = DefaultRouter()
router.register('activities', NormalizedActivityViewSet)

urlpatterns = [
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    path('', include(router.urls)),
]
