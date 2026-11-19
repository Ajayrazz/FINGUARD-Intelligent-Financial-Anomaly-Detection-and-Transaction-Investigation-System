from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.datasets.models import Dataset, ImportJob


class Account(models.Model):
    """A financial account (customer or merchant) as it appears in one dataset."""

    class AccountType(models.TextChoices):
        CUSTOMER = "customer"
        MERCHANT = "merchant"
        UNKNOWN = "unknown"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="accounts")
    account_ref = models.CharField(max_length=64)
    account_type = models.CharField(max_length=10, choices=AccountType.choices, default=AccountType.UNKNOWN)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["account_ref"]
        constraints = [models.UniqueConstraint(fields=["dataset", "account_ref"], name="uniq_account_per_dataset")]
        indexes = [models.Index(fields=["dataset", "account_type"])]

    def __str__(self) -> str:
        return self.account_ref


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"
        FAILED = "failed"
        REVERSED = "reversed"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="transactions")
    import_job = models.ForeignKey(ImportJob, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    transaction_id = models.CharField(max_length=64, help_text="External or generated identifier, unique per dataset")
    sender = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="sent_transactions")
    receiver = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.PROTECT, related_name="received_transactions"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, blank=True)
    tx_type = models.CharField(max_length=32)
    occurred_at = models.DateTimeField()
    step = models.IntegerField(null=True, blank=True, help_text="Dataset time step (e.g. PaySim hour)")
    sender_balance_before = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    sender_balance_after = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    receiver_balance_before = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    receiver_balance_after = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    merchant_name = models.CharField(max_length=120, blank=True)
    merchant_category = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    # Dataset-provided label, used ONLY for evaluation. Never exposed as a prediction (decision D-018).
    ground_truth_label = models.BooleanField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "transaction_id"], name="uniq_txid_per_dataset"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="tx_amount_non_negative"),
        ]
        indexes = [
            models.Index(fields=["dataset", "-occurred_at", "-id"], name="tx_dataset_time_idx"),
            models.Index(fields=["sender", "occurred_at"], name="tx_sender_time_idx"),
            models.Index(fields=["receiver", "occurred_at"], name="tx_receiver_time_idx"),
            models.Index(fields=["dataset", "tx_type"], name="tx_dataset_type_idx"),
            models.Index(fields=["amount"], name="tx_amount_idx"),
            models.Index(fields=["status"], name="tx_status_idx"),
            models.Index(fields=["import_job"], name="tx_import_job_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.transaction_id} ({self.amount})"


class TransactionEvent(models.Model):
    """Append-only per-transaction audit trail (UPDATE/DELETE blocked by trigger, migration 0002)."""

    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=40)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["transaction", "created_at"])]

    def __str__(self) -> str:
        return f"{self.event_type} on {self.transaction_id}"
