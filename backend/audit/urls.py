# pyrefly: ignore [missing-import]
from django.urls import path, include
# pyrefly: ignore [missing-import]
from rest_framework.routers import DefaultRouter
from .views import AuditEventViewSet

router = DefaultRouter()
router.register('audit-events', AuditEventViewSet)

urlpatterns = [path('', include(router.urls))]
