# pyrefly: ignore [missing-import]
from django.contrib import admin
from .models import NormalizedActivity


@admin.register(NormalizedActivity)
class NormalizedActivityAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'source_type', 'category', 'scope', 'activity_date',
        'normalized_quantity', 'normalized_unit', 'review_status', 'suspicious_flag'
    ]
    list_filter = ['tenant', 'source_type', 'scope', 'review_status', 'suspicious_flag']
    search_fields = ['reference_id', 'vendor', 'description', 'site']
    readonly_fields = ['id', 'created_at', 'updated_at', 'source_row', 'batch']
    date_hierarchy = 'activity_date'
