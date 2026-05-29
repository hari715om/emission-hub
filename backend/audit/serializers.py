# pyrefly: ignore [missing-import]
from rest_framework import serializers
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default='system')

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'actor', 'actor_username', 'action', 'entity_type',
            'entity_id', 'before_json', 'after_json', 'notes', 'ip_address', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']
