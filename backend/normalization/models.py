"""
Normalization models.

NormalizedActivity is the single central record that analysts review.
It stores:
  - what the activity was (category, date, site, quantity)
  - where it came from (tenant, batch, source_row for full provenance)
  - which GHG scope it belongs to (1/2/3)
  - both original and normalized quantity/unit so nothing is lost
  - review lifecycle (PENDING → APPROVED | REJECTED, then LOCKED)
  - flags for anything suspicious the parser detected

Design decision: NormalizedActivity is NOT the same as SourceRow.
SourceRow is immutable raw storage. NormalizedActivity can be edited
by analysts before approval. Edits are tracked in AuditEvent.

Scope classification rationale (GHG Protocol):
  Scope 1 — direct combustion: diesel, petrol, natural gas at owned facilities
  Scope 2 — purchased electricity consumed at owned/controlled sites
  Scope 3 — indirect: business travel (flights, hotels, ground), upstream
             procurement of goods/services not combusted on-site
"""
# pyrefly: ignore [missing-import]
import uuid
# pyrefly: ignore [missing-import]
from django.db import models
# pyrefly: ignore [missing-import]
from django.contrib.auth import get_user_model
from tenants.models import Tenant
from ingestion.models import IngestionBatch, SourceRow

User = get_user_model()


class NormalizedActivity(models.Model):
    # --- Source classification ---
    SOURCE_SAP = 'SAP'
    SOURCE_UTILITY = 'UTILITY'
    SOURCE_TRAVEL = 'TRAVEL'
    SOURCE_CHOICES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement'),
        (SOURCE_UTILITY, 'Utility Electricity'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    # --- GHG Scope ---
    SCOPE_1 = '1'
    SCOPE_2 = '2'
    SCOPE_3 = '3'
    SCOPE_CHOICES = [('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3')]

    # --- Category (what type of activity) ---
    # SAP: FUEL_DIESEL, FUEL_PETROL, FUEL_NATURAL_GAS, FUEL_LPG, PROCUREMENT
    # Utility: ELECTRICITY
    # Travel: FLIGHT, HOTEL, CAR_RENTAL, TRAIN, TAXI
    CATEGORY_CHOICES = [
        ('FUEL_DIESEL', 'Diesel'),
        ('FUEL_PETROL', 'Petrol / Gasoline'),
        ('FUEL_NATURAL_GAS', 'Natural Gas'),
        ('FUEL_LPG', 'LPG'),
        ('FUEL_HFO', 'Heavy Fuel Oil'),
        ('PROCUREMENT', 'Procurement (non-fuel)'),
        ('ELECTRICITY', 'Electricity'),
        ('FLIGHT', 'Flight'),
        ('HOTEL', 'Hotel Stay'),
        ('CAR_RENTAL', 'Car Rental / Ground Transport'),
        ('TRAIN', 'Train'),
        ('TAXI', 'Taxi / Rideshare'),
        ('UNKNOWN', 'Unknown / Unclassified'),
    ]

    # --- Review lifecycle ---
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_FLAGGED = 'FLAGGED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_FLAGGED, 'Flagged / Suspicious'),
    ]

    # --- Core identity ---
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='activities')
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name='activities', null=True, blank=True
    )
    source_row = models.OneToOneField(
        SourceRow, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='normalized_activity',
        help_text='The raw row this was derived from. NULL if manually entered.'
    )

    # --- Classification ---
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='UNKNOWN')
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES, null=True, blank=True)

    # --- Activity dates ---
    activity_date = models.DateField(
        null=True, blank=True,
        help_text='The date the activity occurred (document date for SAP, period start for utility, trip date for travel)'
    )
    period_start = models.DateField(null=True, blank=True, help_text='For utility billing periods')
    period_end = models.DateField(null=True, blank=True, help_text='For utility billing periods')

    # --- Location ---
    site = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Resolved site name (after SiteMapping lookup)'
    )
    raw_site_code = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Original code from source (SAP WERKS, meter ID, etc.)'
    )
    country = models.CharField(max_length=100, blank=True, default='')

    # --- Quantity: original ---
    quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Original quantity exactly as parsed from source'
    )
    unit = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Original unit string from source'
    )

    # --- Quantity: normalized ---
    normalized_quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Quantity converted to canonical unit'
    )
    normalized_unit = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Canonical unit after conversion (e.g. kWh, litres, km)'
    )

    # --- CO2e estimate (optional, from EmissionFactor) ---
    co2e_kg = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        help_text='Estimated kg CO2e — indicative, not audited'
    )

    # --- Financial ---
    amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True, default='')

    # --- Source metadata (varies by source type) ---
    vendor = models.CharField(max_length=255, blank=True, default='', help_text='SAP vendor / travel merchant')
    description = models.CharField(max_length=500, blank=True, default='')
    reference_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Original doc number / expense ID / meter ID for traceability'
    )
    cost_centre = models.CharField(max_length=100, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')

    # --- Travel-specific ---
    origin = models.CharField(max_length=255, blank=True, default='')
    destination = models.CharField(max_length=255, blank=True, default='')
    traveler_name = models.CharField(max_length=255, blank=True, default='')
    class_of_service = models.CharField(max_length=50, blank=True, default='')
    hotel_nights = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- Review lifecycle ---
    review_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    suspicious_flag = models.BooleanField(default=False)
    suspicious_reasons = models.JSONField(
        default=list, blank=True,
        help_text='List of human-readable reasons the row was flagged'
    )
    locked_for_audit = models.BooleanField(
        default=False,
        help_text='True after approval — prevents further edits'
    )

    # --- Approval tracking ---
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_activities'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='rejected_activities'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        verbose_name_plural = 'Normalized Activities'
        indexes = [
            models.Index(fields=['tenant', 'source_type']),
            models.Index(fields=['tenant', 'review_status']),
            models.Index(fields=['tenant', 'scope']),
            models.Index(fields=['suspicious_flag']),
            models.Index(fields=['locked_for_audit']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return (
            f'{self.tenant.slug} | {self.source_type} | {self.category} | '
            f'{self.activity_date} | {self.normalized_quantity} {self.normalized_unit}'
        )
