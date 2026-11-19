from django.conf import settings
from django.db import models

from apps.alerts.models import Alert
from apps.datasets.models import Dataset
from apps.transactions.models import Transaction

STATUSES = ["new", "under_review", "investigation", "escalated", "resolved", "closed"]
OUTCOMES = ["confirmed_suspicious", "false_positive", "inconclusive", "referred"]
PRIORITIES = ["low", "medium", "high", "critical"]
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}

# The complete state machine (docs/02). Everything not listed is rejected, including staying in the same status.
TRANSITIONS: dict[str, set[str]] = {
    "new": {"under_review"},
    "under_review": {"investigation", "resolved"},  # resolved straight from review = false positive / no case to answer
    "investigation": {"escalated", "resolved"},
    "escalated": {"investigation"},
    "resolved": {"closed"},
    "closed": set(),
}


class Case(models.Model):
    class Status(models.TextChoices):
        NEW = "new"
        UNDER_REVIEW = "under_review"
        INVESTIGATION = "investigation"
        ESCALATED = "escalated"
        RESOLVED = "resolved"
        CLOSED = "closed"

    class Outcome(models.TextChoices):
        CONFIRMED = "confirmed_suspicious"
        FALSE_POSITIVE = "false_positive"
        INCONCLUSIVE = "inconclusive"
        REFERRED = "referred"

    case_ref = models.CharField(max_length=20, unique=True)  # FG-YYYY-NNNNNN, number from a database sequence
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, default="medium")
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.NEW)
    dataset = models.ForeignKey(Dataset, null=True, blank=True, on_delete=models.PROTECT, related_name="cases")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_cases"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    auto_created = models.BooleanField(default=False)
    opened_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(
        max_length=24, choices=Outcome.choices, blank=True
    )  # set by an investigator, never by a model
    resolution_summary = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=STATUSES), name="case_status_valid"),
            models.CheckConstraint(condition=models.Q(priority__in=PRIORITIES), name="case_priority_valid"),
            models.CheckConstraint(
                condition=models.Q(outcome="") | models.Q(outcome__in=OUTCOMES), name="case_outcome_valid"
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=["resolved", "closed"])
                | (~models.Q(outcome="") & ~models.Q(resolution_summary="")),
                name="case_resolved_needs_outcome_and_summary",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "priority", "-opened_at"], name="case_status_prio_idx"),
            models.Index(fields=["assignee", "status"], name="case_assignee_status_idx"),
        ]

    def __str__(self) -> str:
        return self.case_ref


class CaseAlert(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="case_alerts")
    alert = models.ForeignKey(Alert, on_delete=models.PROTECT, related_name="case_links")
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["case", "alert"], name="uniq_case_alert")]

    def __str__(self) -> str:
        return f"{self.case_id}~alert {self.alert_id}"


class CaseTransaction(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="case_transactions")
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="case_links")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    note = models.CharField(max_length=300, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["case", "transaction"], name="uniq_case_transaction")]

    def __str__(self) -> str:
        return f"{self.case_id}~tx {self.transaction_id}"


class CaseNote(models.Model):
    """A comment or note. Its text lives in append-only revisions; there is no hard delete."""

    class Kind(models.TextChoices):
        COMMENT = "comment"
        NOTE = "note"

    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.kind} {self.pk} on case {self.case_id}"


class CaseNoteRevision(models.Model):
    note = models.ForeignKey(CaseNote, on_delete=models.PROTECT, related_name="revisions")
    revision = models.PositiveIntegerField()
    body = models.TextField()
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["revision"]
        constraints = [models.UniqueConstraint(fields=["note", "revision"], name="uniq_note_revision")]

    def __str__(self) -> str:
        return f"note {self.note_id} r{self.revision}"


class CaseEvidence(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="evidence")
    file_path = models.CharField(max_length=300)  # random name under MEDIA_ROOT/cases/
    original_name = models.CharField(max_length=200)  # display only
    sha256 = models.CharField(max_length=64)
    mime = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    description = models.CharField(max_length=300, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"evidence {self.pk} of case {self.case_id}"


class CaseEvent(models.Model):
    """Immutable case history (UPDATE/DELETE blocked by a trigger). Drives the timeline."""

    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=30)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    from_status = models.CharField(max_length=14, blank=True)
    to_status = models.CharField(max_length=14, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["case", "created_at"], name="caseevent_case_time_idx")]

    def __str__(self) -> str:
        return f"{self.event_type} on {self.case_id}"
