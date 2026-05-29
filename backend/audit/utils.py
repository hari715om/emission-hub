"""Utility to create audit events from views."""
from .models import AuditEvent


def log_event(actor, action, entity, before=None, after=None, notes='', request=None):
    """
    Create an AuditEvent for a NormalizedActivity change.

    entity: the model instance being changed
    before: dict of fields before change (pass None for CREATE events)
    after: dict of fields after change (pass None for DELETE events)
    """
    ip = None
    if request:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR')

    AuditEvent.objects.create(
        actor=actor if (actor and actor.is_authenticated) else None,
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        before_json=before,
        after_json=after,
        notes=notes,
        ip_address=ip,
    )
