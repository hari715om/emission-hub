# pyrefly: ignore [missing-import]
from rest_framework import serializers
from .models import Tenant, SiteMapping


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'country', 'industry', 'created_at', 'is_active']
        read_only_fields = ['id', 'created_at']


class SiteMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteMapping
        fields = ['id', 'tenant', 'source_code', 'site_name', 'country', 'region', 'source_type']
