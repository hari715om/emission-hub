# pyrefly: ignore [missing-import]
from django.urls import path, include
# pyrefly: ignore [missing-import]
from rest_framework.routers import DefaultRouter
# pyrefly: ignore [missing-import]
from .views import TenantViewSet, SiteMappingViewSet

router = DefaultRouter()
router.register('tenants', TenantViewSet)
router.register('site-mappings', SiteMappingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
