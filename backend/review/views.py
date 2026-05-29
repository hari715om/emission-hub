"""
Review app views — the analyst workflow.

Endpoints:
  GET  /api/v1/activities/           — paginated, filterable list
  GET  /api/v1/activities/{id}/      — detail with raw payload side-by-side
  PATCH /api/v1/activities/{id}/     — edit before approval (locked rows blocked)
  POST /api/v1/activities/{id}/approve/  — approve a row
  POST /api/v1/activities/{id}/reject/   — reject with reason
  POST /api/v1/activities/bulk-approve/  — bulk approve list of IDs
  GET  /api/v1/activities/{id}/history/  — audit trail for this row
  GET  /api/v1/dashboard/stats/          — summary numbers for dashboard

Design note on locking:
  Once approved, locked_for_audit = True prevents further edits.
  This mirrors what auditors require: the record that was approved must
  be identical to what the auditor reviews. An admin can unlock via
  Django admin if genuinely needed (tracked in audit log).
"""
# pyrefly: ignore [missing-import]
import logging
# pyrefly: ignore [missing-import]
from django.utils import timezone
# pyrefly: ignore [missing-import]
from rest_framework import status, permissions, viewsets
# pyrefly: ignore [missing-import]
from rest_framework.decorators import api_view, permission_classes, action
# pyrefly: ignore [missing-import]
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from rest_framework.filters import SearchFilter, OrderingFilter
# pyrefly: ignore [missing-import]
from django_filters.rest_framework import DjangoFilterBackend
# pyrefly: ignore [missing-import]
import django_filters

from normalization.models import NormalizedActivity
from audit.models import AuditEvent
from audit.utils import log_event
from .serializers import (
    NormalizedActivityListSerializer,
    NormalizedActivityDetailSerializer,
    NormalizedActivityEditSerializer,
)

logger = logging.getLogger('review')


def _activity_snapshot(activity: NormalizedActivity) -> dict:
    """Build a before/after dict for audit logging — only the mutable fields."""
    return {
        'category': activity.category,
        'scope': activity.scope,
        'activity_date': str(activity.activity_date) if activity.activity_date else None,
        'quantity': str(activity.quantity) if activity.quantity is not None else None,
        'unit': activity.unit,
        'normalized_quantity': str(activity.normalized_quantity) if activity.normalized_quantity is not None else None,
        'normalized_unit': activity.normalized_unit,
        'amount': str(activity.amount) if activity.amount is not None else None,
        'currency': activity.currency,
        'review_status': activity.review_status,
        'site': activity.site,
        'description': activity.description,
    }


class ActivityFilter(django_filters.FilterSet):
    scope = django_filters.CharFilter(field_name='scope')
    source_type = django_filters.CharFilter(field_name='source_type')
    review_status = django_filters.CharFilter(field_name='review_status')
    suspicious_flag = django_filters.BooleanFilter(field_name='suspicious_flag')
    locked_for_audit = django_filters.BooleanFilter(field_name='locked_for_audit')
    tenant = django_filters.UUIDFilter(field_name='tenant__id')
    batch = django_filters.UUIDFilter(field_name='batch__id')
    category = django_filters.CharFilter(field_name='category')
    activity_date_from = django_filters.DateFilter(field_name='activity_date', lookup_expr='gte')
    activity_date_to = django_filters.DateFilter(field_name='activity_date', lookup_expr='lte')

    class Meta:
        model = NormalizedActivity
        fields = [
            'scope', 'source_type', 'review_status', 'suspicious_flag',
            'locked_for_audit', 'tenant', 'batch', 'category',
        ]


class NormalizedActivityViewSet(viewsets.ModelViewSet):
    queryset = NormalizedActivity.objects.select_related(
        'tenant', 'batch', 'source_row', 'approved_by', 'rejected_by'
    ).all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ActivityFilter
    search_fields = ['reference_id', 'vendor', 'description', 'site', 'traveler_name']
    ordering_fields = ['activity_date', 'created_at', 'normalized_quantity', 'amount']
    ordering = ['-activity_date']
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return NormalizedActivityDetailSerializer
        if self.action == 'partial_update':
            return NormalizedActivityEditSerializer
        return NormalizedActivityListSerializer

    def partial_update(self, request, *args, **kwargs):
        activity = self.get_object()

        if activity.locked_for_audit:
            return Response(
                {'error': 'This record is locked for audit and cannot be edited.'},
                status=status.HTTP_403_FORBIDDEN
            )

        before = _activity_snapshot(activity)
        serializer = NormalizedActivityEditSerializer(activity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        after = _activity_snapshot(activity)

        log_event(
            actor=request.user,
            action=AuditEvent.ACTION_EDIT,
            entity=activity,
            before=before,
            after=after,
            request=request,
        )
        return Response(NormalizedActivityDetailSerializer(activity).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        activity = self.get_object()

        if activity.review_status == NormalizedActivity.STATUS_APPROVED:
            return Response({'error': 'Already approved.'}, status=400)
        if activity.locked_for_audit:
            return Response({'error': 'Record is locked.'}, status=403)

        before = _activity_snapshot(activity)
        activity.review_status = NormalizedActivity.STATUS_APPROVED
        activity.approved_by = request.user
        activity.approved_at = timezone.now()
        activity.locked_for_audit = True
        activity.save(update_fields=[
            'review_status', 'approved_by', 'approved_at', 'locked_for_audit', 'updated_at'
        ])

        log_event(
            actor=request.user,
            action=AuditEvent.ACTION_APPROVE,
            entity=activity,
            before=before,
            after=_activity_snapshot(activity),
            request=request,
        )
        return Response({'status': 'approved', 'id': str(activity.id)})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        activity = self.get_object()

        if activity.locked_for_audit:
            return Response({'error': 'Record is locked for audit.'}, status=403)

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'A rejection reason is required.'}, status=400)

        before = _activity_snapshot(activity)
        activity.review_status = NormalizedActivity.STATUS_REJECTED
        activity.rejected_by = request.user
        activity.rejected_at = timezone.now()
        activity.rejection_reason = reason
        activity.save(update_fields=[
            'review_status', 'rejected_by', 'rejected_at', 'rejection_reason', 'updated_at'
        ])

        log_event(
            actor=request.user,
            action=AuditEvent.ACTION_REJECT,
            entity=activity,
            before=before,
            after=_activity_snapshot(activity),
            notes=reason,
            request=request,
        )
        return Response({'status': 'rejected', 'id': str(activity.id)})

    @action(detail=False, methods=['post'], url_path='bulk-approve')
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'Provide a list of activity IDs in "ids".'}, status=400)

        activities = NormalizedActivity.objects.filter(
            id__in=ids,
            review_status__in=[NormalizedActivity.STATUS_PENDING, NormalizedActivity.STATUS_FLAGGED],
            locked_for_audit=False,
        )
        approved_ids = []
        for activity in activities:
            before = _activity_snapshot(activity)
            activity.review_status = NormalizedActivity.STATUS_APPROVED
            activity.approved_by = request.user
            activity.approved_at = timezone.now()
            activity.locked_for_audit = True
            activity.save(update_fields=[
                'review_status', 'approved_by', 'approved_at', 'locked_for_audit', 'updated_at'
            ])
            log_event(
                actor=request.user,
                action=AuditEvent.ACTION_APPROVE,
                entity=activity,
                before=before,
                after=_activity_snapshot(activity),
                notes='Bulk approve',
                request=request,
            )
            approved_ids.append(str(activity.id))

        return Response({'approved': len(approved_ids), 'ids': approved_ids})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        activity = self.get_object()
        events = AuditEvent.objects.filter(
            entity_type='NormalizedActivity',
            entity_id=str(activity.id)
        ).select_related('actor').order_by('-timestamp')
        from audit.serializers import AuditEventSerializer
        return Response(AuditEventSerializer(events, many=True).data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """
    Summary statistics for the analyst dashboard home page.
    Optionally filtered by tenant_id query param.
    """
    tenant_id = request.query_params.get('tenant_id')
    qs = NormalizedActivity.objects.all()
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    from ingestion.models import IngestionBatch
    batch_qs = IngestionBatch.objects.all()
    if tenant_id:
        batch_qs = batch_qs.filter(tenant_id=tenant_id)

    scope_breakdown = {}
    for scope in ['1', '2', '3']:
        scope_breakdown[f'scope_{scope}'] = qs.filter(scope=scope).count()

    source_breakdown = {}
    for src in ['SAP', 'UTILITY', 'TRAVEL']:
        source_breakdown[src.lower()] = qs.filter(source_type=src).count()

    return Response({
        'total_batches': batch_qs.count(),
        'total_activities': qs.count(),
        'pending': qs.filter(review_status='PENDING').count(),
        'flagged': qs.filter(review_status='FLAGGED').count(),
        'approved': qs.filter(review_status='APPROVED').count(),
        'rejected': qs.filter(review_status='REJECTED').count(),
        'suspicious': qs.filter(suspicious_flag=True).count(),
        'locked': qs.filter(locked_for_audit=True).count(),
        'scope_breakdown': scope_breakdown,
        'source_breakdown': source_breakdown,
    })
