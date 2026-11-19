"""Model registry tables. Populated by the training pipeline in Phase 5 (no API/logic yet)."""

from django.conf import settings
from django.db import models

from apps.datasets.models import Dataset


class MLModel(models.Model):
    class TaskType(models.TextChoices):
        SUPERVISED = "supervised"
        UNSUPERVISED = "unsupervised"
        GRAPH = "graph"

    name = models.CharField(max_length=80, unique=True)
    task_type = models.CharField(max_length=14, choices=TaskType.choices)
    algorithm = models.CharField(max_length=60)

    def __str__(self) -> str:
        return self.name


class ModelVersion(models.Model):
    class Status(models.TextChoices):
        CANDIDATE = "candidate"
        ACTIVE = "active"
        RETIRED = "retired"

    model = models.ForeignKey(MLModel, on_delete=models.PROTECT, related_name="versions")
    version = models.CharField(max_length=40)
    artifact_path = models.CharField(max_length=300)
    artifact_sha256 = models.CharField(max_length=64)
    artifact_format = models.CharField(max_length=30)
    hyperparameters = models.JSONField(default=dict)
    feature_schema = models.JSONField(default=dict)
    preprocessing_artifact_path = models.CharField(max_length=300, blank=True)
    training_dataset = models.ForeignKey(
        Dataset, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    training_data_sha256 = models.CharField(max_length=64, blank=True)
    split_strategy = models.JSONField(default=dict)
    random_seed = models.IntegerField(null=True, blank=True)
    library_versions = models.JSONField(default=dict)
    code_commit = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CANDIDATE)
    trained_at = models.DateTimeField(null=True, blank=True)
    trained_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["model_id", "-trained_at"]
        constraints = [models.UniqueConstraint(fields=["model", "version"], name="uniq_model_version")]

    def __str__(self) -> str:
        return f"{self.model} {self.version}"


class ModelEvaluation(models.Model):
    version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name="evaluations")
    split_name = models.CharField(max_length=40)
    metrics = models.JSONField(default=dict)
    curves_path = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.version} / {self.split_name}"
