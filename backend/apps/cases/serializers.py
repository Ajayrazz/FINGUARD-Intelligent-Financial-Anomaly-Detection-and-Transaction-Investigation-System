from typing import Any

from rest_framework import serializers

from apps.alerts.serializers import AlertSerializer

from .models import Case, CaseEvent, CaseEvidence, CaseNote, CaseTransaction
from .services import allowed_transitions


class CaseSerializer(serializers.ModelSerializer):
    assignee_email = serializers.SerializerMethodField()
    created_by_email = serializers.SerializerMethodField()
    alert_count = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            "id", "case_ref", "title", "priority", "status", "dataset", "assignee", "assignee_email", "created_by_email", "auto_created", "opened_at",
            "outcome", "closed_at", "alert_count", "transaction_count",
        ]  # fmt: skip
        read_only_fields = fields

    def get_assignee_email(self, obj: Case) -> str | None:
        return obj.assignee.email if obj.assignee else None

    def get_created_by_email(self, obj: Case) -> str | None:
        return obj.created_by.email if obj.created_by else None

    def get_alert_count(self, obj: Case) -> int:
        n = getattr(obj, "_alert_count", None)  # annotated by the list view (avoids one COUNT per row)
        return obj.case_alerts.count() if n is None else n

    def get_transaction_count(self, obj: Case) -> int:
        n = getattr(obj, "_transaction_count", None)
        return obj.case_transactions.count() if n is None else n


class CaseDetailSerializer(CaseSerializer):
    allowed_transitions = serializers.SerializerMethodField()
    read_only_reason = serializers.SerializerMethodField()
    alerts = serializers.SerializerMethodField()
    resolved_by_email = serializers.SerializerMethodField()
    closed_by_email = serializers.SerializerMethodField()

    class Meta(CaseSerializer.Meta):
        fields = [
            *CaseSerializer.Meta.fields,
            "description",
            "resolution_summary",
            "resolved_at",
            "resolved_by_email",
            "closed_by_email",
            "allowed_transitions",
            "read_only_reason",
            "alerts",
        ]
        read_only_fields = fields

    def get_allowed_transitions(self, obj: Case) -> list[str]:
        request = self.context.get("request")
        return allowed_transitions(obj, request.user) if request else []

    def get_read_only_reason(self, obj: Case) -> str | None:
        return (
            "This case is closed: it is read-only, but its history remains viewable."
            if obj.status == "closed"
            else None
        )

    def get_alerts(self, obj: Case) -> Any:
        return AlertSerializer(
            [
                link.alert
                for link in obj.case_alerts.select_related(
                    "alert__transaction", "alert__account", "alert__assignee", "alert__assessment", "alert__dataset"
                )
            ],
            many=True,
        ).data

    def get_resolved_by_email(self, obj: Case) -> str | None:
        return obj.resolved_by.email if obj.resolved_by else None

    def get_closed_by_email(self, obj: Case) -> str | None:
        return obj.closed_by.email if obj.closed_by else None


class CaseCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=["low", "medium", "high", "critical"], default="medium")
    dataset = serializers.IntegerField(required=False)
    alert = serializers.IntegerField(required=False)
    transactions = serializers.ListField(child=serializers.IntegerField(), required=False)


class CaseUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=["low", "medium", "high", "critical"], required=False)


class TransitionSerializer(serializers.Serializer):
    to_status = serializers.CharField()
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    outcome = serializers.CharField(required=False, allow_blank=True, default="")
    summary = serializers.CharField(required=False, allow_blank=True, default="", max_length=5000)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class ResolveSerializer(serializers.Serializer):
    outcome = serializers.CharField()
    summary = serializers.CharField(max_length=5000)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class CloseSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AssignSerializer(serializers.Serializer):
    assignee = serializers.IntegerField()


class NoteSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)
    body = serializers.SerializerMethodField()
    revision_count = serializers.SerializerMethodField()
    edited = serializers.SerializerMethodField()

    class Meta:
        model = CaseNote
        fields = ["id", "kind", "author", "author_email", "body", "revision_count", "edited", "created_at"]
        read_only_fields = fields

    def _last(self, obj: CaseNote):  # noqa: ANN202
        return obj.revisions.order_by("-revision").first()

    def get_body(self, obj: CaseNote) -> str:
        last = self._last(obj)
        return last.body if last else ""

    def get_revision_count(self, obj: CaseNote) -> int:
        return obj.revisions.count()

    def get_edited(self, obj: CaseNote) -> bool:
        return obj.revisions.count() > 1


class NoteBodySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["comment", "note"], default="comment")
    body = serializers.CharField(max_length=10000)


class NoteEditSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=10000)


class EvidenceSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.SerializerMethodField()

    class Meta:
        model = CaseEvidence
        fields = ["id", "original_name", "sha256", "mime", "size", "description", "uploaded_by_email", "created_at"]
        read_only_fields = fields

    def get_uploaded_by_email(self, obj: CaseEvidence) -> str | None:
        return obj.uploaded_by.email if obj.uploaded_by else None


class EventSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = CaseEvent
        fields = ["id", "event_type", "actor_email", "from_status", "to_status", "payload", "created_at"]
        read_only_fields = fields

    def get_actor_email(self, obj: CaseEvent) -> str | None:
        return obj.actor.email if obj.actor else None


class CaseTransactionSerializer(serializers.ModelSerializer):
    external_id = serializers.CharField(source="transaction.transaction_id", read_only=True)
    amount = serializers.DecimalField(source="transaction.amount", max_digits=18, decimal_places=2, read_only=True)
    tx_type = serializers.CharField(source="transaction.tx_type", read_only=True)
    occurred_at = serializers.DateTimeField(source="transaction.occurred_at", read_only=True)
    sender = serializers.CharField(source="transaction.sender.account_ref", read_only=True)
    receiver = serializers.SerializerMethodField()

    class Meta:
        model = CaseTransaction
        fields = [
            "id",
            "transaction",
            "external_id",
            "amount",
            "tx_type",
            "occurred_at",
            "sender",
            "receiver",
            "note",
            "added_at",
        ]
        read_only_fields = fields

    def get_receiver(self, obj: CaseTransaction) -> str | None:
        r = obj.transaction.receiver
        return r.account_ref if r else None


class AddTransactionSerializer(serializers.Serializer):
    transaction = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)


class LinkAlertSerializer(serializers.Serializer):
    alert = serializers.IntegerField()


class LinkCaseSerializer(serializers.Serializer):
    case = serializers.IntegerField()
