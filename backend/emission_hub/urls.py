"""URL configuration for emission_hub project."""
# pyrefly: ignore [missing-import]
from django.contrib import admin
# pyrefly: ignore [missing-import]
from django.urls import path, include
# pyrefly: ignore [missing-import]
from django.conf import settings
# pyrefly: ignore [missing-import]
from django.conf.urls.static import static
from .auth_views import api_login, api_logout, api_me

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/',  api_login,  name='api-login'),
    path('api/auth/logout/', api_logout, name='api-logout'),
    path('api/auth/me/',     api_me,     name='api-me'),
    path('api/v1/', include('tenants.urls')),
    path('api/v1/', include('ingestion.urls')),
    path('api/v1/', include('review.urls')),
    path('api/v1/', include('audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
