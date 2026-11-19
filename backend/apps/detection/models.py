from django.conf import settings
from django.db import models

from apps.datasets.models import Dataset
from apps.model_registry.models import ModelVersion
from apps.transactions.models import Transaction


class DetectionRun(models.Model):
    """One batch scoring of a dataset's transactions by one registered model version."""

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    model_version = models.ForeignKey(ModelVersion, on_delete=models.PROTECT, related_name="detection_runs")
    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="detection_runs")
    threshold = models.FloatField()
    threshold_source = models.CharField(max_length=80)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rows_scored = models.PositiveIntegerField(default=0)
    rows_flagged = models.PositiveIntegerField(default=0)
    score_summary = models.JSONField(default=dict, blank=True)  # quantiles + histogram of all scores
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"run {self.pk}: {self.model_version} on {self.dataset}"


class Prediction(models.Model):
    """The score one run gave one transaction. Scores are model output, never dataset ground truth."""

    run = models.ForeignKey(DetectionRun, on_delete=models.CASCADE, related_name="predictions")
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="predictions")
    score = models.FloatField()
    flagged = models.BooleanField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "transaction"], name="uniq_prediction_per_run_tx")]
        indexes = [
            models.Index(fields=["run", "-score"], name="pred_run_score_idx"),
            models.Index(fields=["run", "flagged", "-score"], name="pred_run_flag_score_idx"),
            models.Index(fields=["transaction"], name="pred_tx_idx"),
        ]

    def __str__(self) -> str:
        return f"run {self.run_id} / tx {self.transaction_id}: {self.score:.4f}"
