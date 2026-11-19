from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "created_at", "actor", "actor_email", "action", "resource_type", "resource_id",
            "ip_address", "user_agent", "request_id", "changes",
        ]  # fmt: skip
        read_only_fields = fields
