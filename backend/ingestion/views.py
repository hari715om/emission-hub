"""Ingestion views — file upload orchestration for all three source types."""
import logging
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from tenants.models import Tenant, SiteMapping
from .models import IngestionBatch, SourceRow, UnitMapping, EmissionFactor
from .serializers import (
    IngestionBatchSerializer, IngestionBatchDetailSerializer,
    SourceRowSerializer, UnitMappingSerializer, EmissionFactorSerializer
)
from .parsers.sap_parser import parse_sap_csv
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser import parse_travel_csv
from normalization.normalizer import normalize_row, build_unit_cache
from normalization.models import NormalizedActivity

logger = logging.getLogger('ingestion')


def _get_tenant(request):
    """
    Resolve the tenant for this request.
    For the prototype, tenant is passed as a query param or defaults to first.
    Production would use JWT claims or subdomain resolution.
    """
    tenant_id = request.data.get('tenant_id') or request.query_params.get('tenant_id')
    if tenant_id:
        return Tenant.objects.get(id=tenant_id)
    return Tenant.objects.filter(is_active=True).first()


def _resolve_site(raw_code: str, tenant, source_type: str) -> str:
    """Look up site name from SiteMapping; return raw code if not found."""
    if not raw_code:
        return ''
    mapping = SiteMapping.objects.filter(
        tenant=tenant,
        source_code=raw_code,
        source_type__in=[source_type, 'ALL']
    ).first()
    return mapping.site_name if mapping else raw_code


def _run_ingestion(request, source_type: str, parser_fn):
    """
    Shared ingestion logic for all three source types.
    1. Validate upload
    2. Create IngestionBatch
    3. Parse rows
    4. Store SourceRows
    5. Normalize valid rows
    6. Update batch counts
    7. Return summary
    """
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return Response({'error': 'No file uploaded. Send as multipart/form-data with key "file".'}, status=400)

    allowed_types = ['text/csv', 'application/csv', 'application/octet-stream', 'text/plain']
    if uploaded_file.content_type not in allowed_types and not uploaded_file.name.endswith('.csv'):
        return Response({'error': 'Only CSV files are accepted.'}, status=400)

    try:
        tenant = _get_tenant(request)
    except Tenant.DoesNotExist:
        return Response({'error': 'Tenant not found.'}, status=400)

    if not tenant:
        return Response({'error': 'No tenant configured. Create a tenant first.'}, status=400)

    # Create the batch record
    batch = IngestionBatch.objects.create(
        tenant=tenant,
        source_type=source_type,
        file_name=uploaded_file.name,
        file_size_bytes=uploaded_file.size,
        status=IngestionBatch.STATUS_PROCESSING,
        uploaded_by=request.user if request.user.is_authenticated else None,
    )

    try:
        file_bytes = uploaded_file.read()
        parsed_rows = parser_fn(file_bytes)
    except Exception as e:
        logger.exception('Parser crashed for batch %s', batch.id)
        batch.status = IngestionBatch.STATUS_FAILED
        batch.notes = f'Parser exception: {e}'
        batch.completed_at = timezone.now()
        batch.save()
        return Response({'error': f'Failed to parse file: {e}'}, status=400)

    unit_cache = build_unit_cache()

    total = 0
    success_count = 0
    failed_count = 0
    suspicious_count = 0

    for row_data in parsed_rows:
        total += 1
        line_num = row_data['line_num']
        raw = row_data['raw']
        parsed = row_data['parsed']
        error = row_data['error']

        if error or parsed is None:
            # Store raw row as FAILED
            SourceRow.objects.create(
                batch=batch,
                line_number=line_num,
                raw_payload=raw,
                parse_status=SourceRow.STATUS_FAILED,
                parse_error=error or 'Unknown parse failure',
            )
            failed_count += 1
            continue

        # Store raw row as PARSED
        source_row = SourceRow.objects.create(
            batch=batch,
            line_number=line_num,
            raw_payload=raw,
            parse_status=SourceRow.STATUS_PARSED,
        )

        # Resolve site name from SiteMapping
        raw_site_code = parsed.get('raw_site_code', '')
        resolved_site = parsed.get('site') or _resolve_site(raw_site_code, tenant, source_type)

        # Normalize
        try:
            norm_fields = normalize_row(
                parsed=parsed,
                source_type=source_type,
                tenant=tenant,
                batch=batch,
                source_row=source_row,
                unit_cache=unit_cache,
            )
            norm_fields['site'] = resolved_site or norm_fields.get('site', '')

            activity = NormalizedActivity.objects.create(**norm_fields)
            success_count += 1
            if activity.suspicious_flag:
                suspicious_count += 1
        except Exception as e:
            logger.exception('Normalization failed for row %s in batch %s', line_num, batch.id)
            source_row.parse_status = SourceRow.STATUS_FAILED
            source_row.parse_error = f'Normalization error: {e}'
            source_row.save()
            failed_count += 1
            success_count -= 1  # undo the early increment

    # Finalise batch
    batch.status = IngestionBatch.STATUS_DONE
    batch.total_rows = total
    batch.success_count = success_count
    batch.failed_count = failed_count
    batch.suspicious_count = suspicious_count
    batch.completed_at = timezone.now()
    batch.save()

    return Response({
        'batch_id': str(batch.id),
        'source_type': source_type,
        'file_name': uploaded_file.name,
        'total_rows': total,
        'success_count': success_count,
        'failed_count': failed_count,
        'suspicious_count': suspicious_count,
        'status': batch.status,
    }, status=201)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_sap(request):
    """Upload a SAP flat-file CSV (fuel & procurement data)."""
    return _run_ingestion(request, IngestionBatch.SOURCE_SAP, parse_sap_csv)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_utility(request):
    """Upload a utility portal CSV (electricity consumption)."""
    return _run_ingestion(request, IngestionBatch.SOURCE_UTILITY, parse_utility_csv)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_travel(request):
    """Upload a corporate travel CSV (Concur / Navan export)."""
    return _run_ingestion(request, IngestionBatch.SOURCE_TRAVEL, parse_travel_csv)


class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IngestionBatch.objects.select_related('tenant', 'uploaded_by').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tenant', 'source_type', 'status']
    search_fields = ['file_name']
    ordering_fields = ['uploaded_at', 'total_rows']
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return IngestionBatchDetailSerializer
        return IngestionBatchSerializer


class SourceRowViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SourceRow.objects.select_related('batch').all()
    serializer_class = SourceRowSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['batch', 'parse_status']
    permission_classes = [permissions.IsAuthenticated]


class UnitMappingViewSet(viewsets.ModelViewSet):
    queryset = UnitMapping.objects.all()
    serializer_class = UnitMappingSerializer
    permission_classes = [permissions.IsAuthenticated]


class EmissionFactorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmissionFactor.objects.all()
    serializer_class = EmissionFactorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['scope', 'category', 'year']
    permission_classes = [permissions.IsAuthenticated]
