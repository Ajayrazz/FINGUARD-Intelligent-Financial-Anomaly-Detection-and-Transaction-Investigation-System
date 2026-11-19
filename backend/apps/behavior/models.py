from django.conf import settings
from django.db import models

from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction


class BehaviorRun(models.Model):
    """Batch behavioral scoring of every transaction in a dataset, as-of each transaction's own time."""

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="behavior_runs")
    params = models.JSONField(default=dict)  # the engine configuration used (versioned)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rows_total = models.PositiveIntegerField(default=0)
    rows_scored = models.PositiveIntegerField(default=0)
    rows_unavailable = models.PositiveIntegerField(default=0)  # cold start: no score, stated explicitly
    profiles_stored = models.PositiveIntegerField(default=0)
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
        return f"behavior run {self.pk} on {self.dataset}"


class AccountBehaviorProfile(models.Model):
    """Stored profile snapshot of an account as of a point in time (written by runs for accounts with history)."""

    run = models.ForeignKey(BehaviorRun, null=True, blank=True, on_delete=models.CASCADE, related_name="profiles")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="behavior_profiles")
    as_of = models.DateTimeField()
    window_days = models.PositiveSmallIntegerField()
    direction = models.CharField(max_length=3, default="out")
    tx_count = models.PositiveIntegerField()
    avg_amount = models.FloatField(null=True)
    median_amount = models.FloatField(null=True)
    std_amount = models.FloatField(null=True)
    p95_amount = models.FloatField(null=True)
    aggregates = models.JSONField(default=dict)  # {"daily": [...], "weekly": [...], "monthly": [...]}
    hour_histogram = models.JSONField(default=list)
    merchant_category_dist = models.JSONField(null=True, blank=True)  # null = not available in the data
    unique_counterparties = models.PositiveIntegerField(default=0)
    tx_per_day = models.FloatField(default=0)
    profile_version = models.CharField(max_length=10)

    class Meta:
        indexes = [models.Index(fields=["account", "-as_of"], name="behprof_account_asof_idx")]

    def __str__(self) -> str:
        return f"profile of {self.account_id} as of {self.as_of:%Y-%m-%d}"


class BehaviorAnalysisResult(models.Model):
    class Status(models.TextChoices):
        SCORED = "scored"
        UNAVAILABLE = "unavailable_cold_start"

    run = models.ForeignKey(BehaviorRun, on_delete=models.CASCADE, related_name="results")
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="behavior_results")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    deviation_score = models.FloatField(null=True)  # null when unavailable — never 0
    coverage = models.FloatField(default=0)
    components = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices)
    history_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "transaction"], name="uniq_behavior_result_per_run_tx")]
        indexes = [
            models.Index(fields=["run", "status", "-deviation_score"], name="behres_run_status_score_idx"),
            models.Index(fields=["transaction"], name="behres_tx_idx"),
        ]

    def __str__(self) -> str:
        return f"run {self.run_id} / tx {self.transaction_id}: {self.deviation_score}"
