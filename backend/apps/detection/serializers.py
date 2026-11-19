from rest_framework import serializers

from apps.model_registry.models import ModelVersion

from .models import DetectionRun, Prediction


class DetectionRunSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model_version.model.name", read_only=True)
    algorithm = serializers.CharField(source="model_version.model.algorithm", read_only=True)
    version = serializers.CharField(source="model_version.version", read_only=True)
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    is_mock_data = serializers.SerializerMethodField()
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = DetectionRun
        fields = [
            "id", "model_version", "model_name", "algorithm", "version", "dataset", "dataset_name", "is_mock_data",
            "threshold", "threshold_source", "status", "rows_scored", "rows_flagged", "score_summary",
            "error_message", "created_by_email", "created_at", "started_at", "finished_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_is_mock_data(self, obj: DetectionRun) -> bool:
        return obj.dataset.name.upper().startswith("MOCK")

    def get_created_by_email(self, obj: DetectionRun) -> str | None:
        return obj.created_by.email if obj.created_by else None


class DetectionRunCreateSerializer(serializers.Serializer):
    model_version = serializers.PrimaryKeyRelatedField(queryset=ModelVersion.objects.select_related("model"))
    dataset = serializers.IntegerField()
    threshold = serializers.FloatField(required=False)


class PredictionSerializer(serializers.ModelSerializer):
    """Prediction + the few transaction fields an analyst needs. No ground-truth label (D-018)."""

    transaction_id = serializers.IntegerField(source="transaction.id", read_only=True)
    external_id = serializers.CharField(source="transaction.transaction_id", read_only=True)
    amount = serializers.DecimalField(source="transaction.amount", max_digits=18, decimal_places=2, read_only=True)
    tx_type = serializers.CharField(source="transaction.tx_type", read_only=True)
    occurred_at = serializers.DateTimeField(source="transaction.occurred_at", read_only=True)
    sender = serializers.CharField(source="transaction.sender.account_ref", read_only=True)
    receiver = serializers.SerializerMethodField()

    class Meta:
        model = Prediction
        fields = [
            "id",
            "transaction_id",
            "external_id",
            "amount",
            "tx_type",
            "occurred_at",
            "sender",
            "receiver",
            "score",
            "flagged",
        ]
        read_only_fields = fields

    def get_receiver(self, obj: Prediction) -> str | None:
        r = obj.transaction.receiver
        return r.account_ref if r else None


class TransactionPredictionSerializer(serializers.ModelSerializer):
    run = serializers.IntegerField(source="run_id", read_only=True)
    model_name = serializers.CharField(source="run.model_version.model.name", read_only=True)
    version = serializers.CharField(source="run.model_version.version", read_only=True)
    threshold = serializers.FloatField(source="run.threshold", read_only=True)
    created_at = serializers.DateTimeField(source="run.created_at", read_only=True)

    class Meta:
        model = Prediction
        fields = ["id", "run", "model_name", "version", "score", "flagged", "threshold", "created_at"]
        read_only_fields = fields
