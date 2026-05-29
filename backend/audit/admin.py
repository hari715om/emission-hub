# pyrefly: ignore [missing-import]
from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'entity_type', 'entity_id', 'timestamp']
    list_filter = ['action', 'entity_type']
    search_fields = ['entity_id', 'notes']
    readonly_fields = ['id', 'timestamp', 'before_json', 'after_json']
