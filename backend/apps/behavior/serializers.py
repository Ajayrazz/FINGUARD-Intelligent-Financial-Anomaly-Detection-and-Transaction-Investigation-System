from rest_framework import serializers

from .models import BehaviorAnalysisResult, BehaviorRun


class BehaviorRunSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    created_by_email = serializers.SerializerMethodField()
    is_mock_data = serializers.SerializerMethodField()

    class Meta:
        model = BehaviorRun
        fields = [
            "id", "dataset", "dataset_name", "is_mock_data", "status", "rows_total", "rows_scored", "rows_unavailable",
            "profiles_stored", "error_message", "params", "created_by_email", "created_at", "started_at", "finished_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_created_by_email(self, obj: BehaviorRun) -> str | None:
        return obj.created_by.email if obj.created_by else None

    def get_is_mock_data(self, obj: BehaviorRun) -> bool:
        return obj.dataset.name.upper().startswith(("MOCK", "DEMO"))


class BehaviorRunCreateSerializer(serializers.Serializer):
    dataset = serializers.IntegerField()


class BehaviorResultSerializer(serializers.ModelSerializer):
    """Result + the transaction fields a reviewer needs. No ground-truth label (D-018)."""

    transaction_id = serializers.IntegerField(source="transaction.id", read_only=True)
    external_id = serializers.CharField(source="transaction.transaction_id", read_only=True)
    amount = serializers.DecimalField(source="transaction.amount", max_digits=18, decimal_places=2, read_only=True)
    occurred_at = serializers.DateTimeField(source="transaction.occurred_at", read_only=True)
    account_ref = serializers.CharField(source="account.account_ref", read_only=True)

    class Meta:
        model = BehaviorAnalysisResult
        fields = [
            "id", "transaction_id", "external_id", "amount", "occurred_at", "account", "account_ref",
            "deviation_score", "coverage", "status", "history_count", "components",
        ]  # fmt: skip
        read_only_fields = fields
