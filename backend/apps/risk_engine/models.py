from django.conf import settings
from django.db import models

from apps.behavior.models import BehaviorRun
from apps.datasets.models import Dataset
from apps.detection.models import DetectionRun
from apps.graph_engine.models import GraphSnapshot
from apps.model_registry.models import ModelVersion
from apps.transactions.models import Account, Transaction


class RiskConfig(models.Model):
    """A versioned scoring configuration. Immutable once any assessment used it: changes create a new version."""

    class Source(models.TextChoices):
        DEFAULT = "default"
        MANUAL = "manual"
        CALIBRATED = "calibrated"

    version = models.PositiveIntegerField(unique=True)
    weights = models.JSONField()  # {"A": .25, "B": .20, "G": .20, "F": .15, "D": .10, "H": .10}
    thresholds = models.JSONField()  # {"medium": 30, "high": 60, "critical": 80}
    missing_signal_policy = models.CharField(max_length=14, default="renormalize")
    min_coverage = models.FloatField(default=0.5)
    model_version = models.ForeignKey(ModelVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    is_active = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=models.Q(is_active=True), name="one_active_risk_config"
            )
        ]

    def __str__(self) -> str:
        return f"risk config v{self.version}"

    def save(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if self.pk and RiskAssessment.objects.filter(config_id=self.pk).exists():
            old = RiskConfig.objects.get(pk=self.pk)
            frozen = ("weights", "thresholds", "missing_signal_policy", "min_coverage", "model_version_id", "version")
            if any(getattr(old, f) != getattr(self, f) for f in frozen):
                raise ValueError("A risk configuration that has been used is immutable; create a new version.")
        super().save(*args, **kwargs)


class RiskScoreRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="risk_runs")
    config = models.ForeignKey(RiskConfig, on_delete=models.PROTECT, related_name="runs")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    params = models.JSONField(default=dict)  # which detection/behavior/graph/duplicate inputs were used, priors
    rows_total = models.PositiveIntegerField(default=0)
    rows_scored = models.PositiveIntegerField(default=0)
    category_counts = models.JSONField(default=dict)
    coverage_summary = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"risk run {self.pk} on {self.dataset}"


class RiskAssessment(models.Model):
    """One immutable assessment (UPDATE/DELETE blocked by a trigger): scores are history, never rewritten."""

    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="risk_assessments")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="risk_assessments")  # the sender
    config = models.ForeignKey(RiskConfig, on_delete=models.PROTECT, related_name="assessments")
    run = models.ForeignKey(RiskScoreRun, on_delete=models.PROTECT, related_name="assessments")
    algorithm_version = models.CharField(max_length=10)
    components = models.JSONField()  # {A: {available, value, reason, source, weight, contribution, imputed}, ...}
    overall_score = models.FloatField(null=True)  # null: unscored (no signal, or strict policy with a missing signal)
    category = models.CharField(max_length=10)  # low | medium | high | critical | unscored
    weight_coverage = models.FloatField()
    low_coverage = models.BooleanField(default=False)
    capped = models.BooleanField(default=False)  # a Critical score was held at High because coverage was low
    policy = models.CharField(max_length=14)
    detection_run = models.ForeignKey(DetectionRun, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    behavior_run = models.ForeignKey(BehaviorRun, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    graph_snapshot = models.ForeignKey(GraphSnapshot, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction", "computed_at"], name="risk_tx_time_idx"),
            models.Index(fields=["account", "computed_at"], name="risk_acct_time_idx"),
            models.Index(fields=["category", "computed_at"], name="risk_cat_time_idx"),
            models.Index(fields=["run", "-overall_score"], name="risk_run_score_idx"),
        ]

    def __str__(self) -> str:
        return f"risk {self.overall_score} ({self.category}) tx {self.transaction_id}"


class AccountRiskHistory(models.Model):
    """Account-level risk over time: the highest assessment among its outgoing transactions in a run.
    Stored only for accounts at Medium or above (the rest carry no signal and would be millions of rows)."""

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="risk_history")
    run = models.ForeignKey(RiskScoreRun, on_delete=models.CASCADE, related_name="account_history")
    as_of = models.DateTimeField()
    score = models.FloatField()
    category = models.CharField(max_length=10)
    assessment_count = models.PositiveIntegerField()

    class Meta:
        indexes = [models.Index(fields=["account", "-as_of"], name="acctrisk_account_asof_idx")]

    def __str__(self) -> str:
        return f"account {self.account_id} risk {self.score} ({self.category})"
