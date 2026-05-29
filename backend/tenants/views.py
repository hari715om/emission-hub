# pyrefly: ignore [missing-import]
from rest_framework import viewsets, permissions
# pyrefly: ignore [missing-import]
from rest_framework.decorators import action
# pyrefly: ignore [missing-import]
from rest_framework.response import Response
from .models import Tenant, SiteMapping
from .serializers import TenantSerializer, SiteMappingSerializer


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.filter(is_active=True)
    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name', 'slug']

    @action(detail=True, methods=['get'])
    def site_mappings(self, request, pk=None):
        tenant = self.get_object()
        mappings = SiteMapping.objects.filter(tenant=tenant)
        serializer = SiteMappingSerializer(mappings, many=True)
        return Response(serializer.data)


class SiteMappingViewSet(viewsets.ModelViewSet):
    queryset = SiteMapping.objects.select_related('tenant').all()
    serializer_class = SiteMappingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['tenant', 'source_type']
