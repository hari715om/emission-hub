"""
Tenants models.

Multi-tenancy design: every data-bearing model carries a FK to Tenant.
A Tenant is the top-level account — one company = one tenant.

SiteMapping translates opaque plant/site codes (e.g. SAP WERKS "1000")
into human-readable site names so analysts see meaningful labels, not
SAP codes.  The mapping lives here (not in ingestion) because it is
shared across source types.
"""
import uuid
# pyrefly: ignore [missing-import]
from django.db import models


class Tenant(models.Model):
    """A client company using Breathe ESG."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    country = models.CharField(max_length=100, blank=True, default='')
    industry = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SiteMapping(models.Model):
    """
    Translates raw source codes into canonical site names.

    SAP WERKS codes (e.g. "1000", "2000") mean nothing without a lookup
    table.  Utility meter IDs, cost centres, and depot codes have the same
    problem.  This table is seeded per tenant during onboarding.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='site_mappings')
    source_code = models.CharField(max_length=100, help_text='Raw code from the source system, e.g. SAP WERKS')
    site_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    source_type = models.CharField(
        max_length=20,
        choices=[('SAP', 'SAP'), ('UTILITY', 'Utility'), ('TRAVEL', 'Travel'), ('ALL', 'All')],
        default='ALL'
    )

    class Meta:
        unique_together = ('tenant', 'source_code', 'source_type')
        ordering = ['tenant', 'source_code']

    def __str__(self):
        return f'{self.tenant.slug} | {self.source_code} → {self.site_name}'
