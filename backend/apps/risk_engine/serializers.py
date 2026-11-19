from rest_framework import serializers

from risk_engine_lib import COMPONENTS

from .models import AccountRiskHistory, RiskAssessment, RiskConfig, RiskScoreRun


class RiskConfigSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()
    model_version_name = serializers.SerializerMethodField()
    used_by_assessments = serializers.SerializerMethodField()

    class Meta:
        model = RiskConfig
        fields = [
            "id", "version", "weights", "thresholds", "missing_signal_policy", "min_coverage", "model_version", "model_version_name",
            "is_active", "source", "notes", "created_by_email", "created_at", "used_by_assessments",
        ]  # fmt: skip
        read_only_fields = fields

    def get_created_by_email(self, obj: RiskConfig) -> str | None:
        return obj.created_by.email if obj.created_by else None

    def get_model_version_name(self, obj: RiskConfig) -> str | None:
        return str(obj.model_version) if obj.model_version else None

    def get_used_by_assessments(self, obj: RiskConfig) -> bool:
        return RiskAssessment.objects.filter(config=obj).exists()


class RiskConfigCreateSerializer(serializers.Serializer):
    weights = serializers.DictField(child=serializers.FloatField())
    thresholds = serializers.DictField(child=serializers.FloatField())
    missing_signal_policy = serializers.ChoiceField(
        choices=["renormalize", "neutral_prior", "strict"], default="renormalize"
    )
    min_coverage = serializers.FloatField(default=0.5)
    model_version = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class RiskRunSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    config_version = serializers.IntegerField(source="config.version", read_only=True)
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = RiskScoreRun
        fields = [
            "id", "dataset", "dataset_name", "config", "config_version", "status", "params", "rows_total", "rows_scored",
            "category_counts", "coverage_summary", "error_message", "created_by_email", "created_at", "finished_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_created_by_email(self, obj: RiskScoreRun) -> str | None:
        return obj.created_by.email if obj.created_by else None


class RiskRunCreateSerializer(serializers.Serializer):
    dataset = serializers.IntegerField()
    config = serializers.IntegerField(required=False)


class AssessmentListSerializer(serializers.ModelSerializer):
    """List row + the transaction fields a reviewer needs. Never the ground-truth label (D-018)."""

    external_id = serializers.CharField(source="transaction.transaction_id", read_only=True)
    amount = serializers.DecimalField(source="transaction.amount", max_digits=18, decimal_places=2, read_only=True)
    tx_type = serializers.CharField(source="transaction.tx_type", read_only=True)
    occurred_at = serializers.DateTimeField(source="transaction.occurred_at", read_only=True)
    account_ref = serializers.CharField(source="account.account_ref", read_only=True)
    component_values = serializers.SerializerMethodField()
    config_version = serializers.IntegerField(source="config.version", read_only=True)

    class Meta:
        model = RiskAssessment
        fields = [
            "id", "transaction", "external_id", "amount", "tx_type", "occurred_at", "account", "account_ref", "overall_score",
            "category", "weight_coverage", "low_coverage", "capped", "policy", "config_version", "run", "component_values", "computed_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_component_values(self, obj: RiskAssessment) -> dict[str, float | None]:
        return {
            c: (obj.components[c]["value"] if obj.components[c]["available"] else None)
            for c in COMPONENTS
            if c in obj.components
        }


class AssessmentDetailSerializer(AssessmentListSerializer):
    class Meta(AssessmentListSerializer.Meta):
        fields = [
            *AssessmentListSerializer.Meta.fields,
            "components",
            "algorithm_version",
            "detection_run",
            "behavior_run",
            "graph_snapshot",
        ]
        read_only_fields = fields


class AccountRiskHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountRiskHistory
        fields = ["id", "run", "as_of", "score", "category", "assessment_count"]
        read_only_fields = fields
