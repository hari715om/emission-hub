from django.contrib import admin
from .models import IngestionBatch, SourceRow, UnitMapping, EmissionFactor


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'source_type', 'file_name', 'status', 'total_rows',
                    'success_count', 'failed_count', 'suspicious_count', 'uploaded_at']
    list_filter = ['tenant', 'source_type', 'status']
    search_fields = ['file_name']
    readonly_fields = ['id', 'uploaded_at', 'completed_at']


@admin.register(SourceRow)
class SourceRowAdmin(admin.ModelAdmin):
    list_display = ['batch', 'line_number', 'parse_status', 'created_at']
    list_filter = ['parse_status']
    readonly_fields = ['id', 'created_at']


@admin.register(UnitMapping)
class UnitMappingAdmin(admin.ModelAdmin):
    list_display = ['source_unit', 'canonical_unit', 'conversion_factor', 'source_type']
    search_fields = ['source_unit', 'canonical_unit']


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ['category', 'subcategory', 'scope', 'factor_kg_co2e_per_unit', 'unit', 'year', 'source']
    list_filter = ['scope', 'year', 'category']
