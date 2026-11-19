from django.conf import settings
from django.db import models

from apps.datasets.models import Dataset
from apps.risk_engine.models import RiskAssessment
from apps.transactions.models import Account, Transaction

SEVERITIES = ["low", "medium", "high", "critical"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


class AlertPolicy(models.Model):
    """Versioned alert rules and thresholds (one active). Like risk configurations: new versions, no edits."""

    version = models.PositiveIntegerField(unique=True)
    config = models.JSONField()
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=models.Q(is_active=True), name="one_active_alert_policy"
            )
        ]

    def __str__(self) -> str:
        return f"alert policy v{self.version}"


class Alert(models.Model):
    class Status(models.TextChoices):
        NEW = "new"
        ACKNOWLEDGED = "acknowledged"
        ESCALATED = "escalated"
        CLOSED = "closed"

    class Outcome(models.TextChoices):
        TRUE_POSITIVE = "true_positive"
        FALSE_POSITIVE = "false_positive"
        DUPLICATE = "duplicate_of_other_alert"
        OTHER = "other"

    alert_type = models.CharField(max_length=30)
    severity = models.CharField(max_length=10)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.NEW)
    dedup_key = models.CharField(max_length=200)  # type + subject + time bucket
    dataset = models.ForeignKey(Dataset, null=True, blank=True, on_delete=models.PROTECT, related_name="alerts")
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="alerts")
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="alerts")
    assessment = models.ForeignKey(
        RiskAssessment, null=True, blank=True, on_delete=models.PROTECT, related_name="alerts"
    )
    reason = models.TextField()
    evidence_snapshot = models.JSONField(default=dict)  # copied at creation and never changed
    policy_version = models.PositiveIntegerField(default=1)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_alerts"
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=30, choices=Outcome.choices, blank=True)
    close_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dedup_key"], condition=~models.Q(status="closed"), name="one_open_alert_per_dedup_key"
            )
        ]
        indexes = [
            models.Index(fields=["status", "severity", "-created_at"], name="alert_status_sev_idx"),
            models.Index(fields=["assignee", "status"], name="alert_assignee_status_idx"),
            models.Index(fields=["transaction"], name="alert_tx_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.severity} {self.alert_type} alert #{self.pk}"


class AlertEvent(models.Model):
    """Immutable history of an alert (UPDATE/DELETE blocked by a trigger)."""

    alert = models.ForeignKey(Alert, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=30)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["alert", "created_at"], name="alertevent_alert_time_idx")]

    def __str__(self) -> str:
        return f"{self.event_type} on alert {self.alert_id}"


class NotificationLog(models.Model):
    class Status(models.TextChoices):
        SENT = "sent"
        FAILED = "failed"
        SKIPPED = "skipped"

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=12)  # email | websocket
    recipient = models.CharField(max_length=254)
    status = models.CharField(max_length=8, choices=Status.choices)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at", "-id"]

    def __str__(self) -> str:
        return f"{self.channel} to {self.recipient}: {self.status}"


class AlertRun(models.Model):
    """One rule evaluation over a dataset."""

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="alert_runs")
    policy_version = models.PositiveIntegerField()
    trigger = models.CharField(max_length=20, default="manual")  # manual | risk_run
    source_risk_run = models.PositiveIntegerField(
        null=True, blank=True
    )  # the risk run that triggered an automatic evaluation
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(
        default=dict
    )  # {"candidates": n, "created": n, "deduplicated": n, "raised": n, "by_type": {...}}
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"alert run {self.pk} on {self.dataset}"
