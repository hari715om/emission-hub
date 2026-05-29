# pyrefly: ignore [missing-import]
from rest_framework import serializers
from normalization.models import NormalizedActivity
from ingestion.models import IngestionBatch


class NormalizedActivityListSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    batch_file = serializers.CharField(source='batch.file_name', read_only=True)
    scope_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = NormalizedActivity
        fields = [
            'id', 'tenant', 'tenant_name', 'batch', 'batch_file',
            'source_type', 'category', 'scope', 'scope_label',
            'activity_date', 'period_start', 'period_end',
            'site', 'raw_site_code', 'country',
            'quantity', 'unit', 'normalized_quantity', 'normalized_unit', 'co2e_kg',
            'amount', 'currency',
            'vendor', 'description', 'reference_id',
            'origin', 'destination', 'traveler_name', 'class_of_service', 'hotel_nights',
            'review_status', 'status_label', 'suspicious_flag', 'suspicious_reasons',
            'locked_for_audit', 'approved_at', 'rejected_at', 'rejection_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_scope_label(self, obj):
        mapping = {'1': 'Scope 1', '2': 'Scope 2', '3': 'Scope 3'}
        return mapping.get(obj.scope, 'Unknown')

    def get_status_label(self, obj):
        mapping = {
            'PENDING': 'Pending Review',
            'APPROVED': 'Approved',
            'REJECTED': 'Rejected',
            'FLAGGED': 'Flagged',
        }
        return mapping.get(obj.review_status, obj.review_status)


class NormalizedActivityDetailSerializer(NormalizedActivityListSerializer):
    """Includes raw payload from the source row for side-by-side comparison."""
    raw_payload = serializers.SerializerMethodField()
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True)
    rejected_by_username = serializers.CharField(source='rejected_by.username', read_only=True)
    source_row_id = serializers.CharField(source='source_row.id', read_only=True)
    source_row_line = serializers.IntegerField(source='source_row.line_number', read_only=True)

    class Meta(NormalizedActivityListSerializer.Meta):
        fields = NormalizedActivityListSerializer.Meta.fields + [
            'raw_payload', 'approved_by_username', 'rejected_by_username',
            'source_row_id', 'source_row_line', 'cost_centre', 'department',
        ]

    def get_raw_payload(self, obj):
        if obj.source_row:
            return obj.source_row.raw_payload
        return None


class NormalizedActivityEditSerializer(serializers.ModelSerializer):
    """Only the fields analysts are allowed to change before approval."""
    class Meta:
        model = NormalizedActivity
        fields = [
            'category', 'scope', 'activity_date', 'period_start', 'period_end',
            'site', 'country', 'quantity', 'unit', 'normalized_quantity', 'normalized_unit',
            'amount', 'currency', 'vendor', 'description', 'reference_id',
            'origin', 'destination', 'class_of_service', 'hotel_nights',
            'cost_centre', 'department',
        ]

    def validate(self, data):
        instance = self.instance
        if instance and instance.locked_for_audit:
            raise serializers.ValidationError('Cannot edit a locked record.')
        return data
