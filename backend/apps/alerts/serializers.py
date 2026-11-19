from rest_framework import serializers

from .models import Alert, AlertEvent, AlertPolicy, AlertRun, NotificationLog
from .rules import TYPE_LABEL


class AlertSerializer(serializers.ModelSerializer):
    type_label = serializers.SerializerMethodField()
    assignee_email = serializers.SerializerMethodField()
    transaction_external_id = serializers.SerializerMethodField()
    account_ref = serializers.SerializerMethodField()
    risk_score = serializers.SerializerMethodField()
    dataset_name = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id", "alert_type", "type_label", "severity", "status", "dataset", "dataset_name", "transaction", "transaction_external_id", "account", "account_ref",
            "assessment", "risk_score", "reason", "assignee", "assignee_email", "acknowledged_at", "escalated_at", "closed_at", "outcome", "created_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_type_label(self, obj: Alert) -> str:
        return TYPE_LABEL.get(obj.alert_type, obj.alert_type)

    def get_assignee_email(self, obj: Alert) -> str | None:
        return obj.assignee.email if obj.assignee else None

    def get_transaction_external_id(self, obj: Alert) -> str | None:
        return obj.transaction.transaction_id if obj.transaction else None

    def get_account_ref(self, obj: Alert) -> str | None:
        return obj.account.account_ref if obj.account else None

    def get_risk_score(self, obj: Alert) -> float | None:
        return obj.assessment.overall_score if obj.assessment else None

    def get_dataset_name(self, obj: Alert) -> str | None:
        return obj.dataset.name if obj.dataset else None


class AlertDetailSerializer(AlertSerializer):
    class Meta(AlertSerializer.Meta):
        fields = [
            *AlertSerializer.Meta.fields,
            "evidence_snapshot",
            "escalation_reason",
            "close_notes",
            "policy_version",
            "dedup_key",
        ]
        read_only_fields = fields


class AlertEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = AlertEvent
        fields = ["id", "event_type", "actor_email", "payload", "created_at"]
        read_only_fields = fields

    def get_actor_email(self, obj: AlertEvent) -> str | None:
        return obj.actor.email if obj.actor else None


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ["id", "channel", "recipient", "status", "error", "sent_at"]
        read_only_fields = fields


class AssignSerializer(serializers.Serializer):
    assignee = serializers.IntegerField()


class EscalateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class CloseSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=[c.value for c in Alert.Outcome])
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class EvaluateSerializer(serializers.Serializer):
    dataset = serializers.IntegerField()


class AlertRunSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)

    class Meta:
        model = AlertRun
        fields = [
            "id",
            "dataset",
            "dataset_name",
            "policy_version",
            "trigger",
            "status",
            "result",
            "error_message",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields


class PolicySerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = AlertPolicy
        fields = ["id", "version", "config", "is_active", "notes", "created_by_email", "created_at"]
        read_only_fields = fields

    def get_created_by_email(self, obj: AlertPolicy) -> str | None:
        return obj.created_by.email if obj.created_by else None


class PolicyCreateSerializer(serializers.Serializer):
    config = serializers.DictField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
