from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.datasets.models import Dataset
from apps.transactions.models import Account


class GraphSnapshot(models.Model):
    """A graph analysis of one dataset's transactions up to `as_of` (optionally limited to a trailing window)."""

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="graph_snapshots")
    as_of = models.DateTimeField()
    window_days = models.PositiveIntegerField(null=True, blank=True)  # null = all history up to as_of
    params = models.JSONField(default=dict)  # detector configuration (versioned)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    node_count = models.PositiveIntegerField(default=0)
    edge_count = models.PositiveIntegerField(default=0)
    finding_count = models.PositiveIntegerField(default=0)
    truncated = models.JSONField(default=dict)  # detector -> hit its budget/limit
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    built_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"graph snapshot {self.pk} of {self.dataset}"


class AccountGraphMetrics(models.Model):
    """Stored for accounts that matter: degree >= 2 or part of a finding (the rest are leaves with no signal)."""

    snapshot = models.ForeignKey(GraphSnapshot, on_delete=models.CASCADE, related_name="metrics")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    in_degree = models.PositiveIntegerField()
    out_degree = models.PositiveIntegerField()
    weighted_in = models.FloatField()
    weighted_out = models.FloatField()
    pagerank = models.FloatField()
    clustering = models.FloatField()
    community_id = models.IntegerField()  # -1 = no community (component smaller than 3)
    graph_risk_score = models.FloatField()  # G, 0-100
    components = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "account"], name="uniq_graph_metrics_snapshot_account")
        ]
        indexes = [models.Index(fields=["snapshot", "-graph_risk_score"], name="graphm_snap_score_idx")]

    def __str__(self) -> str:
        return f"metrics {self.account_id} @ snapshot {self.snapshot_id}"


class GraphFinding(models.Model):
    class FindingType(models.TextChoices):
        CYCLE = "cycle"
        CHAIN = "chain"
        FAN_IN = "fan_in"
        FAN_OUT = "fan_out"
        SHARED = "shared_beneficiary"
        CLUSTER = "dense_cluster"

    snapshot = models.ForeignKey(GraphSnapshot, on_delete=models.CASCADE, related_name="findings")
    finding_type = models.CharField(max_length=20, choices=FindingType.choices)
    account_ids = ArrayField(models.BigIntegerField(), default=list)
    transaction_ids = ArrayField(models.BigIntegerField(), default=list)  # capped (50)
    score = models.FloatField()  # 0-100 heuristic, uncalibrated
    evidence = models.JSONField(default=dict)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["snapshot", "finding_type", "-score"], name="graphf_snap_type_score_idx"),
            models.Index(fields=["snapshot", "-score"], name="graphf_snap_score_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.finding_type} ({self.score}) in snapshot {self.snapshot_id}"


class Neo4jSyncState(models.Model):
    """Watermark of the one-way PostgreSQL -> Neo4j projection of a dataset (PostgreSQL stays authoritative)."""

    class Status(models.TextChoices):
        NEVER = "never"
        RUNNING = "running"
        SYNCED = "synced"
        FAILED = "failed"

    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name="neo4j_sync")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.NEVER)
    last_tx_id = models.BigIntegerField(default=0)  # highest transaction id projected
    nodes_synced = models.PositiveBigIntegerField(default=0)
    edges_synced = models.PositiveBigIntegerField(default=0)
    last_error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"neo4j sync of {self.dataset_id}: {self.status}"
