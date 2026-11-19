from rest_framework import serializers

from .models import ModelEvaluation, ModelVersion

HEADLINE = ("pr_auc", "pr_auc_ci95", "roc_auc", "base_rate", "positives", "rows", "recall_at_fpr_1pct")


class ModelVersionSerializer(serializers.ModelSerializer):
    """List view: identity plus the headline *test-split* metrics from the offline experiment."""

    model_name = serializers.CharField(source="model.name", read_only=True)
    algorithm = serializers.CharField(source="model.algorithm", read_only=True)
    task_type = serializers.CharField(source="model.task_type", read_only=True)
    dataset = serializers.SerializerMethodField()
    feature_set = serializers.SerializerMethodField()
    test_metrics = serializers.SerializerMethodField()
    scorable = serializers.SerializerMethodField()

    class Meta:
        model = ModelVersion
        fields = [
            "id", "model_name", "algorithm", "task_type", "version", "status", "dataset", "feature_set",
            "random_seed", "trained_at", "test_metrics", "scorable",
        ]  # fmt: skip
        read_only_fields = fields

    def _evals(self, obj: ModelVersion) -> dict[str, dict]:
        return {e.split_name: e.metrics for e in obj.evaluations.all()}

    def get_dataset(self, obj: ModelVersion) -> str:
        return obj.version.split("-")[0]  # "<dataset>-s<seed>-<hash>" (see D-041)

    def get_feature_set(self, obj: ModelVersion) -> str | None:
        return (obj.feature_schema or {}).get("feature_set")

    def get_test_metrics(self, obj: ModelVersion) -> dict | None:
        test = self._evals(obj).get("test")
        return {k: test[k] for k in HEADLINE if k in test} if test else None

    def get_scorable(self, obj: ModelVersion) -> bool:
        from apps.detection.services import is_scorable  # local import: registry must not depend on detection

        return is_scorable(obj)


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelEvaluation
        fields = ["id", "split_name", "metrics", "notes", "created_at"]
        read_only_fields = fields


class ModelVersionDetailSerializer(ModelVersionSerializer):
    evaluations = EvaluationSerializer(many=True, read_only=True)

    class Meta(ModelVersionSerializer.Meta):
        fields = [
            *ModelVersionSerializer.Meta.fields, "hyperparameters", "feature_schema", "split_strategy",
            "library_versions", "training_data_sha256", "artifact_sha256", "evaluations",
        ]  # fmt: skip
        read_only_fields = fields
