# pyrefly: ignore [missing-import]
from rest_framework import viewsets, permissions
# pyrefly: ignore [missing-import]
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only audit log. Auditors and analysts can view but never edit.
    """
    queryset = AuditEvent.objects.select_related('actor').all()
    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['action', 'entity_type', 'entity_id', 'actor']
    ordering_fields = ['timestamp']
