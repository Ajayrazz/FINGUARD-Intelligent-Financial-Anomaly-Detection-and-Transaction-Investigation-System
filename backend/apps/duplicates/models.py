from django.conf import settings
from django.db import models

from apps.datasets.models import Dataset


class InvoiceDocument(models.Model):
    """An uploaded invoice file (PNG/JPEG/PDF) and the OCR output derived from it."""

    class Status(models.TextChoices):
        UPLOADED = "uploaded"
        OCR_DONE = "ocr_done"
        NEEDS_REVIEW = "needs_review"  # fields extracted; a human has not verified them yet
        REVIEWED = "reviewed"  # a human verified or corrected the fields
        FAILED = "failed"

    file_path = models.CharField(max_length=300)  # random name under MEDIA_ROOT/invoices/
    original_name = models.CharField(max_length=200)  # display only, never used as a path
    sha256 = models.CharField(max_length=64, db_index=True)
    mime = models.CharField(max_length=30)
    size = models.PositiveIntegerField()
    page_count = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.UPLOADED)
    ocr_text = models.TextField(blank=True)
    ocr_confidence = models.FloatField(null=True, blank=True)  # mean word confidence 0-100
    phash = models.CharField(max_length=16, blank=True)  # 64-bit perceptual hash, hex
    error_message = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"invoice file {self.pk}"


class Invoice(models.Model):
    document = models.OneToOneField(
        InvoiceDocument, null=True, blank=True, on_delete=models.CASCADE, related_name="invoice"
    )
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_normalized = models.CharField(max_length=200, blank=True, db_index=True)
    invoice_number = models.CharField(max_length=60, blank=True)
    invoice_number_normalized = models.CharField(max_length=60, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    extracted_fields = models.JSONField(default=dict)  # what OCR produced, kept even after human correction
    field_confidence = models.JSONField(default=dict)  # OCR line confidence per field (0-100)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"invoice {self.invoice_number or self.pk} ({self.vendor_name})"


class DuplicateScanRun(models.Model):
    class Kind(models.TextChoices):
        TRANSACTION = "transaction"
        INVOICE = "invoice"

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    dataset = models.ForeignKey(Dataset, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    candidates_found = models.PositiveIntegerField(default=0)
    params = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.kind} duplicate scan {self.pk}"


class DuplicateCandidate(models.Model):
    """A pair of records that may be duplicates. The similarity is evidence for a human; only a reviewer decides."""

    class MatchClass(models.TextChoices):
        EXACT = "exact"
        STRONG = "strong_similar"
        POTENTIAL = "potential"
        LEGIT = "legitimate_repeat"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending"
        CONFIRMED = "confirmed_duplicate"
        NOT_DUPLICATE = "not_duplicate"
        LEGIT = "legitimate_repeat"

    kind = models.CharField(max_length=12, choices=DuplicateScanRun.Kind.choices)
    record_a_type = models.CharField(max_length=12)  # "transaction" | "invoice"
    record_a_id = models.BigIntegerField()
    record_b_type = models.CharField(max_length=12)
    record_b_id = models.BigIntegerField()
    match_class = models.CharField(max_length=20, choices=MatchClass.choices)
    similarity_score = models.FloatField()  # 0-100, a ranking aid and not proof
    evidence = models.JSONField(default=dict)
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    scan_run = models.ForeignKey(
        DuplicateScanRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="candidates"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-similarity_score", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "record_a_type", "record_a_id", "record_b_type", "record_b_id"],
                name="uniq_duplicate_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(record_a_id__lt=models.F("record_b_id"))
                | ~models.Q(record_a_type=models.F("record_b_type")),
                name="duplicate_pair_ordered",
            ),
        ]
        indexes = [
            models.Index(fields=["kind", "match_class", "review_status"], name="dupcand_kind_class_status_idx"),
            models.Index(fields=["review_status", "-similarity_score"], name="dupcand_status_score_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.match_class} {self.record_a_type}:{self.record_a_id} ~ {self.record_b_type}:{self.record_b_id}"
