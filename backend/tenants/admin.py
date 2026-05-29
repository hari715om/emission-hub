# pyrefly: ignore [missing-import]
from django.contrib import admin
from .models import Tenant, SiteMapping


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'country', 'industry', 'is_active', 'created_at']
    search_fields = ['name', 'slug']
    list_filter = ['is_active', 'country']


@admin.register(SiteMapping)
class SiteMappingAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'source_code', 'site_name', 'source_type', 'country']
    search_fields = ['source_code', 'site_name']
    list_filter = ['tenant', 'source_type']
