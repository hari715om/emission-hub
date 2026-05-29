"""
Ingestion models.

Design rationale:
  IngestionBatch — one upload event. Stores what came in, from which source,
    who uploaded it, and a summary of outcomes. Deliberately separate from
    normalized data so raw provenance is never mixed with cleaned data.

  SourceRow — the literal row from the source file, stored as JSON.
    Never mutated after write. This is the source of truth for what
    the client actually sent. If normalization is wrong, you fix the
    normalizer and re-process; the raw row remains unchanged.

  NormalizedActivity — the cleaned, typed record that analysts review.
    Has full lineage back to SourceRow → IngestionBatch → Tenant.
    Scope 1/2/3 is set here, not in the raw layer.

  UnitMapping — a simple lookup table for unit aliases the sources use.
    SAP uses MEINS codes (L, KG, M3, KWH, TO, etc.) which need mapping
    to our canonical unit set.  Utility and travel sources have their own
    variants. This table allows runtime correction without code changes.

  EmissionFactor — reference data for Scope 3 calculations.
    Deliberately kept separate; not used in initial prototype but the
    schema supports it. Populated from DEFRA/EPA reference tables.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()


class IngestionBatch(models.Model):
    SOURCE_SAP = 'SAP'
    SOURCE_UTILITY = 'UTILITY'
    SOURCE_TRAVEL = 'TRAVEL'
    SOURCE_CHOICES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement'),
        (SOURCE_UTILITY, 'Utility Electricity'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_DONE = 'DONE'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    file_name = models.CharField(max_length=500)
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='batches'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Row-level outcome summary
    total_rows = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    suspicious_count = models.PositiveIntegerField(default=0)

    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['tenant', 'source_type']),
            models.Index(fields=['status']),
            models.Index(fields=['-uploaded_at']),
        ]

    def __str__(self):
        return f'{self.tenant.slug} | {self.source_type} | {self.file_name} ({self.status})'


class SourceRow(models.Model):
    """
    Raw row exactly as parsed from the source file.
    Immutable after creation — never edit this, only read it.
    """
    STATUS_PARSED = 'PARSED'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PARSED, 'Parsed OK'),
        (STATUS_FAILED, 'Parse Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='source_rows')
    line_number = models.PositiveIntegerField(help_text='1-indexed row number in the original file')
    raw_payload = models.JSONField(help_text='Exact key-value pairs from the source row')
    parse_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PARSED)
    parse_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['batch', 'line_number']
        indexes = [
            models.Index(fields=['batch', 'parse_status']),
        ]

    def __str__(self):
        return f'Row {self.line_number} of batch {self.batch_id} ({self.parse_status})'


class UnitMapping(models.Model):
    """
    Translates source unit strings to a canonical unit.

    SAP MEINS codes: L (litres), KG (kilograms), M3 (cubic metres),
    KWH (kilowatt-hours), TO (metric tonnes), G (grams), etc.
    Utility portals may use MWH, GJ, MMBTU.
    Travel sources may give distances in MI or KM.

    conversion_factor: multiply source value by this to get canonical value.
    canonical_unit: what we store after conversion (e.g. kWh, kg, km, l).
    """
    source_unit = models.CharField(max_length=50, unique=True)
    canonical_unit = models.CharField(max_length=50)
    conversion_factor = models.DecimalField(max_digits=20, decimal_places=10)
    source_type = models.CharField(
        max_length=20,
        choices=[('SAP', 'SAP'), ('UTILITY', 'Utility'), ('TRAVEL', 'Travel'), ('ALL', 'All')],
        default='ALL'
    )
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['source_unit']

    def __str__(self):
        return f'{self.source_unit} → {self.canonical_unit} (×{self.conversion_factor})'


class EmissionFactor(models.Model):
    """
    Reference emission factors (kg CO2e per unit of activity).
    Source: DEFRA 2023 / EPA 2023.
    Used for Scope 3 estimates — flights, hotel stays, fuel combustion.
    """
    SCOPE_1 = '1'
    SCOPE_2 = '2'
    SCOPE_3 = '3'
    SCOPE_CHOICES = [('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3')]

    category = models.CharField(max_length=100, help_text='e.g. fuel_diesel, electricity_uk, flight_economy')
    subcategory = models.CharField(max_length=100, blank=True, default='')
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    factor_kg_co2e_per_unit = models.DecimalField(max_digits=20, decimal_places=8)
    unit = models.CharField(max_length=50, help_text='Unit of the activity quantity, e.g. litre, kWh, km')
    source = models.CharField(max_length=100, help_text='e.g. DEFRA 2023, EPA 2023')
    year = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('category', 'subcategory', 'year')
        ordering = ['scope', 'category']

    def __str__(self):
        return f'Scope {self.scope} | {self.category} | {self.factor_kg_co2e_per_unit} kgCO2e/{self.unit}'
