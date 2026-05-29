"""
AuditEvent model.

Records every significant state change on a NormalizedActivity.
Designed for auditors: who changed what, when, and what did it look like
before and after.

Deliberate design choices:
  - before_json / after_json stored as JSON, not model diffs, so
    the audit log is self-contained even if the model changes later.
  - actor is nullable — system-generated events (ingestion, normalization)
    record None actor.
  - entity_type is a string, not a ContentType FK. This keeps the table
    simple and avoids migrations when models are renamed.
  - IP address captured for security audit purposes.
"""
import uuid
# pyrefly: ignore [missing-import]
from django.db import models
# pyrefly: ignore [missing-import]
from django.contrib.auth import get_user_model

User = get_user_model()


class AuditEvent(models.Model):
    ACTION_INGEST = 'INGEST'
    ACTION_NORMALIZE = 'NORMALIZE'
    ACTION_EDIT = 'EDIT'
    ACTION_APPROVE = 'APPROVE'
    ACTION_REJECT = 'REJECT'
    ACTION_UNLOCK = 'UNLOCK'
    ACTION_CHOICES = [
        (ACTION_INGEST, 'Ingested'),
        (ACTION_NORMALIZE, 'Normalized'),
        (ACTION_EDIT, 'Edited'),
        (ACTION_APPROVE, 'Approved'),
        (ACTION_REJECT, 'Rejected'),
        (ACTION_UNLOCK, 'Unlocked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='audit_events',
        help_text='User who performed the action. NULL for system actions.'
    )
    action = models.CharField(max_length=15, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=100, help_text='Model name, e.g. NormalizedActivity')
    entity_id = models.CharField(max_length=255, help_text='PK of the affected record as string')
    before_json = models.JSONField(
        null=True, blank=True,
        help_text='Snapshot of relevant fields before the change'
    )
    after_json = models.JSONField(
        null=True, blank=True,
        help_text='Snapshot of relevant fields after the change'
    )
    notes = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['actor']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        actor_str = self.actor.username if self.actor else 'system'
        return f'{actor_str} {self.action} {self.entity_type} {self.entity_id} @ {self.timestamp}'
