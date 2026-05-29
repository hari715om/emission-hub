from rest_framework import serializers
from .models import IngestionBatch, SourceRow, UnitMapping, EmissionFactor


class IngestionBatchSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'tenant', 'tenant_name', 'source_type', 'file_name', 'file_size_bytes',
            'status', 'uploaded_by', 'uploaded_by_username', 'uploaded_at', 'completed_at',
            'total_rows', 'success_count', 'failed_count', 'suspicious_count', 'notes',
        ]
        read_only_fields = ['id', 'uploaded_at', 'completed_at']


class IngestionBatchDetailSerializer(IngestionBatchSerializer):
    """Includes failed source rows for the detail view."""
    failed_rows = serializers.SerializerMethodField()

    class Meta(IngestionBatchSerializer.Meta):
        fields = IngestionBatchSerializer.Meta.fields + ['failed_rows']

    def get_failed_rows(self, obj):
        rows = obj.source_rows.filter(parse_status=SourceRow.STATUS_FAILED)[:50]
        return SourceRowSerializer(rows, many=True).data


class SourceRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceRow
        fields = ['id', 'batch', 'line_number', 'raw_payload', 'parse_status', 'parse_error', 'created_at']
        read_only_fields = ['id', 'created_at']


class UnitMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitMapping
        fields = ['id', 'source_unit', 'canonical_unit', 'conversion_factor', 'source_type', 'notes']


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = [
            'id', 'category', 'subcategory', 'scope',
            'factor_kg_co2e_per_unit', 'unit', 'source', 'year', 'notes'
        ]
