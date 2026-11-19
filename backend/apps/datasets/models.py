from django.conf import settings
from django.db import models


class Dataset(models.Model):
    class SourceType(models.TextChoices):
        PAYSIM = "paysim", "PaySim"
        ULB = "ulb", "ULB credit card"
        ELLIPTIC = "elliptic", "Elliptic"
        CUSTOM = "custom", "Custom / uploaded"

    name = models.CharField(max_length=120, unique=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.CUSTOM)
    is_synthetic = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    # Maintained by imports/seeding (a live COUNT(*) over millions of rows is too slow for list views).
    row_count = models.PositiveBigIntegerField(default=0)
    schema_version = models.CharField(max_length=20, default="1")
    content_sha256 = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ColumnMappingProfile(models.Model):
    class DuplicatePolicy(models.TextChoices):
        REJECT = "reject", "Reject duplicate IDs"
        SKIP = "skip", "Skip duplicate IDs"
        FLAG = "flag", "Import and flag duplicate IDs"

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="mapping_profiles")
    name = models.CharField(max_length=80)
    mapping = models.JSONField(default=dict, help_text="source column -> canonical field")
    dup_policy = models.CharField(
        max_length=10, choices=DuplicatePolicy.choices, default=DuplicatePolicy.REJECT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "name"], name="uniq_mapping_name_per_dataset")
        ]

    def __str__(self) -> str:
        return f"{self.dataset} / {self.name}"


class ImportJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        VALIDATING = "validating"
        RUNNING = "running"
        COMPLETED = "completed"
        COMPLETED_WITH_ERRORS = "completed_with_errors"
        FAILED = "failed"
        CANCELLED = "cancelled"

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="import_jobs")
    mapping_profile = models.ForeignKey(
        ColumnMappingProfile, null=True, blank=True, on_delete=models.SET_NULL
    )
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(default=0)
    file_sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    rows_total = models.PositiveBigIntegerField(default=0)
    rows_processed = models.PositiveBigIntegerField(default=0)
    rows_accepted = models.PositiveBigIntegerField(default=0)
    rows_rejected = models.PositiveBigIntegerField(default=0)
    rows_duplicate = models.PositiveBigIntegerField(default=0)
    celery_task_id = models.CharField(max_length=64, blank=True)
    error_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Import {self.pk} ({self.file_name})"


class ImportRowError(models.Model):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="row_errors")
    row_number = models.PositiveBigIntegerField()
    raw = models.JSONField(default=dict)
    error_code = models.CharField(max_length=40)
    message = models.CharField(max_length=300)

    class Meta:
        ordering = ["job_id", "row_number"]
        indexes = [models.Index(fields=["job", "row_number"])]

    def __str__(self) -> str:
        return f"Row {self.row_number} of import {self.job_id}: {self.error_code}"
